from odoo import models, fields

class StudentHobby(models.Model):
    _name = "student.hobby"
    _description = "Student Hobby"

    name = fields.Char(required=True)
