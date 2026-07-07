from odoo import models, fields

class StudentMarks(models.Model):
    _name = 'student.marks'
    _description = "Student Marks"

    subject = fields.Char(string="Subject")
    score = fields.Integer(string="Score")

    student_id = fields.Many2one('student.student', string="Student")
    mark_ids = fields.One2many('student.marks', 'student_id', string="Marks")

