# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date


class StudentEnquiry(models.Model):
    """
    Student Enquiry — standalone admission pipeline model.

    Replaces the previous crm.lead inheritance approach.
    100% university-specific — no sales CRM baggage.

    Pipeline states:
        new → contacted → counselling_scheduled → interested
            → seat_blocked → admitted → lost
    """
    _name = 'student.enquiry'
    _description = 'Student Enquiry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'applicant_name'

    # ── Identity ─────────────────────────────────────────────────────
    applicant_name = fields.Char(
        string='Applicant Name', required=True, tracking=True, index=True,
    )
    mobile = fields.Char(string='Mobile', required=True, tracking=True)
    email = fields.Char(string='Email', tracking=True)

    # ── Pipeline ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('new', 'New Enquiry'),
        ('contacted', 'Contacted'),
        ('counselling_scheduled', 'Counselling Scheduled'),
        ('interested', 'Interested'),
        ('seat_blocked', 'Seat Blocked'),
        ('admitted', 'Admitted'),
        ('lost', 'Not Interested'),
    ], string='Status', default='new', tracking=True, index=True)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Hot'),
        ('2', 'Very Hot'),
    ], string='Priority', default='0')

    counsellor_id = fields.Many2one(
        'res.users', string='Counsellor',
        default=lambda self: self.env.user,
        tracking=True, index=True,
    )

    # ── Program of Interest ───────────────────────────────────────────
    program_id = fields.Many2one(
        'university.program', string='Program of Interest',
        tracking=True, index=True,
    )
    department_id = fields.Many2one(
        'university.department', string='Department',
        related='program_id.department_id', store=True,
    )
    alternate_program_id = fields.Many2one(
        'university.program', string='Alternate Program',
    )
    academic_year_id = fields.Many2one(
        'university.academic.year', string='Target Academic Year',
        tracking=True,
    )
    batch_id = fields.Many2one(
        'university.batch', string='Batch',
        tracking=True,
    )

    # ── Personal Details ──────────────────────────────────────────────
    date_of_birth = fields.Date(string='Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    city = fields.Char(string='City / Town')
    state_id = fields.Many2one('res.country.state', string='State')

    # ── Previous Education ────────────────────────────────────────────
    previous_qualification = fields.Selection([
        ('10th', '10th / SSLC'),
        ('12th', '12th / PUC / HSC'),
        ('diploma', 'Diploma'),
        ('ug', 'Under Graduate'),
        ('pg', 'Post Graduate'),
        ('other', 'Other'),
    ], string='Current Qualification')
    previous_school = fields.Char(
        string='School / College', placeholder='School / College name',
    )
    previous_percentage = fields.Float(string='Percentage / CGPA')
    previous_year = fields.Integer(string='Year of Passing')

    # ── Entrance Exams ────────────────────────────────────────────────
    entrance_exam_taken = fields.Boolean(string='Entrance Exam Taken', default=False)
    entrance_exam_name = fields.Char(
        string='Exam Name', placeholder='JEE / KCET / COMEDK / NEET',
    )
    entrance_exam_score = fields.Float(string='Score')
    entrance_exam_rank = fields.Integer(string='Rank')
    entrance_exam_percentile = fields.Float(string='Percentile')

    # ── Source / Marketing ────────────────────────────────────────────
    source_id = fields.Many2one('utm.source', string='Lead Source')
    medium_id = fields.Many2one('utm.medium', string='Medium')
    referral_name = fields.Char(
        string='Referred By',
        placeholder='Name of referring student / person',
    )

    # ── Quick Counselling Date ────────────────────────────────────────
    counselling_date = fields.Datetime(string='Counselling Scheduled On')
    counselling_mode = fields.Selection([
        ('in_person', 'In Person'),
        ('phone', 'Phone'),
        ('video', 'Video Call'),
        ('whatsapp', 'WhatsApp'),
    ], string='Counselling Mode')
    counselling_done_date = fields.Date(
        string='Counselling Done On', readonly=True,
    )

    # ── Follow-up ─────────────────────────────────────────────────────
    follow_up_date = fields.Date(string='Follow-up Date', tracking=True)

    # ── Related Records ───────────────────────────────────────────────
    seat_blocking_id = fields.Many2one(
        'student.seat.blocking', string='Seat Blocking',
        readonly=True, copy=False,
    )
    admission_id = fields.Many2one(
        'student.admission', string='Admission Application',
        readonly=True, copy=False,
    )

    # ── Sessions ─────────────────────────────────────────────────────
    session_ids = fields.One2many(
        'student.counselling.session', 'enquiry_id',
        string='Counselling Sessions',
    )
    session_count = fields.Integer(
        string='Sessions', compute='_compute_session_count', store=True,
    )
    completed_session_count = fields.Integer(
        string='Completed Sessions', compute='_compute_session_count', store=True,
    )

    # ── Internal Notes ────────────────────────────────────────────────
    notes = fields.Text(string='Internal Notes')

    # ── Computed ─────────────────────────────────────────────────────

    @api.depends('session_ids', 'session_ids.state')
    def _compute_session_count(self):
        for rec in self:
            sessions = rec.session_ids
            rec.session_count = len(sessions)
            rec.completed_session_count = len(
                sessions.filtered(lambda s: s.state == 'completed')
            )

    # ── Onchange ─────────────────────────────────────────────────────

    @api.onchange('source_id')
    def _onchange_source(self):
        if self.source_id and 'referral' not in (self.source_id.name or '').lower():
            self.referral_name = False

    # ── State Actions ─────────────────────────────────────────────────

    def action_contacted(self):
        self.write({'state': 'contacted'})

    def action_mark_interested(self):
        self.write({'state': 'interested'})

    def action_mark_won(self):
        self.write({'state': 'admitted'})
        self.message_post(body=_('Enquiry marked as Admitted.'))

    def action_mark_lost(self):
        self.write({'state': 'lost'})
        self.message_post(body=_('Enquiry marked as Not Interested.'))

    def action_reset_to_new(self):
        self.write({'state': 'new'})

    # ── Session Actions ───────────────────────────────────────────────

    def action_schedule_counselling(self):
        """Open a new counselling session form pre-linked to this enquiry."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Counselling Session'),
            'res_model': 'student.counselling.session',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_enquiry_id': self.id,
                'default_counsellor_id': self.counsellor_id.id,
                'default_program_discussed_id': self.program_id.id
                    if self.program_id else False,
                'default_qualification_discussed': self.previous_qualification,
                'default_percentage_discussed': self.previous_percentage,
                'default_entrance_exam_name': self.entrance_exam_name,
                'default_entrance_exam_score': self.entrance_exam_score,
            },
        }

    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Counselling Sessions — %s') % self.applicant_name,
            'res_model': 'student.counselling.session',
            'view_mode': 'list,form,calendar',
            'domain': [('enquiry_id', '=', self.id)],
            'context': {
                'default_enquiry_id': self.id,
                'default_counsellor_id': self.counsellor_id.id,
                'default_program_discussed_id': self.program_id.id
                    if self.program_id else False,
            },
        }

    # ── Convert Actions ───────────────────────────────────────────────

    def action_convert_to_seat_blocking(self):
        """
        Open a new seat blocking form pre-filled from the enquiry.
        We do NOT create the record here — the user must fill in
        token amount and expiry date before saving.
        Once saved, the seat blocking links back to this enquiry via enquiry_id.
        """
        self.ensure_one()
        if self.seat_blocking_id:
            raise ValidationError(_(
                'A seat blocking already exists for this enquiry: %s'
            ) % self.seat_blocking_id.name)
        if not self.program_id:
            raise ValidationError(_(
                'Please select a Program of Interest before blocking a seat.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Seat Blocking'),
            'res_model': 'student.seat.blocking',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_applicant_name': self.applicant_name,
                'default_email': self.email or '',
                'default_mobile': self.mobile,
                'default_date_of_birth': self.date_of_birth or False,
                'default_gender': self.gender or False,
                'default_program_id': self.program_id.id,
                'default_academic_year_id': self.academic_year_id.id
                    if self.academic_year_id else False,
                'default_batch_id': self.batch_id.id if self.batch_id else False,
                'default_counsellor_id': self.counsellor_id.id,
                'default_entrance_exam_taken': self.entrance_exam_taken,
                'default_entrance_exam_name': self.entrance_exam_name or '',
                'default_entrance_exam_score': self.entrance_exam_score or 0.0,
                'default_entrance_exam_rank': self.entrance_exam_rank or 0,
                'default_entrance_exam_percentile': self.entrance_exam_percentile or 0.0,
                'default_enquiry_id': self.id,
            },
        }

    def action_convert_to_admission(self):
        self.ensure_one()
        if self.admission_id:
            raise ValidationError(_(
                'An admission application already exists: %s'
            ) % self.admission_id.name)
        if not self.program_id:
            raise ValidationError(_(
                'Please select a Program of Interest before creating an admission.'
            ))
        admission = self.env['student.admission'].create({
            'applicant_name': self.applicant_name,
            'email': self.email or '',
            'mobile': self.mobile,
            'date_of_birth': self.date_of_birth or date.today(),
            'gender': self.gender or 'male',
            'program_id': self.program_id.id,
            'academic_year_id': self.academic_year_id.id
                if self.academic_year_id else False,
            'previous_qualification': self.previous_qualification or '',
            'previous_school': self.previous_school or '',
            'previous_board': '',
            'previous_percentage': self.previous_percentage or 0.0,
            'previous_year': self.previous_year or date.today().year,
            'current_address': '',
            'permanent_address': '',
            'father_name': '',
            'mother_name': '',
            'admission_category': 'general',
            'entrance_exam_taken': self.entrance_exam_taken,
            'entrance_exam_name': self.entrance_exam_name or '',
            'entrance_exam_score': self.entrance_exam_score or 0.0,
            'entrance_exam_rank': self.entrance_exam_rank or 0,
            'entrance_exam_percentile': self.entrance_exam_percentile or 0.0,
            'state_id': self.state_id.id if self.state_id else False,
        })
        self.write({
            'admission_id': admission.id,
            'state': 'admitted',
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Application'),
            'res_model': 'student.admission',
            'res_id': admission.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_seat_blocking(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seat Blocking'),
            'res_model': 'student.seat.blocking',
            'res_id': self.seat_blocking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_admission(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Application'),
            'res_model': 'student.admission',
            'res_id': self.admission_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Cron ──────────────────────────────────────────────────────────

    @api.model
    def _cron_remind_follow_ups(self):
        """Daily: post follow-up reminder on overdue enquiries."""
        today = date.today()
        due = self.search([
            ('follow_up_date', '=', today),
            ('state', 'not in', ['admitted', 'lost']),
        ])
        for rec in due:
            rec.message_post(
                body=_('Follow-up due today for <b>%s</b>. Counsellor: %s.')
                % (rec.applicant_name, rec.counsellor_id.name or '—')
            )
        return f'{len(due)} follow-up reminder(s) posted.'