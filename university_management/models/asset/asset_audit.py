# -*- coding: utf-8 -*-
"""
asset_audit.py — Asset Audit (Principal-initiated, Auditor-executed)
====================================================================
Extends the existing AssetAuditSession. This file adds a new model
`asset.audit` that implements the exact client-specified audit flow:

  1. Principal initiates audit (selects scope + assigns auditor)
  2. Auditor notified
  3. Assets set to 'in_audit' state
  4. Assigned auditor scans QR codes one by one (QR scan page shows
     "Conduct Audit" button ONLY for the assigned auditor)
  5. Each scan: auditor confirms physical condition, location, present/missing
  6. On completion: Principal + Trust Secretary notified with report
  7. Missing assets trigger immediate escalation to Principal

This is the NEW audit model. The existing asset.audit.session is kept
as-is for backward compatibility.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date


class AssetAudit(models.Model):
    """
    Asset Audit — Principal-initiated audit with assigned auditor.
    """
    _name = 'asset.audit'
    _description = 'Asset Audit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, name'
    _rec_name = 'name'

    name = fields.Char(
        string='Audit Reference', required=True, readonly=True,
        copy=False, default='/',
    )

    # ── Scope ─────────────────────────────────────────────────────────
    audit_scope = fields.Selection([
        ('full_campus', 'Full Campus'),
        ('department', 'Department'),
        ('specific_assets', 'Specific Assets'),
    ], string='Audit Scope', required=True, default='full_campus', tracking=True)

    department_id = fields.Many2one(
        'university.department', string='Department',
        help='Required when scope = Department.',
    )

    # ── Assignment ────────────────────────────────────────────────────
    initiated_by = fields.Many2one(
        'res.users', string='Initiated By',
        default=lambda self: self.env.user,
        readonly=True, required=True,
    )
    assigned_to = fields.Many2one(
        'res.users', string='Assigned Auditor',
        required=True, tracking=True,
        help='The staff member or HOD assigned to physically verify assets.',
    )
    start_date = fields.Date(string='Audit Start Date', default=fields.Date.today, required=True)
    target_completion_date = fields.Date(string='Target Completion Date')
    end_date = fields.Date(string='Completed On', readonly=True)

    notes = fields.Text(string='Audit Instructions / Notes')

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ── Audit Lines ───────────────────────────────────────────────────
    audit_line_ids = fields.One2many(
        'asset.audit.line.v2', 'audit_id', string='Asset Checklist',
    )
    total_assets = fields.Integer(
        string='Total Assets', compute='_compute_audit_stats', store=True,
    )
    scanned_count = fields.Integer(
        string='Scanned', compute='_compute_audit_stats', store=True,
    )
    missing_count = fields.Integer(
        string='Missing', compute='_compute_audit_stats', store=True,
    )
    discrepancy_count = fields.Integer(
        string='Discrepancies', compute='_compute_audit_stats', store=True,
    )
    completion_pct = fields.Integer(
        string='Completion %', compute='_compute_audit_stats', store=False,
    )

    @api.depends('audit_line_ids', 'audit_line_ids.scan_status')
    def _compute_audit_stats(self):
        for rec in self:
            lines = rec.audit_line_ids
            rec.total_assets = len(lines)
            rec.scanned_count = len(lines.filtered(lambda l: l.scan_status != 'pending'))
            rec.missing_count = len(lines.filtered(lambda l: l.scan_status == 'missing'))
            rec.discrepancy_count = len(lines.filtered(lambda l: l.has_discrepancy))
            rec.completion_pct = (
                int(rec.scanned_count * 100 / rec.total_assets)
                if rec.total_assets else 0
            )

    # ── Sequence ──────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.audit') or '/'
        return super().create(vals)

    # ══════════════════════════════════════════════════════════════════
    #  STATE MACHINE ACTIONS
    # ══════════════════════════════════════════════════════════════════

    def action_start_audit(self):
        """Principal starts audit → generates asset checklist → sets assets to in_audit → notifies auditor."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Audit must be in Draft state to start.'))

            # Build asset checklist based on scope
            rec._generate_audit_lines()

            # Set assets to in_audit status
            asset_ids = rec.audit_line_ids.mapped('asset_id')
            asset_ids.write({'status': 'in_audit'})

            rec.write({'state': 'in_progress'})

            # Notify assigned auditor
            rec._notify_users(
                [rec.assigned_to],
                subject=_('You have been assigned an Asset Audit: %s') % rec.name,
                body=_(
                    '<p>Dear %s,</p>'
                    '<p>The Principal has initiated an asset audit <b>%s</b> and '
                    'assigned you as the auditor.</p>'
                    '<p><b>Scope:</b> %s<br/>'
                    '<b>Department:</b> %s<br/>'
                    '<b>Total Assets:</b> %d<br/>'
                    '<b>Target Completion:</b> %s</p>'
                    '<p><b>Instructions:</b> %s</p>'
                    '<p>Please visit each asset location, scan the QR code, and '
                    'confirm the physical condition. The "Conduct Audit" button '
                    'will appear on each asset\'s QR scan page for you.</p>'
                ) % (
                    rec.assigned_to.name, rec.name,
                    dict(rec._fields['audit_scope'].selection).get(rec.audit_scope, '—'),
                    rec.department_id.name if rec.department_id else 'All Departments',
                    rec.total_assets,
                    rec.target_completion_date or 'Not specified',
                    rec.notes or 'Verify physical condition, location accuracy, and presence of each asset.',
                ),
            )
            rec.message_post(
                body=_('Audit started by Principal <b>%s</b>. <b>%d</b> assets included. '
                       'Auditor: <b>%s</b>') % (
                    rec.initiated_by.name, rec.total_assets, rec.assigned_to.name)
            )

    def _generate_audit_lines(self):
        """Generate audit lines (asset checklist) based on scope."""
        self.ensure_one()
        domain = [('state', 'not in', ['disposed', 'condemned', 'lost'])]

        if self.audit_scope == 'department' and self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        elif self.audit_scope == 'specific_assets':
            # Lines can be manually added; skip auto-generation
            return

        assets = self.env['asset.asset'].search(domain)
        lines = []
        for asset in assets:
            lines.append((0, 0, {
                'audit_id': self.id,
                'asset_id': asset.id,
                'expected_location': asset.room or '—',
                'expected_department_id': asset.department_id.id if asset.department_id else False,
            }))
        if lines:
            self.audit_line_ids = lines

    def action_complete_audit(self):
        """Mark audit as complete → notify Principal and Trust Secretary."""
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(_('Audit must be in progress to complete.'))

            # Restore asset status for non-missing assets
            present_assets = rec.audit_line_ids.filtered(
                lambda l: l.scan_status != 'missing'
            ).mapped('asset_id')
            present_assets.write({'status': 'available'})

            rec.write({
                'state': 'completed',
                'end_date': date.today(),
            })

            summary = _(
                '<p>Audit <b>%s</b> has been completed.</p>'
                '<p><b>Total Assets:</b> %d<br/>'
                '<b>Verified Present:</b> %d<br/>'
                '<b>Missing:</b> %d<br/>'
                '<b>Discrepancies:</b> %d<br/>'
                '<b>Auditor:</b> %s<br/>'
                '<b>Completed On:</b> %s</p>'
            ) % (
                rec.name, rec.total_assets,
                rec.scanned_count - rec.missing_count,
                rec.missing_count, rec.discrepancy_count,
                rec.assigned_to.name, date.today(),
            )

            # Notify Principal and Trust Secretary
            for group_xml_id in ['asset.group_asset_principal', 'asset.group_asset_secretary']:
                rec._notify_group(
                    group_xml_id,
                    subject=_('Audit %s Completed — Report Ready') % rec.name,
                    body=summary,
                )
            rec.message_post(body=summary)

    def action_cancel(self):
        """Cancel audit and restore asset status."""
        for rec in self:
            asset_ids = rec.audit_line_ids.mapped('asset_id')
            asset_ids.filtered(lambda a: a.status == 'in_audit').write({'status': 'available'})
            rec.write({'state': 'cancelled'})

    def action_flag_missing(self, asset_id):
        """Called from QR scan controller when auditor marks asset as missing."""
        line = self.audit_line_ids.filtered(lambda l: l.asset_id.id == asset_id)
        if line:
            line.write({'scan_status': 'missing'})
            # Immediate escalation to Principal
            self._notify_group(
                'asset.group_asset_principal',
                subject=_('ALERT: Asset Reported Missing During Audit %s') % self.name,
                body=_(
                    '<p>Dear Principal,</p>'
                    '<p><b>ALERT:</b> Asset <b>%s (%s)</b> could not be found during '
                    'audit <b>%s</b>.</p>'
                    '<p>The auditor %s has flagged this asset as missing. '
                    'Please investigate immediately.</p>'
                ) % (
                    line.asset_id.name, line.asset_id.asset_code,
                    self.name, self.assigned_to.name,
                ),
            )
            self.message_post(
                body=_('⚠️ MISSING ASSET: <b>%s (%s)</b> flagged as missing by auditor %s. '
                       'Principal notified.') % (
                    line.asset_id.name, line.asset_id.asset_code, self.assigned_to.name)
            )

    # ── Notification Helpers ──────────────────────────────────────────
    def _notify_group(self, group_xml_id, subject, body):
        try:
            group = self.env.ref(group_xml_id, raise_if_not_found=False)
            if group:
                self._notify_users(group.users, subject, body)
        except Exception:
            pass

    def _notify_users(self, users, subject, body):
        for user in users:
            if user and user.partner_id:
                try:
                    self.message_notify(
                        partner_ids=[user.partner_id.id],
                        subject=subject, body=body,
                        message_type='email',
                        subtype_xmlid='mail.mt_comment',
                    )
                except Exception:
                    pass


