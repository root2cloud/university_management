from odoo import fields, models, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
class Component(models.Model):
    
    _name = "it.components"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    comp_number = fields.Char(string = "Component Number")
    name = fields.Char(string = "Name")
    user = fields.Many2many(
                            'res.users',
                            'component_user_rel',  
                            'component_id',        
                            'user_id',             
                            string="Assignees"
                            )
    asset_kind = fields.Selection([("physical","Physical"),("virtual", "Virtual")], string = "Asset Kind")
    serial_number = fields.Char(string = "Serial No.")
    brand= fields.Many2one('asset.brand', string = "Brand")
    model= fields.Many2one('asset.model', string = "Model")
    vendor_id = fields.Many2one('res.partner', string = "Vendor")
    os_type = fields.Char(string = "OS Type")
    ip_address = fields.Char(string = "IP Address")
    license = fields.Char(string = "License")
    warranty = fields.Integer(string = "Warranty(In Months)", compute="_compute_warranty", store=True)
    buy_date = fields.Date(string = "Buy Date")
    warranty_end_date = fields.Date(string = "Warranty End Date")
    image_1920 = fields.Binary()
    used_users = fields.One2many("used.user.logs", "component_id", string = "Used User")
    it_assets = fields.Many2many(
        'it.assets',
        'component_asset_rel',   
        'component_id',          
        'asset_id',              
        string="IT Assets"
    )
    total_quantity = fields.Integer(string = "Total quantity", default = 1)
    available_quantity = fields.Integer(string = "Available Quanity", default = 1)
    state = fields.Selection([
        ('new', 'New'),
        ('assigned', 'Assigned'),
        ('in_repair', 'In Repair'),
        ('unassigned', 'Unassigned'),
    ], string='Status', default='new', compute="_compute_state", store=True)
    is_repair = fields.Boolean(string = "Repairing")
    
    @api.depends('buy_date', 'warranty_end_date')
    def _compute_warranty(self):
        for rec in self:
            if rec.buy_date and rec.warranty_end_date:
                delta = relativedelta(rec.warranty_end_date, rec.buy_date)
                rec.warranty = delta.years * 12 + delta.months
            else:
                rec.warranty = 0
    
    @api.depends('user', 'is_repair')
    def _compute_state(self):
        for record in self:
            if record.is_repair:
                record.state = 'in_repair'
            elif record.user:
                record.state = 'assigned'
            else:
                record.state = 'unassigned'

    @api.model
    def create(self, vals):
        asset_user = []
        asset_count = 0
        if vals.get('it_assets'):
            asset_ids = [asset[1] for asset in vals['it_assets'] if isinstance(asset, (list, tuple))]
            assets = self.env['it.assets'].browse(asset_ids)
            asset_count = len(assets)

            available_quantity = vals.get('available_quantity') if vals.get('available_quantity') is not None else self.available_quantity

            if available_quantity < asset_count:
                raise ValidationError(f"Not enough available quantity to allocate to {asset_count} asset(s). Only {available_quantity} available.")
            
            for asset in vals['it_assets']:
                asset = self.env['it.assets'].browse(asset[1])
                if asset.item_user:
                    asset_user.append(asset.item_user.id)
            vals['user'] = [(6, 0, asset_user)]
            vals['available_quantity'] = available_quantity - asset_count
        result = super(Component, self).create(vals)
        return result

    def write(self, vals):

        for record in self:
            original_user_ids = set(record.user.ids)
            removed_user_ids = set()

            if 'user' in vals:
                new_user_ids = set(vals['user'][0][2]) if vals['user'] and vals['user'][0][0] == 6 else set()
                removed_user_ids = original_user_ids - new_user_ids
        
                if vals.get('user') and vals['user'][0][0] == 3:
                    for uid in removed_user_ids:
                        record.with_context(skip_user_log=True).used_users = [(0, 0, {
                            'user_id': uid,
                            'last_used_date': fields.Datetime.now()
                        })]
        
        for record in self:
            if 'it_assets' in vals:
                user_ids = set(record.user.ids)  
                added_asset_ids = []
                removed_asset_ids = []
                
                for command in vals['it_assets']:
                    if isinstance(command, (list, tuple)):
                        if command[0] == 4:
                            asset = self.env['it.assets'].browse(command[1])
                            if asset.item_user:
                                user_ids.add(asset.item_user.id)
                            added_asset_ids.append(command[1])

                        elif command[0] == 3:
                            asset = self.env['it.assets'].browse(command[1])
                            if asset.item_user and asset.item_user.id in user_ids:
                                user_ids.remove(asset.item_user.id)
                            removed_asset_ids.append(command[1])
                        
                        elif command[0] == 6:
                            user_ids.clear()
                            asset_ids = command[2]
                            assets = self.env['it.assets'].browse(asset_ids)
                            for asset in assets:
                                if asset.item_user:
                                    user_ids.add(asset.item_user.id)
                            new_ids = set(command[2])
                            old_ids = set(record.it_assets.ids)
                            added_asset_ids = list(new_ids - old_ids)
                            removed_asset_ids = list(old_ids - new_ids)

                available_qty = record.available_quantity
                required_qty = len(added_asset_ids)

                if required_qty > 0:
                    if available_qty < required_qty:
                        raise ValidationError(f"Only {available_qty} component(s) are available, but you're trying to allocate {required_qty}.")
                    record.available_quantity -= required_qty
                
                if removed_asset_ids:
                    record.available_quantity += len(removed_asset_ids)

                record.user = [(6, 0, list(user_ids))] 

        return super(Component, self).write(vals)
