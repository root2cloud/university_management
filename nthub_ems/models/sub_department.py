# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SubDepartment(models.Model):
    _name = 'sub.department'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Sub Department'
    _rec_name = "name"

    name = fields.Char(string=_("name"))
    alternative_name = fields.Char(string=_("Alternative Name"))
    department_id = fields.Many2one("department", string=_("Department"))

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Name must be unique!'),
        ('alternative_name_unique', 'UNIQUE(alternative_name)', 'Alternative Name must be unique!'),
    ]
