# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FeeDateRangeWizard(models.TransientModel):
    _name = 'fee.date.range.wizard'
    _description = 'Fee Payment Date Range Filter'

    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1),
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today,
    )

    # ── Summary fields – computed live as user picks dates ─────────────
    total_transactions = fields.Integer(
        string='Total Transactions',
        compute='_compute_summary',
    )
    total_collected = fields.Monetary(
        string='Total Collected',
        compute='_compute_summary',
        currency_field='currency_id',
    )
    total_pending = fields.Monetary(
        string='Total Pending',
        compute='_compute_summary',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(
                    _('From Date cannot be later than To Date.')
                )

    @api.depends('date_from', 'date_to')
    def _compute_summary(self):
        for rec in self:
            if not rec.date_from or not rec.date_to:
                rec.total_transactions = 0
                rec.total_collected = 0.0
                rec.total_pending = 0.0
                continue

            domain_range = [
                ('payment_date', '>=', rec.date_from),
                ('payment_date', '<=', rec.date_to),
            ]

            paid = self.env['fee.payment'].search(
                domain_range + [('state', 'in', ['paid', 'partial'])]
            )
            pending = self.env['fee.payment'].search(
                domain_range + [('state', 'in', ['draft', 'pending', 'verified', 'invoiced'])]
            )

            rec.total_transactions = len(paid) + len(pending)
            rec.total_collected = sum(paid.mapped('total_amount'))
            rec.total_pending = sum(pending.mapped('total_amount'))

    def action_view_transactions(self):
        """Open fee payments list view filtered to the selected date range."""
        self.ensure_one()

        if self.date_from > self.date_to:
            raise ValidationError(_('From Date cannot be later than To Date.'))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Fee Payments: %s → %s') % (
                self.date_from.strftime('%d %b %Y'),
                self.date_to.strftime('%d %b %Y'),
            ),
            'res_model': 'fee.payment',
            'view_mode': 'list,form,kanban,calendar,pivot,graph',
            'domain': [
                ('payment_date', '>=', self.date_from),
                ('payment_date', '<=', self.date_to),
            ],
            'context': {
                'date_range_from': str(self.date_from),
                'date_range_to': str(self.date_to),
            },
            'target': 'current',
        }