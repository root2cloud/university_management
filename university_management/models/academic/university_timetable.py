# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityTimetable(models.Model):
    _name = 'university.timetable'
    _description = 'Class Timetable'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'day_of_week, start_time'

    name = fields.Char(string='Title', compute='_compute_name', store=True)

    # Course & Academic
    course_id = fields.Many2one('university.course', string='Course',
                                required=True, tracking=True)
    subject_id = fields.Many2one(related='course_id.subject_id', string='Subject', store=True)
    program_id = fields.Many2one(related='course_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='course_id.department_id',
                                    string='Department', store=True)
    semester_id = fields.Many2one(related='course_id.semester_id', string='Semester', store=True)
    batch_id = fields.Many2one(related='course_id.batch_id', string='Batch', store=True)
    academic_year_id = fields.Many2one(related='course_id.academic_year_id',
                                       string='Academic Year', store=True)

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True)

    # Schedule
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Day', required=True, tracking=True)

    start_time = fields.Float(string='Start Time', required=True,
                              help='Time in 24-hour format (e.g., 9.0 for 9:00 AM)')
    end_time = fields.Float(string='End Time', required=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)

    # Classroom
    classroom_id = fields.Many2one('university.classroom', string='Classroom', tracking=True)
    room_number_id = fields.Many2one('university.classroom', string='Room Number')

    # Class Type
    class_type = fields.Selection([
        ('theory', 'Theory'),
        ('practical', 'Practical'),
        ('lab', 'Laboratory'),
        ('tutorial', 'Tutorial'),
        ('seminar', 'Seminar'),
    ], string='Class Type', required=True, default='theory')

    # Recurrence
    is_recurring = fields.Boolean(string='Recurring', default=True)
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')

    # Linked to Calendar Event
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event')

    # Status
    active = fields.Boolean(string='Active', default=True)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_slot', 'unique(course_id, day_of_week, start_time, end_date)',
         'Time slot already occupied for this course!'),
    ]

    @api.depends('course_id', 'day_of_week', 'start_time')
    def _compute_name(self):
        days = dict(self._fields['day_of_week'].selection)
        for record in self:
            day = days.get(record.day_of_week, '')
            time = '{:02.0f}:{:02.0f}'.format(*divmod(record.start_time * 60, 60))
            record.name = f"{record.course_id.name} - {day} {time}"

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
        for record in self:
            conflicts = self.search([
                ('id', '!=', record.id),
                ('faculty_id', '=', record.faculty_id.id),
                ('day_of_week', '=', record.day_of_week),
                ('active', '=', True),
                '|',
                '&', ('start_time', '<=', record.start_time), ('end_time', '>', record.start_time),
                '&', ('start_time', '<', record.end_time), ('end_time', '>=', record.end_time),
            ])
            if conflicts:
                raise ValidationError(_('Faculty already has a class at this time!'))

    @api.model
    def create(self, vals):
        record = super(UniversityTimetable, self).create(vals)
        record._create_calendar_event()
        return record

    def write(self, vals):
        result = super(UniversityTimetable, self).write(vals)
        for record in self:
            if record.calendar_event_id:
                record._update_calendar_event()
        return result

    def _create_calendar_event(self):
        """Create calendar event for timetable"""
        if not self.is_recurring:
            return

        CalendarEvent = self.env['calendar.event']
        days_map = {'0': '1', '1': '2', '2': '3', '3': '4', '4': '5', '5': '6', '6': '7'}

        # Create recurrence first
        recurrence_vals = {
            'rrule_type': 'weekly',
            'interval': 1,
            'count': 0,  # 0 means infinite until end_date
            'mon': self.day_of_week == '0',
            'tue': self.day_of_week == '1',
            'wed': self.day_of_week == '2',
            'thu': self.day_of_week == '3',
            'fri': self.day_of_week == '4',
            'sat': self.day_of_week == '5',
            'sun': self.day_of_week == '6',
        }

        if self.end_date:
            recurrence_vals['until'] = self.end_date
            recurrence_vals['end_type'] = 'end_date'
        else:
            recurrence_vals['end_type'] = 'forever'

        recurrence = self.env['calendar.recurrence'].create(recurrence_vals)

        event_vals = {
            'name': f"{self.course_id.name} - {self.subject_id.name}",
            'start': self._get_next_occurrence(),
            'stop': self._get_next_occurrence(end=True),
            'allday': False,
            'recurrence_id': recurrence.id,
            'description': f"Faculty: {self.faculty_id.name}\nRoom: {self.room_number_id or 'N/A'}",
            'partner_ids': [(6, 0, [])],  # Empty partner list
        }

        event = CalendarEvent.create(event_vals)
        self.calendar_event_id = event.id

    def _get_next_occurrence(self, end=False):
        """Get next occurrence datetime"""
        from datetime import datetime, timedelta
        import pytz

        today = fields.Date.today()
        current_weekday = today.weekday()
        target_weekday = int(self.day_of_week)

        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0:
            days_ahead += 7

        next_date = today + timedelta(days=days_ahead)

        time = self.end_time if end else self.start_time
        hours = int(time)
        minutes = int((time % 1) * 60)

        dt = datetime.combine(next_date, datetime.min.time().replace(hour=hours, minute=minutes))
        return dt

    def _update_calendar_event(self):
        """Update linked calendar event"""
        if self.calendar_event_id:
            self.calendar_event_id.write({
                'name': f"{self.course_id.name} - {self.subject_id.name}",
                'start': self._get_next_occurrence(),
                'stop': self._get_next_occurrence(end=True),
            })

    def action_view_calendar_event(self):
        self.ensure_one()
        if not self.calendar_event_id:
            return False
        return {
            'name': _('Calendar Event'),
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
            'target': 'current',
        }

