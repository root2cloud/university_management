# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FacultyAttendance(models.Model):
    _name = 'faculty.attendance'
    _description = 'Faculty Attendance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, faculty_id'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True, index=True)
    employee_id = fields.Many2one(related='faculty_id.employee_id', string='Employee', store=True)
    department_id = fields.Many2one(related='faculty_id.department_id',
                                    string='Department', store=True)

    date = fields.Date(string='Date', required=True, default=fields.Date.today(),
                       tracking=True, index=True)
    check_in = fields.Datetime(string='Check In', tracking=True)
    check_out = fields.Datetime(string='Check Out', tracking=True)
    worked_hours = fields.Float(string='Worked Hours', compute='_compute_worked_hours', store=True)

    state = fields.Selection([
        ('present',  'Present'),
        ('absent',   'Absent'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
        ('late',     'Late'),
        ('holiday',  'Holiday'),
        ('week_off', 'Week Off'),
    ], string='Status', required=True, default='present', tracking=True)

    leave_id = fields.Many2one('faculty.leave', string='Leave Application')
    is_late = fields.Boolean(string='Late Coming')
    late_minutes = fields.Integer(string='Late By (Minutes)')
    late_reason = fields.Text(string='Reason for Late')
    is_overtime = fields.Boolean(string='Overtime')
    overtime_hours = fields.Float(string='Overtime Hours')
    overtime_approved = fields.Boolean(string='Overtime Approved')
    remarks = fields.Text(string='Remarks')

    # ── Link to Odoo HR Attendance ────────────────────────────────────────
    hr_attendance_id = fields.Many2one(
        'hr.attendance', string='HR Attendance',
        copy=False, ondelete='set null'
    )

    _sql_constraints = [
        ('unique_attendance', 'unique(faculty_id, date)',
         'Attendance already marked for this faculty on this date!'),
    ]

    _SYNC_STATES = {'present', 'late', 'half_day'}

    @api.depends('faculty_id', 'date')
    def _compute_name(self):
        for record in self:
            record.name = '%s - %s' % (record.faculty_id.name, record.date)

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for record in self:
            if record.check_in and record.check_out:
                record.worked_hours = (record.check_out - record.check_in).total_seconds() / 3600
            else:
                record.worked_hours = 0.0

    @api.constrains('check_in', 'check_out')
    def _check_times(self):
        for record in self:
            if record.check_in and record.check_out:
                if record.check_out <= record.check_in:
                    raise ValidationError(_('Check out time must be after check in time!'))

    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date > fields.Date.today():
                raise ValidationError(_('Cannot mark attendance for future dates!'))

    def _sync_hr_attendance(self):
        HrAttendance = self.env['hr.attendance'].sudo()
        for rec in self:
            if not rec.employee_id:
                continue
            if rec.state in rec._SYNC_STATES and rec.check_in:
                vals = {
                    'employee_id': rec.employee_id.id,
                    'check_in':    rec.check_in,
                    'check_out':   rec.check_out or False,
                }
                if rec.hr_attendance_id:
                    rec.hr_attendance_id.sudo().write(vals)
                else:
                    rec.hr_attendance_id = HrAttendance.create(vals).id
            else:
                if rec.hr_attendance_id:
                    rec.hr_attendance_id.sudo().unlink()
                    rec.hr_attendance_id = False

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_hr_attendance()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if {'state', 'check_in', 'check_out', 'employee_id'}.intersection(vals.keys()):
            self._sync_hr_attendance()
        return res

    def unlink(self):
        for rec in self:
            if rec.hr_attendance_id:
                rec.hr_attendance_id.sudo().unlink()
        return super().unlink()

    # ── Core Attendance Processing Engine ─────────────────────────────────
    @api.model
    def process_punch(self, faculty_id, check_in, check_out=None, hr_attendance_id=None):
        """
        Core engine called by both:
          - ZK bridge (production) after hr.attendance is created
          - Simulation button (demo) when manually entering punch data

        Classifies attendance as Present / Late / Half Day / Absent
        based on faculty work schedule rules.

        :param int    faculty_id:       faculty.faculty record id
        :param datetime check_in:       check-in datetime (UTC)
        :param datetime check_out:      check-out datetime (UTC) or False
        :param int    hr_attendance_id: hr.attendance record id to link
        :return: faculty.attendance record
        """
        from datetime import date as date_cls
        import pytz

        faculty = self.env['faculty.faculty'].browse(faculty_id)
        if not faculty.exists():
            return False

        punch_date = check_in.date() if check_in else date_cls.today()

        # Convert check_in to local time for schedule comparison
        user_tz = self.env.user.tz or 'Asia/Kolkata'
        local_tz = pytz.timezone(user_tz)
        check_in_local = pytz.utc.localize(check_in).astimezone(local_tz)

        # Work schedule values from faculty
        work_start  = faculty.work_start_time    # e.g. 9.0
        work_end    = faculty.work_end_time      # e.g. 17.5
        grace_min   = faculty.grace_minutes      # e.g. 10
        half_thresh = faculty.half_day_threshold # e.g. 4.0

        # Actual check-in in decimal hours
        actual_checkin_decimal = check_in_local.hour + check_in_local.minute / 60.0

        # Late detection
        late_threshold = work_start + grace_min / 60.0
        is_late = actual_checkin_decimal > late_threshold
        late_minutes = 0
        if is_late:
            late_minutes = int((actual_checkin_decimal - work_start) * 60)

        # Worked hours
        worked_hours = 0.0
        if check_in and check_out:
            worked_hours = (check_out - check_in).total_seconds() / 3600.0

        # State classification
        if check_in and check_out:
            if worked_hours < half_thresh:
                state = 'half_day'
            elif is_late:
                state = 'late'
            else:
                state = 'present'
        elif check_in and not check_out:
            # Only check-in present — mark late or present provisionally
            state = 'late' if is_late else 'present'
        else:
            state = 'absent'

        # Find or create faculty.attendance for this date
        existing = self.search([
            ('faculty_id', '=', faculty_id),
            ('date', '=', punch_date),
        ], limit=1)

        vals = {
            'faculty_id':       faculty_id,
            'date':             punch_date,
            'check_in':         check_in,
            'check_out':        check_out or False,
            'state':            state,
            'is_late':          is_late,
            'late_minutes':     late_minutes,
            'worked_hours':     worked_hours,
        }
        if hr_attendance_id:
            vals['hr_attendance_id'] = hr_attendance_id

        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)

    def action_simulate_punch(self):
        """
        Demo / simulation button on faculty.attendance form.
        Re-processes the current record's check_in / check_out
        through the attendance engine — same logic as ZK bridge.
        Useful for demos without a physical biometric device.
        """
        self.ensure_one()
        if not self.check_in:
            from odoo.exceptions import UserError
            raise UserError(_('Please enter Check In time before simulating.'))

        self.process_punch(
            faculty_id=self.faculty_id.id,
            check_in=self.check_in,
            check_out=self.check_out or False,
            hr_attendance_id=self.hr_attendance_id.id if self.hr_attendance_id else False,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': _('Punch processed. Attendance classified as: %s') % dict(
                    self._fields['state'].selection).get(self.state, self.state),
                'type': 'success',
                'sticky': False,
            }
        }