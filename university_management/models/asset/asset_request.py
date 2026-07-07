# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class AssetRequest(models.Model):
    """
    Asset Request — raised by staff/faculty when they need an asset.

    Flow:
        draft → submitted → in_review → approved → fulfilled
                                      ↘ pending_purchase (if asset unavailable)
                                                  → fulfilled (after PO + receipt)
        Any state → rejected

    On submit:
      - Checks availability of the requested category
      - Auto-creates a helpdesk ticket (ticket.helpdesk) routed to IT team
      - If asset available: state → approved, asset assigned
      - If unavailable: state → pending_purchase, IT team picks up from helpdesk
    """
    _name = 'asset.request'
    _description = 'Asset Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Request Reference', required=True, readonly=True,
        copy=False, default='/',
        help='Auto-generated: AREQ/YYYY/NNNN',
    )

    # ── Who / What ───────────────────────────────────────────────────
    requester_id = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user,
        required=True, tracking=True,
    )
    requester_partner_id = fields.Many2one(
        'res.partner', related='requester_id.partner_id',
        string='Requester Partner', store=True,
    )
    department_id = fields.Many2one(
        'university.department', string='Department', tracking=True,
    )
    asset_category_id = fields.Many2one(
        'asset.category', string='Asset Category Required',
        required=True, tracking=True,
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Specific Asset (if known)',
        domain="[('state', '=', 'active')]",
        help='Leave empty to let the system find an available asset in the category.',
        tracking=True,
    )
    description = fields.Text(
        string='Purpose / Justification', required=True,
        help='What the asset will be used for and why it is needed.',
    )
    quantity = fields.Integer(string='Quantity Needed', default=1, required=True)
    required_date = fields.Date(
        string='Required By Date', required=True,
        default=fields.Date.today,
    )
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', default='medium', tracking=True)

    # ── Availability ─────────────────────────────────────────────────
    availability_status = fields.Selection([
        ('unknown', 'Not Checked'),
        ('available', 'Available'),
        ('not_available', 'Not Available — Purchase Required'),
        ('partial', 'Partially Available'),
    ], string='Availability', default='unknown', readonly=True, tracking=True)

    assigned_asset_id = fields.Many2one(
        'asset.asset', string='Assigned Asset',
        readonly=True, tracking=True,
        help='Asset assigned to this request after approval.',
    )

    # ── Helpdesk ─────────────────────────────────────────────────────
    helpdesk_ticket_id = fields.Many2one(
        'ticket.helpdesk', string='Helpdesk Ticket',
        readonly=True, copy=False,
        help='Auto-created helpdesk ticket when request is submitted.',
    )
    helpdesk_ticket_count = fields.Integer(
        string='Tickets', compute='_compute_helpdesk_count',
    )

    # ── Purchase ──────────────────────────────────────────────────────
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase Order',
        readonly=True, copy=False, tracking=True,
        help='Purchase order raised by IT team when asset is not available.',
    )
    vendor_id = fields.Many2one(
        'res.partner', string='Preferred Vendor',
        help='Suggested vendor for purchase. IT team can change this.',
    )
    estimated_cost = fields.Monetary(
        string='Estimated Cost', currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    # ── State & Dates ─────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_review', 'Under Review'),
        ('approved', 'Approved'),
        ('pending_purchase', 'Pending Purchase'),
        ('fulfilled', 'Fulfilled'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True, index=True)

    request_date = fields.Date(
        string='Request Date', default=fields.Date.today, readonly=True,
    )
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approved On', readonly=True)
    fulfilled_date = fields.Date(string='Fulfilled On', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    notes = fields.Text(string='Internal Notes')

    # ── Computed ──────────────────────────────────────────────────────

    def _compute_helpdesk_count(self):
        for rec in self:
            rec.helpdesk_ticket_count = 1 if rec.helpdesk_ticket_id else 0

    # ── ORM ───────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            year = date.today().year
            seq = self.env['ir.sequence'].next_by_code('asset.request') or '0001'
            vals['name'] = f'AREQ/{year}/{seq}'
        return super().create(vals)

    # ── Availability Check ────────────────────────────────────────────

    def _check_availability(self):
        """Check if an asset of the requested category is available."""
        self.ensure_one()
        if self.asset_id:
            if self.asset_id.state == 'active':
                self.availability_status = 'available'
            else:
                self.availability_status = 'not_available'
            return

        available = self.env['asset.asset'].search([
            ('category_id', '=', self.asset_category_id.id),
            ('state', '=', 'active'),
        ], limit=1)

        if available:
            self.asset_id = available.id
            self.availability_status = 'available'
        else:
            self.availability_status = 'not_available'

    # ── Helpdesk Ticket ───────────────────────────────────────────────

    def _map_priority_to_helpdesk(self):
        mapping = {'low': '0', 'medium': '1', 'high': '3', 'critical': '4'}
        return mapping.get(self.priority, '1')

    def _create_helpdesk_ticket(self):
        """Auto-create a ticket.helpdesk record on request submission."""
        self.ensure_one()
        if self.helpdesk_ticket_id:
            return  # Already created

        # Find IT helpdesk team
        it_team = self.env['team.helpdesk'].search(
            ['|', ('name', 'ilike', 'IT'), ('name', 'ilike', 'Asset')],
            limit=1,
        )

        ticket_type = (
            'asset_request' if self.availability_status == 'available'
            else 'asset_procurement'
        )

        subject = (
            f'Asset Request [{self.name}]: {self.asset_category_id.name}'
            f' — {self.requester_id.name}'
        )
        description = (
            f'Request Reference: {self.name}\n'
            f'Category: {self.asset_category_id.name}\n'
            f'Quantity: {self.quantity}\n'
            f'Required By: {self.required_date}\n'
            f'Department: {self.department_id.name if self.department_id else "—"}\n'
            f'Availability: {dict(self._fields["availability_status"].selection).get(self.availability_status)}\n\n'
            f'Purpose:\n{self.description}'
        )

        ticket_vals = {
            'subject': subject,
            'description': description,
            'customer_id': self.requester_partner_id.id if self.requester_partner_id else False,
            'team_id': it_team.id if it_team else False,
            'priority': self._map_priority_to_helpdesk(),
            'asset_request_id': self.id,
            'asset_id': self.asset_id.id if self.asset_id else False,
            'ticket_type': ticket_type,
        }

        ticket = self.env['ticket.helpdesk'].create(ticket_vals)
        self.helpdesk_ticket_id = ticket.id
        self.message_post(
            body=_('Helpdesk ticket <b>%s</b> created and routed to IT team.') % ticket.name
        )

    # ── Actions ───────────────────────────────────────────────────────

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft requests can be submitted.'))
            rec._check_availability()
            rec._create_helpdesk_ticket()
            rec.state = 'submitted'
            rec.message_post(
                body=_(
                    'Request submitted. Availability: <b>%s</b>. '
                    'Helpdesk ticket: <b>%s</b>.'
                ) % (
                    dict(rec._fields['availability_status'].selection).get(rec.availability_status),
                    rec.helpdesk_ticket_id.name if rec.helpdesk_ticket_id else '—',
                )
            )

    def action_review(self):
        self.write({'state': 'in_review'})
        self.message_post(body=_('Request taken under review by IT team.'))

    def action_approve(self):
        """Approve and assign asset if available."""
        self.ensure_one()
        if self.availability_status == 'available' and self.asset_id:
            self.assigned_asset_id = self.asset_id.id
            self.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approval_date': date.today(),
            })
            self.message_post(
                body=_('Request approved. Asset <b>%s</b> assigned to <b>%s</b>.') % (
                    self.asset_id.name, self.requester_id.name)
            )
            # Close helpdesk ticket as resolved
            if self.helpdesk_ticket_id:
                resolved_stage = self.env['ticket.stage'].search(
                    [('name', 'ilike', 'solved')], limit=1
                ) or self.env['ticket.stage'].search(
                    [('name', 'ilike', 'closed')], limit=1
                ) or self.env['ticket.stage'].search(
                    [('name', 'ilike', 'done')], limit=1
                )
                if resolved_stage:
                    self.helpdesk_ticket_id.stage_id = resolved_stage
        else:
            self.write({
                'state': 'pending_purchase',
                'approved_by': self.env.user.id,
                'approval_date': date.today(),
            })
            self.message_post(
                body=_('Request approved. Asset not available — routed to IT for purchase order.')
            )
            if self.helpdesk_ticket_id:
                self.helpdesk_ticket_id.ticket_type = 'asset_procurement'
                self.helpdesk_ticket_id.message_post(
                    body=_('Asset request approved but no stock available. '
                           'IT team: please raise a purchase order.')
                )

    def action_fulfill(self):
        self.write({
            'state': 'fulfilled',
            'fulfilled_date': date.today(),
        })
        self.message_post(body=_('Request fulfilled on %s.') % date.today())

    def action_reject(self):
        self.ensure_one()
        if not self.rejection_reason:
            raise ValidationError(_('Please enter a rejection reason before rejecting.'))
        self.state = 'rejected'
        self.message_post(
            body=_('Request rejected. Reason: %s') % self.rejection_reason
        )
        if self.helpdesk_ticket_id:
            cancelled_stage = self.env['ticket.stage'].search(
                [('name', 'ilike', 'cancel')], limit=1
            )
            if cancelled_stage:
                self.helpdesk_ticket_id.stage_id = cancelled_stage

    def action_reset_draft(self):
        self.write({'state': 'draft', 'availability_status': 'unknown'})

    # ── Smart Buttons ──────────────────────────────────────────────────

    def action_view_helpdesk_ticket(self):
        self.ensure_one()
        if not self.helpdesk_ticket_id:
            raise UserError(_('No helpdesk ticket linked yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Helpdesk Ticket'),
            'res_model': 'ticket.helpdesk',
            'res_id': self.helpdesk_ticket_id.id,
            'view_mode': 'form',
        }

    def action_view_purchase_order(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_('No purchase order linked yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
        }
