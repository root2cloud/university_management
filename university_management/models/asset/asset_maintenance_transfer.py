# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class AssetMaintenance(models.Model):
    """
    Maintenance Request / Service Record for an asset.

    Covers:
      - Preventive maintenance (scheduled AMC service)
      - Corrective maintenance (breakdown / repair)

    Accounting integration (base_accounting_kit):
      - maintenance_invoice_id: links to the vendor bill created in accounting
        so the cost hits the proper GL expense account.

    Budget integration (base_account_budget):
      - analytic_account_id: pulled from the asset's category. When a vendor
        bill is linked, the analytic tag ensures the cost appears in budget
        reports against the category's budgetary position.
    """
    _name = 'asset.maintenance'
    _description = 'Asset Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Reference', required=True, readonly=True,
                       copy=False, default='/')
    asset_id = fields.Many2one('asset.asset', string='Asset', required=True,
                                tracking=True, index=True, ondelete='cascade')
    asset_code = fields.Char(related='asset_id.asset_code', string='Asset Code', store=True)
    category_id = fields.Many2one(related='asset_id.category_id', string='Category', store=True)
    department_id = fields.Many2one(related='asset_id.department_id', string='Department', store=True)

    # ── Request ──────────────────────────────────────────────────────
    maintenance_type = fields.Selection([
        ('preventive', 'Preventive / Scheduled'),
        ('corrective', 'Corrective / Breakdown'),
        ('amc', 'AMC Service'),
        ('calibration', 'Calibration'),
        ('inspection', 'Inspection'),
    ], string='Type', required=True, default='corrective', tracking=True)

    request_date = fields.Date(string='Request Date', default=fields.Date.today, required=True)
    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user)
    faculty_id = fields.Many2one('faculty.faculty', string='Reported By (Faculty)',
                                  help='Faculty member who reported the issue')
    problem_description = fields.Text(string='Problem / Issue Description', required=True)
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High — Urgent'),
        ('critical', 'Critical — Stopped Working'),
    ], string='Priority', default='medium', tracking=True)

    # ── Assignment ───────────────────────────────────────────────────
    assigned_to = fields.Many2one('res.users', string='Assigned To (Technician)', tracking=True)
    vendor_id = fields.Many2one('res.partner', string='External Vendor / Service Centre')
    scheduled_date = fields.Date(string='Scheduled Service Date', tracking=True)

    # ── Completion ───────────────────────────────────────────────────
    completion_date = fields.Date(string='Completed On', tracking=True)
    work_done = fields.Text(string='Work Done / Remarks')
    parts_replaced = fields.Text(string='Parts Replaced / Spare Parts Used')
    cost = fields.Monetary(string='Maintenance Cost (₹)', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                   default=lambda self: self.env.company.currency_id)
    invoice_no = fields.Char(string='Vendor Invoice No.')
    next_service_date = fields.Date(string='Next Service Due')

    # ── Accounting integration (base_accounting_kit) ─────────────────
    maintenance_invoice_id = fields.Many2one(
        'account.move',
        string='Vendor Bill (Accounting)',
        domain=[('move_type', 'in', ['in_invoice', 'in_refund'])],
        copy=False,
        help='Link to the vendor bill in accounting for this maintenance. '
             'Ensures the cost hits the correct GL expense account and '
             'appears in financial reports.',
    )
    maintenance_invoice_state = fields.Selection(
        related='maintenance_invoice_id.state',
        string='Bill Status',
        store=True, readonly=True,
    )

    # ── Budget integration (base_account_budget) ─────────────────────
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        related='asset_id.analytic_account_id',
        store=True, readonly=True,
        help='Pulled from the asset category. Maintenance costs tagged here '
             'feed budget reports and budgetary position tracking.',
    )

    # ── State ────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'New Request'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # ── Satisfaction ─────────────────────────────────────────────────
    feedback = fields.Selection([
        ('satisfied', 'Satisfied'),
        ('partially', 'Partially Satisfied'),
        ('unsatisfied', 'Not Satisfied'),
    ], string='Faculty Feedback')

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.maintenance') or '/'
        return super().create(vals)

    def action_assign(self):
        self.ensure_one()
        if not self.assigned_to and not self.vendor_id:
            raise ValidationError(_('Please assign a technician or vendor before proceeding.'))
        self.write({'state': 'assigned'})
        self.message_post(body=_('Maintenance request assigned to %s.') % (
            self.assigned_to.name if self.assigned_to else self.vendor_id.name))

    def action_start(self):
        self.ensure_one()
        self.asset_id.write({'state': 'under_maintenance'})
        self.write({'state': 'in_progress'})
        self.message_post(body=_('Maintenance work started. Asset moved to Under Maintenance.'))

    def action_complete(self):
        self.ensure_one()
        if not self.work_done:
            raise ValidationError(_('Please enter work done details before completing.'))
        self.write({
            'state': 'completed',
            'completion_date': date.today(),
        })
        # Update asset
        update_vals = {
            'state': 'active',
            'last_service_date': date.today(),
        }
        if self.next_service_date:
            update_vals['next_service_date'] = self.next_service_date
        self.asset_id.write(update_vals)

        # If the linked accounting asset exists, update its note so the
        # service history is visible on the accounting record too
        if self.asset_id.account_asset_id:
            existing_note = self.asset_id.account_asset_id.note or ''
            service_note = (
                f'\n[{date.today()}] Maintenance completed — {self.name}. '
                f'Cost: {self.cost or 0}. Work: {self.work_done or "-"}'
            )
            self.asset_id.account_asset_id.sudo().write({
                'note': existing_note + service_note
            })

        self.message_post(
            body=_('Maintenance completed. Cost: ₹%s. Asset returned to Active.') % (
                self.cost or 0)
        )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_open_vendor_bill(self):
        """Open the linked vendor bill in accounting."""
        self.ensure_one()
        if not self.maintenance_invoice_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'res_id': self.maintenance_invoice_id.id,
            'view_mode': 'form',
        }

    def action_create_vendor_bill(self):
        """
        Quick-create a draft vendor bill for this maintenance cost.
        Pre-fills the vendor, amount, and analytic account so the cost
        flows into the correct GL account and budget report.
        """
        self.ensure_one()
        acc_cat = self.category_id.account_asset_category_id
        expense_account = acc_cat.account_depreciation_expense_id if acc_cat else False

        bill_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.vendor_id.id if self.vendor_id else False,
            'ref': self.name,
            'invoice_date': date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': f'Maintenance — {self.asset_id.name} ({self.name})',
                'quantity': 1,
                'price_unit': self.cost or 0.0,
                'account_id': expense_account.id if expense_account else False,
                'analytic_distribution': {
                    str(self.analytic_account_id.id): 100
                } if self.analytic_account_id else {},
            })],
        }
        bill = self.env['account.move'].create(bill_vals)
        self.write({'maintenance_invoice_id': bill.id})
        self.message_post(
            body=_('Vendor bill <b>%s</b> created for maintenance cost ₹%s.') % (
                bill.name, self.cost or 0)
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Bill'),
            'res_model': 'account.move',
            'res_id': bill.id,
            'view_mode': 'form',
        }


