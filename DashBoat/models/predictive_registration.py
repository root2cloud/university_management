from odoo import models, fields

class PredictiveRegistration(models.Model):
    _name = 'predictive.registration'
    _description = 'Predictive Registration'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email')
    phone_number = fields.Char(string='Phone Number')
    address = fields.Text(string='Address')
    registration_date = fields.Date(string='Registration Date', default=fields.Date.today)