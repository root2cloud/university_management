# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FacultySalary(models.Model):
    _name = 'faculty.salary'
    _description = 'Faculty Salary Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc'

    name = fields.Char(string='Salary Slip Number', required=True, readonly=True,
                       copy=False, default='/')

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True, index=True)
    employee_id = fields.Many2one(related='faculty_id.employee_id', string='Employee', store=True)
    department_id = fields.Many2one(related='faculty_id.department_id', string='Department', store=True)
    designation_id = fields.Many2one(related='faculty_id.designation_id', string='Designation', store=True)

    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', required=True)
    year = fields.Integer(string='Year', required=True, default=lambda self: fields.Date.today().year)
    payment_date = fields.Date(string='Payment Date', tracking=True)

    # Earnings
    basic_salary = fields.Monetary(string='Basic Salary', required=True, currency_field='currency_id')
    hra = fields.Monetary(string='HRA', currency_field='currency_id')
    da = fields.Monetary(string='DA (Dearness Allowance)', currency_field='currency_id')
    special_allowance = fields.Monetary(string='Special Allowance', currency_field='currency_id')
    transport_allowance = fields.Monetary(string='Transport Allowance', currency_field='currency_id')
    medical_allowance = fields.Monetary(string='Medical Allowance', currency_field='currency_id')
    other_allowances = fields.Monetary(string='Other Allowances', currency_field='currency_id')
    performance_bonus = fields.Monetary(string='Performance Bonus', currency_field='currency_id')
    overtime_pay = fields.Monetary(string='Overtime Pay', currency_field='currency_id')
    total_earnings = fields.Monetary(string='Total Earnings', compute='_compute_totals',
                                     store=True, currency_field='currency_id')

    # Deductions
    pf = fields.Monetary(string='PF (Provident Fund)', currency_field='currency_id')
    esi = fields.Monetary(string='ESI', currency_field='currency_id')
    professional_tax = fields.Monetary(string='Professional Tax', currency_field='currency_id')
    income_tax = fields.Monetary(string='Income Tax (TDS)', currency_field='currency_id')
    advance_deduction = fields.Monetary(string='Advance Deduction', currency_field='currency_id')
    loan_deduction = fields.Monetary(string='Loan Deduction', currency_field='currency_id')
    other_deductions = fields.Monetary(string='Other Deductions', currency_field='currency_id')
    leave_without_pay_days = fields.Float(string='LWP Days')
    leave_deduction = fields.Monetary(string='Leave Deduction', compute='_compute_leave_deduction',
                                      store=True, currency_field='currency_id')
    total_deductions = fields.Monetary(string='Total Deductions', compute='_compute_totals',
                                       store=True, currency_field='currency_id')
    net_salary = fields.Monetary(string='Net Salary', compute='_compute_totals',
                                 store=True, currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
    ], string='Payment Method', default='bank_transfer')
    payment_reference = fields.Char(string='Payment Reference')

    bank_account_number = fields.Char(related='faculty_id.bank_account_number', string='Bank Account')
    bank_name = fields.Char(related='faculty_id.bank_name', string='Bank Name')

    state = fields.Selection([
        ('draft',    'Draft'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('paid',     'Paid'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    # ── Link to Odoo HR Payslip ───────────────────────────────────────────
    hr_payslip_id = fields.Many2one(
        'hr.payslip', string='HR Payslip',
        copy=False, ondelete='set null',
        help='Linked Odoo payslip created when faculty salary is approved.',
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Salary Slip Number must be unique!'),
        ('unique_salary', 'unique(faculty_id, month, year)',
         'Salary already generated for this faculty in this month!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('faculty.salary') or '/'
        return super().create(vals)

    @api.depends('basic_salary', 'hra', 'da', 'special_allowance', 'transport_allowance',
                 'medical_allowance', 'other_allowances', 'performance_bonus', 'overtime_pay',
                 'pf', 'esi', 'professional_tax', 'income_tax', 'advance_deduction',
                 'loan_deduction', 'other_deductions', 'leave_deduction')
    def _compute_totals(self):
        for record in self:
            record.total_earnings = (
                record.basic_salary + record.hra + record.da +
                record.special_allowance + record.transport_allowance +
                record.medical_allowance + record.other_allowances +
                record.performance_bonus + record.overtime_pay
            )
            record.total_deductions = (
                record.pf + record.esi + record.professional_tax +
                record.income_tax + record.advance_deduction +
                record.loan_deduction + record.other_deductions +
                record.leave_deduction
            )
            record.net_salary = record.total_earnings - record.total_deductions

    @api.depends('basic_salary', 'leave_without_pay_days')
    def _compute_leave_deduction(self):
        for record in self:
            if record.leave_without_pay_days > 0:
                record.leave_deduction = (record.basic_salary / 30) * record.leave_without_pay_days
            else:
                record.leave_deduction = 0.0

    def action_fetch_attendance(self):
        """Auto-fill LWP days and overtime from faculty attendance/leave records."""
        for rec in self:
            if not rec.faculty_id or not rec.month or not rec.year:
                continue
            month = int(rec.month)
            year = rec.year
            from datetime import date
            import calendar
            first_day = date(year, month, 1)
            last_day = date(year, month, calendar.monthrange(year, month)[1])

            # Count unpaid leave days in this month
            lwp_leaves = self.env['faculty.leave'].search([
                ('faculty_id', '=', rec.faculty_id.id),
                ('leave_type', '=', 'unpaid'),
                ('state', '=', 'approved'),
                ('date_from', '<=', last_day),
                ('date_to', '>=', first_day),
            ])
            lwp_days = 0.0
            for leave in lwp_leaves:
                # Clip to month boundaries
                from_date = max(leave.date_from, first_day)
                to_date = min(leave.date_to, last_day)
                lwp_days += (to_date - from_date).days + 1
            if leave.half_day if lwp_leaves else False:
                lwp_days = lwp_days / 2

            # Count approved overtime hours in this month
            overtime_records = self.env['faculty.attendance'].search([
                ('faculty_id', '=', rec.faculty_id.id),
                ('is_overtime', '=', True),
                ('overtime_approved', '=', True),
                ('date', '>=', first_day),
                ('date', '<=', last_day),
            ])
            total_overtime_hours = sum(overtime_records.mapped('overtime_hours'))

            # Per-hour rate for overtime (basic / 26 working days / 8 hours)
            hourly_rate = rec.basic_salary / (26 * 8) if rec.basic_salary else 0
            overtime_amount = hourly_rate * total_overtime_hours

            rec.write({
                'leave_without_pay_days': lwp_days,
                'overtime_pay': overtime_amount,
            })

    def action_verify(self):
        self.write({'state': 'verified'})

    def action_approve(self):
        self.write({'state': 'approved'})
        if 'hr.payslip' in self.env:
            self._sync_hr_payslip()

    def action_mark_paid(self):
        self.write({'state': 'paid', 'payment_date': fields.Date.today()})
        if 'hr.payslip' not in self.env:
            return
        for rec in self:
            if rec.hr_payslip_id and rec.hr_payslip_id.state in ('draft', 'verify'):
                try:
                    rec.hr_payslip_id.action_payslip_done()
                except Exception:
                    pass

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        if 'hr.payslip' not in self.env:
            return
        for rec in self:
            if rec.hr_payslip_id and rec.hr_payslip_id.state not in ('done', 'cancel'):
                try:
                    rec.hr_payslip_id.action_payslip_cancel()
                except Exception:
                    pass
                rec.hr_payslip_id = False

    def action_print_salary_slip(self):
        return self.env.ref('university_management.action_report_salary_slip').report_action(self)

    def _sync_hr_payslip(self):
        """Create or update hr.payslip when faculty salary is approved."""
        if 'hr.payslip' not in self.env:
            return  # hr_payroll module not installed yet
        HrPayslip = self.env['hr.payslip'].sudo()
        # Get faculty payroll structure
        structure = self.env.ref(
            'university_management.faculty_payroll_structure', raise_if_not_found=False)

        for rec in self:
            if not rec.employee_id:
                continue
            month = int(rec.month)
            year = rec.year
            from datetime import date
            import calendar
            date_from = date(year, month, 1)
            date_to = date(year, month, calendar.monthrange(year, month)[1])

            vals = {
                'employee_id': rec.employee_id.id,
                'date_from':   date_from,
                'date_to':     date_to,
                'name':        'Salary Slip - %s - %s/%s' % (rec.faculty_id.name, rec.month, rec.year),
            }
            if structure:
                vals['struct_id'] = structure.id

            if rec.hr_payslip_id:
                if rec.hr_payslip_id.state == 'draft':
                    rec.hr_payslip_id.write(vals)
            else:
                payslip = HrPayslip.create(vals)
                rec.hr_payslip_id = payslip.id

            # Push input lines with our salary components
            if rec.hr_payslip_id:
                rec._push_payslip_inputs()

    def _push_payslip_inputs(self):
        """Push salary component values as payslip input lines."""
        if not self.hr_payslip_id:
            return
        # Map faculty salary fields to payslip input type codes
        input_map = {
            'BASIC':     self.basic_salary,
            'HRA':       self.hra,
            'DA':        self.da,
            'SP_ALLOW':  self.special_allowance,
            'TRANS':     self.transport_allowance,
            'MED':       self.medical_allowance,
            'OTHER_ALL': self.other_allowances,
            'BONUS':     self.performance_bonus,
            'OT_PAY':    self.overtime_pay,
            'PF':        self.pf,
            'ESI':       self.esi,
            'PT':        self.professional_tax,
            'TDS':       self.income_tax,
            'LWP_DED':   self.leave_deduction,
        }
        payslip = self.hr_payslip_id
        # Clear existing input lines
        payslip.input_line_ids.sudo().unlink()
        lines = []
        for code, amount in input_map.items():
            if amount:
                input_type = self.env['hr.payslip.input.type'].sudo().search(
                    [('code', '=', code)], limit=1)
                if input_type:
                    lines.append((0, 0, {
                        'input_type_id': input_type.id,
                        'amount': amount,
                    }))
        if lines:
            payslip.sudo().write({'input_line_ids': lines})