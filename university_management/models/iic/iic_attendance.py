# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IICAttendance(models.Model):
    _name = 'iic.attendance'
    _description = 'IIC Event Attendance'
    _order = 'event_id, name'

    event_id = fields.Many2one('iic.event', string='Event', required=True, ondelete='cascade')
    name = fields.Char(compute='_compute_name', store=True, readonly=False)

    attendee_type = fields.Selection([
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('external', 'External'),
    ], string='Attendee Type', default='student')

    participant_type = fields.Selection([
        ('student', 'Student'),
        ('faculty', 'Faculty'),
        ('external', 'External'),
    ], string='Participant Type', default='student', required=True)

    student_id = fields.Many2one('student.student', string='Student')
    faculty_id = fields.Many2one('hr.employee', string='Faculty')
    department_id = fields.Many2one('university.department', string='Department')

    # Batch is resolved from the student; stored so dashboard queries avoid joins
    batch_id = fields.Many2one(
        'university.batch',
        string='Batch',
        store=True,
        compute='_compute_student_meta',
        readonly=False,
    )

    registration_number = fields.Char(string='Registration Number')
    external_name = fields.Char(string='External Participant Name')
    external_org = fields.Char(string='External Organisation')

    # Stored related fields from the parent event.
    # Odoo 18 rejects relational traversal (e.g. 'event_id.quarter') in
    # search-view group_by context — the field must exist directly on the
    # model. Storing them here also avoids a JOIN on every dashboard query.
    quarter = fields.Selection(
        related='event_id.quarter',
        string='Quarter',
        store=True,
        readonly=True,
    )
    academic_year_id = fields.Many2one(
        'university.academic.year',
        related='event_id.academic_year_id',
        string='Academic Year',
        store=True,
        readonly=True,
    )

    # Final attendance status — computed from checkin/checkout
    status = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('checked_in', 'Checked In (Pending Check-out)'),
    ], string='Attendance Status', default='absent', required=True)

    # Check-in details (QR 1 scan)
    checkin_time = fields.Datetime(string='Check-in Time')
    checkin_qr_verified = fields.Boolean(string='Check-in QR Verified', default=False)

    # Check-out details (QR 2 scan)
    checkout_time = fields.Datetime(string='Check-out Time')
    checkout_qr_verified = fields.Boolean(string='Check-out QR Verified', default=False)

    # Duration stayed (minutes)
    duration_minutes = fields.Integer(
        string='Duration Stayed (minutes)',
        compute='_compute_duration',
        store=True,
    )

    # Legacy fields kept for compatibility
    marked_at = fields.Datetime(string='Marked At', default=fields.Datetime.now)
    timestamp = fields.Datetime(string='Timestamp', related='marked_at', store=True)
    notes = fields.Text(string='Notes')
    qr_verified = fields.Boolean(string='QR Verified', default=False)
    marked_by = fields.Many2one('res.users', string='Marked By', default=lambda self: self.env.user)

    # ── Computed fields ───────────────────────────────────────────────────────

    @api.depends('checkin_time', 'checkout_time')
    def _compute_duration(self):
        for rec in self:
            if rec.checkin_time and rec.checkout_time:
                delta = rec.checkout_time - rec.checkin_time
                rec.duration_minutes = int(delta.total_seconds() / 60)
            else:
                rec.duration_minutes = 0

    @api.depends('student_id')
    def _compute_student_meta(self):
        """
        Relay department and batch from the linked student record.
        This keeps the attendance record self-contained for dashboard queries
        without requiring joins to student.student every time.
        """
        for rec in self:
            if rec.student_id:
                rec.department_id = rec.student_id.department_id
                rec.batch_id = rec.student_id.batch_id
                rec.registration_number = rec.student_id.registration_number
            # Do not blank out manually set values when student is not set

    @api.depends('student_id', 'faculty_id', 'external_name', 'attendee_type')
    def _compute_name(self):
        for rec in self:
            if rec.attendee_type == 'student' and rec.student_id:
                rec.name = rec.student_id.name
            elif rec.attendee_type == 'faculty' and rec.faculty_id:
                rec.name = rec.faculty_id.name
            elif rec.attendee_type == 'external' and rec.external_name:
                rec.name = rec.external_name

    # ── Onchange helpers (kept for manual form edits) ─────────────────────────

    @api.onchange('student_id')
    def _onchange_student(self):
        if self.student_id:
            self.name = self.student_id.name
            self.department_id = self.student_id.department_id
            self.batch_id = self.student_id.batch_id
            self.registration_number = self.student_id.registration_number

    @api.onchange('faculty_id')
    def _onchange_faculty(self):
        if self.faculty_id:
            self.name = self.faculty_id.name
            faculty = self.env['faculty.faculty'].search(
                [('employee_id', '=', self.faculty_id.id)], limit=1
            )
            if faculty and faculty.department_id:
                self.department_id = faculty.department_id