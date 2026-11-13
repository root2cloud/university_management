# -*- coding: utf-8 -*-

from odoo import models, fields, tools


class FacultyTimetable(models.Model):
    _name = 'faculty.timetable'
    _description = 'Faculty Timetable View'
    _auto = False  # SQL VIEW over university_timetable
    _order = 'faculty_id, day_of_week, start_time'

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty', readonly=True)
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Day', readonly=True)

    start_time = fields.Float(string='Start Time', readonly=True)
    end_time = fields.Float(string='End Time', readonly=True)
    duration = fields.Float(string='Duration', readonly=True)

    subject_id = fields.Many2one('university.subject', string='Subject', readonly=True)
    batch_id = fields.Many2one('university.batch', string='Batch', readonly=True)
    room_number_id = fields.Many2one('university.classroom', string='Room Number', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW faculty_timetable AS (
                SELECT
                    id,
                    faculty_id,
                    day_of_week,
                    start_time,
                    end_time,
                    (end_time - start_time) AS duration,
                    subject_id,
                    batch_id,
                    COALESCE(room_number_id, classroom_id) AS room_number_id
                FROM university_timetable
                WHERE active = true
            )
        """)