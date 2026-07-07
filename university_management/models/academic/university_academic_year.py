# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityAcademicYear(models.Model):
    _name = 'university.academic.year'
    _description = 'University Academic Year'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Academic Year', required=True, tracking=True,
                       help='e.g., 2024-2025')
    code = fields.Char(string='Code', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Duration
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)

    # Semesters
    semester_ids = fields.One2many('university.semester', 'academic_year_id',
                                   string='Semesters')
    total_semesters = fields.Integer(string='Total Semesters', compute='_compute_counts')

    # Courses
    course_ids = fields.One2many('university.course', 'academic_year_id', string='Courses')
    total_courses = fields.Integer(string='Total Courses', compute='_compute_counts')

    # Examinations
    examination_ids = fields.One2many('examination.examination', 'academic_year_id',
                                      string='Examinations')

    # Current Status
    is_current = fields.Boolean(string='Current Academic Year', default=False, tracking=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Academic Year Code must be unique!'),
    ]

    @api.depends('semester_ids', 'course_ids')
    def _compute_counts(self):
        for record in self:
            record.total_semesters = len(record.semester_ids)
            record.total_courses = len(record.course_ids)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date >= record.end_date:
                raise ValidationError(_('End date must be after start date!'))

    @api.constrains('is_current')
    def _check_current_year(self):
        if self.is_current:
            other_current = self.search([
                ('id', '!=', self.id),
                ('is_current', '=', True)
            ])
            if other_current:
                raise ValidationError(_('Only one academic year can be current!'))

    def action_reset_to_draft(self):
        """Reset the academic year to draft state"""
        if self.state == 'closed':
            self.write({'state': 'draft'})
        else:
            raise ValidationError(_('Only closed academic years can be reset to draft!'))

    def action_set_current(self):
        self.search([('is_current', '=', True)]).write({'is_current': False})
        self.write({'is_current': True, 'state': 'active'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})
