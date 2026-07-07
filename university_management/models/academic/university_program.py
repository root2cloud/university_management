# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityProgram(models.Model):
    _name = 'university.program'
    _description = 'University Program (B.Tech, M.Tech, MBA, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Program Name', required=True, tracking=True,
                       help='e.g., B.Tech, M.Tech, MBA, BBA, B.Pharmacy')
    code = fields.Char(string='Program Code', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)
    image_128 = fields.Image(
        string='Image',
        max_width=128,
        max_height=128
    )

    # Program Type
    program_type = fields.Selection([
        ('undergraduate', 'Undergraduate (UG)'),
        ('postgraduate', 'Postgraduate (PG)'),
        ('diploma', 'Diploma'),
        ('phd', 'Ph.D'),
        ('certificate', 'Certificate Course'),
    ], string='Program Type', required=True, tracking=True)

    # Department
    department_id = fields.Many2one('university.department', string='Department',
                                    required=True, tracking=True)

    # Duration
    duration_years = fields.Integer(string='Duration (Years)', required=True, default=4)
    total_semesters = fields.Integer(string='Total Semesters', required=True, default=8)

    # Eligibility
    eligibility_criteria = fields.Text(string='Eligibility Criteria',
                                       help='Minimum qualification required')
    min_percentage = fields.Float(string='Minimum Percentage Required')

    # Curriculum
    syllabus_ids = fields.One2many('university.syllabus', 'program_id', string='Syllabus')
    course_ids = fields.One2many('university.course', 'program_id', string='Courses')

    # Students & Batches
    student_ids = fields.One2many('student.student', 'program_id', string='Students')
    batch_ids = fields.One2many('university.batch', 'program_id', string='Batches')

    # Capacity
    total_seats = fields.Integer(string='Total Seats', default=60)
    available_seats = fields.Integer(string='Available Seats', compute='_compute_available_seats', store=True)

    # Fee Structure
    fee_structure_ids = fields.One2many('fee.structure', 'program_id', string='Fee Structure')

    # Accreditation
    is_accredited = fields.Boolean(string='Accredited')
    accreditation_body = fields.Char(string='Accreditation Body', help='e.g., NAAC, NBA')
    accreditation_grade = fields.Char(string='Grade', help='e.g., A++, A+')

    # Counts
    total_students = fields.Integer(string='Total Students', compute='_compute_counts', store=True)
    total_courses = fields.Integer(string='Total Courses', compute='_compute_counts', store=True)
    total_batches = fields.Integer(string='Total Batches', compute='_compute_counts', store=True)

    # Description
    description = fields.Html(string='Program Description')
    career_opportunities = fields.Html(string='Career Opportunities')

    # Kept color field for the working of the Examinations of Applicable Programs
    color = fields.Integer(string='Color Index', default=0)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Program Code must be unique!'),
    ]

    @api.depends('student_ids', 'total_seats')
    def _compute_available_seats(self):
        for record in self:
            enrolled = len(record.student_ids.filtered(lambda s: s.state in ['enrolled', 'active']))
            record.available_seats = record.total_seats - enrolled

    @api.depends('student_ids', 'course_ids', 'batch_ids')
    def _compute_counts(self):
        for record in self:
            record.total_students = len(record.student_ids)
            record.total_courses = len(record.course_ids)
            record.total_batches = len(record.batch_ids)

    def action_view_students(self):
        return {
            'name': _('Students'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'kanban,list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id}
        }

    def action_view_courses(self):
        return {
            'name': _('Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.course',
            'view_mode': 'list,form',
            'domain': [('program_id', '=', self.id)],
            'context': {'default_program_id': self.id}
        }
