from odoo import models, fields, api
from odoo.exceptions import ValidationError

class Student(models.Model):
    _name = 'student.student'
    _description = 'Student Record'
    _order = 'age desc'

    # Relational Fields
    teacher_id = fields.Many2one('res.partner', string="Teacher")
    hobby_ids = fields.Many2many('student.hobby', string="Hobbies")
    mark_ids = fields.One2many('student.marks', 'student_id', string="Marks")

    # Simple Fields
    name = fields.Char(required=True)
    age = fields.Integer()
    email = fields.Char()

    # SQL Constraints
    _sql_constraints = [
        ('unique_email', 'unique(email)', 'Email must be unique!'),
        ('check_age', 'CHECK(age >= 0)', 'Age cannot be negative!')
    ]

    # Model Constraints
    @api.constrains('age')
    def _check_realistic_age(self):
        for rec in self:
            if rec.age > 120:
                raise ValidationError("Age is not realistic.")

    # Compute Field Example
    total_marks = fields.Integer(compute="_compute_total", store=True)

    @api.depends('mark_ids.marks')
    def _compute_total(self):
        for rec in self:
            rec.total_marks = sum(rec.mark_ids.mapped('marks'))

    # Onchange
    @api.onchange('age')
    def _onchange_age(self):
        if self.age < 18:
            return {
                'warning': {
                    'title': "Minor",
                    'message': "Student is below 18."
                }
            }

    # ORM Methods
    def write(self, vals):
        res = super().write(vals)
        print("Record updated:", self.name)
        return res

    @api.model
    def create(self, vals):
        print("Creating student:", vals.get('name'))
        return super().create(vals)

# Delegation inheritance example
class StudentProfile(models.Model):
    _name = 'student.profile'
    _inherits = {'student.student': 'student_id'}

    student_id = fields.Many2one('student.student', required=True, ondelete='cascade')
    bio = fields.Text()

class StudentHobby(models.Model):
    _name = 'student.hobby'
    name = fields.Char()

class StudentMarks(models.Model):
    _name = 'student.marks'

    student_id = fields.Many2one('student.student')
    subject = fields.Char()
    marks = fields.Integer()
