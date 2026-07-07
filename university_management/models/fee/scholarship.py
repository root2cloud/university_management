# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Scholarship(models.Model):
    _name = 'scholarship.scholarship'
    _description = 'Scholarship Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Scholarship Name', required=True, tracking=True)
    code = fields.Char(string='Scholarship Code', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Scholarship Type
    scholarship_type = fields.Selection([
        ('government', 'Government Scholarship'),
        ('institutional', 'Institutional Scholarship'),
        ('private', 'Private/Corporate Scholarship'),
        ('merit', 'Merit Based'),
        ('need', 'Need Based'),
        ('sports', 'Sports Scholarship'),
        ('minority', 'Minority Scholarship'),
        ('research', 'Research Scholarship'),
    ], string='Scholarship Type', required=True, tracking=True)

    # Sponsor (link to res.partner for companies/organizations)
    sponsor_id = fields.Many2one('res.partner', string='Sponsor/Organization',
                                 domain=[('is_company', '=', True)])
    sponsor_type = fields.Selection([
        ('government', 'Government'),
        ('corporate', 'Corporate'),
        ('ngo', 'NGO'),
        ('alumni', 'Alumni'),
        ('individual', 'Individual'),
    ], string='Sponsor Type')

    # Financial Details
    total_amount = fields.Monetary(string='Total Scholarship Amount',
                                   currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    amount_per_student = fields.Monetary(string='Amount per Student',
                                         currency_field='currency_id')

    # Accounting Integration
    income_account_id = fields.Many2one('account.account',
                                        string='Scholarship Account',
                                        domain="[('account_type', 'in', ['income', 'income_other'])]",
                                        help="Account to record scholarship income")

    expense_account_id = fields.Many2one('account.account',
                                         string='Expense Account',
                                         domain="[('account_type', 'in', ['expense', 'expense_depreciation'])]",
                                         help="Account to record scholarship expenses")

    journal_id = fields.Many2one('account.journal',
                                 string='Journal',
                                 domain="[('type', 'in', ['bank', 'cash', 'general']), ('company_id', '=', company_id)]")

    analytic_account_id = fields.Many2one('account.analytic.account',
                                          string='Analytic Account')

    company_id = fields.Many2one('res.company',
                                 string='Company',
                                 default=lambda self: self.env.company)

    # Coverage
    coverage_type = fields.Selection([
        ('full', 'Full Tuition Fee'),
        ('partial', 'Partial Coverage'),
        ('fixed', 'Fixed Amount'),
    ], string='Coverage Type', default='partial', required=True)

    coverage_percentage = fields.Float(string='Coverage %')

    # Number of Scholarships
    total_scholarships = fields.Integer(string='Total Scholarships Available', default=1)
    awarded_count = fields.Integer(string='Awarded', compute='_compute_counts')
    available_count = fields.Integer(string='Available', compute='_compute_counts')

    # Eligibility
    eligibility_criteria = fields.Html(string='Eligibility Criteria')
    min_percentage = fields.Float(string='Minimum Percentage/CGPA Required')
    max_family_income = fields.Monetary(string='Maximum Family Income',
                                        currency_field='currency_id')

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)

    # Applicable Programs
    program_ids = fields.Many2many('university.program', string='Applicable Programs')
    department_ids = fields.Many2many('university.department', string='Applicable Departments')

    # Application Period
    application_start_date = fields.Date(string='Application Start Date', required=True)
    application_end_date = fields.Date(string='Application End Date', required=True)

    # Selection Process
    selection_process = fields.Html(string='Selection Process')
    requires_interview = fields.Boolean(string='Requires Interview')
    requires_test = fields.Boolean(string='Requires Test')

    # Applications
    application_ids = fields.One2many('scholarship.application', 'scholarship_id',
                                      string='Applications')
    total_applications = fields.Integer(string='Total Applications',
                                        compute='_compute_counts')

    # Documents Required
    required_document_types = fields.Many2many('scholarship.document.type',
                                               string='Required Documents')

    # Payment Schedule
    payment_frequency = fields.Selection([
        ('one_time', 'One Time'),
        ('semester', 'Per Semester'),
        ('annual', 'Annual'),
        ('monthly', 'Monthly'),
    ], string='Payment Frequency', default='semester')

    # Payment Configuration
    payment_term_id = fields.Many2one('account.payment.term',
                                      string='Payment Terms')

    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('online', 'Online'),
    ], string='Default Payment Method', default='bank_transfer')

    # Terms & Conditions
    terms_conditions = fields.Html(string='Terms & Conditions')

    # Renewal
    is_renewable = fields.Boolean(string='Renewable', default=False)
    renewal_criteria = fields.Html(string='Renewal Criteria')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open for Applications'),
        ('closed', 'Applications Closed'),
        ('selection', 'Selection in Progress'),
        ('awarded', 'Scholarships Awarded'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Html(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Scholarship Code must be unique!'),
    ]

    @api.depends('application_ids', 'total_scholarships')
    def _compute_counts(self):
        for record in self:
            record.total_applications = len(record.application_ids)
            record.awarded_count = len(record.application_ids.filtered(
                lambda a: a.state == 'awarded'))
            record.available_count = record.total_scholarships - record.awarded_count

    def action_open_applications(self):
        self.write({'state': 'open'})

    def action_close_applications(self):
        self.write({'state': 'closed'})

    def action_start_selection(self):
        self.write({'state': 'selection'})

    def action_complete_awards(self):
        self.write({'state': 'awarded'})
        # Create accounting entries for awarded scholarships
        self._create_scholarship_payments()

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _create_scholarship_payments(self):
        """Create payment entries for awarded scholarships"""
        awarded_applications = self.application_ids.filtered(lambda a: a.state == 'awarded')

        for application in awarded_applications:
            if application.awarded_amount > 0:
                application._create_scholarship_payment()

    def action_create_batch_payments(self):
        """Create batch payments for all awarded scholarships"""
        awarded_applications = self.application_ids.filtered(lambda a: a.state == 'awarded')

        # Resolve journal: use the one configured on the scholarship, or fall back to
        # the first available bank/cash journal in the company.
        journal = self.journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', 'in', ['bank', 'cash']),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        if not journal:
            raise ValidationError(_(
                'No payment journal found. Please set a journal on the scholarship "%s" '
                'or configure a bank/cash journal for this company.'
            ) % self.name)

        payment_vals_list = []
        for application in awarded_applications:
            if application.awarded_amount > 0:
                # Fetch student's bank account for direct transfer
                bank_account_id = False
                if application.student_id.bank_account_id:
                    bank_account_id = application.student_id.bank_account_id.id
                else:
                    partner_bank = self.env['res.partner.bank'].search([
                        ('partner_id', '=', application.student_id.partner_id.id)
                    ], limit=1)
                    if partner_bank:
                        bank_account_id = partner_bank.id

                payment_vals = {
                    'payment_type': 'outbound',
                    'partner_type': 'supplier' if application.student_id.partner_id.supplier_rank > 0 else 'customer',
                    'partner_id': application.student_id.partner_id.id,
                    'amount': application.awarded_amount,
                    'currency_id': self.currency_id.id,
                    'date': fields.Date.today(),
                    'journal_id': journal.id,
                    'memo': f'Scholarship: {self.name} - {application.student_id.name}',
                }

                if bank_account_id:
                    payment_vals['partner_bank_id'] = bank_account_id

                payment_vals_list.append(payment_vals)

        if payment_vals_list:
            payments = self.env['account.payment'].create(payment_vals_list)
            for payment in payments:
                payment.action_post()

            return {
                'type': 'ir.actions.act_window',
                'name': 'Scholarship Payments',
                'res_model': 'account.payment',
                'view_mode': 'list,form',
                'domain': [('id', 'in', payments.ids)],
                'target': 'current',
            }


class ScholarshipApplication(models.Model):
    _name = 'scholarship.application'
    _description = 'Scholarship Application'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'application_date desc'

    name = fields.Char(string='Application Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    current_cgpa = fields.Float(related='student_id.cgpa', string='Current CGPA')

    # Scholarship
    scholarship_id = fields.Many2one('scholarship.scholarship', string='Scholarship',
                                     required=True, tracking=True, index=True)

    # Application Details
    application_date = fields.Date(string='Application Date', default=fields.Date.today(),
                                   required=True)

    # Reason & Justification
    reason = fields.Html(string='Reason for Application', required=True)
    achievements = fields.Html(string='Academic/Co-curricular Achievements')
    financial_need = fields.Html(string='Statement of Financial Need')

    # Family Details
    family_annual_income = fields.Monetary(string='Family Annual Income',
                                           currency_field='currency_id', required=True)
    family_size = fields.Integer(string='Family Size')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Academic Performance
    previous_year_percentage = fields.Float(string='Previous Year %')
    overall_percentage = fields.Float(string='Overall %')

    # Accounting Integration
    payment_id = fields.Many2one('account.payment',
                                 string='Payment Record',
                                 readonly=True)

    move_id = fields.Many2one('account.move',
                              string='Journal Entry',
                              readonly=True)

    invoice_id = fields.Many2one('account.move',
                                 string='Scholarship Invoice',
                                 domain="[('move_type', '=', 'in_invoice')]",
                                 readonly=True)

    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
    ], string='Payment Status', compute='_compute_payment_state', store=True)

    payment_date = fields.Date(string='Payment Date', tracking=True, index=True)

    # Documents
    document_ids = fields.One2many('scholarship.application.document', 'application_id',
                                   string='Documents')
    documents_verified = fields.Boolean(string='All Documents Verified',
                                        compute='_compute_documents_verified', store=True)

    # Selection Score
    selection_score = fields.Float(string='Selection Score')
    rank = fields.Integer(string='Rank')

    # Interview
    interview_scheduled = fields.Boolean(string='Interview Scheduled')
    interview_date = fields.Datetime(string='Interview Date')
    interview_remarks = fields.Text(string='Interview Remarks')

    # Recommendation
    recommended_by = fields.Many2one('faculty.faculty', string='Recommended By')
    recommendation_letter = fields.Html(string='Recommendation Letter')

    # Award Details
    awarded_amount = fields.Monetary(string='Awarded Amount', currency_field='currency_id')
    award_date = fields.Date(string='Award Date')
    award_certificate = fields.Binary(string='Award Certificate')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interview', 'Interview Scheduled'),
        ('approved', 'Approved'),
        ('awarded', 'Awarded'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Rejection
    rejection_reason = fields.Text(string='Rejection Reason')

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Application Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('scholarship.application') or '/'
        return super(ScholarshipApplication, self).create(vals)

    @api.depends('document_ids', 'document_ids.is_verified')
    def _compute_documents_verified(self):
        for record in self:
            if record.document_ids:
                record.documents_verified = all(doc.is_verified for doc in record.document_ids)
            else:
                record.documents_verified = False

    @api.depends('payment_id', 'payment_id.state', 'invoice_id', 'invoice_id.payment_state')
    def _compute_payment_state(self):
        # In Odoo 17+, account.payment no longer has payment_state.
        # Use payment.state (draft/posted/cancel) and map to our selection.
        # account.move (invoice) still has payment_state.
        for record in self:
            if record.payment_id:
                pay_state = record.payment_id.state
                if pay_state == 'posted':
                    record.payment_state = 'paid'
                elif pay_state == 'cancel':
                    record.payment_state = 'reversed'
                else:
                    record.payment_state = 'in_payment'
            elif record.invoice_id:
                record.payment_state = record.invoice_id.payment_state
            else:
                record.payment_state = 'not_paid'

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_review(self):
        self.write({'state': 'under_review'})

    def action_shortlist(self):
        self.write({'state': 'shortlisted'})

    def action_schedule_interview(self):
        self.write({'state': 'interview', 'interview_scheduled': True})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_award(self):
        self.write({
            'state': 'awarded',
            'award_date': fields.Date.today(),
            'awarded_amount': self.scholarship_id.amount_per_student
        })
        # Create scholarship payment
        self._create_scholarship_payment()

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _create_scholarship_payment(self):
        """Create payment entry for scholarship"""
        if not self.awarded_amount or self.awarded_amount <= 0:
            return

        # Resolve journal: use the one configured on the scholarship, or fall back to
        # the first available bank/cash journal in the company.
        journal = self.scholarship_id.journal_id
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', 'in', ['bank', 'cash']),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        if not journal:
            raise ValidationError(_(
                'No payment journal found. Please set a journal on the scholarship "%s" '
                'or configure a bank/cash journal for this company.'
            ) % self.scholarship_id.name)

        # Determine if student is supplier or customer
        partner_type = 'supplier' if self.student_id.partner_id.supplier_rank > 0 else 'customer'

        # Fetch student's bank account for direct transfer
        bank_account_id = False
        if self.student_id.bank_account_id:
            bank_account_id = self.student_id.bank_account_id.id
        else:
            partner_bank = self.env['res.partner.bank'].search([
                ('partner_id', '=', self.student_id.partner_id.id)
            ], limit=1)
            if partner_bank:
                bank_account_id = partner_bank.id

        payment_vals = {
            'payment_type': 'outbound',
            'partner_type': partner_type,
            'partner_id': self.student_id.partner_id.id,
            'amount': self.awarded_amount,
            'currency_id': self.currency_id.id,
            'date': self.award_date or fields.Date.today(),
            'journal_id': journal.id,
            'memo': f'Scholarship: {self.scholarship_id.name} - {self.name}',
        }

        if bank_account_id:
            payment_vals['partner_bank_id'] = bank_account_id

        payment = self.env['account.payment'].create(payment_vals)
        payment.action_post()

        self.payment_id = payment.id

        # Create journal entry for scholarship expense
        self._create_scholarship_expense_entry(payment)

    def _create_scholarship_expense_entry(self, payment):
        """Create expense entry for scholarship"""
        if not self.scholarship_id.expense_account_id:
            raise ValidationError(_('Please configure expense account in scholarship settings'))

        move_vals = {
            'move_type': 'entry',
            'date': fields.Date.today(),
            'journal_id': payment.journal_id.id,
            'line_ids': [],
            'ref': f'Scholarship Expense: {self.name}',
        }

        # Debit: Scholarship Expense Account
        debit_line_vals = {
            'account_id': self.scholarship_id.expense_account_id.id,
            'debit': self.awarded_amount,
            'credit': 0,
            'name': f'Scholarship: {self.scholarship_id.name} - {self.student_id.name}',
        }
        # Odoo 17+ uses analytic_distribution (JSON dict) instead of analytic_account_id
        if self.scholarship_id.analytic_account_id:
            debit_line_vals['analytic_distribution'] = {
                str(self.scholarship_id.analytic_account_id.id): 100
            }
        move_vals['line_ids'].append((0, 0, debit_line_vals))

        # Credit: Bank Account (from payment)
        bank_account = payment.destination_account_id
        move_vals['line_ids'].append((0, 0, {
            'account_id': bank_account.id,
            'debit': 0,
            'credit': self.awarded_amount,
            'name': f'Scholarship Payment: {self.student_id.name}',
        }))

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        self.move_id = move.id

    def action_view_payment(self):
        """View scholarship payment"""
        if self.payment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'view_mode': 'form',
                'res_id': self.payment_id.id,
                'target': 'current',
            }

    def action_create_scholarship_invoice(self):
        """Create vendor bill for scholarship payment"""
        if not self.scholarship_id.sponsor_id:
            raise ValidationError(_('No sponsor configured for this scholarship'))

        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': self.scholarship_id.sponsor_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': f'Scholarship: {self.scholarship_id.name} - {self.student_id.name}',
                'quantity': 1,
                'price_unit': self.awarded_amount,
                'account_id': self.scholarship_id.income_account_id.id if self.scholarship_id.income_account_id else False,
            })],
            'ref': f'Scholarship Invoice: {self.name}',
        }

        invoice = self.env['account.move'].create(invoice_vals)
        invoice.action_post()

        self.invoice_id = invoice.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }


class ScholarshipDocumentType(models.Model):
    _name = 'scholarship.document.type'
    _description = 'Scholarship Document Type'

    name = fields.Char(string='Document Type', required=True)
    description = fields.Text(string='Description')


class ScholarshipApplicationDocument(models.Model):
    _name = 'scholarship.application.document'
    _description = 'Scholarship Application Document'

    application_id = fields.Many2one('scholarship.application', string='Application',
                                     required=True, ondelete='cascade')
    document_type_id = fields.Many2one('scholarship.document.type', string='Document Type',
                                       required=True)
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=True, ondelete='cascade')

    is_verified = fields.Boolean(string='Verified')
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verification_date = fields.Date(string='Verification Date', readonly=True)