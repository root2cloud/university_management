# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ClassTimetable(models.Model):
    _name = 'class.timetable'
    _description = 'Class Timetable/Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'day_of_week, start_datetime'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Academic Details
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, index=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, index=True)

    program_id = fields.Many2one('university.program', string='Program', required=True)
    department_id = fields.Many2one('university.department', string='Department', required=True)
    batch_id = fields.Many2one('university.batch', string='Batch/Year', required=True)
    section = fields.Char(string='Section')

    # Day & Time
    day_of_week = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ], string='Day', required=True, index=True)

    start_time = fields.Float(string='Start Time', required=True,
                              help='Time in 24-hour format (e.g., 9.0 for 9:00 AM)')
    end_time = fields.Float(string='End Time', required=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)

    # fields used by calendar
    start_datetime = fields.Datetime(string='Start Datetime')
    end_datetime = fields.Datetime(string='End Datetime')

    # Subject & Course
    course_id = fields.Many2one('university.course', string='Course', required=True)
    subject_id = fields.Many2one(related='course_id.subject_id', string='Subject', store=True)

    # Class Type
    class_type = fields.Selection([
        ('theory', 'Theory Class'),
        ('practical', 'Practical/Lab'),
        ('tutorial', 'Tutorial'),
    ], string='Class Type', required=True, default='theory')

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True)

    # Room
    room_number_id = fields.Many2one('university.classroom', string='Room/Lab Number')
    building_name_id = fields.Many2one('university.classroom', string='Building Name')

    # Status
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('unique_slot', 'unique(batch_id, day_of_week, start_time, room_number_id)',
         'Time slot already allocated for this batch/room!'),
    ]

    @api.depends('subject_id', 'day_of_week', 'start_time')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.subject_id.name if record.subject_id else ''} - {record.day_of_week} - {record.start_time}"

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

    @api.constrains('faculty_id', 'day_of_week', 'start_time', 'end_time')
    def _check_faculty_conflict(self):
        """Check if faculty is already assigned to another class at the same time"""
        for record in self:
            conflicts = self.search([
                ('id', '!=', record.id),
                ('faculty_id', '=', record.faculty_id.id),
                ('day_of_week', '=', record.day_of_week),
                ('start_time', '<', record.end_time),
                ('end_time', '>', record.start_time),
                ('active', '=', True)
            ])
            if conflicts:
                raise ValidationError(_(f'Faculty {record.faculty_id.name} already has a class at this time!'))

    @api.onchange('start_datetime', 'end_datetime')
    def _onchange_datetimes(self):
        """Keep float times in sync when user changes calendar event."""
        for rec in self:
            if rec.start_datetime:
                rec.start_time = rec.start_datetime.hour + rec.start_datetime.minute / 60.0
            if rec.end_datetime:
                rec.end_time = rec.end_datetime.hour + rec.end_datetime.minute / 60.0
