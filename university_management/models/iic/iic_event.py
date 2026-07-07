# -*- coding: utf-8 -*-

import base64
import uuid
try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
import io
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IICEvent(models.Model):
    _name = 'iic.event'
    _description = 'IIC Activity / Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'event_date desc'

    name = fields.Char(string='Event Title', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    # Activity Classification
    activity_type = fields.Selection([
        ('mandatory', 'MSME Mandatory Activity'),
        ('self_driven', 'Self Driven Activity'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('innovation_talk', 'Innovation Talk'),
        ('entrepreneurship', 'Entrepreneurship Session'),
        ('hackathon', 'Hackathon'),
        ('other', 'Other'),
    ], string='Activity Type', required=True, tracking=True)

    event_category = fields.Selection([
        ('ideation', 'Ideation & Innovation'),
        ('entrepreneurship', 'Entrepreneurship'),
        ('technology', 'Technology'),
        ('social', 'Social Innovation'),
        ('IPR', 'IPR & Patents'),
        ('startup', 'Startup Ecosystem'),
    ], string='Event Category', tracking=True)

    # Scheduling
    event_date = fields.Datetime(string='Start Date & Time', required=True, tracking=True)
    date_end = fields.Datetime(string='End Date & Time', tracking=True)
    venue = fields.Char(string='Venue', tracking=True)
    expected_participants = fields.Integer(string='Expected Participants')

    # Minimum attendance duration (in minutes) — admin sets this
    min_attendance_minutes = fields.Integer(
        string='Minimum Attendance Duration (minutes)',
        default=180,
        help='Student/faculty must stay at least this many minutes between check-in and check-out QR scans to be marked Present. Default is 180 minutes (3 hours).'
    )

    # Quarter
    quarter = fields.Selection([
        ('Q1', 'Quarter 1 (Jan-Mar)'),
        ('Q2', 'Quarter 2 (Apr-Jun)'),
        ('Q3', 'Quarter 3 (Jul-Sep)'),
        ('Q4', 'Quarter 4 (Oct-Dec)'),
    ], string='Quarter', compute='_compute_quarter', store=True, readonly=False)

    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year', tracking=True)

    # People
    speaker_id = fields.Many2one('iic.speaker', string='Speaker / Resource Person', tracking=True)
    speaker_name = fields.Char(string='External Speaker Name', tracking=True)
    faculty_id = fields.Many2one('hr.employee', string='Faculty Coordinator', tracking=True)
    qr_verified = fields.Boolean(string='QR Verified', default=False)
    faculty_incharge_id = fields.Many2one('hr.employee', string='Faculty In-Charge', tracking=True)
    iic_president_id = fields.Many2one('hr.employee', string='IIC President')
    iic_convenor_id = fields.Many2one('hr.employee', string='IIC Convenor')

    # Description
    description = fields.Html(string='Event Description')
    objectives = fields.Text(string='Objectives')

    # State
    iic_state = fields.Selection([
        ('planning', 'Planning'),
        ('poster_pending', 'Poster Pending'),
        ('poster_approved', 'Poster Approved'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('report_pending', 'Report Pending'),
        ('report_approved', 'Report Approved'),
        ('archived', 'Archived'),
    ], string='Status', default='planning', tracking=True)

    # Odoo event.event inheritance (calendar integration)
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event', copy=False)

    # Relations
    attendance_ids = fields.One2many('iic.attendance', 'event_id', string='Attendance')
    media_ids = fields.One2many('iic.media', 'event_id', string='Event Media')
    report_ids = fields.One2many('iic.event.report', 'event_id', string='Event Reports')
    poster_ids = fields.One2many('iic.poster', 'event_id', string='Posters')
    approval_log_ids = fields.One2many('iic.approval.log', 'event_id', string='Approval Logs')

    # Computed count fields (for stat buttons)
    attendance_count = fields.Integer(string='Attendees', compute='_compute_counts', store=True)
    media_count = fields.Integer(string='Media', compute='_compute_counts', store=True)
    poster_count = fields.Integer(string='Posters', compute='_compute_counts', store=True)
    report_count = fields.Integer(string='Reports', compute='_compute_counts', store=True)

    # Computed stats
    total_attendees = fields.Integer(string='Total Attendees', compute='_compute_attendance_stats', store=True)
    present_count = fields.Integer(string='Present', compute='_compute_attendance_stats', store=True)
    absent_count = fields.Integer(string='Absent', compute='_compute_attendance_stats', store=True)
    participation_percentage = fields.Float(string='Participation %', compute='_compute_attendance_stats', store=True)

    # QR Code — CHECK-IN (QR 1) — shown at the START of the event
    qr_code = fields.Binary(string='Check-in QR Code', attachment=True, copy=False)
    qr_token = fields.Char(string='Check-in QR Token', copy=False)
    qr_code_url = fields.Char(string='Check-in QR URL', compute='_compute_qr_url')

    # QR Code — CHECK-OUT (QR 2) — shown at the END of the event
    qr_checkout_code = fields.Binary(string='Check-out QR Code', attachment=True, copy=False)
    qr_checkout_token = fields.Char(string='Check-out QR Token', copy=False)
    qr_checkout_url = fields.Char(string='Check-out QR URL', compute='_compute_qr_url')

    # Report finalized
    report_submitted = fields.Boolean(string='Report Submitted to MSME', tracking=True)

    # Fields used in views
    actual_participants = fields.Integer(string='Actual Participants')
    department_id = fields.Many2one('university.department', string='Organizing Department', tracking=True)
    faculty_coordinator_ids = fields.Many2many('hr.employee', string='Faculty Coordinators')
    event_summary = fields.Html(string='Event Summary')
    key_takeaways = fields.Text(string='Key Takeaways')
    remarks = fields.Text(string='Remarks')
    iic_sequence = fields.Char(string='IIC Sequence No.')

    # Date aliases
    date_begin = fields.Datetime(string='Start Date & Time', compute='_compute_date_begin', inverse='_inverse_date_begin', store=True)

    @api.depends('event_date')
    def _compute_date_begin(self):
        for rec in self:
            rec.date_begin = rec.event_date

    def _inverse_date_begin(self):
        for rec in self:
            rec.event_date = rec.date_begin

    # Approval tracking
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_date = fields.Datetime(string='Approved On', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('reference', '/') == '/':
            vals['reference'] = self.env['ir.sequence'].next_by_code('iic.event') or '/'
        rec = super().create(vals)
        rec._generate_qr_codes()
        return rec

    @api.depends('event_date')
    def _compute_quarter(self):
        for rec in self:
            if rec.event_date:
                month = rec.event_date.month
                if month in [1, 2, 3]:
                    rec.quarter = 'Q1'
                elif month in [4, 5, 6]:
                    rec.quarter = 'Q2'
                elif month in [7, 8, 9]:
                    rec.quarter = 'Q3'
                else:
                    rec.quarter = 'Q4'
            else:
                rec.quarter = False

    @api.depends('qr_token', 'qr_checkout_token')
    def _compute_qr_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        for rec in self:
            rec.qr_code_url = '%s/iic/attendance/checkin/%s' % (base_url, rec.qr_token or '')
            rec.qr_checkout_url = '%s/iic/attendance/checkout/%s' % (base_url, rec.qr_checkout_token or '')

    @api.depends('attendance_ids', 'media_ids', 'poster_ids', 'report_ids')
    def _compute_counts(self):
        for rec in self:
            rec.attendance_count = len(rec.attendance_ids)
            rec.media_count = len(rec.media_ids)
            rec.poster_count = len(rec.poster_ids)
            rec.report_count = len(rec.report_ids)

    @api.depends('attendance_ids', 'attendance_ids.status')
    def _compute_attendance_stats(self):
        for rec in self:
            total = len(rec.attendance_ids)
            present = len(rec.attendance_ids.filtered(lambda a: a.status == 'present'))
            rec.total_attendees = total
            rec.present_count = present
            rec.absent_count = total - present
            rec.participation_percentage = (present / total * 100) if total > 0 else 0.0

    def _generate_qr_codes(self):
        """Generate both check-in and check-out QR codes for the event."""
        for rec in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            # Check-in QR
            checkin_token = str(uuid.uuid4())
            rec.qr_token = checkin_token
            checkin_url = f"{base_url}/iic/attendance/checkin/{checkin_token}"
            rec.qr_code = self._make_qr_image(checkin_url)

            # Check-out QR
            checkout_token = str(uuid.uuid4())
            rec.qr_checkout_token = checkout_token
            checkout_url = f"{base_url}/iic/attendance/checkout/{checkout_token}"
            rec.qr_checkout_code = self._make_qr_image(checkout_url)

    def _make_qr_image(self, url):
        """Generate a QR code image and return as base64."""
        if not HAS_QRCODE:
            return False
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue())

    def action_regenerate_qr(self):
        self._generate_qr_codes()

    def action_set_poster_pending(self):
        self.iic_state = 'poster_pending'
        self._log_approval('Poster submitted for approval')

    def action_approve_poster(self):
        self.iic_state = 'poster_approved'
        self.approved_by = self.env.user
        self.approved_date = fields.Datetime.now()
        self._log_approval('Poster approved')

    def action_mark_ongoing(self):
        self.iic_state = 'ongoing'
        self._log_approval('Event marked as ongoing')
        self._create_calendar_event()

    def action_complete(self):
        self.iic_state = 'completed'
        self._log_approval('Event completed')

    def action_mark_completed(self):
        self.action_complete()

    def action_submit_report(self):
        self.iic_state = 'report_pending'
        self._log_approval('Event report submitted for review')

    def action_approve_report(self):
        self.iic_state = 'report_approved'
        self._log_approval('Event report approved')

    def action_archive_event(self):
        self.iic_state = 'archived'
        self._log_approval('Event archived')

    def action_cancel(self):
        self.iic_state = 'planning'
        self._log_approval('Event reset to planning')

    def _log_approval(self, action):
        self.env['iic.approval.log'].create({
            'event_id': self.id,
            'action': action,
            'user_id': self.env.user.id,
        })

    def _create_calendar_event(self):
        if not self.calendar_event_id and self.event_date:
            cal_event = self.env['calendar.event'].create({
                'name': f"[IIC] {self.name}",
                'start': self.event_date,
                'stop': self.date_end or self.event_date,
                'description': self.description or '',
                'location': self.venue or '',
            })
            self.calendar_event_id = cal_event.id

    def action_open_media(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Event Media',
            'res_model': 'iic.media',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }

    def action_open_posters(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Event Posters',
            'res_model': 'iic.poster',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }

    def action_open_reports(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Event Reports',
            'res_model': 'iic.event.report',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }

    def action_open_attendance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attendance',
            'res_model': 'iic.attendance',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }

    def action_view_attendance(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendance - {self.name}',
            'res_model': 'iic.attendance',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id},
        }

    def action_generate_report(self):
        if not self.report_ids:
            self.env['iic.event.report'].create({
                'event_id': self.id,
                'name': f"Report - {self.name}",
            })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Event Report',
            'res_model': 'iic.event.report',
            'view_mode': 'form',
            'res_id': self.report_ids[0].id,
        }

    def action_print_attendance_sheet(self):
        return self.env.ref(
            'university_management.action_report_iic_attendance_sheet'
        ).report_action(self)

    def action_print_attendance(self):
        return self.env.ref('university_management.action_report_iic_attendance_sheet').report_action(self)

    def action_print_event_report(self):
        if not self.report_ids:
            raise UserError(_('Please generate the event report first.'))
        return self.env.ref('university_management.action_report_iic_event_report').report_action(self.report_ids[0])