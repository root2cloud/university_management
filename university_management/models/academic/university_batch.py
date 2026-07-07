# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversityBatch(models.Model):
    _name = 'university.batch'
    _description = 'University Batch/Year Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_year desc'

    name = fields.Char(string='Batch Name', required=True, tracking=True,
                       help='e.g., 2021-2025 Batch, 2022 Batch')
    code = fields.Char(string='Batch Code', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Program
    program_id = fields.Many2one('university.program', string='Program',
                                 required=True, tracking=True)
    department_id = fields.Many2one(related='program_id.department_id',
                                    string='Department', store=True)

    # Academic Year
    start_year = fields.Integer(string='Start Year', required=True)
    end_year = fields.Integer(string='Expected End Year', required=True)

    # ADD THESE COMPUTED DATE FIELDS FOR CALENDAR VIEW
    calendar_start_date = fields.Date(string='Calendar Start Date', compute='_compute_calendar_dates', store=True)
    calendar_end_date = fields.Date(string='Calendar End Date', compute='_compute_calendar_dates', store=True)

    # Students
    student_ids = fields.One2many('student.student', 'batch_id', string='Students')
    total_students = fields.Integer(string='Total Students', compute='_compute_counts', store=True)
    current_semester = fields.Integer(string='Current Semester')

    # Courses
    course_ids = fields.One2many('university.course', 'batch_id', string='Courses')

    # Class Coordinator
    coordinator_id = fields.Many2one('faculty.faculty', string='Class Coordinator')

    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('graduated', 'Graduated'),
        ('archived', 'Archived'),
    ], string='Status', default='active', tracking=True)

    # Description
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Batch Code must be unique!'),
    ]

    @api.depends('start_year', 'end_year')
    def _compute_calendar_dates(self):
        for record in self:
            # Convert integer year to date (e.g., 2021 -> 2021-01-01)
            if record.start_year:
                record.calendar_start_date = fields.Date.to_date(f"{record.start_year}-01-01")
            else:
                record.calendar_start_date = False

            if record.end_year:
                record.calendar_end_date = fields.Date.to_date(f"{record.end_year}-12-31")
            else:
                record.calendar_end_date = False

    @api.depends('student_ids')
    def _compute_counts(self):
        for record in self:
            record.total_students = len(record.student_ids)

    def action_view_students(self):
        return {
            'name': _('Batch Students'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'kanban,list,form',
            'domain': [('batch_id', '=', self.id)],
            'context': {'default_batch_id': self.id}
        }
