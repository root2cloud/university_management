from odoo import models, fields, api

class FeeType(models.Model):
    _name = 'school.fee.type'
    _description = 'Fee Type'

    name = fields.Char(string='Fee Type')
    description = fields.Text(string='Description')
    amount = fields.Float(string='Amount')