class AssetTransfer(models.Model):
    """
    Asset Transfer — tracks movement of assets between departments/locations/custodians.

    Required when:
      - Department changes (Lab 1 → Lab 2)
      - Faculty changes (new faculty takes over)
      - Building changes (renovation, shifting)
      - Temporary transfer (loan to another dept)

    Every transfer requires approval and is audited.

    Accounting note: when a transfer is completed, the linked
    account.asset.asset record's note is updated so the location
    change is visible in the accounting asset too.
    """
    _name = 'asset.transfer'
    _description = 'Asset Transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'transfer_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Transfer Reference', required=True, readonly=True,
                       copy=False, default='/')
    asset_id = fields.Many2one('asset.asset', string='Asset', required=True,
                                tracking=True, index=True, ondelete='cascade')

    # ── From ─────────────────────────────────────────────────────────
    from_department_id = fields.Many2one('university.department', string='From Department')
    from_location = fields.Char(string='From Location')
    from_custodian = fields.Char(string='From Custodian')
    from_faculty_id = fields.Many2one('faculty.faculty', string='From Faculty')

    # ── To ───────────────────────────────────────────────────────────
    to_department_id = fields.Many2one('university.department', string='To Department',
                                        required=True, tracking=True)
    to_location = fields.Char(string='To Location', required=True)
    to_custodian = fields.Char(string='To Custodian')
    to_faculty_id = fields.Many2one('faculty.faculty', string='To Faculty')

    transfer_date = fields.Date(string='Transfer Date', default=fields.Date.today,
                                 required=True, tracking=True)
    transfer_type = fields.Selection([
        ('permanent', 'Permanent Transfer'),
        ('temporary', 'Temporary / On Loan'),
    ], string='Transfer Type', default='permanent', tracking=True)
    return_date = fields.Date(string='Expected Return Date',
                               help='Required for temporary transfers')
    reason = fields.Text(string='Reason for Transfer', required=True)

    # ── Inventory Location Sync (stock module) ────────────────────────
    from_location_id = fields.Many2one(
        'stock.location', string='From Inventory Location',
        domain=[('usage', 'in', ['internal', 'transit'])],
        help='Inventory location the asset is moving from. Auto-filled from asset.location_id.',
    )
    to_location_id = fields.Many2one(
        'stock.location', string='To Inventory Location',
        domain=[('usage', 'in', ['internal', 'transit'])],
        help='Inventory location the asset is moving to. '
             'Updates asset.location_id on transfer completion.',
    )

    requested_by = fields.Many2one('res.users', string='Requested By',
                                    default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approved On', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('returned', 'Returned'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.transfer') or '/'
        # Auto-fill from_location_id from the asset's current location
        if vals.get('asset_id') and not vals.get('from_location_id'):
            asset = self.env['asset.asset'].browse(vals['asset_id'])
            if asset.location_id:
                vals['from_location_id'] = asset.location_id.id
        return super().create(vals)

    def action_submit(self):
        self.write({'state': 'pending'})
        self.message_post(body=_('Transfer request submitted for approval.'))

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': date.today(),
        })
        self.message_post(body=_('Transfer approved by %s.') % self.env.user.name)

    def action_complete(self):
        self.ensure_one()
        asset_update = {
            'department_id': self.to_department_id.id,
            'room': self.to_location,
            'custodian_name': self.to_custodian,
            'faculty_id': self.to_faculty_id.id if self.to_faculty_id else False,
            'state': 'transferred' if self.transfer_type == 'temporary' else 'active',
        }
        # Sync inventory location
        if self.to_location_id:
            asset_update['location_id'] = self.to_location_id.id

        self.asset_id.write(asset_update)
        self.write({'state': 'completed'})

        # Sync the location note on the accounting asset record
        if self.asset_id.account_asset_id:
            existing_note = self.asset_id.account_asset_id.note or ''
            transfer_note = (
                f'\n[{date.today()}] Transfer {self.name}: '
                f'{self.from_department_id.name or "?"} → {self.to_department_id.name}, '
                f'Location: {self.to_location}'
            )
            self.asset_id.account_asset_id.sudo().write({
                'note': existing_note + transfer_note
            })

        self.message_post(
            body=_('Asset transferred to <b>%s</b> — %s.') % (
                self.to_department_id.name, self.to_location)
        )

    def action_return(self):
        """Return asset after temporary transfer."""
        self.ensure_one()
        asset_return = {
            'department_id': self.from_department_id.id if self.from_department_id else False,
            'room': self.from_location,
            'custodian_name': self.from_custodian,
            'faculty_id': self.from_faculty_id.id if self.from_faculty_id else False,
            'state': 'active',
        }
        # Restore original inventory location
        if self.from_location_id:
            asset_return['location_id'] = self.from_location_id.id

        self.asset_id.write(asset_return)
        self.write({'state': 'returned'})

        if self.asset_id.account_asset_id:
            existing_note = self.asset_id.account_asset_id.note or ''
            return_note = (
                f'\n[{date.today()}] Asset returned from transfer {self.name} '
                f'to {self.from_department_id.name or "original location"}.'
            )
            self.asset_id.account_asset_id.sudo().write({
                'note': existing_note + return_note
            })

        self.message_post(body=_('Asset returned from temporary transfer.'))

    def action_reject(self):
        self.write({'state': 'rejected'})


