# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FeeStructure(models.Model):
    _name = 'fee.structure'
    _description = 'Fee Structure (Tuition, Lab, Hostel, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, program_id'

    name = fields.Char(string='Fee Structure Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Academic
    program_id = fields.Many2one('university.program', string='Program',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one(related='program_id.department_id',
                                    string='Department', store=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)

    # Semester — filtered by academic year
    semester_id = fields.Many2one(
        'university.semester',
        string='Semester',
        domain="[('academic_year_id', '=', academic_year_id)]",
        tracking=True
    )

    # Payment Term — computed from semester number
    # "Term 1" for Semester I, "Term 2" for Semester II, etc.
    payment_term = fields.Char(
        string='Payment Term',
        compute='_compute_payment_term',
        store=True,
    )

    # Fee Category (Link to sale.product)
    product_id = fields.Many2one('product.product', string='Fee Product',
                                 domain=[('type', '=', 'service'), ('sale_ok', '=', True)],
                                 help='Link to product for invoicing (should be a saleable service)')

    # Accounting Integration
    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        help="Default income account for fee components"
    )

    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        help="Default expense account for refunds"
    )

    late_fee_account_id = fields.Many2one(
        'account.account',
        string='Late Fee Account',
        help="Default late fee account"
    )

    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Odoo Payment Terms',
        help="Payment terms for invoice due date calculation"
    )

    journal_id = fields.Many2one('account.journal',
                                 string='Invoice Journal',
                                 domain="[('type', '=', 'sale')]",
                                 default=lambda self: self._default_journal())

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account')

    company_id = fields.Many2one('res.company',
                                 string='Company',
                                 default=lambda self: self.env.company)

    # Fee Components
    fee_line_ids = fields.One2many('fee.structure.line', 'fee_structure_id',
                                   string='Fee Components')

    # Total Amount
    total_amount = fields.Monetary(string='Total Fee', compute='_compute_total', store=True,
                                   currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                  default=lambda self: self.env.company.currency_id)

    # Due Date
    due_date = fields.Date(string='Fee Due Date', tracking=True)

    # Late Fee
    has_late_fee = fields.Boolean(string='Charge Late Fee', default=True)
    late_fee_amount = fields.Monetary(string='Late Fee Amount', currency_field='currency_id')
    late_fee_percentage = fields.Float(string='Late Fee %')
    grace_period_days = fields.Integer(string='Grace Period (Days)', default=0)

    # Discounts
    discount_ids = fields.One2many('fee.discount', 'fee_structure_id', string='Discounts')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Html(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code, academic_year_id)',
         'Fee Structure Code must be unique per academic year!'),
    ]

    # -------------------------------------------------------------------------
    # Defaults
    # -------------------------------------------------------------------------

    def _default_journal(self):
        return self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    # -------------------------------------------------------------------------
    # Computed Fields
    # -------------------------------------------------------------------------

    @api.depends('semester_id', 'semester_id.semester_number')
    def _compute_payment_term(self):
        """
        Computes the payment term based on semester number.
        Semester I (semester_number=1) → Term 1
        Semester II (semester_number=2) → Term 2
        etc.
        """
        for record in self:
            if record.semester_id and record.semester_id.semester_number:
                record.payment_term = f"Term {record.semester_id.semester_number}"
            else:
                record.payment_term = False

    @api.depends('fee_line_ids', 'fee_line_ids.amount')
    def _compute_total(self):
        for record in self:
            record.total_amount = sum(record.fee_line_ids.mapped('amount'))

    # -------------------------------------------------------------------------
    # Onchange
    # -------------------------------------------------------------------------

    @api.onchange('academic_year_id')
    def _onchange_academic_year_id(self):
        """Clear semester when academic year changes to avoid stale data."""
        self.semester_id = False

    # -------------------------------------------------------------------------
    # State Actions
    # -------------------------------------------------------------------------

    def action_activate(self):
        self.write({'state': 'active'})

    def action_archive(self):
        self.write({'state': 'archived'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_create_invoices(self):
        """Create invoices for all students in this program"""
        students = self.env['student.student'].search([
            ('program_id', '=', self.program_id.id),
            ('state', 'in', ['enrolled', 'active'])
        ])

        created_invoices = []
        for student in students:
            existing_invoice = self.env['account.move'].search([
                ('partner_id', '=', student.partner_id.id),
                ('invoice_origin', '=', self.code),
                ('state', '!=', 'cancel')
            ])

            if not existing_invoice:
                invoice = self._create_student_invoice(student)
                created_invoices.append(invoice.id)

        if created_invoices:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Created Invoices',
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'domain': [('id', 'in', created_invoices)],
                'target': 'current',
            }

    def _create_student_invoice(self, student):
        """Create invoice for a specific student"""
        invoice_lines = []
        for line in self.fee_line_ids:
            invoice_lines.append((0, 0, {
                'name': line.name,
                'quantity': 1,
                'price_unit': line.amount,
                'product_id': line.product_id.id if line.product_id else self.product_id.id,
                'account_id': (
                    line.income_account_id.id
                    if line.income_account_id
                    else self.income_account_id.id
                ),
                'analytic_distribution': (
                    {str(line.analytic_account_id.id): 100}
                    if line.analytic_account_id
                    else (
                        {str(self.analytic_account_id.id): 100}
                        if self.analytic_account_id
                        else False
                    )
                ),
            }))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': student.partner_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_date_due': self.due_date or fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'journal_id': (
                self.journal_id.id
                if self.journal_id
                else self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id
            ),
            'invoice_payment_term_id': (
                self.payment_term_id.id if self.payment_term_id else False
            ),
            'invoice_origin': self.code,
        }

        invoice = self.env['account.move'].create(invoice_vals)
        invoice.action_post()
        return invoice

    @api.onchange('company_id')
    def _onchange_company_id(self):
        domain = {}
        if self.company_id:
            income_domain = [
                ('account_type', 'in', ('income', 'income_other')),
                ('company_id', '=', self.company_id.id)
            ]
            expense_domain = [
                ('account_type', '=', 'expense'),
                ('company_id', '=', self.company_id.id)
            ]
            domain = {
                'income_account_id': income_domain,
                'expense_account_id': expense_domain,
                'late_fee_account_id': income_domain,
            }
        return {'domain': domain}


