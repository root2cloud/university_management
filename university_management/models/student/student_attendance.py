# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentAttendance(models.Model):
    _name = 'student.attendance'
    _description = 'Student Attendance Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, student_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one('university.program', related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one('university.department', related='student_id.department_id',
                                    string='Department', store=True)
    batch_id = fields.Many2one('university.batch', related='student_id.batch_id', string='Batch', store=True)

    # Course
    course_id = fields.Many2one('university.course', string='Course', tracking=True, index=True)
    subject_id = fields.Many2one('university.subject', related='course_id.subject_id', string='Subject', store=True)
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty')

    # Attendance Date & Time
    date = fields.Date(string='Date', required=True, default=fields.Date.today(),
                       tracking=True, index=True)
    time_in = fields.Float(string='Time In', help='Time in 24-hour format')
    time_out = fields.Float(string='Time Out', help='Time in 24-hour format')

    # Timetable Reference
    timetable_id = fields.Many2one('university.timetable', string='Timetable Entry')

    # Status
    state = fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('on_leave', 'On Leave'),
        ('holiday', 'Holiday'),
    ], string='Status', required=True, default='present', tracking=True)

    # receipt_printed = fields.Boolean(string='Receipt Printed')
    # company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Leave
    leave_application_id = fields.Many2one('student.leave', string='Leave Application')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('unique_attendance', 'unique(student_id, course_id, date)',
         'Attendance already marked for this student, course and date!'),
    ]

    @api.depends('student_id', 'course_id', 'date')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.student_id.name} - {record.course_id.name if record.course_id else 'General'} - {record.date}"

    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_('Cannot mark attendance for future dates!'))

    @api.constrains('time_in', 'time_out')
    def _check_times(self):
        for record in self:
            if record.time_in and record.time_out and record.time_out <= record.time_in:
                raise ValidationError(_('Time Out must be after Time In!'))

    def action_print_receipt(self):
        """Print Attendance report"""
        self.write({'receipt_printed': True})
        return self.env.ref('university_management.report_attendance').report_action(self)

    def action_mark_present(self):
        """Mark attendance as Present"""
        for record in self:
            record.state = 'present'
        return True

    def action_mark_absent(self):
        """Mark attendance as Absent"""
        for record in self:
            record.state = 'absent'
        return True

    def action_mark_late(self):
        """Mark attendance as Late"""
        for record in self:
            record.state = 'late'
        return True

    def action_mark_on_leave(self):
        """Mark attendance as On Leave"""
        for record in self:
            record.state = 'on_leave'
        return True

    def action_mark_holiday(self):
        """Mark attendance as Holiday"""
        for record in self:
            record.state = 'holiday'
        return True
