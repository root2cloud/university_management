# -*- coding: utf-8 -*-
"""
asset_handover.py — Asset Handover Request
==========================================
Flow:
    draft
      → pending_hod         (submitter submits → hod_user_id notified)
      → pending_principal   (hod_user_id approves → principal_id notified)
      → approved            (principal_id gives final approval → asset updated)
      → rejected            (hod_user_id or principal_id rejects)

Approver roles are set as specific users on each record — no security groups needed.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AssetHandover(models.Model):
    _name = 'asset.handover'
    _description = 'Asset Handover Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, name'
    _rec_name = 'name'

    name = fields.Char(string='Handover Reference', required=True, readonly=True, copy=False, default='/')

    # ── Asset ─────────────────────────────────────────────────────────
    asset_id = fields.Many2one('asset.asset', string='Asset', required=True,
        domain="[('state', 'in', ['active', 'transferred'])]", tracking=True, index=True, ondelete='restrict')
    asset_code = fields.Char(related='asset_id.asset_code', store=True, string='Asset Code')
    asset_category_id = fields.Many2one(related='asset_id.category_id', store=True, string='Category')

    # ── From ─────────────────────────────────────────────────────────
    from_department_id = fields.Many2one('university.department', string='From Department', tracking=True)
    from_location = fields.Char(string='Current Location')
    from_faculty_id = fields.Many2one('faculty.faculty', string='Current Custodian')
    from_gps_lat = fields.Float(string='GPS Latitude (Scan)', digits=(10, 6))
    from_gps_lng = fields.Float(string='GPS Longitude (Scan)', digits=(10, 6))

    # ── To ────────────────────────────────────────────────────────────
    to_department_id = fields.Many2one('university.department', string='Destination Department', required=True, tracking=True)
    to_location = fields.Char(string='Destination Location', required=True)
    to_faculty_id = fields.Many2one('faculty.faculty', string='Receiving Person', required=True)
    purpose = fields.Text(string='Purpose / Reason for Handover', required=True)
    handover_type = fields.Selection([
        ('permanent', 'Permanent Handover'), ('temporary', 'Temporary (On Loan)'),
    ], string='Handover Type', default='permanent', required=True, tracking=True)
    expected_return_date = fields.Date(string='Expected Return Date')
    asset_photo = fields.Binary(string='Asset Photo at Handover', attachment=True)
    asset_photo_name = fields.Char(string='Photo Filename')
    scan_triggered = fields.Boolean(string='Initiated via QR Scan', default=False, readonly=True)

    # ── Request Metadata ──────────────────────────────────────────────
    requested_by = fields.Many2one('res.users', string='Requested By',
        default=lambda self: self.env.user, required=True, tracking=True)
    request_date = fields.Datetime(string='Request Date', default=fields.Datetime.now, readonly=True)

    # ── Approver Fields (set per-record, no groups required) ──────────
    hod_user_id = fields.Many2one('res.users', string='HOD Approver', tracking=True,
        help='User who approves at HOD/department level.')
    principal_id = fields.Many2one('res.users', string='Principal Approver', tracking=True,
        help='User who gives final approval.')

    # ── Role flags for button visibility ─────────────────────────────
    is_hod_approver = fields.Boolean(compute='_compute_role_flags', store=False)
    is_principal = fields.Boolean(compute='_compute_role_flags', store=False)
    is_requester = fields.Boolean(compute='_compute_role_flags', store=False)

    @api.depends('hod_user_id', 'principal_id', 'requested_by')
    def _compute_role_flags(self):
        uid = self.env.uid
        is_admin = self.env.user.has_group('university_management.group_university_admin')
        for rec in self:
            rec.is_hod_approver = is_admin or rec.hod_user_id.id == uid
            rec.is_principal = is_admin or rec.principal_id.id == uid
            rec.is_requester = is_admin or rec.requested_by.id == uid

    # ── HOD Approval ──────────────────────────────────────────────────
    hod_approved_by = fields.Many2one('res.users', string='HOD Approved By', readonly=True)
    hod_approval_date = fields.Datetime(string='HOD Approval Date', readonly=True)
    hod_remarks = fields.Text(string='HOD Remarks')

    # ── Principal Approval ────────────────────────────────────────────
    principal_approved_by = fields.Many2one('res.users', string='Principal Approved By', readonly=True)
    principal_approval_date = fields.Datetime(string='Principal Approval Date', readonly=True)
    principal_remarks = fields.Text(string='Principal Remarks')

    # ── Rejection ─────────────────────────────────────────────────────
    rejection_reason = fields.Text(string='Rejection Reason')
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejection_date = fields.Datetime(string='Rejection Date', readonly=True)

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_hod', 'Pending HOD Approval'),
        ('pending_principal', 'Pending Principal Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True, required=True)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.handover') or '/'
        if vals.get('asset_id') and not vals.get('from_department_id'):
            asset = self.env['asset.asset'].browse(vals['asset_id'])
            if asset.department_id:
                vals['from_department_id'] = asset.department_id.id
            if asset.room:
                vals['from_location'] = asset.room
            if asset.faculty_id:
                vals['from_faculty_id'] = asset.faculty_id.id
        return super().create(vals)

    @api.constrains('handover_type', 'expected_return_date')
    def _check_return_date(self):
        for rec in self:
            if rec.handover_type == 'temporary' and not rec.expected_return_date:
                raise UserError(_('Expected Return Date is required for temporary handovers.'))

    # ══════════════════════════════════════════════════════════════════
    #  STATE MACHINE
    # ══════════════════════════════════════════════════════════════════

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            if not rec.hod_user_id:
                raise UserError(_('Please set an HOD Approver before submitting.'))
            rec.asset_id.write({'status': 'not_available'})
            rec.write({'state': 'pending_hod'})
            rec._notify_users([rec.hod_user_id],
                subject=_('Handover Request for Asset %s — Your Approval Needed') % rec.asset_id.name,
                body=_('<p>Dear %s,</p><p><b>%s</b> submitted a handover request for asset <b>%s</b>.</p>'
                       '<p><b>From:</b> %s → <b>To:</b> %s<br/><b>Purpose:</b> %s</p>') % (
                    rec.hod_user_id.name, rec.requested_by.name, rec.asset_id.name,
                    rec.from_department_id.name if rec.from_department_id else '—',
                    rec.to_department_id.name, rec.purpose))
            rec.message_post(body=_('Submitted by <b>%s</b>. Pending HOD approval.') % rec.requested_by.name)

    def action_hod_approve(self):
        for rec in self:
            if rec.state != 'pending_hod':
                raise UserError(_('Request must be pending HOD approval.'))
            if not rec.principal_id:
                raise UserError(_('Please set a Principal Approver before approving.'))
            rec.write({'state': 'pending_principal', 'hod_approved_by': self.env.user.id,
                       'hod_approval_date': fields.Datetime.now()})
            rec._notify_users([rec.principal_id],
                subject=_('Handover Request %s Needs Your Final Approval') % rec.name,
                body=_('<p>Dear %s,</p><p>Handover request <b>%s</b> for asset <b>%s</b> '
                       'approved by HOD — needs your final approval.</p>'
                       '<p><b>From:</b> %s → <b>To:</b> %s<br/><b>Purpose:</b> %s</p>') % (
                    rec.principal_id.name, rec.name, rec.asset_id.name,
                    rec.from_department_id.name if rec.from_department_id else '—',
                    rec.to_department_id.name, rec.purpose))
            rec.message_post(body=_('HOD approved by <b>%s</b>. Escalated to Principal.') % self.env.user.name)

    def action_hod_reject(self):
        for rec in self:
            if rec.state != 'pending_hod':
                raise UserError(_('Request must be pending HOD approval.'))
            if not rec.hod_remarks:
                raise UserError(_('Please provide HOD remarks/rejection reason.'))
            rec.asset_id.write({'status': 'available'})
            rec.write({'state': 'rejected', 'rejected_by': self.env.user.id,
                       'rejection_reason': rec.hod_remarks, 'rejection_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Handover Request %s Rejected by HOD') % rec.name,
                body=_('<p>Dear %s,</p><p>Handover request <b>%s</b> rejected by HOD.</p>'
                       '<p><b>Reason:</b> %s</p>') % (rec.requested_by.name, rec.name, rec.rejection_reason))
            rec.message_post(body=_('Rejected by HOD <b>%s</b>. Reason: %s') % (self.env.user.name, rec.rejection_reason))

    def action_principal_approve(self):
        for rec in self:
            if rec.state != 'pending_principal':
                raise UserError(_('Request must be pending Principal approval.'))
            rec.asset_id.write({
                'department_id': rec.to_department_id.id,
                'room': rec.to_location,
                'faculty_id': rec.to_faculty_id.id if rec.to_faculty_id else False,
                'custodian_name': rec.to_faculty_id.name if rec.to_faculty_id else False,
                'status': 'available',
                **(({'state': 'transferred'} if rec.handover_type == 'temporary' else {})),
            })
            rec.write({'state': 'approved', 'principal_approved_by': self.env.user.id,
                       'principal_approval_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Handover Request %s Approved — Asset Transferred') % rec.name,
                body=_('<p>Dear %s,</p><p>Handover request <b>%s</b> approved by Principal. '
                       'Asset transferred to %s.</p>') % (
                    rec.requested_by.name, rec.name, rec.to_department_id.name))
            rec.message_post(body=_('FINAL APPROVAL by Principal <b>%s</b>. Asset location updated.') % self.env.user.name)

    def action_principal_reject(self):
        for rec in self:
            if rec.state != 'pending_principal':
                raise UserError(_('Request must be pending Principal approval.'))
            if not rec.principal_remarks:
                raise UserError(_('Please provide Principal rejection remarks.'))
            rec.asset_id.write({'status': 'available'})
            rec.write({'state': 'rejected', 'rejected_by': self.env.user.id,
                       'rejection_reason': rec.principal_remarks, 'rejection_date': fields.Datetime.now()})
            rec._notify_users([rec.requested_by],
                subject=_('Handover Request %s Rejected by Principal') % rec.name,
                body=_('<p>Dear %s,</p><p>Handover request <b>%s</b> rejected by Principal.</p>'
                       '<p><b>Reason:</b> %s</p>') % (rec.requested_by.name, rec.name, rec.rejection_reason))
            rec.message_post(body=_('Rejected by Principal <b>%s</b>. Reason: %s') % (
                self.env.user.name, rec.rejection_reason))

    # ── Notification Helper ───────────────────────────────────────────
    def _notify_users(self, users, subject, body):
        seen = set()
        for user in users:
            if user and user.id not in seen and user.partner_id:
                seen.add(user.id)
                try:
                    self.message_notify(partner_ids=[user.partner_id.id], subject=subject, body=body,
                                        message_type='email', subtype_xmlid='mail.mt_comment')
                except Exception:
                    pass