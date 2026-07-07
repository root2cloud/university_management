from odoo import models, fields, api
from odoo.exceptions import ValidationError

class Assets(models.Model):

    _name = "it.assets"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    item_code = fields.Char(string = "Asset Code")
    name = fields.Char(string = "Asset Name")
    item_user = fields.Many2one('res.users', string = "Asset User")
    all_components = fields.Many2many(
        'it.components',
        'component_asset_rel',   
        'asset_id',              
        'component_id',          
        string="All Components"
    )
    asset_repaired = fields.Boolean(string = 'Asset Repaired') 
    asset_type = fields.Many2one("asset.type", string = "Asset Type")
    system_id = fields.Many2one('system.system', string="System")
    image = fields.Binary()

    @api.model
    def create(self, vals):

        if vals.get('system_id'):
            system = self.env['system.system'].browse(vals['system_id'])
            if system.user:
                vals['item_user'] = system.user.id 
        
        asset = super(Assets, self).create(vals)

        user = asset.item_user
        components = asset.all_components

        for component in components:
            if component.available_quantity <= 0:
                raise ValidationError(
                    f"Component '{component.name}' has no available quantity to assign."
                )
            if user:
                if user.id not in component.user.ids:
                    component.user =  [(4, user.id)] 
            component.available_quantity -= 1 

        return asset
    
    def write(self, vals):
        if 'all_components' in vals:
            for record in self:
                new_user_id = vals.get('item_user') or (record.item_user.id if record.item_user else None)
                old_user_id = record.item_user.id if record.item_user else None

                old_components = record.all_components
                res = super(Assets, self).write(vals)  
                new_components = record.all_components

                added_components = new_components - old_components
                removed_components = old_components - new_components

                for component in added_components:
                    if component.available_quantity <= 0:
                        raise ValidationError(
                            f"Component '{component.name}' has no available quantity to assign."
                    )
                    if new_user_id not in component.user.ids:
                        component.user = [(4, new_user_id)]
                    component.available_quantity -= 1

                for component in removed_components:
                    if old_user_id and old_user_id in component.user.ids:
                        still_used = self.search_count([
                            ('all_components', 'in', component.id),
                            ('item_user', '=', old_user_id),
                            ('id', '!=', record.id)
                        ])
                        if not still_used:
                            component.user = [(3, old_user_id)]
                        component.available_quantity += 1 
            return res
        
        elif 'item_user' in vals:
            new_user_id = vals.get('item_user')
            for record in self:
               old_user_id = record.item_user.id if record.item_user else None
               components = record.all_components
               for component in components:
                    if old_user_id and old_user_id in component.user.ids:
                        component.user = [(3, old_user_id)]
                    if new_user_id not in component.user.ids and new_user_id:
                        component.user = [(4, new_user_id)]
                   
            result = super(Assets, self).write(vals)
            return result
        else:
            return super(Assets, self).write(vals)
    
    def unlink(self):
        for asset in self:
            user_id = asset.item_user.id
            for component in asset.all_components:
                component.available_quantity += 1 
                if user_id and user_id in component.user.ids:
                    still_used = self.search_count([
                        ('all_components', 'in', component.id),
                        ('item_user', '=', user_id),
                        ('id', '!=', asset.id)
                    ])
                    if not still_used:
                        component.user = [(3, user_id)]

        return super(Assets, self).unlink()
    
    def getAssetAndComponentCount(self):
        total_assets = self.env['it.assets'].search_count([])
        total_components = self.env['it.components'].search_count([])
        total_system = self.env['system.system'].search_count([])
        repairing_components = self.env['it.components'].search_count([('is_repair', '=', True)])
      
        return {
            'total_assets': total_assets,
            'total_systems': total_system,
            'total_components': total_components,
            'repairing_components': repairing_components,
        }