class FeeStructureLine(models.Model):
    _name = 'fee.structure.line'
    _description = 'Fee Structure Line'
    _order = 'sequence, name'

    sequence = fields.Integer(string='Sequence', default=10)
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure',
                                       required=True, ondelete='cascade')

    name = fields.Char(string='Fee Component', required=True)
    fee_type = fields.Selection([
        ('tuition', 'Tuition Fee'),
        ('lab', 'Lab Fee'),
        ('library', 'Library Fee'),
        ('exam', 'Examination Fee'),
        ('development', 'Development Fee'),
        ('sports', 'Sports Fee'),
        ('transport', 'Transport Fee'),
        ('hostel', 'Hostel Fee'),
        ('caution_deposit', 'Caution Deposit'),
        ('registration', 'Registration Fee'),
        ('other', 'Other'),
    ], string='Fee Type', required=True)

    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(related='fee_structure_id.currency_id', string='Currency')

    # Accounting Integration
    product_id = fields.Many2one('product.product',
                                 string='Product',
                                 domain=[('type', '=', 'service')],
                                 help="Product for this fee component")

    income_account_id = fields.Many2one(
        'account.account',
        string='Income Account',
        help="Income account for this specific fee component"
    )

    late_fee_account_id = fields.Many2one(
        'account.account',
        string='Late Fee Account',
        help="Late fee account for this fee component"
    )

    payment_term_id = fields.Many2one('account.payment.term',
                                      string='Payment Terms',
                                      help="Payment terms for this fee component")

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        help="Journal for this fee component"
    )

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account')

    company_id = fields.Many2one(related='fee_structure_id.company_id',
                                 string='Company',
                                 store=True)

    is_mandatory = fields.Boolean(string='Mandatory', default=True)
    is_refundable = fields.Boolean(string='Refundable', default=False)

    description = fields.Text(string='Description')

    @api.onchange('company_id')
    def _onchange_company_id(self):
        domain = {}
        if self.company_id:
            income_domain = [
                ('account_type', 'in', ('income', 'income_other')),
                ('company_id', '=', self.company_id.id)
            ]
            journal_domain = [
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id)
            ]
            domain = {
                'income_account_id': income_domain,
                'late_fee_account_id': income_domain,
                'journal_id': journal_domain,
            }
        return {'domain': domain}