# -- coding: utf-8 --

from odoo import models, fields, api, _


class QualificationStudent(models.Model):
    _name = 'qualification.student'
    _description = 'Qualification Student'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    alternative_name = fields.Char(string=_("Alternative Name"))

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Name must be unique!'),
        ('alternative_name_unique', 'UNIQUE(alternative_name)', 'Alternative Name must be unique!'),
    ]
