from odoo import models, fields, api


class Subject(models.Model):
    _name = 'school.subject'
    _description = 'Subject'

    name = fields.Char(string="Subject Name", required=True)
    subject_code = fields.Char(string="Subject Code", required=True, unique=True)
    description = fields.Text(string="Description")
    teacher_ids = fields.Many2many('hr.employee', string="Assigned Teachers")