class AssetAuditLineV2(models.Model):
    """
    Asset Audit Line (v2) — one line per asset in an audit session.
    Linked to the new asset.audit model.
    """
    _name = 'asset.audit.line.v2'
    _description = 'Asset Audit Line'
    _order = 'audit_id, asset_id'

    audit_id = fields.Many2one(
        'asset.audit', string='Audit', required=True, ondelete='cascade',
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Asset', required=True, ondelete='restrict',
    )
    asset_code = fields.Char(related='asset_id.asset_code', store=True)
    category_id = fields.Many2one(related='asset_id.category_id', store=True, string='Category')

    # ── Expected (before audit) ───────────────────────────────────────
    expected_location = fields.Char(string='Expected Location')
    expected_department_id = fields.Many2one(
        'university.department', string='Expected Department',
    )

    # ── Scan Result ───────────────────────────────────────────────────
    scan_status = fields.Selection([
        ('pending', 'Not Yet Scanned'),
        ('present', 'Present & Verified'),
        ('missing', 'Not Found / Missing'),
        ('location_mismatch', 'Found — Wrong Location'),
        ('condition_issue', 'Found — Condition Issue'),
    ], string='Scan Status', default='pending', tracking=True)

    scanned_by = fields.Many2one('res.users', string='Scanned By', readonly=True)
    scan_date = fields.Datetime(string='Scanned On', readonly=True)
    actual_location = fields.Char(string='Actual Location Found')
    actual_gps_lat = fields.Float(string='Scan GPS Lat', digits=(10, 6))
    actual_gps_lng = fields.Float(string='Scan GPS Lng', digits=(10, 6))

    # ── Condition ─────────────────────────────────────────────────────
    physical_condition = fields.Selection([
        ('good', 'Good — Working Fine'),
        ('fair', 'Fair — Minor Issues'),
        ('poor', 'Poor — Needs Repair'),
        ('damaged', 'Damaged'),
        ('beyond_repair', 'Beyond Repair'),
    ], string='Physical Condition')

    has_discrepancy = fields.Boolean(
        string='Has Discrepancy',
        compute='_compute_discrepancy', store=True,
    )
    auditor_notes = fields.Text(string='Auditor Notes')

    @api.depends('scan_status', 'physical_condition')
    def _compute_discrepancy(self):
        for line in self:
            line.has_discrepancy = (
                line.scan_status in ('missing', 'location_mismatch', 'condition_issue')
                or line.physical_condition in ('poor', 'damaged', 'beyond_repair')
            )