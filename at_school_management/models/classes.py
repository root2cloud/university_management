from odoo import models, fields


class SchoolClass(models.Model):
    _name = 'school.class'
    _description = 'Class Record'

    name = fields.Char(string="Class Name", required=True)
    section = fields.Char(string="Section")
    grade = fields.Char(string="Grade")
    academic_year = fields.Char(string="Academic Year")
    students = fields.One2many('school.student', 'class_id', string="Students")
