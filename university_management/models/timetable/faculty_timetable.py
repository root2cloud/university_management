# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools


class FacultyTimetable(models.Model):
    _name = 'faculty.timetable'
    _description = 'Faculty Timetable View'
    _auto = False  # This is a SQL VIEW

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty', readonly=True)
    day_of_week = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
    ], string='Day', readonly=True)

    start_time = fields.Float(string='Start Time', readonly=True)
    end_time = fields.Float(string='End Time', readonly=True)
    duration = fields.Float(string='Duration', readonly=True)

    # fields used by calendar
    start_datetime = fields.Datetime(string='Start Datetime', required=True)
    end_datetime = fields.Datetime(string='End Datetime', required=True)

    subject_id = fields.Many2one('university.subject', string='Subject', readonly=True)
    batch_id = fields.Many2one('university.batch', string='Batch', readonly=True)
    room_number_id = fields.Many2one('university.classroom', string='Room Number', readonly=True)

    @api.onchange('start_datetime', 'end_datetime')
    def _onchange_datetimes(self):
        """Keep float times in sync when user changes calendar event."""
        for rec in self:
            if rec.start_datetime:
                rec.start_time = rec.start_datetime.hour + rec.start_datetime.minute / 60.0
            if rec.end_datetime:
                rec.end_time = rec.end_datetime.hour + rec.end_datetime.minute / 60.0

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW faculty_timetable AS (
                SELECT
                    ROW_NUMBER() OVER() as id,
                    faculty_id,
                    day_of_week,
                    start_time,
                    end_time,
                    (end_time - start_time) as duration,
                    subject_id,
                    batch_id,
                    room_number_id,
                    start_datetime,
                    end_datetime
                FROM class_timetable
                WHERE active = true
            )
        """)
