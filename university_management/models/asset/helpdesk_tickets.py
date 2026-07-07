# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class TicketHelpdeskAssetInherit(models.Model):
    """
    Extends ticket.helpdesk (odoo_website_helpdesk) with asset management fields.

    New fields:
      - asset_request_id  : link to the originating asset.request
      - asset_id          : which asset this ticket concerns
      - purchase_order_id : PO raised by IT team from this ticket
      - invoice_ids       : invoices linked via PO
      - ticket_type       : categorises asset-related tickets for IT queue filtering

    New methods:
      - action_create_purchase_order() : IT team raises purchase.order directly from ticket
      - action_view_asset()            : opens the linked asset form
      - action_view_purchase()         : opens the linked purchase order form
      - action_view_invoices()         : opens linked invoices
    """
    _inherit = 'ticket.helpdesk'

    # ── Asset Integration Fields ──────────────────────────────────────
    asset_request_id = fields.Many2one(
        'asset.request', string='Asset Request',
        copy=False, index=True,
        help='Asset request that triggered this helpdesk ticket.',
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Related Asset',
        help='Asset this ticket is about.',
    )
    ticket_type = fields.Selection([
        ('general', 'General'),
        ('asset_request', 'Asset Request'),
        ('asset_procurement', 'Asset Procurement (Purchase Required)'),
        ('asset_maintenance', 'Asset Maintenance'),
        ('asset_transfer', 'Asset Transfer'),
    ], string='Ticket Type', default='general', tracking=True, index=True)

    # ── Purchase Order Integration ────────────────────────────────────
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase Order',
        copy=False, tracking=True,
        help='Purchase order raised by IT team for unavailable asset.',
    )
    purchase_order_state = fields.Selection(
        related='purchase_order_id.state',
        string='PO Status', store=True, readonly=True,
    )

    # ── Invoice Integration ───────────────────────────────────────────
    invoice_ids = fields.Many2many(
        'account.move', string='Invoices',
        compute='_compute_invoice_ids',
        help='Vendor invoices linked via the purchase order.',
    )
    invoice_count = fields.Integer(
        string='Invoices', compute='_compute_invoice_count',
    )

    # ── Computed ──────────────────────────────────────────────────────

    def _compute_invoice_ids(self):
        for rec in self:
            if rec.purchase_order_id:
                rec.invoice_ids = rec.purchase_order_id.invoice_ids
            else:
                rec.invoice_ids = self.env['account.move']

    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    # ── Actions ───────────────────────────────────────────────────────

    def action_create_purchase_order(self):
        """
        IT Team action: Create a purchase.order from this helpdesk ticket.
        Pre-fills vendor, product (from asset_category.product_id), quantity,
        and links everything back to the asset_request and helpdesk ticket.
        """
        self.ensure_one()
        if self.purchase_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'res_id': self.purchase_order_id.id,
                'view_mode': 'form',
            }

        req = self.asset_request_id
        product = False
        vendor = req.vendor_id if req else False
        quantity = req.quantity if req else 1
        category_name = req.asset_category_id.name if req else (
            self.asset_id.category_id.name if self.asset_id else 'Asset Purchase'
        )

        if req and req.asset_category_id and req.asset_category_id.product_id:
            product = req.asset_category_id.product_id
        elif self.asset_id and self.asset_id.category_id and self.asset_id.category_id.product_id:
            product = self.asset_id.category_id.product_id

        order_lines = []
        if product:
            order_lines = [(0, 0, {
                'product_id': product.id,
                'name': f'[Asset Request {req.name if req else ""}] {category_name}',
                'product_qty': quantity,
                'price_unit': req.estimated_cost / quantity if (req and req.estimated_cost and quantity) else 0.0,
                'date_planned': req.required_date if req else date.today(),
            })]

        po_vals = {
            'partner_id': vendor.id if vendor else False,
            'asset_request_id': req.id if req else False,
            'helpdesk_ticket_id': self.id,
            'notes': (
                f'Asset Request: {req.name if req else "—"}\n'
                f'Helpdesk Ticket: {self.name}\n'
                f'Category: {category_name}\n'
                f'Requested By: {req.requester_id.name if req else "—"}'
            ),
            'order_line': order_lines,
        }

        po = self.env['purchase.order'].create(po_vals)
        self.purchase_order_id = po.id

        # Update asset request state
        if req:
            req.purchase_order_id = po.id
            if req.state not in ('pending_purchase', 'rejected', 'fulfilled'):
                req.state = 'pending_purchase'
            req.message_post(
                body=_('Purchase order <b>%s</b> created by IT team from helpdesk ticket <b>%s</b>.') % (
                    po.name, self.name)
            )

        self.message_post(
            body=_('Purchase order <b>%s</b> created for asset procurement.') % po.name
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_asset(self):
        self.ensure_one()
        if not self.asset_id:
            raise UserError(_('No asset linked to this ticket.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset'),
            'res_model': 'asset.asset',
            'res_id': self.asset_id.id,
            'view_mode': 'form',
        }

    def action_view_purchase(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_('No purchase order linked to this ticket.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
        }

    def action_view_invoices(self):
        self.ensure_one()
        invoices = self.invoice_ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
        }

    def action_view_asset_request(self):
        self.ensure_one()
        if not self.asset_request_id:
            raise UserError(_('No asset request linked to this ticket.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Request'),
            'res_model': 'asset.request',
            'res_id': self.asset_request_id.id,
            'view_mode': 'form',
        }
