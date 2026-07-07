# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FacultyWorkload(models.Model):
    _name = 'faculty.workload'
    _description = 'Faculty Teaching Workload'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc, semester_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    active = fields.Boolean(string='Active', default=True)

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one(related='faculty_id.department_id',
                                    string='Department', store=True)
    designation_id = fields.Many2one(related='faculty_id.designation_id',
                                     string='Designation', store=True)

    # Academic Period
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, tracking=True)

    # Courses
    course_ids = fields.Many2many('university.course', 'faculty_workload_course_rel',
                                  'workload_id', 'course_id',
                                  string='Courses Assigned', tracking=True)
    total_courses = fields.Integer(string='Total Courses', compute='_compute_workload')

    # Hours
    theory_hours = fields.Float(string='Theory Hours/Week')
    practical_hours = fields.Float(string='Practical Hours/Week')
    lab_hours = fields.Float(string='Lab Hours/Week')
    tutorial_hours = fields.Float(string='Tutorial Hours/Week')

    total_hours = fields.Float(string='Total Hours/Week', compute='_compute_total_hours',
                               store=True)
    hours_per_week = fields.Float(string='Total Teaching Hours/Week',
                                  compute='_compute_total_hours', store=True)

    # Maximum Workload
    max_allowed_hours = fields.Float(string='Max Allowed Hours/Week',
                                     related='designation_id.max_teaching_hours')
    is_overloaded = fields.Boolean(string='Overloaded', compute='_compute_overload', store=True)

    # Non-Teaching Activities
    administrative_hours = fields.Float(string='Administrative Hours/Week')
    research_hours = fields.Float(string='Research Hours/Week')
    exam_duties_hours = fields.Float(string='Exam Duties Hours/Week')

    # Student Count
    total_students = fields.Integer(string='Total Students', compute='_compute_workload')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approval Date', readonly=True)

    # Notes
    notes = fields.Text(string='Notes')

    @api.depends('faculty_id', 'academic_year_id', 'semester_id')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.faculty_id.name} - {record.academic_year_id.name} - {record.semester_id.name}"

    @api.depends('course_ids')
    def _compute_workload(self):
        for record in self:
            record.total_courses = len(record.course_ids)
            record.total_students = sum(record.course_ids.mapped('total_enrolled'))

    @api.depends('theory_hours', 'practical_hours', 'lab_hours', 'tutorial_hours')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = (record.theory_hours + record.practical_hours +
                                  record.lab_hours + record.tutorial_hours)
            record.hours_per_week = record.total_hours

    @api.depends('hours_per_week', 'max_allowed_hours')
    def _compute_overload(self):
        for record in self:
            record.is_overloaded = record.hours_per_week > record.max_allowed_hours

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today()
        })

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
