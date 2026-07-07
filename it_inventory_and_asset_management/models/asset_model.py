from odoo import models, fields

class AssetModel(models.Model):

    _name = "asset.model"

    name = fields.Char(string = "Name")