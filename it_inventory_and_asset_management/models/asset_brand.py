from odoo import models, fields

class AssetBrand(models.Model):

    _name = "asset.brand"

    name = fields.Char(string = "Name")