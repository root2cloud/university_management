# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationTimetable(models.Model):
    _name = 'examination.timetable'
    _description = 'Exam Timetable'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_date, start_time'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Examination
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True, index=True,
                                     ondelete='cascade')

    # Subject & Course
    course_id = fields.Many2one('university.course', string='Course',
                                required=True, tracking=True)
    subject_id = fields.Many2one(related='course_id.subject_id', string='Subject',
                                 store=True, readonly=True)
    program_id = fields.Many2one(related='course_id.program_id', string='Program',
                                 store=True, readonly=True)
    department_id = fields.Many2one(related='course_id.department_id', string='Department',
                                    store=True, readonly=True)
    semester_id = fields.Many2one(related='course_id.semester_id', string='Semester',
                                  store=True, readonly=True)

    # Exam Schedule
    exam_date = fields.Date(string='Exam Date', required=True, tracking=True, index=True)
    start_time = fields.Float(string='Start Time', required=True,
                              help='Time in 24-hour format (e.g., 9.0 for 9:00 AM)')
    end_time = fields.Float(string='End Time', required=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)

    # Exam Details
    max_marks = fields.Integer(string='Maximum Marks', required=True, default=100)
    passing_marks = fields.Integer(string='Passing Marks', required=True, default=40)

    # Venue
    venue = fields.Char(string='Exam Venue')
    room_numbers = fields.Char(string='Room Numbers')

    # Instructions
    instructions = fields.Html(string='Specific Instructions')

    # Supervisors/Invigilators
    invigilator_ids = fields.Many2many('faculty.faculty', 'exam_invigilator_rel',
                                       'timetable_id', 'faculty_id',
                                       string='Invigilators')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', tracking=True)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_exam', 'unique(examination_id, course_id)',
         'Exam already scheduled for this course!'),
    ]

    @api.depends('subject_id', 'exam_date')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.subject_id.name if record.subject_id else ''} - {record.exam_date}"

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            record.duration = record.end_time - record.start_time

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError(_('End time must be after start time!'))
            if record.start_time < 0 or record.end_time > 24:
                raise ValidationError(_('Time must be between 0 and 24!'))

    @api.constrains('exam_date', 'examination_id')
    def _check_exam_date(self):
        for record in self:
            if record.examination_id:
                if (record.exam_date < record.examination_id.start_date or
                        record.exam_date > record.examination_id.end_date):
                    raise ValidationError(_('Exam date must be within examination period!'))

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_start(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
