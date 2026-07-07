from odoo import models, fields

class PredictionAnalysisRegistrationBackup(models.Model):
    _name = 'prediction.analysis.registration.backup'
    _description = 'Prediction Analysis Registration Backup'

    name = fields.Char(string="Name")
    email = fields.Char(string="Email")
    contacts = fields.Char(string="Contacts")
    uuid = fields.Char(string="UUID")
    secret_key = fields.Char(string="Secret Key")
    status = fields.Char(string="Status")
