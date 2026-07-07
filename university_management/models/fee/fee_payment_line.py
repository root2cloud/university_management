# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FeePaymentLine(models.Model):
    """
    Tracks per-component payment status for a fee.payment record.

    One line per fee.structure.line component.
    Created automatically when admin clicks 'Confirm & Send Invoice'.

    State machine per line:
        pending  → student has not paid anything for this component
        partial  → student paid some but not full component amount
        paid     → student paid full component amount
    """
    _name = 'fee.payment.line'
    _description = 'Fee Payment Component Line'
    _order = 'sequence, id'

    # ── Parent ────────────────────────────────────────────────────────
    fee_payment_id = fields.Many2one(
        'fee.payment',
        string='Fee Payment',
        required=True,
        ondelete='cascade',
        index=True,
    )

    # ── Component Reference ───────────────────────────────────────────
    fee_structure_line_id = fields.Many2one(
        'fee.structure.line',
        string='Fee Component',
        required=True,
        ondelete='restrict',
    )
    sequence = fields.Integer(
        related='fee_structure_line_id.sequence',
        store=True,
    )
    name = fields.Char(
        string='Component Name',
        related='fee_structure_line_id.name',
        store=True,
    )
    fee_type = fields.Selection(
        related='fee_structure_line_id.fee_type',
        string='Fee Type',
        store=True,
    )
    is_mandatory = fields.Boolean(
        related='fee_structure_line_id.is_mandatory',
        string='Mandatory',
        store=True,
    )

    # ── Amounts ───────────────────────────────────────────────────────
    component_amount = fields.Monetary(
        string='Component Amount',
        currency_field='currency_id',
        help='Original fee amount for this component',
    )
    amount_paid = fields.Monetary(
        string='Amount Paid',
        currency_field='currency_id',
        default=0.0,
    )
    outstanding_amount = fields.Monetary(
        string='Outstanding',
        compute='_compute_outstanding',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='fee_payment_id.currency_id',
        store=True,
    )

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string='Status', default='pending', tracking=False)

    # ── Computed ──────────────────────────────────────────────────────

    @api.depends('component_amount', 'amount_paid')
    def _compute_outstanding(self):
        for line in self:
            line.outstanding_amount = max(
                0.0, line.component_amount - line.amount_paid
            )

    # ── Constraints ───────────────────────────────────────────────────

    @api.constrains('amount_paid', 'component_amount')
    def _check_amount_paid(self):
        for line in self:
            if line.amount_paid < 0:
                raise ValidationError(_(
                    'Amount paid cannot be negative for component: %s'
                ) % line.name)
            if line.amount_paid > line.component_amount:
                raise ValidationError(_(
                    'Amount paid (₹%s) cannot exceed component amount (₹%s) for: %s'
                ) % (line.amount_paid, line.component_amount, line.name))

    # ── Business Methods ──────────────────────────────────────────────

    def _compute_state(self):
        """Recompute state based on amount_paid vs component_amount."""
        for line in self:
            if line.amount_paid <= 0:
                line.state = 'pending'
            elif line.amount_paid >= line.component_amount:
                line.state = 'paid'
            else:
                line.state = 'partial'

    def apply_payment(self, amount):
        """
        Apply a payment amount to this component line.
        Returns the amount actually applied (capped at outstanding).
        """
        self.ensure_one()
        applicable = min(amount, self.outstanding_amount)
        if applicable <= 0:
            return 0.0

        new_paid = self.amount_paid + applicable
        self.write({'amount_paid': new_paid})
        self._compute_state()
        self.write({'state': self.state})
        return applicable