from odoo import models, fields


class Student(models.Model):
    _name = 'school.student'
    _description = 'Student Record'

    name = fields.Char(string="Full Name", required=True)
    admission_no = fields.Char(string="Admission No", required=True, unique=True)
    dob = fields.Date(string="Date of Birth", required=True,)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string="Gender", required=True,)
    medical_history = fields.Text(string="Medical History")
    parent_id = fields.Many2one('school.parent', string="Parent/Guardian")
    class_id = fields.Many2one('school.class', string="Class", required=True,)
    document_ids = fields.One2many('school.student.document', 'student_id', string="Documents")
    blood_group = fields.Selection([
        ('O-', 'O-'),
        ('O+', 'O+'),
        ('A-', 'A-'),
        ('A+', 'A+'),
        ('B-', 'B-'),
        ('B+', 'B+'),
        ('AB-', 'AB-'),
        ('AB+', 'AB+')
    ], string="Blood group", required=True,)
    is_student = fields.Boolean(string="Is Student", default=True)
    roll_no = fields.Char(string="Roll No", unique=True, required=True)
    house_address = fields.Text(string="Home Address", required=True)
    doj = fields.Date(string="Date of joining", required=True)
    trackskill = fields.Text(string="Track Skills")

    # 👇 New field for uploading and storing student image
    image_1920 = fields.Image(string="Student Photo", max_width=1920, max_height=1920, store=True)
