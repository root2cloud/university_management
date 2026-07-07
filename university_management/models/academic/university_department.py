# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversityDepartment(models.Model):
    _name = 'university.department'
    _description = 'University Department (CSE, ECE, Civil, Mechanical, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Department Name', required=True, tracking=True,
                       help='e.g., Computer Science & Engineering, Electronics & Communication')
    code = fields.Char(string='Department Code', required=True, tracking=True,
                       help='e.g., CSE, ECE, ME, CE, EEE')
    active = fields.Boolean(string='Active', default=True)
    image_128 = fields.Image(string='Image', max_width=128, max_height=128)

    # Head of Department
    hod_id = fields.Many2one('faculty.faculty', string='Head of Department (HOD)',
                             tracking=True)

    # Contact
    email = fields.Char(string='Department Email')
    phone = fields.Char(string='Department Phone')
    website = fields.Char(string='Department Website')

    # Location
    building_name_id = fields.Many2one('university.classroom', string='Building Name')
    floor_id = fields.Many2one('university.classroom', string='Floor')
    room_number_id = fields.Many2one('university.classroom', string='Room Number')

    # Programs
    program_ids = fields.One2many('university.program', 'department_id', string='Programs')

    # Faculty
    faculty_ids = fields.One2many('faculty.faculty', 'department_id', string='Faculty Members')

    # Students
    student_ids = fields.One2many('student.student', 'department_id', string='Students')

    # Courses & Subjects
    course_ids = fields.One2many('university.course', 'department_id', string='Courses')
    subject_ids = fields.One2many('university.subject', 'department_id', string='Subjects')

    # Labs & Equipment
    lab_count = fields.Integer(string='Number of Labs')
    lab_details = fields.Text(string='Lab Details')

    # Research
    research_areas = fields.Text(string='Research Areas')
    publications_count = fields.Integer(string='Research Publications')

    # Accreditation
    is_accredited = fields.Boolean(string='Accredited')
    accreditation_details = fields.Text(string='Accreditation Details')


    # Counts
    total_programs = fields.Integer(string='Programs', compute='_compute_counts', store=True)
    total_faculty = fields.Integer(string='Faculty', compute='_compute_counts', store=True)
    total_students = fields.Integer(string='Students', compute='_compute_counts', store=True)
    total_courses = fields.Integer(string='Courses', compute='_compute_counts', store=True)

    # Description
    description = fields.Html(string='Department Description')
    vision = fields.Text(string='Vision')
    mission = fields.Text(string='Mission')

    # Kept color field for the working of the Examinations of Applicable Departments
    color = fields.Integer(string='Color Index', default=0)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Department Code must be unique!'),
    ]

    @api.depends('program_ids', 'faculty_ids', 'student_ids', 'course_ids')
    def _compute_counts(self):
        for record in self:
            record.total_programs = len(record.program_ids)
            record.total_faculty = len(record.faculty_ids)
            record.total_students = len(record.student_ids)
            record.total_courses = len(record.course_ids)

    def action_view_courses(self):
        """Open courses list filtered by this department"""
        return {
            'name': _('Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.course',
            'view_mode': 'list,form,kanban',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id}
        }

    def action_view_faculty(self):
        return {
            'name': _('Faculty Members'),
            'type': 'ir.actions.act_window',
            'res_model': 'faculty.faculty',
            'view_mode': 'kanban,list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id}
        }

    def action_view_students(self):
        return {
            'name': _('Students'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'kanban,list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {'default_department_id': self.id}
        }
