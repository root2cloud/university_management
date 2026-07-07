from odoo import models , fields, api

class System(models.Model):
    _name = 'system.system'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    user= fields.Many2one('res.users', string="Users")
    name = fields.Char(string = 'Name')
    assets = fields.One2many('it.assets', 'system_id', string= 'Assets')
    update_date = fields.Date(string  = 'Update Date', default=fields.Date.today)
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('unassigned', 'Unassigned'),
    ], string='Status', default='new', compute="_compute_state", store=True)
    
    @api.depends('user')
    def _compute_state(self):
        for record in self:
            if record.user:
                record.state = 'assigned'
            else:
                record.state = 'unassigned'

    @api.model
    def create(self, vals):
        record = super(System, self).create(vals)
        if vals.get('user'):
            record._update_asset_users()
        return record

    def write(self, vals):
        # Track old assets before change
        old_assets_by_record = {rec.id: rec.assets.ids for rec in self}
        old_users_by_record = {rec.id: rec.user.id for rec in self}

        res = super(System, self).write(vals)

        for rec in self:
            new_assets = rec.assets.ids
            old_assets = old_assets_by_record.get(rec.id, [])
            old_user = old_users_by_record.get(rec.id)
            new_user = rec.user.id

            removed_assets = list(set(old_assets) - set(new_assets))
            added_assets = list(set(new_assets) - set(old_assets))

            # If user is removed from the system
            if 'user' in vals and not new_user and old_user:
                # Clear user from all linked assets
                for asset in rec.assets:
                    if asset.item_user.id == old_user:
                        asset.item_user = None

            # Handle removed assets
            if removed_assets and new_user:
                for asset in self.env['it.assets'].browse(removed_assets):
                    if asset.item_user.id == new_user:
                        asset.item_user = None  # Remove the user from the asset

            # Handle added assets
            if added_assets and new_user:
                for asset in self.env['it.assets'].browse(added_assets):
                    asset.item_user = new_user  # Assign user to the asset

            # Update all assets with new user if user is changed
            if 'user' in vals and new_user:
                for asset in rec.assets:
                    asset.item_user = new_user

        return res

    def _update_asset_users(self):
        for rec in self:
            rec.assets.write({'item_user': rec.user.id})

    
