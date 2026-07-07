from odoo import models, fields

class Teacher(models.Model):
    _inherit = 'hr.employee'

    is_teacher = fields.Boolean(string="Is a Teacher", default=True)
    qualification = fields.Text(string="Qualification")
    subject_ids = fields.Many2many('school.subject', string="Subjects")
    joining_date = fields.Date(string="Joining Date")




