# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MessAttendance(models.Model):
    _name = 'mess.attendance'
    _description = 'Mess Attendance/Meal Tracking'
    _order = 'date desc, student_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, index=True)

    # Mess
    mess_id = fields.Many2one('hostel.mess', string='Mess', required=True)

    # Date & Meal
    date = fields.Date(string='Date', default=fields.Date.today(), required=True, index=True)
    meal_type = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snacks', 'Snacks'),
        ('dinner', 'Dinner'),
    ], string='Meal Type', required=True)

    # Attendance
    present = fields.Boolean(string='Present', default=True)

    _sql_constraints = [
        ('unique_attendance', 'unique(student_id, date, meal_type)',
         'Attendance already marked for this student, date and meal!'),
    ]

    @api.depends('student_id', 'date', 'meal_type')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.student_id.name} - {record.date} - {record.meal_type}"
