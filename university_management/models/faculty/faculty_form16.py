# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FacultyForm16(models.Model):
    _name = 'faculty.form16'
    _description = 'Faculty Form 16 – TDS Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'assessment_year desc, faculty_id'

    name = fields.Char(
        string='Certificate Number', required=True, readonly=True,
        copy=False, default='/', tracking=True,
    )

    faculty_id = fields.Many2one(
        'faculty.faculty', string='Faculty', required=True,
        tracking=True, index=True,
    )
    employee_id = fields.Many2one(
        related='faculty_id.employee_id', string='Employee', store=True,
    )
    department_id = fields.Many2one(
        related='faculty_id.department_id', string='Department', store=True,
    )
    designation_id = fields.Many2one(
        related='faculty_id.designation_id', string='Designation', store=True,
    )

    # ── Employee details (auto-filled, editable) ──────────────────────────
    pan_number = fields.Char(
        string='PAN', compute='_compute_faculty_details', store=True, readonly=False,
    )
    date_of_joining = fields.Date(
        string='Date of Joining', compute='_compute_faculty_details', store=True, readonly=False,
    )
    residential_address = fields.Text(
        string='Residential Address', compute='_compute_faculty_details', store=True, readonly=False,
    )

    # ── Period ─────────────────────────────────────────────────────────────
    financial_year = fields.Char(
        string='Financial Year', required=True,
        help='e.g. 2024-25',
    )
    assessment_year = fields.Char(
        string='Assessment Year', required=True,
        help='e.g. 2025-26',
        compute='_compute_assessment_year', store=True, readonly=False,
    )
    period_from = fields.Date(string='Period From', required=True)
    period_to   = fields.Date(string='Period To',   required=True)

    # ── Employer details ──────────────────────────────────────────────────
    employer_name = fields.Char(
        string='Employer Name',
        compute='_compute_employer_defaults', store=True, readonly=False,
    )
    employer_tan = fields.Char(string='TAN of Employer')
    employer_pan = fields.Char(string='PAN of Employer')
    employer_address = fields.Text(
        string='Employer Address',
        compute='_compute_employer_defaults', store=True, readonly=False,
    )

    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
    )

    # ── PART A – TDS Summary ──────────────────────────────────────────────
    # These are aggregated from salary slips; can be overridden.
    gross_salary = fields.Monetary(
        string='Gross Salary', currency_field='currency_id',
        compute='_compute_from_salary_slips', store=True, readonly=False,
    )
    tds_deducted = fields.Monetary(
        string='Total TDS Deducted', currency_field='currency_id',
        compute='_compute_from_salary_slips', store=True, readonly=False,
    )
    tds_deposited = fields.Monetary(
        string='TDS Deposited (Govt)', currency_field='currency_id',
        compute='_compute_from_salary_slips', store=True, readonly=False,
    )

    # ── PART B – Salary Break-up ──────────────────────────────────────────
    basic_salary       = fields.Monetary(string='Basic Salary',         currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    hra                = fields.Monetary(string='HRA',                   currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    da                 = fields.Monetary(string='DA',                    currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    special_allowance  = fields.Monetary(string='Special Allowance',     currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    transport_allow    = fields.Monetary(string='Transport Allowance',   currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    medical_allow      = fields.Monetary(string='Medical Allowance',     currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    other_allowances   = fields.Monetary(string='Other Allowances',      currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)
    performance_bonus  = fields.Monetary(string='Performance Bonus',     currency_field='currency_id', compute='_compute_from_salary_slips', store=True, readonly=False)

    # ── Deductions u/s 16 ────────────────────────────────────────────────
    standard_deduction = fields.Monetary(
        string='Standard Deduction u/s 16(ia)',
        currency_field='currency_id',
        default=50000.0,
    )
    entertainment_allow_deduction = fields.Monetary(
        string='Entertainment Allowance u/s 16(ii)',
        currency_field='currency_id',
    )
    professional_tax_deduction = fields.Monetary(
        string='Professional Tax u/s 16(iii)',
        currency_field='currency_id',
        compute='_compute_from_salary_slips', store=True, readonly=False,
    )

    income_chargeable = fields.Monetary(
        string='Income Chargeable under "Salaries"',
        currency_field='currency_id',
        compute='_compute_income_chargeable', store=True,
    )

    # ── Chapter VI-A Deductions ───────────────────────────────────────────
    deduction_80c  = fields.Monetary(string='80C (PF/LIC/PPF etc.)',     currency_field='currency_id')
    deduction_80d  = fields.Monetary(string='80D (Medical Insurance)',   currency_field='currency_id')
    deduction_80e  = fields.Monetary(string='80E (Education Loan)',      currency_field='currency_id')
    deduction_80g  = fields.Monetary(string='80G (Donations)',           currency_field='currency_id')
    deduction_80tta = fields.Monetary(string='80TTA (Savings Interest)', currency_field='currency_id')
    other_deductions_vi = fields.Monetary(string='Other Chapter VI-A',   currency_field='currency_id')
    total_vi_a_deductions = fields.Monetary(
        string='Total Chapter VI-A Deductions',
        currency_field='currency_id',
        compute='_compute_vi_a', store=True,
    )

    # ── Tax computation ───────────────────────────────────────────────────
    net_taxable_income = fields.Monetary(
        string='Net Taxable Income',
        currency_field='currency_id',
        compute='_compute_tax', store=True,
    )
    tax_on_income = fields.Monetary(
        string='Tax on Total Income',
        currency_field='currency_id',
        compute='_compute_tax', store=True,
    )
    surcharge = fields.Monetary(string='Surcharge',   currency_field='currency_id')
    health_edu_cess = fields.Monetary(
        string='Health & Education Cess (4%)',
        currency_field='currency_id',
        compute='_compute_cess', store=True, readonly=False,
    )
    rebate_87a = fields.Monetary(
        string='Rebate u/s 87A',
        currency_field='currency_id',
        compute='_compute_tax', store=True, readonly=False,
    )
    total_tax_payable = fields.Monetary(
        string='Total Tax Payable',
        currency_field='currency_id',
        compute='_compute_total_tax', store=True,
    )
    relief_89 = fields.Monetary(string='Relief u/s 89', currency_field='currency_id')
    net_tax_payable = fields.Monetary(
        string='Net Tax Payable',
        currency_field='currency_id',
        compute='_compute_net_tax', store=True,
    )

    # ── Verification ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',    'Draft'),
        ('verified', 'Verified'),
        ('issued',   'Issued'),
    ], string='Status', default='draft', tracking=True)

    date_issued = fields.Date(string='Date of Issue')
    authorised_signatory = fields.Char(string='Authorised Signatory')
    designation_signatory = fields.Char(string='Designation of Signatory')
    place_issued = fields.Char(string='Place')
    notes = fields.Text(string='Remarks')

    _sql_constraints = [
        ('unique_form16', 'unique(faculty_id, financial_year)',
         'Form 16 already exists for this faculty in this financial year!'),
    ]

    # ── ORM ───────────────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('faculty.form16') or '/'
        return super().create(vals)

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('faculty_id')
    def _compute_faculty_details(self):
        for rec in self:
            if rec.faculty_id:
                rec.pan_number = rec.faculty_id.pan_number
                rec.date_of_joining = rec.faculty_id.date_of_joining
                rec.residential_address = (
                    rec.faculty_id.current_address or rec.faculty_id.permanent_address or ''
                )
            else:
                rec.pan_number = False
                rec.date_of_joining = False
                rec.residential_address = False

    @api.depends('financial_year')
    def _compute_assessment_year(self):
        for rec in self:
            if rec.financial_year:
                parts = rec.financial_year.split('-')
                if len(parts) == 2:
                    try:
                        y1 = int(parts[0])
                        y2_short = int(parts[1])
                        # AY is next year: FY 2024-25 → AY 2025-26
                        rec.assessment_year = '%d-%02d' % (y1 + 1, (y2_short + 1) % 100)
                    except Exception:
                        rec.assessment_year = ''
                else:
                    rec.assessment_year = ''
            else:
                rec.assessment_year = False

    @api.depends('faculty_id')
    def _compute_employer_defaults(self):
        for rec in self:
            company = self.env.company
            rec.employer_name = company.name
            parts = [
                company.street or '', company.street2 or '',
                company.city or '', company.state_id.name or '',
                company.zip or '', company.country_id.name or '',
            ]
            rec.employer_address = ', '.join(p for p in parts if p)

    @api.depends('faculty_id', 'financial_year', 'period_from', 'period_to')
    def _compute_from_salary_slips(self):
        """Aggregate paid salary slips for the financial year."""
        for rec in self:
            if not rec.faculty_id or not rec.period_from or not rec.period_to:
                rec.gross_salary = rec.basic_salary = rec.hra = rec.da = 0
                rec.special_allowance = rec.transport_allow = rec.medical_allow = 0
                rec.other_allowances = rec.performance_bonus = 0
                rec.tds_deducted = rec.tds_deposited = 0
                rec.professional_tax_deduction = 0
                continue

            slips = self.env['faculty.salary'].search([
                ('faculty_id', '=', rec.faculty_id.id),
                ('state', 'in', ('approved', 'paid')),
                ('payment_date', '>=', rec.period_from),
                ('payment_date', '<=', rec.period_to),
            ])

            rec.basic_salary      = sum(slips.mapped('basic_salary'))
            rec.hra               = sum(slips.mapped('hra'))
            rec.da                = sum(slips.mapped('da'))
            rec.special_allowance = sum(slips.mapped('special_allowance'))
            rec.transport_allow   = sum(slips.mapped('transport_allowance'))
            rec.medical_allow     = sum(slips.mapped('medical_allowance'))
            rec.other_allowances  = sum(slips.mapped('other_allowances'))
            rec.performance_bonus = sum(slips.mapped('performance_bonus'))
            rec.tds_deducted      = sum(slips.mapped('income_tax'))
            rec.tds_deposited     = rec.tds_deducted
            rec.professional_tax_deduction = sum(slips.mapped('professional_tax'))

            rec.gross_salary = (
                rec.basic_salary + rec.hra + rec.da + rec.special_allowance +
                rec.transport_allow + rec.medical_allow + rec.other_allowances +
                rec.performance_bonus
            )

    @api.depends(
        'gross_salary', 'standard_deduction',
        'entertainment_allow_deduction', 'professional_tax_deduction',
    )
    def _compute_income_chargeable(self):
        for rec in self:
            rec.income_chargeable = max(
                0,
                rec.gross_salary
                - rec.standard_deduction
                - rec.entertainment_allow_deduction
                - rec.professional_tax_deduction,
            )

    @api.depends(
        'deduction_80c', 'deduction_80d', 'deduction_80e',
        'deduction_80g', 'deduction_80tta', 'other_deductions_vi',
    )
    def _compute_vi_a(self):
        for rec in self:
            rec.total_vi_a_deductions = (
                rec.deduction_80c + rec.deduction_80d + rec.deduction_80e +
                rec.deduction_80g + rec.deduction_80tta + rec.other_deductions_vi
            )

    @api.depends('income_chargeable', 'total_vi_a_deductions')
    def _compute_tax(self):
        """Old tax regime slabs for FY 2024-25."""
        for rec in self:
            taxable = max(0, rec.income_chargeable - rec.total_vi_a_deductions)
            rec.net_taxable_income = taxable

            # Basic tax (old regime)
            tax = 0.0
            if taxable <= 250000:
                tax = 0.0
            elif taxable <= 500000:
                tax = (taxable - 250000) * 0.05
            elif taxable <= 1000000:
                tax = 12500 + (taxable - 500000) * 0.20
            else:
                tax = 112500 + (taxable - 1000000) * 0.30
            rec.tax_on_income = tax

            # Rebate 87A (taxable ≤ 5L → full rebate)
            rec.rebate_87a = tax if taxable <= 500000 else 0.0

    @api.depends('tax_on_income', 'rebate_87a', 'surcharge')
    def _compute_cess(self):
        for rec in self:
            base = max(0, rec.tax_on_income - rec.rebate_87a) + rec.surcharge
            rec.health_edu_cess = round(base * 0.04, 2)

    @api.depends('tax_on_income', 'rebate_87a', 'surcharge', 'health_edu_cess')
    def _compute_total_tax(self):
        for rec in self:
            rec.total_tax_payable = max(
                0,
                rec.tax_on_income - rec.rebate_87a + rec.surcharge + rec.health_edu_cess,
            )

    @api.depends('total_tax_payable', 'relief_89')
    def _compute_net_tax(self):
        for rec in self:
            rec.net_tax_payable = max(0, rec.total_tax_payable - rec.relief_89)

    # ── Actions ───────────────────────────────────────────────────────────
    def action_verify(self):
        self.write({'state': 'verified'})

    def action_issue(self):
        self.write({'state': 'issued', 'date_issued': fields.Date.today()})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_print_form16(self):
        return self.env.ref('university_management.action_report_faculty_form16').report_action(self)

    def action_compute_from_slips(self):
        """Manual re-trigger of salary aggregation."""
        self._compute_from_salary_slips()
        self._compute_income_chargeable()
        self._compute_vi_a()
        self._compute_tax()
        self._compute_cess()
        self._compute_total_tax()
        self._compute_net_tax()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Recomputed'),
                'message': _('Salary data re-aggregated from paid salary slips.'),
                'type': 'success',
            },
        }