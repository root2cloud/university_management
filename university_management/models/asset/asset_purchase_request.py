# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class AssetPurchaseRequest(models.Model):
    """
    Asset Purchase Request — raised by any user when an asset needs to be purchased.

    6-Stage Approval Chain:
        draft
          → principal_review   (submitter submits → principal_id notified)
          → vendor_quotes      (principal_id approves → submitter notified)
          → acc_review         (submitter uploads quotes → acc_user_id notified)
          → secretary_review   (acc_user_id forwards → secretary_id notified)
          → trust_execution    (secretary_id approves → trust_manager_id notified)
          → done               (trust_manager_id confirms execution)
        Any stage → rejected   (principal_id or secretary_id rejects)

    Approver roles are set as specific users on each record — no security groups needed.
    Button visibility is controlled via computed boolean fields (is_principal, etc.).
    """
    _name = 'asset.purchase.request'
    _description = 'Asset Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Request Reference', required=True, readonly=True,
        copy=False, default='/',
        help='Auto-generated: APREQ/YYYY/NNNN',
    )

    # ── Request Details ───────────────────────────────────────────────
    requested_by = fields.Many2one(
        'res.users', string='Requested By',
        default=lambda self: self.env.user,
        required=True, tracking=True,
    )
    department_id = fields.Many2one(
        'university.department', string='Department', tracking=True,
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Asset to Replace (if any)',
        domain="[('state', 'not in', ['disposed', 'condemned'])]",
        tracking=True,
    )
    asset_request_id = fields.Many2one(
        'asset.request', string='Originating Asset Request',
        readonly=True, copy=False, tracking=True, index=True,
    )
    asset_request_state = fields.Selection(
        related='asset_request_id.state',
        string='Asset Request Status', store=True, readonly=True,
    )
    item_description = fields.Text(string='Item Description / Specification', required=True)
    justification = fields.Text(string='Justification / Business Need', required=True)
    estimated_cost = fields.Monetary(string='Estimated Cost (₹)', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    quantity = fields.Integer(string='Quantity', default=1, required=True)
    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now, readonly=True)
    priority = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical'),
    ], string='Priority', default='medium', tracking=True)

    # ── Approver Fields (set per-record, no security groups required) ─
    principal_id = fields.Many2one(
        'res.users', string='Principal (Approver)', tracking=True,
        help='User who approves/rejects at the Principal stage.',
    )
    acc_user_id = fields.Many2one(
        'res.users', string='ACC Reviewer', tracking=True,
        help='User who reviews at ACC stage and forwards to Secretary.',
    )
    secretary_id = fields.Many2one(
        'res.users', string='Trust Secretary (Final Approver)', tracking=True,
        help='User who gives final approval.',
    )
    trust_manager_id = fields.Many2one(
        'res.users', string='Trust Manager (Executor)', tracking=True,
        help='User who executes post-approval procurement.',
    )

    # ── Role flags — used to show/hide buttons in the form view ───────
    is_principal = fields.Boolean(compute='_compute_role_flags', store=False)
    is_acc_user = fields.Boolean(compute='_compute_role_flags', store=False)
    is_secretary = fields.Boolean(compute='_compute_role_flags', store=False)
    is_trust_manager = fields.Boolean(compute='_compute_role_flags', store=False)
    is_requester = fields.Boolean(compute='_compute_role_flags', store=False)

    @api.depends('principal_id', 'acc_user_id', 'secretary_id', 'trust_manager_id', 'requested_by')
    def _compute_role_flags(self):
        uid = self.env.uid
        is_admin = self.env.user.has_group('university_management.group_university_admin')
        for rec in self:
            rec.is_principal = is_admin or rec.principal_id.id == uid
            rec.is_acc_user = is_admin or rec.acc_user_id.id == uid
            rec.is_secretary = is_admin or rec.secretary_id.id == uid
            rec.is_trust_manager = is_admin or rec.trust_manager_id.id == uid
            rec.is_requester = is_admin or rec.requested_by.id == uid

    # ── State Machine ─────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('principal_review', 'Awaiting Principal'),
        ('vendor_quotes', 'Awaiting Vendor Quotes'),
        ('acc_review', 'ACC Review'),
        ('secretary_review', 'Awaiting Secretary Approval'),
        ('trust_execution', 'Trust Manager Executing'),
        ('done', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True, required=True)

    # ── Principal Stage ───────────────────────────────────────────────
    principal_approved = fields.Boolean(string='Principal Approved', readonly=True)
    principal_approved_by = fields.Many2one('res.users', string='Principal Approval By', readonly=True)
    principal_date = fields.Datetime(string='Principal Approval Date', readonly=True)
    principal_remarks = fields.Text(string='Principal Remarks')

    # ── Vendor Quotes Stage ───────────────────────────────────────────
    vendor_quote_1 = fields.Binary(string='Vendor Quote 1 (PDF)', attachment=True)
    vendor_quote_1_name = fields.Char(string='Quote 1 Filename')
    vendor_quote_1_vendor = fields.Char(string='Vendor 1 Name')
    vendor_quote_1_amount = fields.Monetary(string='Quote 1 Amount', currency_field='currency_id')
    vendor_quote_2 = fields.Binary(string='Vendor Quote 2 (PDF)', attachment=True)
    vendor_quote_2_name = fields.Char(string='Quote 2 Filename')
    vendor_quote_2_vendor = fields.Char(string='Vendor 2 Name')
    vendor_quote_2_amount = fields.Monetary(string='Quote 2 Amount', currency_field='currency_id')
    vendor_quote_3 = fields.Binary(string='Vendor Quote 3 (PDF)', attachment=True)
    vendor_quote_3_name = fields.Char(string='Quote 3 Filename')
    vendor_quote_3_vendor = fields.Char(string='Vendor 3 Name')
    vendor_quote_3_amount = fields.Monetary(string='Quote 3 Amount', currency_field='currency_id')
    quotes_submitted_date = fields.Datetime(string='Quotes Submitted On', readonly=True)

    # ── ACC Review Stage ──────────────────────────────────────────────
    acc_reviewed = fields.Boolean(string='ACC Marked as Reviewed', readonly=True)
    acc_reviewed_by = fields.Many2one('res.users', string='ACC Reviewed By', readonly=True)
    acc_review_date = fields.Datetime(string='ACC Review Date', readonly=True)
    acc_notes = fields.Text(string='ACC Notes / Observations')
    selected_vendor = fields.Many2one('res.partner', string='Preferred Vendor (ACC Selection)')
    selected_vendor_name = fields.Char(string='Preferred Vendor Name')
    selected_quote_amount = fields.Monetary(string='Selected Quote Amount', currency_field='currency_id')

    # ── Trust Secretary Stage ─────────────────────────────────────────
    secretary_approved = fields.Boolean(string='Secretary Approved (Final)', readonly=True)
    secretary_approved_by = fields.Many2one('res.users', string='Secretary Approval By', readonly=True)
    secretary_date = fields.Datetime(string='Secretary Approval Date', readonly=True)
    secretary_remarks = fields.Text(string='Secretary Remarks / Decision Notes')
    final_approval_date = fields.Datetime(string='Final Approval Date', readonly=True)

    # ── Trust Manager Execution Stage ─────────────────────────────────
    trust_manager_executed = fields.Boolean(string='Trust Manager Executed', readonly=True)
    trust_manager_executed_by = fields.Many2one('res.users', string='Executed By', readonly=True)
    trust_manager_execution_date = fields.Datetime(string='Execution Date', readonly=True)
    po_reference = fields.Char(string='PO / Order Reference')
    vendor_notified = fields.Boolean(string='Vendor Notified', readonly=True)
    execution_notes = fields.Text(string='Execution Notes')

    # ── Rejection ─────────────────────────────────────────────────────
    rejection_reason = fields.Text(string='Rejection Reason')
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_date = fields.Datetime(string='Rejection Date', readonly=True)

    # ── Linked Purchase Order ─────────────────────────────────────────
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', copy=False, tracking=True)

    # ── Computed / Display ────────────────────────────────────────────
    days_pending = fields.Integer(string='Days Pending', compute='_compute_days_pending', store=False)

    @api.depends('request_date', 'state')
    def _compute_days_pending(self):
        for rec in self:
            if rec.request_date and rec.state not in ('done', 'rejected'):
                rec.days_pending = (fields.Datetime.now() - rec.request_date).days
            else:
                rec.days_pending = 0

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.purchase.request') or '/'
        return super().create(vals)

    # ══════════════════════════════════════════════════════════════════
    #  STATE MACHINE
    # ══════════════════════════════════════════════════════════════════

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            if not rec.principal_id:
                raise UserError(_('Please set a Principal approver before submitting.'))
            rec.write({'state': 'principal_review'})
            rec._notify_users([rec.principal_id],
                subject=_('New Purchase Request Awaiting Your Approval: %s') % rec.name,
                body=_('<p>Dear %s,</p><p><b>%s</b> has raised purchase request <b>%s</b>.</p>'
                       '<p><b>Item:</b> %s<br/><b>Justification:</b> %s<br/>'
                       '<b>Estimated Cost:</b> ₹%s</p>') % (
                    rec.principal_id.name, rec.requested_by.name, rec.name,
                    rec.item_description, rec.justification, rec.estimated_cost or 0))
            rec.message_post(body=_('Submitted by <b>%s</b>. Awaiting Principal review.') % rec.requested_by.name)

    def action_principal_approve(self):
        for rec in self:
            if rec.state != 'principal_review':
                raise UserError(_('Request must be in Principal Review state.'))
            rec.write({'state': 'vendor_quotes', 'principal_approved': True,
                       'principal_approved_by': self.env.user.id, 'principal_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Principal Approved %s — Please Upload 3 Vendor Quotes') % rec.name,
                body=_('<p>Dear %s,</p><p>Principal approved <b>%s</b>. '
                       'Please upload 3 vendor quotes to proceed.</p><p>Remarks: %s</p>') % (
                    rec.requested_by.name, rec.name, rec.principal_remarks or 'None'))
            rec.message_post(body=_('Approved by Principal <b>%s</b>.') % self.env.user.name)

    def action_principal_reject(self):
        for rec in self:
            if rec.state != 'principal_review':
                raise UserError(_('Request must be in Principal Review state.'))
            if not rec.principal_remarks:
                raise UserError(_('Please provide rejection remarks before rejecting.'))
            rec.write({'state': 'rejected', 'rejected_by': self.env.user.id,
                       'rejection_reason': rec.principal_remarks, 'rejection_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Purchase Request %s Rejected by Principal') % rec.name,
                body=_('<p>Dear %s,</p><p>Request <b>%s</b> rejected by Principal.</p>'
                       '<p><b>Reason:</b> %s</p>') % (rec.requested_by.name, rec.name, rec.rejection_reason))
            rec.message_post(body=_('Rejected by <b>%s</b>. Reason: %s') % (self.env.user.name, rec.rejection_reason))
            if rec.asset_request_id and rec.asset_request_id.state == 'pending_purchase':
                rec.asset_request_id.write({'state': 'in_review'})

    def action_submit_quotes(self):
        for rec in self:
            if rec.state != 'vendor_quotes':
                raise UserError(_('Request must be in Vendor Quotes state.'))
            if not (rec.vendor_quote_1 and rec.vendor_quote_2 and rec.vendor_quote_3):
                raise UserError(_('Please upload all 3 vendor quotes before submitting for ACC review.'))
            if not rec.acc_user_id:
                raise UserError(_('Please set an ACC Reviewer before submitting quotes.'))
            rec.write({'state': 'acc_review', 'quotes_submitted_date': fields.Datetime.now()})
            rec._notify_users([rec.acc_user_id],
                subject=_('Purchase Request %s Ready for ACC Review') % rec.name,
                body=_('<p>Dear %s,</p><p>Request <b>%s</b> by %s has 3 vendor quotes attached '
                       'and awaits your review.</p><p><b>Item:</b> %s</p>') % (
                    rec.acc_user_id.name, rec.name, rec.requested_by.name, rec.item_description))
            rec.message_post(body=_('3 vendor quotes uploaded. Forwarded to ACC for review.'))

    def action_acc_review_and_forward(self):
        for rec in self:
            if rec.state != 'acc_review':
                raise UserError(_('Request must be in ACC Review state.'))
            if not rec.acc_notes:
                raise UserError(_('Please add ACC notes/observations before forwarding to Secretary.'))
            if not rec.secretary_id:
                raise UserError(_('Please set a Trust Secretary before forwarding.'))
            rec.write({'state': 'secretary_review', 'acc_reviewed': True,
                       'acc_reviewed_by': self.env.user.id, 'acc_review_date': fields.Datetime.now()})
            rec._notify_users([rec.secretary_id],
                subject=_('FINAL APPROVAL REQUIRED: Purchase Request %s') % rec.name,
                body=_('<p>Dear %s,</p><p>Request <b>%s</b> needs your final decision.</p>'
                       '<p><b>Item:</b> %s<br/><b>Preferred Vendor:</b> %s<br/>'
                       '<b>Selected Amount:</b> ₹%s</p><p><b>ACC Notes:</b> %s</p>') % (
                    rec.secretary_id.name, rec.name, rec.item_description,
                    rec.selected_vendor.name if rec.selected_vendor else (rec.selected_vendor_name or '—'),
                    rec.selected_quote_amount or 0, rec.acc_notes))
            rec.message_post(body=_('ACC review by <b>%s</b>. Forwarded to Secretary.') % self.env.user.name)

    def action_secretary_approve(self):
        for rec in self:
            if rec.state != 'secretary_review':
                raise UserError(_('Request must be in Secretary Review state.'))
            if not rec.trust_manager_id:
                raise UserError(_('Please set a Trust Manager before approving.'))
            now = fields.Datetime.now()
            rec.write({'state': 'trust_execution', 'secretary_approved': True,
                       'secretary_approved_by': self.env.user.id,
                       'secretary_date': now, 'final_approval_date': now})
            rec._notify_users([rec.trust_manager_id],
                subject=_('ACTION REQUIRED: Approved Purchase Request %s — Please Execute') % rec.name,
                body=_('<p>Dear %s,</p><p>Trust Secretary approved <b>%s</b>.</p>'
                       '<p><b>Item:</b> %s<br/><b>Preferred Vendor:</b> %s<br/>'
                       '<b>Amount:</b> ₹%s</p><p>Please issue PO and mark execution complete.</p>') % (
                    rec.trust_manager_id.name, rec.name, rec.item_description,
                    rec.selected_vendor.name if rec.selected_vendor else (rec.selected_vendor_name or '—'),
                    rec.selected_quote_amount or rec.estimated_cost or 0))
            rec._notify_users([rec.requested_by],
                subject=_('Purchase Request %s APPROVED') % rec.name,
                body=_('<p>Dear %s,</p><p>Request <b>%s</b> approved by Trust Secretary. '
                       'Trust Manager will handle procurement.</p>') % (rec.requested_by.name, rec.name))
            rec.message_post(body=_('FINAL APPROVAL by <b>%s</b>. Trust Manager notified.') % self.env.user.name)

    def action_secretary_reject(self):
        for rec in self:
            if rec.state != 'secretary_review':
                raise UserError(_('Request must be in Secretary Review state.'))
            if not rec.secretary_remarks:
                raise UserError(_('Please provide rejection remarks before rejecting.'))
            rec.write({'state': 'rejected', 'rejected_by': self.env.user.id,
                       'rejection_reason': rec.secretary_remarks, 'rejection_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Purchase Request %s Rejected by Trust Secretary') % rec.name,
                body=_('<p>Dear %s,</p><p>Request <b>%s</b> rejected by Trust Secretary.</p>'
                       '<p><b>Reason:</b> %s</p>') % (rec.requested_by.name, rec.name, rec.rejection_reason))
            rec.message_post(body=_('REJECTED by <b>%s</b>. Reason: %s') % (self.env.user.name, rec.rejection_reason))
            if rec.asset_request_id and rec.asset_request_id.state == 'pending_purchase':
                rec.asset_request_id.write({'state': 'in_review'})

    def action_trust_manager_execute(self):
        for rec in self:
            if rec.state != 'trust_execution':
                raise UserError(_('Request must be in Trust Execution state.'))
            if not rec.po_reference:
                raise UserError(_('Please enter the PO/Order Reference before marking execution complete.'))
            rec.write({'state': 'done', 'trust_manager_executed': True,
                       'trust_manager_executed_by': self.env.user.id,
                       'trust_manager_execution_date': fields.Datetime.now(),
                       'vendor_notified': True})
            body = _('<p>Purchase request <b>%s</b> fully executed.</p>'
                     '<p><b>Item:</b> %s<br/><b>Vendor:</b> %s<br/>'
                     '<b>PO Reference:</b> %s</p>') % (
                rec.name, rec.item_description,
                rec.selected_vendor.name if rec.selected_vendor else (rec.selected_vendor_name or '—'),
                rec.po_reference)
            rec._notify_users(
                [u for u in [rec.requested_by, rec.principal_id, rec.secretary_id] if u],
                subject=_('Purchase Request %s — Execution Complete') % rec.name,
                body=body)
            rec.message_post(body=_('Execution confirmed by <b>%s</b>. PO: <b>%s</b>.') % (
                self.env.user.name, rec.po_reference))
            if rec.asset_request_id and rec.asset_request_id.state == 'pending_purchase':
                rec.asset_request_id.write({'state': 'fulfilled', 'fulfilled_date': fields.Date.today()})

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('draft', 'rejected'):
                raise UserError(_('Only draft or rejected requests can be reset.'))
            rec.write({'state': 'draft', 'principal_approved': False,
                       'acc_reviewed': False, 'secretary_approved': False,
                       'trust_manager_executed': False})

    def action_notify_vendor(self):
        self.ensure_one()
        vendor = self.selected_vendor
        if not vendor:
            raise UserError(_('No vendor selected. Please select a vendor in the ACC Review tab.'))
        if not vendor.email:
            raise UserError(_('Vendor %s has no email address configured.') % vendor.name)
        body = _('<p>Dear %s,</p><p>Your quotation for <b>%s</b> has been selected.</p>'
                 '<p><b>Amount:</b> ₹%s<br/><b>PO Reference:</b> %s</p>') % (
            vendor.name, self.item_description,
            self.selected_quote_amount or self.estimated_cost or 0,
            self.po_reference or 'To be communicated')
        try:
            self.message_post(body=body, subject=_('Procurement Inquiry: %s') % self.name,
                              partner_ids=[vendor.id], message_type='email',
                              subtype_xmlid='mail.mt_comment')
            self.write({'vendor_notified': True})
        except Exception as e:
            raise UserError(_('Failed to send vendor notification: %s') % str(e))
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Vendor Notified'), 'type': 'success', 'sticky': False,
                           'message': _('Email sent to %s') % vendor.name}}

    # ══════════════════════════════════════════════════════════════════
    #  NOTIFICATION HELPER
    # ══════════════════════════════════════════════════════════════════

    def _notify_users(self, users, subject, body):
        seen = set()
        for user in users:
            if user and user.id not in seen and user.partner_id:
                seen.add(user.id)
                try:
                    self.message_notify(partner_ids=[user.partner_id.id],
                                        subject=subject, body=body,
                                        message_type='email', subtype_xmlid='mail.mt_comment')
                except Exception:
                    pass