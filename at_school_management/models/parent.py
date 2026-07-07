from odoo import models, fields, api


class Parent(models.Model):
    _name = 'school.parent'
    _description = 'Parent/Guardian'

    name = fields.Char(string="Full Name", required=True)
    contact_no = fields.Char(string="Contact No", required=True)
    email = fields.Char(string="Email")
    occupation = fields.Char(string="Occupation")
    students = fields.One2many('school.student', 'parent_id', string="Children")
    relation = fields.Selection([
        ('Father', 'Father'),
        ('Mother', 'Mother'),
        ('Guardian', 'Guardian')
    ], string="Relation", required=True)