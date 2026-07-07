# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AssetCategory(models.Model):
    """
    Asset Category — classifies assets into logical groups.

    Inherits/links to account.asset.category from base_accounting_kit so that
    every asset category carries proper GL accounts for:
      - Asset Account       (balance-sheet debit on purchase)
      - Depreciation Account (accumulated depreciation contra account)
      - Depreciation Expense (P&L charge per period)
      - Journal             (asset journal)
      - Analytic Account    (for budget tracking via base_account_budget)

    Examples for Indian colleges:
      IT Equipment, Lab Equipment, Furniture, Sports Equipment,
      Vehicles, Electrical, Medical / Dispensary Equipment.
    """
    _name = 'asset.category'
    _description = 'Asset Category'
    _inherit = ['mail.thread']
    _order = 'name'
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(string='Category Name', required=True, tracking=True)
    code = fields.Char(string='Category Code', required=True)
    parent_id = fields.Many2one('asset.category', string='Parent Category',
                                ondelete='restrict')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('asset.category', 'parent_id', string='Sub Categories')
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    # ── Depreciation defaults ────────────────────────────────────────
    depreciation_method = fields.Selection([
        ('straight_line', 'Straight Line'),
        ('declining', 'Declining Balance'),
        ('none', 'No Depreciation'),
    ], string='Default Depreciation Method', default='straight_line')
    useful_life_years = fields.Integer(string='Default Useful Life (Years)', default=5)
    residual_value_pct = fields.Float(string='Default Residual Value %', default=10.0)

    # ── Maintenance ──────────────────────────────────────────────────
    requires_amc = fields.Boolean(string='Requires AMC', default=False,
                                  help='Annual Maintenance Contract required for this category.')
    maintenance_frequency = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('half_yearly', 'Half Yearly'),
        ('annually', 'Annually'),
    ], string='Maintenance Frequency')

    # ── Accounting (base_accounting_kit) ─────────────────────────────
    account_asset_category_id = fields.Many2one(
        'account.asset.category',
        string='Accounting Asset Type',
        help='Link to base_accounting_kit asset category. '
             'Provides GL accounts and journal for depreciation posting.',
        domain=[('type', '=', 'purchase')],
    )
    # Convenience related fields from the accounting category
    account_asset_id = fields.Many2one(
        'account.account',
        related='account_asset_category_id.account_asset_id',
        string='Asset Account',
        store=True, readonly=True,
        help='GL account where the asset value is recorded (balance sheet).',
    )
    account_depreciation_id = fields.Many2one(
        'account.account',
        related='account_asset_category_id.account_depreciation_id',
        string='Accumulated Depreciation Account',
        store=True, readonly=True,
    )
    account_depreciation_expense_id = fields.Many2one(
        'account.account',
        related='account_asset_category_id.account_depreciation_expense_id',
        string='Depreciation Expense Account',
        store=True, readonly=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        related='account_asset_category_id.journal_id',
        string='Asset Journal',
        store=True, readonly=True,
    )

    # ── Analytic Account (base_account_budget) ───────────────────────
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Analytic account for budget tracking. '
             'Maintenance and AMC costs posted here feed budget reports.',
    )
    budgetary_position_id = fields.Many2one(
        'account.budget.post',
        string='Budgetary Position',
        help='Budget position to track asset-related expenditure '
             '(purchase, maintenance, AMC) for this category.',
    )

    # ── Inventory / Purchase Integration ─────────────────────────────
    product_id = fields.Many2one(
        'product.product', string='Purchase Product',
        domain=[('purchase_ok', '=', True)],
        help='Product used when raising a purchase.order for this category. '
             'Required for IT team to create purchase order from helpdesk ticket.',
    )
    default_location_id = fields.Many2one(
        'stock.location', string='Default Storage Location',
        domain=[('usage', '=', 'internal')],
        help='Default warehouse/inventory location for new assets in this category. '
             'Auto-fills location_id when an asset is created or registered from a PO.',
    )

    # ── Counts ───────────────────────────────────────────────────────
    asset_count = fields.Integer(string='Total Assets', compute='_compute_asset_count')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category Code must be unique!'),
    ]

    @api.depends('name', 'parent_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.parent_id:
                rec.display_name = f'{rec.parent_id.name} / {rec.name}'
            else:
                rec.display_name = rec.name

    def _compute_asset_count(self):
        for rec in self:
            rec.asset_count = self.env['asset.asset'].search_count([
                ('category_id', '=', rec.id)
            ])

    def action_view_assets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Assets — %s' % self.name,
            'res_model': 'asset.asset',
            'view_mode': 'list,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }