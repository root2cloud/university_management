# -*- coding: utf-8 -*-
"""
asset_issue_wizard.py — Consumable Stock Issue Wizard
=====================================================
Formal wizard to decrement consumable stock qty.
Creates an audit trail (asset.stock.issue) so every consumption
is logged — no direct manual editing of stock_qty allowed.

Triggers low-stock check immediately after issue.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class AssetStockIssue(models.Model):
    """
    Consumable Stock Issue Log — immutable record of each issue.
    One record per issue event. Stock qty decremented via this model.
    """
    _name = 'asset.stock.issue'
    _description = 'Consumable Stock Issue'
    _inherit = ['mail.thread']
    _order = 'issue_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Issue Reference', required=True, readonly=True,
        copy=False, default='/',
    )
    asset_id = fields.Many2one(
        'asset.asset', string='Consumable Asset', required=True,
        domain="[('asset_type', '=', 'consumable')]",
        tracking=True,
    )
    qty_issued = fields.Float(
        string='Quantity Issued', required=True,
        help='How many units were consumed/issued.',
    )
    qty_before = fields.Float(string='Stock Before Issue', readonly=True)
    qty_after = fields.Float(string='Stock After Issue', readonly=True)
    issued_to = fields.Many2one(
        'res.users', string='Issued To', required=True,
    )
    issued_by = fields.Many2one(
        'res.users', string='Issued By',
        default=lambda self: self.env.user, required=True,
    )
    issue_date = fields.Datetime(
        string='Issue Date', default=fields.Datetime.now, readonly=True,
    )
    purpose = fields.Text(string='Purpose / Notes', required=True)
    department_id = fields.Many2one(
        'university.department', string='Issued To Department',
    )
    low_stock_triggered = fields.Boolean(
        string='Low Stock Alert Triggered', readonly=True,
    )

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('asset.stock.issue') or '/'
        return super().create(vals)


class AssetStockIssueWizard(models.TransientModel):
    """
    Wizard to issue/consume consumable stock units.
    Called from the consumable asset form or from the faculty dashboard.
    """
    _name = 'asset.stock.issue.wizard'
    _description = 'Issue Consumable Stock'

    asset_id = fields.Many2one(
        'asset.asset', string='Consumable Asset', required=True,
        domain="[('asset_type', '=', 'consumable'), ('state', 'not in', ['disposed', 'condemned'])]",
    )
    current_stock = fields.Float(
        string='Current Stock', related='asset_id.stock_qty', readonly=True,
    )
    min_stock = fields.Float(
        string='Min Stock Threshold', related='asset_id.min_stock_qty', readonly=True,
    )
    qty_issued = fields.Float(
        string='Quantity to Issue', required=True, default=1.0,
    )
    issued_to = fields.Many2one(
        'res.users', string='Issue To (Person)',
        default=lambda self: self.env.user, required=True,
    )
    department_id = fields.Many2one(
        'university.department', string='Issuing Department',
    )
    purpose = fields.Text(
        string='Purpose / Notes', required=True,
        help='What are these consumables being used for?',
    )

    @api.constrains('qty_issued', 'asset_id')
    def _check_qty(self):
        for rec in self:
            if rec.qty_issued <= 0:
                raise ValidationError(_('Quantity to issue must be greater than zero.'))
            if rec.asset_id and rec.qty_issued > rec.asset_id.stock_qty:
                raise ValidationError(_(
                    'Cannot issue %s units. Current stock is only %s units.'
                ) % (rec.qty_issued, rec.asset_id.stock_qty))

    def action_confirm_issue(self):
        """Confirm the stock issue — decrement qty, log record, check low stock."""
        self.ensure_one()
        asset = self.asset_id
        qty_before = asset.stock_qty
        qty_after = qty_before - self.qty_issued

        # Create immutable issue log
        issue = self.env['asset.stock.issue'].create({
            'asset_id': asset.id,
            'qty_issued': self.qty_issued,
            'qty_before': qty_before,
            'qty_after': qty_after,
            'issued_to': self.issued_to.id,
            'issued_by': self.env.user.id,
            'purpose': self.purpose,
            'department_id': self.department_id.id if self.department_id else False,
        })

        # Decrement stock
        asset.write({'stock_qty': qty_after})

        # Check low stock immediately
        low_stock_triggered = False
        if qty_after < asset.min_stock_qty:
            low_stock_triggered = True
            issue.write({'low_stock_triggered': True})
            # Notify faculty and HOD
            asset._send_low_stock_alert()

        asset.message_post(
            body=_(
                'Stock issue logged: <b>%s units</b> issued to <b>%s</b>.<br/>'
                'Stock: <b>%s → %s</b> units.<br/>'
                'Purpose: %s%s'
            ) % (
                self.qty_issued, self.issued_to.name,
                qty_before, qty_after, self.purpose,
                '<br/><b>⚠️ LOW STOCK ALERT triggered!</b>' if low_stock_triggered else '',
            )
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'asset.stock.issue',
            'res_id': issue.id,
            'view_mode': 'form',
            'target': 'current',
        }