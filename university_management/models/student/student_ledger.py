# -*- coding: utf-8 -*-

from odoo import models, fields, api


class StudentLedger(models.Model):
    _inherit = 'student.student'

    student_ledger_line_ids = fields.One2many(
        comodel_name='account.move.line',
        compute='_compute_student_ledger_lines',
        string='Student Ledger',
    )

    student_ledger_balance = fields.Monetary(
        compute='_compute_student_ledger_balance',
        string='Total Balance Due',
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='partner_id.currency_id',
        string='Currency',
    )

    @api.depends('partner_id')
    def _compute_student_ledger_lines(self):
        """
        Fetch all account.move.line records linked to the student's partner.
        Covers invoices, payments, and all journal entries posted against
        the student's receivable account — same logic as the Payment Follow-up
        tab in res.partner (om_account_followup).
        """
        AccountMoveLine = self.env['account.move.line']
        for student in self:
            if student.partner_id:
                lines = AccountMoveLine.search([
                    ('partner_id', '=', student.partner_id.id),
                    ('account_id.account_type', '=', 'asset_receivable'),
                    ('parent_state', '!=', 'cancel'),
                ], order='date asc, id asc')
                student.student_ledger_line_ids = lines
            else:
                student.student_ledger_line_ids = AccountMoveLine

    @api.depends('student_ledger_line_ids', 'student_ledger_line_ids.amount_residual')
    def _compute_student_ledger_balance(self):
        for student in self:
            student.student_ledger_balance = sum(
                student.student_ledger_line_ids.mapped('amount_residual')
            )
