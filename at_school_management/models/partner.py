# school/models/partner.py
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_student = fields.Boolean(string="Is Student", default=False)
    is_parent = fields.Boolean(string="Is Parent", default=False)

    # Student fields
    admission_no = fields.Char(string="Admission No")
    roll_no = fields.Char(string="Roll No")
    dob = fields.Date(string="Date of Birth")
    gender = fields.Selection([
        ('male', 'Male'), ('female', 'Female'), ('other', 'Other')
    ], string="Gender")
    blood_group = fields.Selection([
        ('O-', 'O-'), ('O+', 'O+'), ('A-', 'A-'), ('A+', 'A+'), ('B-', 'B-'), ('B+', 'B+'), ('AB-', 'AB-'), ('AB+', 'AB+')
    ], string="Blood Group")
    doj = fields.Date(string="Date of Joining")
    medical_history = fields.Text(string="Medical History")
    class_id = fields.Many2one('school.class', string="Class")

    # Parent fields
    occupation = fields.Char(string="Occupation")
    relation = fields.Selection([
        ('Father', 'Father'), ('Mother', 'Mother'), ('Guardian', 'Guardian')
    ], string="Relation")
