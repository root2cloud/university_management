# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class FacultyAttendanceRegularization(models.Model):
    """
    Faculty Attendance Regularization System.

    Allows faculty to raise correction requests for attendance discrepancies
    (missed punch, biometric failure, off-campus duty, etc.).

    Workflow:
        Draft → Submitted → HOD Approved → HR Approved → Attendance Updated
                                        ↘ Rejected

    Regularization Window:
        Corrections are allowed only up to the 3rd of the following month.
        After that the window is locked and no corrections can be submitted.
    """
    _name = 'faculty.attendance.regularization'
    _description = 'Faculty Attendance Regularization'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, faculty_id'

    name = fields.Char(
        string='Request Number',
        required=True, readonly=True, copy=False, default='/',
    )

    # ── Faculty & Date ────────────────────────────────────────────────
    faculty_id = fields.Many2one(
        'faculty.faculty', string='Faculty',
        required=True, tracking=True, index=True,
    )
    employee_id = fields.Many2one(
        related='faculty_id.employee_id', string='Employee', store=True,
    )
    department_id = fields.Many2one(
        related='faculty_id.department_id', string='Department', store=True,
    )
    date = fields.Date(
        string='Attendance Date', required=True, tracking=True, index=True,
    )

    # ── Existing Attendance ───────────────────────────────────────────
    attendance_id = fields.Many2one(
        'faculty.attendance', string='Existing Attendance Record',
        domain="[('faculty_id', '=', faculty_id)]",
        help='Link to the attendance record being corrected.',
    )
    existing_check_in = fields.Datetime(
        string='Current Check In',
        related='attendance_id.check_in', readonly=True,
    )
    existing_check_out = fields.Datetime(
        string='Current Check Out',
        related='attendance_id.check_out', readonly=True,
    )
    existing_state = fields.Selection(
        related='attendance_id.state', string='Current Status', readonly=True,
    )

    # ── Corrected Values ──────────────────────────────────────────────
    corrected_check_in = fields.Datetime(
        string='Correct Check In', required=True, tracking=True,
    )
    corrected_check_out = fields.Datetime(
        string='Correct Check Out', tracking=True,
    )

    # ── Reason ────────────────────────────────────────────────────────
    reason = fields.Selection([
        ('biometric_failure',  'Biometric Device Failure'),
        ('forgotten_punch',    'Forgotten to Punch'),
        ('official_duty',      'Official Duty Outside Campus'),
        ('meeting',            'Meeting / Event Before Punching'),
        ('system_error',       'System / Technical Error'),
        ('field_visit',        'Field Visit / Industrial Visit'),
        ('other',              'Other'),
    ], string='Reason', required=True, tracking=True)

    reason_details = fields.Text(string='Reason Details', tracking=True)
    supporting_document = fields.Binary(string='Supporting Document')
    supporting_document_name = fields.Char(string='Document Name')

    # ── Regularization Window ─────────────────────────────────────────
    window_deadline = fields.Date(
        string='Regularization Deadline',
        compute='_compute_window_deadline', store=True,
        help='Corrections allowed until 3rd of the following month.',
    )
    is_window_open = fields.Boolean(
        string='Window Open',
        compute='_compute_is_window_open',
        help='False if the regularization window has closed.',
    )

    # ── Approval ──────────────────────────────────────────────────────
    hod_id = fields.Many2one('res.users', string='HOD', readonly=True)
    hod_approval_date = fields.Date(string='HOD Approval Date', readonly=True)
    hod_remarks = fields.Text(string='HOD Remarks')

    hr_approver_id = fields.Many2one('res.users', string='HR Approver', readonly=True)
    hr_approval_date = fields.Date(string='HR Approval Date', readonly=True)
    hr_remarks = fields.Text(string='HR Remarks')

    rejection_reason = fields.Text(string='Rejection Reason')

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',        'Draft'),
        ('submitted',    'Submitted'),
        ('hod_approved', 'HOD Approved'),
        ('approved',     'HR Approved'),
        ('rejected',     'Rejected'),
        ('cancelled',    'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ── Audit ─────────────────────────────────────────────────────────
    applied_by = fields.Many2one(
        'res.users', string='Applied By',
        default=lambda self: self.env.user, readonly=True,
    )
    applied_date = fields.Date(
        string='Applied On',
        default=fields.Date.today, readonly=True,
    )

    _sql_constraints = [
        ('unique_request', 'unique(faculty_id, date)',
         'A regularization request already exists for this faculty on this date!'),
    ]

    # ── ORM ───────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'faculty.attendance.regularization') or '/'
        return super().create(vals)

    # ── Computed ──────────────────────────────────────────────────────

    @api.depends('date')
    def _compute_window_deadline(self):
        """Deadline = 3rd of the month following the attendance date."""
        for rec in self:
            if rec.date:
                att_date = rec.date
                # First day of next month
                if att_date.month == 12:
                    next_month_first = att_date.replace(
                        year=att_date.year + 1, month=1, day=1)
                else:
                    next_month_first = att_date.replace(
                        month=att_date.month + 1, day=1)
                rec.window_deadline = next_month_first.replace(day=3)
            else:
                rec.window_deadline = False

    @api.depends('window_deadline')
    def _compute_is_window_open(self):
        today = date.today()
        for rec in self:
            rec.is_window_open = bool(
                rec.window_deadline and today <= rec.window_deadline
            )

    # ── Constraints ───────────────────────────────────────────────────

    @api.constrains('corrected_check_in', 'corrected_check_out')
    def _check_times(self):
        for rec in self:
            if rec.corrected_check_in and rec.corrected_check_out:
                if rec.corrected_check_out <= rec.corrected_check_in:
                    raise ValidationError(
                        _('Correct Check Out must be after Correct Check In.'))

    @api.constrains('date')
    def _check_future_date(self):
        for rec in self:
            if rec.date and rec.date > date.today():
                raise ValidationError(
                    _('Cannot raise regularization for a future date.'))

    # ── Actions ───────────────────────────────────────────────────────

    def action_submit(self):
        """Faculty submits the regularization request."""
        for rec in self:
            if not rec.is_window_open:
                raise ValidationError(
                    _('Regularization window is closed for %s. '
                      'Deadline was %s.') % (rec.date, rec.window_deadline)
                )
            rec.write({
                'state': 'submitted',
                'applied_by': self.env.user.id,
                'applied_date': date.today(),
            })

            # Resolve HOD user via department -> hod_id -> user_id
            hod_user = rec.faculty_id.department_id.hod_id.user_id

            rec.message_post(
                body=_('Regularization request submitted by %s. Pending HOD approval.')
                % self.env.user.name,
                partner_ids=hod_user.partner_id.ids if hod_user else [],
            )

            # Create a To-Do activity assigned to the HOD
            if hod_user:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Attendance Regularization Approval Required'),
                    note=_(
                        'Faculty %s has submitted a regularization request for %s. '
                        'Reason: %s. '
                        'Please open the record and click the HOD APPROVE button to approve, '
                        'or the REJECT button to reject. '
                        'Do NOT use Mark Done on this activity — use the buttons on the form.'
                    ) % (rec.faculty_id.name, rec.date, dict(rec._fields['reason'].selection).get(rec.reason, rec.reason)),
                    user_id=hod_user.id,
                )

    def action_hod_approve(self):
        """HOD approves the request and forwards to HR."""
        self.write({
            'state': 'hod_approved',
            'hod_id': self.env.user.id,
            'hod_approval_date': date.today(),
        })

        # Mark HOD activity as done and notify HR group
        self.activity_feedback(
            ['mail.mail_activity_data_todo'],
            feedback=_('Approved by HOD %s.') % self.env.user.name,
        )

        # Notify all users in HR Manager group
        hr_group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
        hr_partners = hr_group.users.mapped('partner_id') if hr_group else []

        self.message_post(
            body=_('HOD approved by %s. Forwarded to HR for final approval.') % self.env.user.name,
            partner_ids=[p.id for p in hr_partners],
        )

        # Create activity for HR
        for rec in self:
            if hr_group and hr_group.users:
                hr_user = hr_group.users[0]
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Attendance Regularization - HR Approval Required'),
                    note=_(
                        'HOD has approved the regularization request for %s on %s. '
                        'Please do the final HR approval.'
                    ) % (rec.faculty_id.name, rec.date),
                    user_id=hr_user.id,
                )

    def action_hr_approve(self):
        """
        HR final approval.
        Updates the linked faculty.attendance record with corrected times
        and re-runs the attendance classification engine.
        """
        for rec in self:
            rec.write({
                'state': 'approved',
                'hr_approver_id': self.env.user.id,
                'hr_approval_date': date.today(),
            })
            rec._apply_correction()
            rec.message_post(
                body=_('HR approved by %s. Attendance record updated.')
                % self.env.user.name
            )

    def action_reject(self):
        """Reject the regularization request."""
        self.write({'state': 'rejected'})
        self.message_post(
            body=_('Regularization request rejected. Reason: %s')
            % (self.rejection_reason or 'Not specified')
        )

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    # ── Core Correction Logic ─────────────────────────────────────────

    def _apply_correction(self):
        """
        Apply the corrected check_in / check_out to faculty.attendance
        and re-run the classification engine.

        All changes are logged for audit trail via mail.thread tracking.
        """
        self.ensure_one()
        # Use sudo() for all attendance writes so this works regardless of
        # the calling user's access level (HR approving regularization,
        # server record rules on hr.attendance, etc.)
        FacultyAttendance = self.env['faculty.attendance'].sudo()
        HrAttendance = self.env['hr.attendance'].sudo()

        if self.attendance_id:
            attendance = self.attendance_id.sudo()
        else:
            attendance = FacultyAttendance.search([
                ('faculty_id', '=', self.faculty_id.id),
                ('date', '=', self.date),
            ], limit=1)

        hr_att_id = attendance.hr_attendance_id.id if attendance and attendance.hr_attendance_id else False

        if attendance:
            # Write corrected times — _sync_hr_attendance will also run sudo internally
            attendance.write({
                'check_in': self.corrected_check_in,
                'check_out': self.corrected_check_out or False,
            })
            # Also directly update the linked hr.attendance to be safe
            if hr_att_id:
                HrAttendance.browse(hr_att_id).write({
                    'check_in': self.corrected_check_in,
                    'check_out': self.corrected_check_out or False,
                })
            # Re-run the classification engine via sudo
            FacultyAttendance.process_punch(
                faculty_id=self.faculty_id.id,
                check_in=self.corrected_check_in,
                check_out=self.corrected_check_out or False,
                hr_attendance_id=hr_att_id,
            )
        else:
            # No existing record — create via engine (sudo inside process_punch)
            FacultyAttendance.process_punch(
                faculty_id=self.faculty_id.id,
                check_in=self.corrected_check_in,
                check_out=self.corrected_check_out or False,
            )

        # Link this regularization to the attendance record for audit
        updated = FacultyAttendance.search([
            ('faculty_id', '=', self.faculty_id.id),
            ('date', '=', self.date),
        ], limit=1)
        if updated:
            updated.message_post(
                body=_(
                    'Attendance corrected via Regularization Request %s '
                    'approved by HR (%s) on %s.'
                ) % (self.name, self.env.user.name, date.today())
            )