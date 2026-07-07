from odoo import models, fields

class DataAnalysisPreserved(models.Model):
    _name = 'predictive_engine.data_analysis_preserved'  # Updated model name
    _description = 'Preserved Data for DashBoat'

    uuid_key = fields.Char(string="UUID Key", required=True, index=True)
    secret_key = fields.Char(string="Secret Key")
    email = fields.Char(string="Email", required=True, index=True)
    name = fields.Char(string="Full Name")
    contact = fields.Char(string="Contact")