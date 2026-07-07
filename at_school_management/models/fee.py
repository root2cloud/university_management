from odoo import models, fields, api

class FeePayment(models.Model):
    _name = 'school.fee.payment'
    _description = 'Fee Payment'
    _order = 'payment_date desc'

    admission_no = fields.Many2one('school.student', string="Student", required=True)
    academic_year = fields.Char(string="Academic Year", required=True)
    fee_type = fields.Many2one('school.fee.type', string="Fee Type", required=True)
    amount_paid = fields.Float(string="Amount Paid", required=True)
    payment_date = fields.Date(string="Payment Date", required=True, default=fields.Date.today)
    payment_mode = fields.Selection(
        [('cash', 'Cash'), ('online', 'Online'), ('cheque', 'Cheque')],
        string="Payment Mode", required=True
    )
    total_amount = fields.Float(string="Total Amount", compute="_compute_total_amount", store=True)
    balance_amount = fields.Float(string="Balance Amount", compute="_compute_balance_amount", store=True)
    note = fields.Text(string="Remarks / Description")

    @api.depends('fee_type')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.fee_type.amount if record.fee_type else 0.0

    @api.depends('total_amount', 'amount_paid')
    def _compute_balance_amount(self):
        for record in self:
            record.balance_amount = record.total_amount - record.amount_paid
