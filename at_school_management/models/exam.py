from odoo import models, fields

class Exam(models.Model):
    _name = 'school.exam'
    _description = 'Exam Record'

    name = fields.Char(string="Exam Name", required=True)
    class_id = fields.Many2one('school.class', string="Class")
    subject_id = fields.Many2one('school.subject', string="Subject")
    exam_datetime = fields.Datetime(string="Exam Date and Time")  # New field
    max_marks = fields.Integer(string="Max Marks")
    passing_marks = fields.Integer(string="Passing Marks")
