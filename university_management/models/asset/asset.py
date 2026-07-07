# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date
from dateutil.relativedelta import relativedelta
from uuid import uuid4
import io
import base64

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class Asset(models.Model):
    """
    Asset — the core model representing a physical asset owned by the institution.

    Full lifecycle:
        draft → active → under_maintenance → disposed / condemned / lost

    Integration points:
      - base_accounting_kit : links to account.asset.asset for GL depreciation
                              posting, depreciation board computation, and
                              proper disposal journal entries.
      - base_account_budget : maintenance costs can be posted to the category's
                              analytic account so they appear in budget reports.

    Each asset tracks:
      - Identity: code, name, category, make/model/serial
      - Location: building, floor, room, department, assigned to
      - Purchase: vendor, date, cost, invoice, warranty
      - Accounting: linked account.asset.asset with full depreciation board
      - Depreciation: method, rate, current book value (from accounting asset)
      - Maintenance: AMC, service history, next service due
      - Audit: annual physical verification status
      - Documents: photos, purchase invoice, warranty card, AMC certificate
    """
    _name = 'asset.asset'
    _description = 'Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'asset_code'
    _rec_name = 'name'

    # ── Identity ─────────────────────────────────────────────────────
    asset_code = fields.Char(
        string='Asset Code', required=True, readonly=True,
        copy=False, default='/',
        help='Auto-generated unique asset code. Format: AST/YEAR/SEQ',
    )
    name = fields.Char(string='Asset Name', required=True, tracking=True)
    category_id = fields.Many2one(
        'asset.category', string='Category', required=True,
        tracking=True, index=True,
    )
    sub_category = fields.Char(string='Sub Type / Model',
                                help='e.g. Desktop, Laptop, Projector under IT Equipment')
    make = fields.Char(string='Make / Brand', help='e.g. Dell, HP, Samsung, Bosch')
    model_number = fields.Char(string='Model Number')
    serial_number = fields.Char(string='Serial Number', index=True)
    asset_tag = fields.Char(string='Asset Tag / Sticker No.',
                             help='Physical sticker number on the asset')
    color = fields.Char(string='Colour / Description')
    asset_photo = fields.Binary(string='Asset Photo', attachment=True)
    qr_code = fields.Binary(string='QR Code', readonly=True,
                            attachment=True,
                            help='Auto-generated QR code for mobile scanning')
    qr_scan_token = fields.Char(
        string='QR Scan Token', readonly=True, copy=False,
        help='UUID token embedded in QR URL for scan authentication.',
    )
    last_scan_date = fields.Datetime(string='Last Scanned On', readonly=True)

    # ── Inventory / Warehouse Location (stock module) ─────────────────
    location_id = fields.Many2one(
        'stock.location', string='Inventory Location',
        domain=[('usage', 'in', ['internal', 'transit'])],
        tracking=True,
        help='Physical warehouse / room location in Odoo inventory. '
             'Lets you see where this asset is in the inventory tree.',
    )
    location_name = fields.Char(
        related='location_id.complete_name', store=True,
        string='Location Path', readonly=True,
    )
    stock_lot_id = fields.Many2one(
        'stock.lot', string='Inventory Lot / Serial',
        domain="[('product_id', '=', False)]",
        copy=False,
        help='Links asset serial number to an Odoo inventory lot for full '
             'inventory traceability.',
    )

    # ── Purchase Order Link (purchase module) ─────────────────────────
    purchase_order_id = fields.Many2one(
        'purchase.order', string='Purchase Order',
        copy=False, tracking=True,
        help='Actual purchase.order record this asset was procured from.',
    )
    purchase_order_state = fields.Selection(
        related='purchase_order_id.state',
        string='PO Status', store=True, readonly=True,
    )

    # ── Asset Request link ────────────────────────────────────────────
    request_ids = fields.One2many(
        'asset.request', 'asset_id', string='Asset Requests',
    )
    request_count = fields.Integer(
        string='Requests', compute='_compute_request_count',
    )

    # ── QR Scan Log ───────────────────────────────────────────────────
    scan_log_ids = fields.One2many(
        'asset.qr.scan.log', 'asset_id', string='QR Scan History',
    )
    scan_log_count = fields.Integer(
        string='QR Scans', compute='_compute_scan_log_count',
    )

    # ── Location ─────────────────────────────────────────────────────
    building = fields.Char(string='Building / Block',
                            help='e.g. Main Block, Science Block, Admin Block')
    floor = fields.Char(string='Floor', help='e.g. Ground Floor, 1st Floor')
    room = fields.Char(string='Room / Lab / Office',
                        help='e.g. Lab 101, Principal Office, Seminar Hall')
    department_id = fields.Many2one(
        'university.department', string='Department',
        help='Department that owns / uses this asset',
    )
    # ── HOD In-Charge ─────────────────────────────────────────────
    hod_id = fields.Many2one(
        'hr.employee',
        string='HOD In-Charge',
        tracking=True,
        help='Head of Department responsible for this asset. '
             'Receives notifications on registration, status changes, and alerts.',
        index=True,
    )
    hod_name = fields.Char(
        related='hod_id.name', store=True, string='HOD Name', readonly=True,
    )
    hod_user_id = fields.Many2one(
        'res.users',
        related='hod_id.resource_id.user_id',
        store=True, string='HOD Odoo User', readonly=True,
    )

    # ── Asset Type & Operational Status ──────────────────────────
    asset_type = fields.Selection([
        ('physical', 'Physical'),
        ('digital', 'Digital / Software'),
        ('consumable', 'Consumable'),
    ], string='Asset Type', default='physical', tracking=True)

    status = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available'),
        ('needs_purchase', 'Needs Purchase'),
        ('in_audit', 'In Audit'),
    ], string='Operational Status', default='available', tracking=True)

    license_expiry = fields.Date(string='License Expiry Date')

    stock_qty = fields.Float(string='Stock Quantity', default=0.0)
    min_stock_qty = fields.Float(string='Minimum Stock Threshold', default=0.0)
    low_stock = fields.Boolean(
        string='Low Stock',
        compute='_compute_low_stock', store=True,
    )
    last_scan_lat = fields.Float(string='Last GPS Latitude', digits=(10, 6), readonly=True)
    last_scan_lng = fields.Float(string='Last GPS Longitude', digits=(10, 6), readonly=True)
    assigned_to = fields.Selection([
        ('department', 'Department'),
        ('faculty', 'Faculty Member'),
        ('student_lab', 'Student Lab'),
        ('common', 'Common / Shared'),
        ('admin', 'Administration'),
    ], string='Assigned To', default='department', tracking=True)
    faculty_id = fields.Many2one(
        'faculty.faculty', string='Assigned Faculty',
        help='Faculty member personally responsible for this asset',
    )
    custodian_name = fields.Char(
        string='Custodian Name',
        help='Person responsible for this asset. Auto-filled from faculty if assigned.',
    )
    custodian_contact = fields.Char(string='Custodian Contact')

    # ── Purchase Details ──────────────────────────────────────────────
    purchase_date = fields.Date(string='Purchase Date', tracking=True)
    purchase_cost = fields.Monetary(
        string='Purchase Cost (₹)', currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    vendor_id = fields.Many2one('res.partner', string='Vendor / Supplier')
    vendor_name = fields.Char(related='vendor_id.name', string='Vendor Name', store=True)
    purchase_order_no = fields.Char(string='Purchase Order No.')
    invoice_no = fields.Char(string='Invoice No.')
    invoice_date = fields.Date(string='Invoice Date')
    # Link to account.move (vendor bill) for proper accounting integration
    account_invoice_id = fields.Many2one(
        'account.move', string='Purchase Invoice (Accounting)',
        domain=[('move_type', 'in', ['in_invoice', 'in_refund'])],
        help='Link to the vendor bill in accounting. '
             'The base_accounting_kit asset record uses this for proper GL posting.',
        copy=False,
    )
    funded_by = fields.Selection([
        ('institute', 'Institute Funds'),
        ('ugc', 'UGC Grant'),
        ('aicte', 'AICTE Grant'),
        ('naac', 'NAAC Fund'),
        ('government', 'Government Grant'),
        ('csr', 'CSR / Donation'),
        ('project', 'Research Project Fund'),
        ('other', 'Other'),
    ], string='Funded By', default='institute', tracking=True,
       help='Funding source — important for NAAC and audit reporting')
    grant_reference = fields.Char(string='Grant / Scheme Reference',
                                   help='Grant number or scheme name if funded by UGC/AICTE/Govt')

    # ── Warranty ─────────────────────────────────────────────────────
    warranty_period_months = fields.Integer(string='Warranty Period (Months)', default=12)
    warranty_expiry_date = fields.Date(
        string='Warranty Expiry Date',
        compute='_compute_warranty_expiry', store=True,
    )
    warranty_vendor_contact = fields.Char(string='Warranty Contact')
    is_under_warranty = fields.Boolean(
        string='Under Warranty', compute='_compute_is_under_warranty', store=True,
    )

    # ── Accounting Asset Link (base_accounting_kit) ──────────────────
    account_asset_id = fields.Many2one(
        'account.asset.asset',
        string='Accounting Asset Record',
        copy=False, readonly=True,
        help='Auto-created account.asset.asset record in base_accounting_kit. '
             'Manages GL depreciation entries, depreciation board, and disposal moves.',
    )
    # Smart button count for accounting entries
    accounting_entry_count = fields.Integer(
        string='Accounting Entries', compute='_compute_accounting_entry_count',
    )
    # Residual value pulled from accounting record
    accounting_value_residual = fields.Monetary(
        string='Accounting Residual Value', currency_field='currency_id',
        compute='_compute_accounting_values', store=True,
    )
    accounting_state = fields.Selection(
        [('draft', 'Draft'), ('open', 'Running'), ('close', 'Closed')],
        string='Accounting Asset Status',
        compute='_compute_accounting_values', store=True,
    )

    # ── Depreciation ─────────────────────────────────────────────────
    depreciation_method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining', 'Declining Balance'),
        ('none', 'No Depreciation'),
    ], string='Depreciation Method', default='straight_line')
    useful_life_years = fields.Integer(string='Useful Life (Years)', default=5)
    residual_value = fields.Monetary(
        string='Residual Value (₹)', currency_field='currency_id',
        help='Expected scrap/salvage value at end of useful life',
    )
    depreciation_rate = fields.Float(
        string='Depreciation Rate %',
        compute='_compute_depreciation_rate', store=True,
    )
    accumulated_depreciation = fields.Monetary(
        string='Accumulated Depreciation (₹)', currency_field='currency_id',
        compute='_compute_accumulated_depreciation', store=True,
    )
    current_book_value = fields.Monetary(
        string='Current Book Value (₹)', currency_field='currency_id',
        compute='_compute_book_value', store=True,
    )

    # ── Condition & Status ────────────────────────────────────────────
    condition = fields.Selection([
        ('new', 'New'),
        ('good', 'Good'),
        ('fair', 'Fair / Working'),
        ('poor', 'Poor / Needs Repair'),
        ('non_functional', 'Non-Functional'),
        ('condemned', 'Condemned'),
    ], string='Physical Condition', default='new', tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('under_maintenance', 'Under Maintenance'),
        ('transferred', 'Transferred'),
        ('disposed', 'Disposed'),
        ('condemned', 'Condemned'),
        ('lost', 'Lost / Stolen'),
        ('audited', 'Verified (Audited)'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ── Maintenance / AMC ─────────────────────────────────────────────
    has_amc = fields.Boolean(string='Has AMC', default=False, tracking=True)
    amc_vendor_id = fields.Many2one('res.partner', string='AMC Vendor')
    amc_start_date = fields.Date(string='AMC Start Date')
    amc_end_date = fields.Date(string='AMC End Date')
    amc_amount = fields.Monetary(string='AMC Amount (₹)', currency_field='currency_id')
    amc_contact = fields.Char(string='AMC Contact Number')
    last_service_date = fields.Date(string='Last Serviced On')
    next_service_date = fields.Date(string='Next Service Due', tracking=True)
    maintenance_ids = fields.One2many(
        'asset.maintenance', 'asset_id', string='Maintenance History',
    )
    maintenance_count = fields.Integer(
        string='Maintenance Records', compute='_compute_maintenance_count',
    )

    # ── Analytic Account (base_account_budget) ───────────────────────
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        related='category_id.analytic_account_id',
        store=True, readonly=True,
        help='Pulled from category. Maintenance & AMC costs tagged here for budget tracking.',
    )

    # ── Physical Audit ────────────────────────────────────────────────
    last_audit_date = fields.Date(string='Last Physically Verified On')
    last_audit_by = fields.Many2one('res.users', string='Last Verified By', readonly=True)
    audit_remarks = fields.Text(string='Audit Remarks')
    is_verified_this_year = fields.Boolean(
        string='Verified This Year', compute='_compute_audit_status', store=True,
    )

    # ── Transfer History ──────────────────────────────────────────────
    transfer_ids = fields.One2many(
        'asset.transfer', 'asset_id', string='Transfer History',
    )
    transfer_count = fields.Integer(
        string='Transfers', compute='_compute_transfer_count',
    )

    # ── Documents ────────────────────────────────────────────────────
    document_ids = fields.One2many(
        'asset.document', 'asset_id', string='Documents',
    )
    document_count = fields.Integer(
        string='Documents', compute='_compute_document_count',
    )

    # ── Disposal ─────────────────────────────────────────────────────
    disposal_date = fields.Date(string='Disposal Date', readonly=True)
    disposal_reason = fields.Selection([
        ('end_of_life', 'End of Useful Life'),
        ('beyond_repair', 'Beyond Repair'),
        ('obsolete', 'Obsolete / Outdated'),
        ('lost', 'Lost / Stolen'),
        ('sold', 'Sold / Auctioned'),
        ('donated', 'Donated'),
        ('condemned', 'Condemned by Committee'),
    ], string='Disposal Reason')
    disposal_amount = fields.Monetary(
        string='Disposal / Scrap Amount (₹)', currency_field='currency_id',
    )
    disposal_remarks = fields.Text(string='Disposal Remarks')
    disposal_approved_by = fields.Many2one('res.users', string='Disposal Approved By',
                                            readonly=True)

    # ── Notes ────────────────────────────────────────────────────────
    notes = fields.Text(string='Notes / Remarks')

    # ── Computed ─────────────────────────────────────────────────────

    @api.depends('purchase_date', 'warranty_period_months')
    def _compute_warranty_expiry(self):
        for rec in self:
            if rec.purchase_date and rec.warranty_period_months:
                rec.warranty_expiry_date = rec.purchase_date + relativedelta(
                    months=rec.warranty_period_months)
            else:
                rec.warranty_expiry_date = False

    @api.depends('warranty_expiry_date')
    def _compute_is_under_warranty(self):
        today = date.today()
        for rec in self:
            rec.is_under_warranty = bool(
                rec.warranty_expiry_date and rec.warranty_expiry_date >= today
            )

    @api.depends('purchase_cost', 'residual_value', 'useful_life_years',
                 'depreciation_method')
    def _compute_depreciation_rate(self):
        for rec in self:
            if rec.depreciation_method == 'straight_line' and rec.useful_life_years:
                depreciable = rec.purchase_cost - rec.residual_value
                if rec.purchase_cost > 0:
                    rec.depreciation_rate = (depreciable / rec.purchase_cost) / rec.useful_life_years * 100
                else:
                    rec.depreciation_rate = 0.0
            elif rec.depreciation_method == 'declining' and rec.useful_life_years:
                rec.depreciation_rate = (1 - (rec.residual_value / rec.purchase_cost) **
                                         (1 / rec.useful_life_years)) * 100 if rec.purchase_cost > 0 else 0.0
            else:
                rec.depreciation_rate = 0.0

    @api.depends('account_asset_id', 'account_asset_id.depreciation_line_ids.move_check',
                 'account_asset_id.depreciation_line_ids.amount')
    def _compute_accumulated_depreciation(self):
        for rec in self:
            if rec.account_asset_id:
                posted_lines = rec.account_asset_id.depreciation_line_ids.filtered(
                    lambda l: l.move_check)
                rec.accumulated_depreciation = sum(posted_lines.mapped('amount'))
            else:
                rec.accumulated_depreciation = 0.0

    @api.depends('purchase_cost', 'accumulated_depreciation')
    def _compute_book_value(self):
        for rec in self:
            rec.current_book_value = max(
                0.0, rec.purchase_cost - rec.accumulated_depreciation
            )

    @api.depends('account_asset_id', 'account_asset_id.value_residual',
                 'account_asset_id.state')
    def _compute_accounting_values(self):
        for rec in self:
            if rec.account_asset_id:
                rec.accounting_value_residual = rec.account_asset_id.value_residual
                rec.accounting_state = rec.account_asset_id.state
            else:
                rec.accounting_value_residual = 0.0
                rec.accounting_state = False

    @api.depends('last_audit_date')
    def _compute_audit_status(self):
        current_year = date.today().year
        for rec in self:
            rec.is_verified_this_year = bool(
                rec.last_audit_date and rec.last_audit_date.year == current_year
            )

    def _compute_maintenance_count(self):
        for rec in self:
            rec.maintenance_count = len(rec.maintenance_ids)

    def _compute_transfer_count(self):
        for rec in self:
            rec.transfer_count = len(rec.transfer_ids)

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = len(rec.document_ids)

    def _compute_accounting_entry_count(self):
        for rec in self:
            if rec.account_asset_id:
                rec.accounting_entry_count = rec.account_asset_id.entry_count
            else:
                rec.accounting_entry_count = 0

    def _compute_request_count(self):
        for rec in self:
            rec.request_count = len(rec.request_ids)

    def _compute_scan_log_count(self):
        for rec in self:
            rec.scan_log_count = len(rec.scan_log_ids)

    # ── Onchange ─────────────────────────────────────────────────────

    @api.onchange('faculty_id')
    def _onchange_faculty(self):
        if self.faculty_id:
            self.custodian_name = self.faculty_id.name
            self.custodian_contact = self.faculty_id.work_mobile or self.faculty_id.work_phone

    @api.onchange('category_id')
    def _onchange_category(self):
        if self.category_id:
            self.depreciation_method = self.category_id.depreciation_method
            self.useful_life_years = self.category_id.useful_life_years
            if self.category_id.residual_value_pct and self.purchase_cost:
                self.residual_value = self.purchase_cost * self.category_id.residual_value_pct / 100

    @api.onchange('purchase_cost', 'category_id')
    def _onchange_purchase_cost(self):
        if self.purchase_cost and self.category_id and self.category_id.residual_value_pct:
            self.residual_value = self.purchase_cost * self.category_id.residual_value_pct / 100

    # ── Constraints ───────────────────────────────────────────────────

    @api.constrains('serial_number')
    def _check_serial_unique(self):
        for rec in self:
            if rec.serial_number:
                existing = self.search([
                    ('serial_number', '=', rec.serial_number),
                    ('id', '!=', rec.id),
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        'Serial Number %s already exists for asset %s.'
                    ) % (rec.serial_number, existing.asset_code))

    # ── ORM ──────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('asset_code', '/') == '/':
            year = date.today().year
            seq = self.env['ir.sequence'].next_by_code('asset.asset') or '0001'
            vals['asset_code'] = f'AST/{year}/{seq}'
        if not vals.get('qr_scan_token'):
            vals['qr_scan_token'] = str(uuid4())
        rec = super().create(vals)
        # Set default location from category if not already set
        if not rec.location_id and rec.category_id and rec.category_id.default_location_id:
            rec.location_id = rec.category_id.default_location_id
        rec._generate_qr_code()
        return rec

    # ── Accounting Asset Sync ─────────────────────────────────────────

    def _get_accounting_method(self):
        """Map our depreciation_method to account.asset.asset method."""
        return 'linear' if self.depreciation_method in ('straight_line', 'none') else 'degressive'

    def action_create_accounting_asset(self):
        """
        Create or sync the linked account.asset.asset record in base_accounting_kit.
        Called from the Activate button flow so that:
          - A proper GL asset record is created.
          - The depreciation board is computed.
          - Future depreciation entries will auto-post to accounting.
        """
        for rec in self:
            acc_cat = rec.category_id.account_asset_category_id
            if not acc_cat:
                raise UserError(_(
                    'Please configure an Accounting Asset Type on the category "%s" '
                    'before activating this asset.'
                ) % rec.category_id.name)

            method_number = rec.useful_life_years * (12 // (acc_cat.method_period or 12))
            vals = {
                'name': rec.name,
                'code': rec.asset_code,
                'category_id': acc_cat.id,
                'value': rec.purchase_cost,
                'salvage_value': rec.residual_value,
                'date': rec.purchase_date or date.today(),
                'partner_id': rec.vendor_id.id if rec.vendor_id else False,
                'invoice_id': rec.account_invoice_id.id if rec.account_invoice_id else False,
                'method': rec._get_accounting_method(),
                'method_number': method_number or acc_cat.method_number,
                'method_period': acc_cat.method_period,
                'method_time': acc_cat.method_time,
                'prorata': acc_cat.prorata,
            }

            if rec.account_asset_id:
                # Sync if still in draft
                if rec.account_asset_id.state == 'draft':
                    rec.account_asset_id.write(vals)
                    rec.account_asset_id.compute_depreciation_board()
            else:
                accounting_asset = self.env['account.asset.asset'].sudo().create(vals)
                rec.account_asset_id = accounting_asset.id
                accounting_asset.compute_depreciation_board()

            rec.message_post(
                body=_('Accounting asset record created/synced: <a href="#">%s</a>') %
                     rec.account_asset_id.name
            )

    def action_validate_accounting_asset(self):
        """Confirm (validate) the linked accounting asset — transitions it to Running state."""
        for rec in self:
            if rec.account_asset_id and rec.account_asset_id.state == 'draft':
                rec.account_asset_id.validate()
                rec.message_post(body=_('Accounting asset confirmed and depreciation entries scheduled.'))

    def action_compute_depreciation_board(self):
        """Recompute the depreciation board on the linked accounting asset."""
        for rec in self:
            if rec.account_asset_id:
                rec.account_asset_id.compute_depreciation_board()
                rec.message_post(body=_('Depreciation board recomputed.'))
            else:
                raise UserError(_('No accounting asset linked. Please activate the asset first.'))

    # ── Actions ──────────────────────────────────────────────────────

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError(_('Only draft assets can be activated.'))
            if rec.category_id and rec.category_id.account_asset_category_id:
                try:
                    rec.action_create_accounting_asset()
                except Exception:
                    pass
            rec.write({'state': 'active'})
            rec._generate_qr_code()
            rec.message_post(body=_('Asset activated and put into service.'))
            rec._notify_hod_on_registration()

    def action_send_for_maintenance(self):
        self.ensure_one()
        self.write({'state': 'under_maintenance'})
        self.message_post(body=_('Asset sent for maintenance.'))

    def action_return_from_maintenance(self):
        self.ensure_one()
        self.write({
            'state': 'active',
            'last_service_date': date.today(),
        })
        self.message_post(body=_('Asset returned from maintenance and is active.'))

    def action_mark_audited(self):
        """Mark asset as physically verified during annual audit."""
        self.ensure_one()
        self.write({
            'state': 'audited',
            'last_audit_date': date.today(),
            'last_audit_by': self.env.user.id,
        })
        self.message_post(
            body=_('Asset physically verified by <b>%s</b> on %s.')
            % (self.env.user.name, date.today())
        )

    def action_dispose(self):
        self.ensure_one()
        if not self.disposal_reason:
            raise ValidationError(_('Please select a disposal reason before disposing.'))
        if self.account_asset_id and self.account_asset_id.state == 'open':
            try:
                self.account_asset_id.set_to_close()
            except Exception:
                pass
        self.write({
            'state': 'disposed',
            'disposal_date': date.today(),
            'disposal_approved_by': self.env.user.id,
            'status': 'not_available',
        })
        reason_label = dict(self._fields['disposal_reason'].selection).get(
            self.disposal_reason, self.disposal_reason
        )
        self.message_post(
            body=_('Asset disposed. Reason: %s. Scrap value: ₹%s.') % (
                reason_label, self.disposal_amount or 0,
            )
        )
        self._notify_lost_or_retired('disposed')

    def action_mark_lost(self):
        self.ensure_one()
        self.write({
            'state': 'lost',
            'disposal_date': date.today(),
            'disposal_reason': 'lost',
            'status': 'not_available',
        })
        if self.account_asset_id and self.account_asset_id.state == 'open':
            try:
                self.account_asset_id.set_to_close()
            except Exception:
                pass
        self.message_post(body=_('Asset marked as Lost / Stolen. FIR/complaint to be filed.'))
        self._notify_lost_or_retired('lost')

    def action_condemn(self):
        self.ensure_one()
        self.write({
            'state': 'condemned',
            'disposal_date': date.today(),
            'disposal_reason': 'condemned',
            'condition': 'condemned',
        })
        if self.account_asset_id and self.account_asset_id.state == 'open':
            self.account_asset_id.set_to_close()
        self.message_post(body=_('Asset condemned by committee.'))

    def action_open_accounting_asset(self):
        """Open the linked account.asset.asset form view."""
        self.ensure_one()
        if not self.account_asset_id:
            raise UserError(_('No accounting asset linked yet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Accounting Asset'),
            'res_model': 'account.asset.asset',
            'res_id': self.account_asset_id.id,
            'view_mode': 'form',
        }

    def action_open_accounting_entries(self):
        """Open journal entries for this asset."""
        self.ensure_one()
        if not self.account_asset_id:
            raise UserError(_('No accounting asset linked yet.'))
        return self.account_asset_id.open_entries()

    # ── QR Code Generation ─────────────────────────────────────────────

    def _generate_qr_code(self):
        """Generate QR PNG using the qrcode library and store as binary."""
        if not HAS_QRCODE:
            return
        for rec in self:
            if not rec.qr_scan_token:
                rec.write({'qr_scan_token': str(uuid4())})
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', 'http://localhost:8069')
            url = f'{base_url}/asset/scan/{rec.id}/{rec.qr_scan_token}'
            try:
                import qrcode as qrc
                img = qrc.make(url)
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                # Use sudo to bypass the immutability guard on qr_code (it's computed-write)
                rec.with_context(skip_qr_validation=True).write({
                    'qr_code': base64.b64encode(buffer.getvalue()).decode('utf-8'),
                })
            except Exception:
                pass

    def action_regenerate_qr(self):
        """Regenerate QR code (e.g., after domain change)."""
        for rec in self:
            rec.qr_scan_token = str(uuid4())
            rec._generate_qr_code()
        self.message_post(body=_('QR code regenerated with new token.'))

    # ── Purchase Order & Invoice Visibility ────────────────────────────

    def action_view_purchase_order(self):
        self.ensure_one()
        if not self.purchase_order_id:
            raise UserError(_('No purchase order linked to this asset.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
        }

    def action_view_invoices(self):
        """Open all vendor invoices related to this asset."""
        self.ensure_one()
        invoice_ids = []
        if self.account_invoice_id:
            invoice_ids.append(self.account_invoice_id.id)
        if self.purchase_order_id:
            invoice_ids += self.purchase_order_id.invoice_ids.ids
        invoice_ids = list(set(invoice_ids))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices / Bills'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoice_ids)],
        }

    def _compute_invoice_count(self):
        for rec in self:
            count = 0
            if rec.account_invoice_id:
                count += 1
            if rec.purchase_order_id:
                count += len(rec.purchase_order_id.invoice_ids)
            rec.invoice_count = count

    invoice_count = fields.Integer(
        string='Invoices', compute='_compute_invoice_count',
    )

    # ── Asset Requests ─────────────────────────────────────────────────

    def action_view_asset_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Asset Requests'),
            'res_model': 'asset.request',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    # ── QR Scan Logs ───────────────────────────────────────────────────

    def action_view_scan_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('QR Scan History'),
            'res_model': 'asset.qr.scan.log',
            'view_mode': 'list',
            'domain': [('asset_id', '=', self.id)],
        }

    def action_view_maintenance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance History'),
            'res_model': 'asset.maintenance',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    def action_view_transfers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer History'),
            'res_model': 'asset.transfer',
            'view_mode': 'list,form',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id},
        }

    # ── Status Actions ────────────────────────────────────────────

    def action_set_status_not_available(self):
        for rec in self:
            rec.write({'status': 'not_available'})
            rec._notify_hod_status_change('Not Available')

    def action_set_status_available(self):
        for rec in self:
            rec.write({'status': 'available'})
            rec._notify_hod_status_change('Available')

    def action_set_status_needs_purchase(self):
        for rec in self:
            rec.write({'status': 'needs_purchase'})
            rec._notify_hod_status_change('Needs Purchase')
            existing = self.env['asset.purchase.request'].search([
                ('asset_id', '=', rec.id),
                ('state', 'in', ('draft', 'principal_review', 'vendor_quotes',
                                 'acc_review', 'secretary_review', 'trust_execution')),
            ], limit=1)
            if not existing:
                self.env['asset.purchase.request'].create({
                    'asset_id': rec.id,
                    'item_description': 'Asset replacement/purchase required: %s' % rec.name,
                    'justification': 'Asset status marked as "Needs Purchase" via QR scan or dashboard.',
                    'requested_by': self.env.user.id,
                    'department_id': rec.department_id.id if rec.department_id else False,
                })
                rec.message_post(
                    body=_('Asset marked as "Needs Purchase". Draft purchase request auto-created.')
                )

    def action_open_issue_wizard(self):
        self.ensure_one()
        if self.asset_type != 'consumable':
            raise UserError(_('Stock issue is only available for consumable assets.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Issue Consumable Stock'),
            'res_model': 'asset.stock.issue.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    # ── HOD Notification Helpers ──────────────────────────────────

    def _notify_hod_on_registration(self):
        self.ensure_one()
        hod_user = self._get_hod_user()
        if not hod_user or not hod_user.partner_id:
            return
        subject = _('New Asset Registered in Your Department: %s (%s)') % (
            self.name, self.asset_code
        )
        body = _(
            '<p>Dear %s,</p>'
            '<p>A new asset has been registered under your department.</p>'
            '<p><b>Asset Name:</b> %s<br/>'
            '<b>Asset Code:</b> %s<br/>'
            '<b>Category:</b> %s<br/>'
            '<b>Location:</b> %s<br/>'
            '<b>Registered By:</b> %s</p>'
            '<p>Please verify the asset details and ensure the QR label is printed and affixed.</p>'
        ) % (
                   hod_user.name, self.name, self.asset_code,
                   self.category_id.name if self.category_id else '—',
                   ' '.join(filter(None, [self.building, self.floor, self.room])) or '—',
                   self.env.user.name,
               )
        try:
            self.message_notify(
                partner_ids=[hod_user.partner_id.id],
                subject=subject, body=body,
                message_type='email', subtype_xmlid='mail.mt_comment',
            )
        except Exception:
            pass

    def _notify_lost_or_retired(self, event_type):
        self.ensure_one()
        if event_type == 'lost':
            subject = _('🚨 ASSET REPORTED LOST: %s (%s)') % (self.name, self.asset_code)
            body_intro = _('has been reported as <b>LOST / STOLEN</b>')
        else:
            subject = _('Asset Disposed: %s (%s)') % (self.name, self.asset_code)
            body_intro = _('has been <b>disposed</b>')

        body = _(
            '<p>Asset <b>%s (%s)</b> %s.</p>'
            '<p><b>Category:</b> %s<br/>'
            '<b>Location (last known):</b> %s<br/>'
            '<b>Department:</b> %s<br/>'
            '<b>Marked by:</b> %s on %s</p>%s'
        ) % (
                   self.name, self.asset_code, body_intro,
                   self.category_id.name if self.category_id else '—',
                   ' '.join(filter(None, [self.building, self.floor, self.room])) or '—',
                   self.department_id.name if self.department_id else '—',
                   self.env.user.name, date.today(),
                   '<p><b>Please investigate and take appropriate action immediately.</b></p>'
                   if event_type == 'lost' else '',
               )

        notify_partners = []
        principal_group = self.env.ref(
            'university_management.group_asset_principal', raise_if_not_found=False
        )
        if principal_group:
            notify_partners += [u.partner_id.id for u in principal_group.users if u.partner_id]

        hod_user = self._get_hod_user()
        if hod_user and hod_user.partner_id:
            notify_partners.append(hod_user.partner_id.id)

        notify_partners = list(set(notify_partners))
        if notify_partners:
            try:
                self.message_notify(
                    partner_ids=notify_partners,
                    subject=subject, body=body,
                    message_type='email', subtype_xmlid='mail.mt_comment',
                )
            except Exception:
                pass

    def _notify_hod_status_change(self, new_status):
        self.ensure_one()
        hod_user = self._get_hod_user()
        if not hod_user or not hod_user.partner_id:
            return
        try:
            self.message_notify(
                partner_ids=[hod_user.partner_id.id],
                subject=_('Asset Status Updated: %s → %s') % (self.name, new_status),
                body=_(
                    '<p>Asset <b>%s (%s)</b> status has been updated to <b>%s</b> by %s.</p>'
                    '<p>Location: %s | Department: %s</p>'
                ) % (
                         self.name, self.asset_code, new_status, self.env.user.name,
                         ' '.join(filter(None, [self.building, self.floor, self.room])) or '—',
                         self.department_id.name if self.department_id else '—',
                     ),
                message_type='email', subtype_xmlid='mail.mt_comment',
            )
        except Exception:
            pass

    def _get_hod_user(self):
        self.ensure_one()
        if self.hod_id and self.hod_id.resource_id and self.hod_id.resource_id.user_id:
            return self.hod_id.resource_id.user_id
        if self.department_id and hasattr(self.department_id, 'hod_id') and self.department_id.hod_id:
            emp = self.department_id.hod_id
            if hasattr(emp, 'resource_id') and emp.resource_id and emp.resource_id.user_id:
                return emp.resource_id.user_id
        return None

    # ── Scheduled Actions ─────────────────────────────────────────────

    @api.model
    def _cron_check_maintenance_due(self):
        """Daily: flag assets whose next_service_date is today or overdue."""
        today = date.today()
        due = self.search([
            ('next_service_date', '<=', today),
            ('state', '=', 'active'),
            ('has_amc', '=', True),
        ])
        for asset in due:
            asset.message_post(
                body=_('Maintenance due! Next service date was <b>%s</b>. '
                        'Please raise a maintenance request.') % asset.next_service_date
            )
        return f'{len(due)} asset(s) flagged for maintenance.'

    @api.model
    def _cron_check_amc_expiry(self):
        """Daily: warn when AMC is expiring within 30 days."""
        today = date.today()
        expiring = self.search([
            ('amc_end_date', '<=', today + relativedelta(days=30)),
            ('amc_end_date', '>=', today),
            ('has_amc', '=', True),
            ('state', 'not in', ['disposed', 'condemned', 'lost']),
        ])
        for asset in expiring:
            days_left = (asset.amc_end_date - today).days
            asset.message_post(
                body=_('AMC expiring in <b>%s days</b> on %s. '
                        'Contact: %s to renew.') % (
                    days_left, asset.amc_end_date, asset.amc_contact or 'AMC vendor')
            )
        return f'{len(expiring)} AMC(s) expiring soon.'

    @api.model
    def _cron_check_warranty_expiry(self):
        """Daily: warn when warranty is expiring within 30 days."""
        today = date.today()
        expiring = self.search([
            ('warranty_expiry_date', '<=', today + relativedelta(days=30)),
            ('warranty_expiry_date', '>=', today),
            ('state', 'not in', ['disposed', 'condemned', 'lost']),
        ])
        for asset in expiring:
            days_left = (asset.warranty_expiry_date - today).days
            asset.message_post(
                body=_('Warranty expiring in <b>%s days</b> on %s.') % (
                    days_left, asset.warranty_expiry_date)
            )
        return f'{len(expiring)} warranty(ies) expiring soon.'

    @api.model
    def _cron_generate_depreciation_entries(self):
        """
        Monthly: trigger depreciation entry generation for all active assets
        that have a linked accounting asset in Running state.
        Delegates to account.asset.asset.compute_generated_entries (base_accounting_kit).
        """
        self.env['account.asset.asset'].sudo().compute_generated_entries(
            date.today(), asset_type='purchase'
        )

    @api.depends('stock_qty', 'min_stock_qty')
    def _compute_low_stock(self):
        for rec in self:
            rec.low_stock = (
                    rec.asset_type == 'consumable'
                    and rec.min_stock_qty > 0
                    and rec.stock_qty < rec.min_stock_qty
            )