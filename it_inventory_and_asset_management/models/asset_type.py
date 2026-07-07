from odoo import models, fields

class AssetType(models.Model):

    _name = "asset.type"

    name = fields.Char(string = "Name")
    status = fields.Selection([("active","Active"),("inactive"," In-Active")])