class AssetDocument(models.Model):
    """
    Documents attached to an asset — purchase invoice, warranty card, AMC certificate,
    calibration certificate, photos, etc.
    """
    _name = 'asset.document'
    _description = 'Asset Document'
    _order = 'document_date desc'

    asset_id = fields.Many2one('asset.asset', string='Asset', required=True,
                                ondelete='cascade', index=True)
    name = fields.Char(string='Document Name', required=True)
    document_type = fields.Selection([
        ('purchase_invoice', 'Purchase Invoice'),
        ('warranty_card', 'Warranty Card'),
        ('amc_certificate', 'AMC Certificate'),
        ('calibration_cert', 'Calibration Certificate'),
        ('photo', 'Asset Photo'),
        ('manual', 'User Manual'),
        ('inspection_report', 'Inspection Report'),
        ('disposal_certificate', 'Disposal Certificate'),
        ('other', 'Other'),
    ], string='Document Type', required=True)
    document_date = fields.Date(string='Document Date')
    attachment = fields.Binary(string='File', attachment=True, required=True)
    attachment_name = fields.Char(string='File Name')
    notes = fields.Text(string='Notes')


class AssetAuditSession(models.Model):
    """
    Annual Physical Verification / Audit Session.

    Every year the college must physically verify all assets.
    This model tracks the audit drive: who did it, when, department-wise.

    On completion, found assets are marked audited on both asset.asset
    and on the linked account.asset.asset record (note updated) so the
    audit trail is visible in the accounting module too.
    """
    _name = 'asset.audit.session'
    _description = 'Asset Physical Audit Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'audit_year desc, name'

    name = fields.Char(string='Audit Reference', required=True, readonly=True,
                       copy=False, default='/')
    audit_year = fields.Integer(string='Audit Year', required=True,
                                 default=lambda self: date.today().year)
    audit_type = fields.Selection([
        ('annual', 'Annual Physical Verification'),
        ('surprise', 'Surprise Verification'),
        ('grant', 'Grant Audit (UGC/AICTE)'),
        ('naac', 'NAAC Accreditation Audit'),
    ], string='Audit Type', default='annual', required=True)
    start_date = fields.Date(string='Audit Start Date', required=True)
    end_date = fields.Date(string='Audit End Date')
    conducted_by = fields.Many2one('res.users', string='Audit Conducted By',
                                    default=lambda self: self.env.user)
    department_ids = fields.Many2many(
        'university.department', string='Departments Covered',
    )
    audit_line_ids = fields.One2many('asset.audit.line', 'session_id', string='Audit Lines')
    total_assets = fields.Integer(string='Total Assets', compute='_compute_stats', store=True)
    verified_count = fields.Integer(string='Verified', compute='_compute_stats', store=True)
    missing_count = fields.Integer(string='Missing / Not Found', compute='_compute_stats', store=True)
    remarks = fields.Text(string='Overall Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('report_generated', 'Report Generated'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('audit_line_ids', 'audit_line_ids.status')
    def _compute_stats(self):
        for rec in self:
            lines = rec.audit_line_ids
            rec.total_assets = len(lines)
            rec.verified_count = len(lines.filtered(lambda l: l.status == 'found'))
            rec.missing_count = len(lines.filtered(lambda l: l.status == 'not_found'))

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.audit.session') or '/'
        return super().create(vals)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_generate_lines(self):
        """Auto-populate audit lines from all active assets in selected departments."""
        self.ensure_one()
        domain = [('state', 'not in', ['disposed', 'condemned', 'lost'])]
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        assets = self.env['asset.asset'].search(domain)
        lines = []
        for asset in assets:
            existing = self.audit_line_ids.filtered(lambda l: l.asset_id == asset)
            if not existing:
                lines.append((0, 0, {
                    'asset_id': asset.id,
                    'expected_location': f'{asset.room or ""} {asset.building or ""}',
                    'has_accounting_asset': bool(asset.account_asset_id),
                }))
        self.write({'audit_line_ids': lines})
        self.message_post(
            body=_('%s asset lines generated for verification.') % len(assets)
        )

    def action_complete(self):
        """
        Complete audit:
        - Mark found assets as audited on asset.asset
        - Update the note on the linked account.asset.asset so the audit
          trail is visible in base_accounting_kit too
        """
        found = self.audit_line_ids.filtered(lambda l: l.status == 'found')
        for line in found:
            line.asset_id.write({
                'last_audit_date': date.today(),
                'last_audit_by': self.env.user.id,
                'audit_remarks': line.remarks,
            })
            # Sync audit note to accounting asset
            if line.asset_id.account_asset_id:
                existing_note = line.asset_id.account_asset_id.note or ''
                audit_note = (
                    f'\n[{date.today()}] Physical audit {self.name} ({self.audit_type}): '
                    f'FOUND at {line.actual_location or line.expected_location or "verified location"}.'
                )
                line.asset_id.account_asset_id.sudo().write({
                    'note': existing_note + audit_note
                })

        # Log not-found assets on their accounting record too
        not_found = self.audit_line_ids.filtered(lambda l: l.status == 'not_found')
        for line in not_found:
            if line.asset_id.account_asset_id:
                existing_note = line.asset_id.account_asset_id.note or ''
                missing_note = (
                    f'\n[{date.today()}] Physical audit {self.name}: '
                    f'NOT FOUND. Remarks: {line.remarks or "-"}'
                )
                line.asset_id.account_asset_id.sudo().write({
                    'note': existing_note + missing_note
                })

        self.write({'state': 'completed', 'end_date': date.today()})
        self.message_post(
            body=_('Audit completed. %s found, %s missing.') % (
                self.verified_count, self.missing_count)
        )


class AssetAuditLine(models.Model):
    """One line per asset in a physical audit session."""
    _name = 'asset.audit.line'
    _description = 'Asset Audit Line'

    session_id = fields.Many2one('asset.audit.session', string='Audit Session',
                                  required=True, ondelete='cascade', index=True)
    asset_id = fields.Many2one('asset.asset', string='Asset', required=True)
    asset_code = fields.Char(related='asset_id.asset_code', store=True)
    category_id = fields.Many2one(related='asset_id.category_id', store=True)
    expected_location = fields.Char(string='Expected Location')
    actual_location = fields.Char(string='Found At')
    # Shows if the asset has a linked accounting record — useful during audit
    has_accounting_asset = fields.Boolean(
        string='Accounting Asset Linked',
        help='Whether this asset has a linked account.asset.asset record in base_accounting_kit.',
    )
    status = fields.Selection([
        ('pending', 'Not Yet Verified'),
        ('found', 'Found — OK'),
        ('found_damaged', 'Found — Damaged'),
        ('not_found', 'Not Found'),
        ('excess', 'Excess / Unregistered'),
    ], string='Verification Status', default='pending')
    verified_by = fields.Many2one('res.users', string='Verified By')
    verification_date = fields.Date(string='Verified On')
    remarks = fields.Char(string='Remarks')

    def action_mark_found(self):
        self.write({
            'status': 'found',
            'verified_by': self.env.user.id,
            'verification_date': date.today(),
            'actual_location': self.expected_location,
        })

    def action_mark_not_found(self):
        self.write({
            'status': 'not_found',
            'verified_by': self.env.user.id,
            'verification_date': date.today(),
        })