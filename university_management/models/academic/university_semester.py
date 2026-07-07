# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversitySemester(models.Model):
    _name = 'university.semester'
    _description = 'University Semester System'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Semester Name', required=True, tracking=True,
                       help='e.g., Semester 1, Semester 2')
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)

    # Semester Number
    semester_number = fields.Integer(string='Semester Number', required=True,
                                     help='1 for Sem-1, 2 for Sem-2, etc.')

    # Program
    program_id = fields.Many2one('university.program', string='Program')

    # Duration
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)

    # Courses
    course_ids = fields.One2many('university.course', 'semester_id', string='Courses')
    total_courses = fields.Integer(string='Total Courses', compute='_compute_counts', store=True)

    # Examinations
    examination_ids = fields.One2many('examination.examination', 'semester_id',
                                      string='Examinations')
    total_exams = fields.Integer(string='Total Exams', compute='_compute_counts', store=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code, academic_year_id)',
         'Semester code must be unique per academic year!'),
    ]

    @api.depends('course_ids', 'examination_ids')
    def _compute_counts(self):
        for record in self:
            record.total_courses = len(record.course_ids)
            record.total_exams = len(record.examination_ids)

    def action_view_courses(self):
        """Open courses list filtered by this semester"""
        return {
            'name': _('Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.course',
            'view_mode': 'list,form,kanban',
            'domain': [('semester_id', '=', self.id)],
            'context': {'default_semester_id': self.id}
        }

    def action_view_examinations(self):
        """Open examinations list filtered by this semester"""
        return {
            'name': _('Examinations'),
            'type': 'ir.actions.act_window',
            'res_model': 'examination.examination',
            'view_mode': 'list,form,calendar',
            'domain': [('semester_id', '=', self.id)],
            'context': {'default_semester_id': self.id}
        }

    def action_schedule_course(self):
        self.write({'state': 'scheduled'})

    def action_start_semester(self):
        self.write({'state': 'ongoing'})

    def action_complete_semester(self):
        self.write({'state': 'completed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
