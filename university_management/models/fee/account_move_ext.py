# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    fee_payment_id = fields.Many2one('fee.payment',
                                     string='Fee Payment',
                                     readonly=True)

    discount_application_id = fields.Many2one('fee.discount.application',
                                              string='Discount Application',
                                              readonly=True)

    scholarship_application_id = fields.Many2one('scholarship.application',
                                                 string='Scholarship Application',
                                                 readonly=True)

    fee_structure_line_id = fields.Many2one('fee.structure.line',
                                            string='Fee Structure Line',
                                            readonly=True)

    def reconcile(self):
        """
        Override reconcile() to instantly sync fee.payment state
        when a payment is reconciled with an invoice.

        Fires at the EXACT moment Odoo reconciles any payment with an invoice.
        Works for:
          - Portal payments (Demo, Razorpay, any provider)
          - Manual payments registered on the invoice
          - Partial payments — student pays ₹20,000 of ₹40,000
          - Final payments — student pays remaining balance
          - in_payment state (Demo provider marks invoice as in_payment
            before fully reconciling)
        """
        res = super().reconcile()

        invoices = self.mapped('move_id').filtered(
            lambda m: m.move_type == 'out_invoice'
        )

        for invoice in invoices:
            # KEY FIX: also trigger sync for 'in_payment' state —
            # Demo provider sets invoice to 'in_payment' immediately after
            # the student clicks "Pay" on the Demo simulate page.
            # Without 'in_payment' here, the fee.payment state never updates
            # until a bank statement is processed (which never happens in Demo).
            if invoice.payment_state in ('paid', 'partial', 'in_payment'):
                if invoice.fee_payment_ids:
                    invoice.fee_payment_ids._sync_state_from_invoice()

        return res


class AccountMove(models.Model):
    _inherit = 'account.move'

    fee_payment_ids = fields.One2many('fee.payment',
                                      'invoice_id',
                                      string='Fee Payments',
                                      readonly=True)

    discount_application_ids = fields.One2many('fee.discount.application',
                                               'move_id',
                                               string='Discount Applications',
                                               readonly=True)

    scholarship_application_ids = fields.One2many('scholarship.application',
                                                  'move_id',
                                                  string='Scholarship Applications',
                                                  readonly=True)

    fee_reminder_ids = fields.One2many('fee.reminder',
                                       'invoice_id',
                                       string='Fee Reminders',
                                       readonly=True)

    def _compute_payment_state(self):
        """
        Override to trigger fee.payment sync whenever invoice payment_state
        changes — catches cases where reconcile() hook doesn't fire
        (e.g. when payment is registered directly on the invoice backend form).
        """
        res = super()._compute_payment_state()

        for invoice in self.filtered(lambda m: m.move_type == 'out_invoice'):
            if invoice.payment_state in ('paid', 'partial', 'in_payment'):
                if invoice.fee_payment_ids:
                    invoice.fee_payment_ids._sync_state_from_invoice()

        return res