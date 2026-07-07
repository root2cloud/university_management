from odoo import models, fields

class UsedUserLogs(models.Model):

    _name = "used.user.logs"

    user_id = fields.Many2one('res.users', string = "User")
    last_used_date = fields.Datetime(string = "Date")
    component_id = fields.Many2one('it.components' , String = "Component")