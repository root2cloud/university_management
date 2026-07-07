# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentSeatBlocking(models.Model):
    """
    Seat Blocking — the step BEFORE a full admission application.

    A prospective student can reserve a seat in a program by paying a
    token amount.  This creates a provisional record that:
      1. Reserves one seat in university.program.available_seats
      2. Captures the token payment reference
      3. Can later be converted into a full student.admission record

    State machine:
        draft  →  token_paid  →  converted
                    ↓
                 expired / cancelled
    """
    _name = 'student.seat.blocking'
    _description = 'Student Seat Blocking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'blocking_date desc, id desc'
    _rec_name = 'name'

    # ── Sequence Number ───────────────────────────────────────────────
    name = fields.Char(
        string='Blocking Reference',
        required=True,
        readonly=True,
        copy=False,
        default='/',
        help='Auto-generated blocking reference. Format: SB/YEAR/SEQUENCE',
    )

    # ── Prospective Student Details ───────────────────────────────────
    applicant_name = fields.Char(
        string='Applicant Name',
        required=True,
        tracking=True,
    )
    email = fields.Char(
        string='Email',
        required=True,
        tracking=True,
    )
    mobile = fields.Char(
        string='Mobile',
        required=True,
        tracking=True,
    )
    date_of_birth = fields.Date(string='Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')

    # ── Program Selection ─────────────────────────────────────────────
    program_id = fields.Many2one(
        'university.program',
        string='Program',
        required=True,
        tracking=True,
        index=True,
    )
    department_id = fields.Many2one(
        related='program_id.department_id',
        string='Department',
        store=True,
    )
    academic_year_id = fields.Many2one(
        'university.academic.year',
        string='Academic Year',
        required=True,
        tracking=True,
    )
    batch_id = fields.Many2one(
        'university.batch',
        string='Batch',
    )

    # ── Seat Availability Snapshot ────────────────────────────────────
    seats_available_at_booking = fields.Integer(
        string='Seats Available at Booking',
        readonly=True,
        help='Snapshot of available seats in the program at the time of blocking.',
    )

    # ── Blocking Details ──────────────────────────────────────────────
    blocking_date = fields.Date(
        string='Blocking Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    seat_expiry_date = fields.Date(
        string='Seat Valid Until',
        required=True,
        tracking=True,
        help='Date until which the blocked seat is reserved. '
             'After this date the blocking expires automatically.',
    )

    # ── Token Payment ─────────────────────────────────────────────────
    token_amount = fields.Monetary(
        string='Token Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Amount collected to reserve the seat. '
             'This is adjustable against the full admission fee.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    token_paid = fields.Boolean(
        string='Token Paid',
        default=False,
        tracking=True,
    )
    token_payment_mode = fields.Selection([
        ('online', 'Online Gateway'),
        ('upi', 'UPI'),
        ('neft', 'NEFT / RTGS'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('dd', 'Demand Draft'),
    ], string='Payment Mode', tracking=True)
    token_payment_ref = fields.Char(
        string='Payment Reference / UTR',
        tracking=True,
        help='UTR number for NEFT/UPI, cheque number for cheque payments, '
             'or transaction ID for online gateway.',
    )
    token_payment_date = fields.Date(
        string='Payment Date',
        tracking=True,
    )
    token_bank_name = fields.Char(
        string='Bank Name',
        help='Required for cheque / DD payments.',
    )
    token_cheque_number = fields.Char(string='Cheque / DD Number')
    token_cheque_date = fields.Date(string='Cheque / DD Date')
    is_adjustable = fields.Boolean(
        string='Adjustable Against Admission Fee',
        default=True,
        help='If checked, the token amount will be deducted from the full '
             'admission fee when the student is formally admitted.',
    )

    # ── Counselling Notes ─────────────────────────────────────────────
    counsellor_id = fields.Many2one(
        'res.users',
        string='Assigned Counsellor',
        tracking=True,
        default=lambda self: self.env.user,
    )
    counsellor_notes = fields.Text(
        string='Counsellor Notes',
        help='Notes from the counselling session that led to this seat blocking.',
    )
    entrance_exam_taken = fields.Boolean(string='Entrance Exam Taken', default=False)
    entrance_exam_name = fields.Char(string='Entrance Exam')
    entrance_exam_score = fields.Float(string='Score / Percentile')
    entrance_exam_rank = fields.Integer(string='Rank')
    entrance_exam_percentile = fields.Float(string='Percentile')

    # ── Status ────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('token_paid', 'Seat Blocked'),
        ('converted', 'Converted to Admission'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ── Linked Records ────────────────────────────────────────────────
    admission_id = fields.Many2one(
        'student.admission',
        string='Admission Application',
        readonly=True,
        help='Created automatically when the seat blocking is converted '
             'to a full admission application.',
    )

    # ── Computed ──────────────────────────────────────────────────────
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired',
        store=False,
    )
    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_is_expired',
        store=False,
    )

    # ── SQL Constraints ───────────────────────────────────────────────
    enquiry_id = fields.Many2one(
        'student.enquiry',
        string='Source Enquiry',
        ondelete='set null',
        index=True,
        help='The admission pipeline enquiry this seat blocking was created from.',
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Blocking Reference must be unique!'),
        ('token_amount_positive', 'CHECK(token_amount > 0)',
         'Token amount must be greater than zero!'),
    ]

    # ── Computed Methods ──────────────────────────────────────────────

    @api.depends('seat_expiry_date', 'state')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for record in self:
            if record.seat_expiry_date and record.state == 'token_paid':
                delta = (record.seat_expiry_date - today).days
                record.days_remaining = delta
                record.is_expired = delta < 0
            else:
                record.days_remaining = 0
                record.is_expired = False

    # ── Onchange ─────────────────────────────────────────────────────

    @api.onchange('program_id')
    def _onchange_program_id(self):
        """Snapshot available seats when program is selected."""
        if self.program_id:
            self.seats_available_at_booking = self.program_id.available_seats

    @api.onchange('blocking_date')
    def _onchange_blocking_date(self):
        """Default expiry to 30 days from blocking date."""
        if self.blocking_date and not self.seat_expiry_date:
            from datetime import timedelta
            self.seat_expiry_date = self.blocking_date + timedelta(days=30)

    # ── Constraints ───────────────────────────────────────────────────

    @api.constrains('program_id', 'state')
    def _check_seat_availability(self):
        """Prevent blocking if no seats available."""
        for record in self:
            if record.state == 'token_paid' and record.program_id:
                if record.program_id.available_seats <= 0:
                    raise ValidationError(_(
                        'No seats available in %s. Cannot block a seat.'
                    ) % record.program_id.name)

    @api.constrains('seat_expiry_date', 'blocking_date')
    def _check_expiry_date(self):
        for record in self:
            if record.seat_expiry_date and record.blocking_date:
                if record.seat_expiry_date <= record.blocking_date:
                    raise ValidationError(_(
                        'Seat expiry date must be after the blocking date.'
                    ))

    # ── ORM Overrides ─────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            year = fields.Date.today().year
            seq = self.env['ir.sequence'].next_by_code('student.seat.blocking') or '0001'
            vals['name'] = f'SB/{year}/{seq}'
        record = super().create(vals)
        # Link back to the source enquiry if created from one
        if record.enquiry_id and not record.enquiry_id.seat_blocking_id:
            record.enquiry_id.write({
                'seat_blocking_id': record.id,
                'state': 'seat_blocked',
            })
        return record

    # ── Business Actions ──────────────────────────────────────────────

    def action_confirm_token_payment(self):
        """
        Confirm token payment received and block the seat.

        Validates that payment details are filled, checks seat availability,
        and moves the record to 'token_paid' state.
        """
        self.ensure_one()

        if self.state != 'draft':
            raise ValidationError(_('Only draft records can be confirmed.'))

        if not self.token_paid:
            raise ValidationError(_(
                'Please mark the token payment as received before confirming.'
            ))
        if not self.token_payment_ref:
            raise ValidationError(_(
                'Payment Reference / UTR is required to confirm the seat blocking.'
            ))
        if not self.token_payment_mode:
            raise ValidationError(_('Please select a payment mode.'))

        # Re-check live seat availability
        if self.program_id.available_seats <= 0:
            raise ValidationError(_(
                'No seats available in %s at this time.'
            ) % self.program_id.name)

        self.write({
            'state': 'token_paid',
            'seats_available_at_booking': self.program_id.available_seats,
        })
        self.message_post(
            body=_(
                'Seat blocked for <b>%s</b> in <b>%s</b>. '
                'Token of ₹%s received via %s (Ref: %s). '
                'Seat valid until <b>%s</b>.'
            ) % (
                self.applicant_name,
                self.program_id.name,
                self.token_amount,
                dict(self._fields['token_payment_mode'].selection).get(
                    self.token_payment_mode, ''),
                self.token_payment_ref,
                self.seat_expiry_date,
            )
        )

    def action_convert_to_admission(self):
        """
        Convert this seat blocking into a full student.admission record.

        Pre-populates all available fields from the blocking record.
        The counsellor notes and token payment details are carried over
        into the admission's internal notes and payment fields.
        """
        self.ensure_one()

        if self.state != 'token_paid':
            raise ValidationError(_(
                'Only confirmed seat blockings (token paid) can be converted to admissions.'
            ))
        if self.admission_id:
            raise ValidationError(_(
                'This seat blocking has already been converted to admission %s.'
            ) % self.admission_id.name)

        # Check expiry
        if self.is_expired:
            raise ValidationError(_(
                'This seat blocking expired on %s. '
                'Please renew or create a new blocking.'
            ) % self.seat_expiry_date)

        # Build internal notes — carry over counsellor notes + token info
        internal_note_parts = []
        if self.counsellor_notes:
            internal_note_parts.append(f'Counsellor Notes: {self.counsellor_notes}')
        internal_note_parts.append(
            f'Seat Blocking: {self.name} | '
            f'Token: ₹{self.token_amount} via {self.token_payment_mode or "-"} '
            f'(Ref: {self.token_payment_ref or "-"})'
        )
        if self.is_adjustable:
            internal_note_parts.append(
                f'Token amount of ₹{self.token_amount} is adjustable against admission fee.'
            )

        admission_vals = {
            'applicant_name': self.applicant_name,
            'email': self.email,
            'mobile': self.mobile,
            'date_of_birth': self.date_of_birth or fields.Date.today(),
            'gender': self.gender or 'male',
            'program_id': self.program_id.id,
            'academic_year_id': self.academic_year_id.id,
            'batch_id': self.batch_id.id if self.batch_id else False,
            'previous_qualification': self.enquiry_id.previous_qualification or '',
            'previous_school': self.enquiry_id.previous_school or '',
            'previous_board': '', # Not available in enquiry or seat blocking
            'previous_percentage': self.enquiry_id.previous_percentage or 0.0,
            'previous_year': self.enquiry_id.previous_year or fields.Date.today().year,
            'current_address': self.enquiry_id.city or '', # Using city from enquiry as current address
            'permanent_address': self.enquiry_id.city or '', # Using city from enquiry as permanent address
            'father_name': '', # Not available in enquiry or seat blocking
            'mother_name': '', # Not available in enquiry or seat blocking
            'admission_category': 'general',
            'entrance_exam_taken': self.entrance_exam_taken,
            'entrance_exam_name': self.entrance_exam_name or '',
            'entrance_exam_score': self.entrance_exam_score or 0.0,
            'entrance_exam_rank': self.entrance_exam_rank or 0,
            'entrance_exam_percentile': self.entrance_exam_percentile or 0.0,
            'state_id': self.enquiry_id.state_id.id if self.enquiry_id.state_id else False,
            # Token payment carried forward as application fee paid
            'application_fee': self.token_amount,
            'application_fee_paid': True,
            'application_payment_ref': self.token_payment_ref,
            'application_payment_date': self.token_payment_date or fields.Date.today(),
            'internal_notes': '\n'.join(internal_note_parts),
            'state': 'draft',
        }

        admission = self.env['student.admission'].create(admission_vals)

        self.write({
            'state': 'converted',
            'admission_id': admission.id,
        })
        self.message_post(
            body=_(
                'Seat blocking converted to admission application <b>%s</b>. '
                'Token amount of ₹%s %s.'
            ) % (
                admission.name,
                self.token_amount,
                'will be adjusted against the admission fee' if self.is_adjustable
                else 'is non-adjustable',
            )
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Application'),
            'res_model': 'student.admission',
            'res_id': admission.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_mark_expired(self):
        """Manually mark a seat blocking as expired."""
        self.ensure_one()
        if self.state not in ('draft', 'token_paid'):
            raise ValidationError(_(
                'Only active seat blockings can be expired.'
            ))
        self.write({'state': 'expired'})
        self.message_post(
            body=_('Seat blocking marked as expired. The reserved seat has been released.')
        )

    def action_cancel(self):
        """Cancel the seat blocking and release the seat."""
        self.ensure_one()
        if self.state in ('converted', 'cancelled'):
            raise ValidationError(_(
                'Converted or already cancelled records cannot be cancelled.'
            ))
        self.write({'state': 'cancelled'})
        self.message_post(
            body=_('Seat blocking cancelled. The reserved seat has been released.')
        )

    def action_reset_to_draft(self):
        """Reset back to draft for correction (admin only)."""
        self.ensure_one()
        if self.state == 'converted':
            raise ValidationError(_(
                'A converted seat blocking cannot be reset. '
                'Cancel the linked admission first.'
            ))
        self.write({'state': 'draft'})

    def action_view_admission(self):
        """Open the linked admission application."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Admission Application'),
            'res_model': 'student.admission',
            'res_id': self.admission_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ── Scheduled Action ──────────────────────────────────────────────

    @api.model
    def _cron_expire_seat_blockings(self):
        """
        Scheduled action: auto-expire seat blockings past their expiry date.
        Run daily via ir.cron.
        """
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'token_paid'),
            ('seat_expiry_date', '<', today),
        ])
        for record in expired:
            record.write({'state': 'expired'})
            record.message_post(
                body=_(
                    'Seat blocking automatically expired. '
                    'Expiry date %s has passed.'
                ) % record.seat_expiry_date
            )
        if expired:
            return f'{len(expired)} seat blocking(s) expired.'
        return 'No seat blockings to expire.'