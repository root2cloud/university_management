# -*- coding: utf-8 -*-

from odoo import models, fields, api,_


class Department(models.Model):
    _name = 'department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Department'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    alternative_name = fields.Char(string=_("Alternative Name"))

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Name must be unique!'),
        ('alternative_name_unique', 'UNIQUE(alternative_name)', 'Alternative Name must be unique!'),
    ]




