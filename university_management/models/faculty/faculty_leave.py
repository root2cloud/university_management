# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime


class FacultyLeave(models.Model):
    _name = 'faculty.leave'
    _description = 'Faculty Leave Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'

    name = fields.Char(string='Leave Number', required=True, readonly=True,
                       copy=False, default='/')

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True, index=True)
    employee_id = fields.Many2one(related='faculty_id.employee_id', string='Employee', store=True)
    department_id = fields.Many2one(related='faculty_id.department_id',
                                    string='Department', store=True)

    leave_type = fields.Selection([
        ('casual',        'Casual Leave'),
        ('sick',          'Sick Leave'),
        ('earned',        'Earned Leave'),
        ('maternity',     'Maternity Leave'),
        ('paternity',     'Paternity Leave'),
        ('compensatory',  'Compensatory Off'),
        ('unpaid',        'Leave Without Pay'),
        ('sabbatical',    'Sabbatical Leave'),
        ('study',         'Study Leave'),
        ('emergency',     'Emergency Leave'),
    ], string='Leave Type', required=True, tracking=True)

    date_from = fields.Date(string='From Date', required=True, tracking=True)
    date_to = fields.Date(string='To Date', required=True, tracking=True)
    number_of_days = fields.Float(string='Number of Days', compute='_compute_days', store=True)
    half_day = fields.Boolean(string='Half Day')
    half_day_type = fields.Selection([
        ('first_half',  'First Half'),
        ('second_half', 'Second Half'),
    ], string='Half Day Type')

    reason = fields.Text(string='Reason', required=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Supporting Documents')

    substitute_required = fields.Boolean(string='Substitute Required', default=True)
    substitute_faculty_id = fields.Many2one('faculty.faculty', string='Substitute Faculty')
    substitute_arrangement = fields.Text(string='Substitute Arrangement Details')

    approved_by_hod = fields.Many2one('res.users', string='Approved by HOD', readonly=True)
    hod_approval_date = fields.Date(string='HOD Approval Date', readonly=True)
    approved_by_principal = fields.Many2one('res.users', string='Approved by Principal', readonly=True)
    principal_approval_date = fields.Date(string='Principal Approval Date', readonly=True)

    state = fields.Selection([
        ('draft',        'Draft'),
        ('submitted',    'Submitted'),
        ('hod_approved', 'HOD Approved'),
        ('approved',     'Approved'),
        ('rejected',     'Rejected'),
        ('cancelled',    'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    rejection_reason = fields.Text(string='Rejection Reason')
    notes = fields.Text(string='Notes')

    # ── Link to Odoo HR Leave ─────────────────────────────────────────────
    hr_leave_id = fields.Many2one(
        'hr.leave', string='HR Leave',
        copy=False, ondelete='set null'
    )

    _LEAVE_TYPE_XMLIDS = {
        'casual':       'university_management.hr_leave_type_casual',
        'sick':         'university_management.hr_leave_type_sick',
        'earned':       'university_management.hr_leave_type_earned',
        'maternity':    'university_management.hr_leave_type_maternity',
        'paternity':    'university_management.hr_leave_type_paternity',
        'compensatory': 'university_management.hr_leave_type_compensatory',
        'unpaid':       'university_management.hr_leave_type_unpaid',
        'sabbatical':   'university_management.hr_leave_type_sabbatical',
        'study':        'university_management.hr_leave_type_study',
        'emergency':    'university_management.hr_leave_type_emergency',
    }

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Leave Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('faculty.leave') or '/'
        return super().create(vals)

    @api.depends('date_from', 'date_to', 'half_day')
    def _compute_days(self):
        for record in self:
            if record.date_from and record.date_to:
                days = (record.date_to - record.date_from).days + 1
                record.number_of_days = days / 2 if record.half_day else days
            else:
                record.number_of_days = 0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(_('To Date must be after From Date!'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_hod_approve(self):
        self.write({
            'state': 'hod_approved',
            'approved_by_hod': self.env.user.id,
            'hod_approval_date': fields.Date.today(),
        })

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by_principal': self.env.user.id,
            'principal_approval_date': fields.Date.today(),
        })
        self._sync_hr_leave()
        self._create_attendance_records()

    def action_reject(self):
        self.write({'state': 'rejected'})
        for rec in self:
            if rec.hr_leave_id and rec.hr_leave_id.state not in ('refuse', 'cancel'):
                try:
                    rec.hr_leave_id.action_refuse()
                except Exception:
                    pass

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        for rec in self:
            if rec.hr_leave_id and rec.hr_leave_id.state not in ('refuse', 'cancel'):
                try:
                    rec.hr_leave_id.action_refuse()
                except Exception:
                    pass

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _get_hr_leave_type(self, leave_type_key):
        xmlid = self._LEAVE_TYPE_XMLIDS.get(leave_type_key)
        if not xmlid:
            return False
        try:
            return self.env.ref(xmlid)
        except ValueError:
            return False

    def _sync_hr_leave(self):
        HrLeave = self.env['hr.leave'].sudo()
        for rec in self:
            if not rec.employee_id or not rec.leave_type:
                continue
            leave_type = rec._get_hr_leave_type(rec.leave_type)
            if not leave_type:
                continue
            date_from_dt = datetime.combine(rec.date_from, datetime.min.time()).replace(hour=8)
            date_to_dt = datetime.combine(rec.date_to, datetime.min.time()).replace(hour=17)
            vals = {
                'employee_id': rec.employee_id.id,
                'holiday_status_id': leave_type.id,
                'date_from': date_from_dt,
                'date_to': date_to_dt,
                'name': rec.reason or rec.name,
            }
            if rec.hr_leave_id:
                if rec.hr_leave_id.state == 'draft':
                    rec.hr_leave_id.write(vals)
            else:
                rec.hr_leave_id = HrLeave.create(vals).id
            if rec.hr_leave_id and rec.hr_leave_id.state in ('draft', 'confirm'):
                try:
                    rec.hr_leave_id.action_approve()
                except Exception:
                    pass

    def _create_attendance_records(self):
        AttendanceObj = self.env['faculty.attendance']
        current_date = self.date_from
        while current_date <= self.date_to:
            existing = AttendanceObj.search([
                ('faculty_id', '=', self.faculty_id.id),
                ('date', '=', current_date),
            ], limit=1)
            if not existing:
                AttendanceObj.create({
                    'faculty_id': self.faculty_id.id,
                    'date': current_date,
                    'state': 'half_day' if self.half_day else 'on_leave',
                    'leave_id': self.id,
                })
            current_date = current_date + timedelta(days=1)

    @api.model
    def update_leave_balances(self):
        today = fields.Date.today()
        if today.month >= 4:
            year_start = today.replace(month=4, day=1)
            year_end = today.replace(year=today.year + 1, month=3, day=31)
        else:
            year_start = today.replace(year=today.year - 1, month=4, day=1)
            year_end = today.replace(month=3, day=31)

        approved_leaves = self.search([
            ('state', '=', 'approved'),
            ('date_from', '>=', year_start),
            ('date_to', '<=', year_end),
        ])
        faculty_leave_summary = {}
        for leave in approved_leaves:
            fid = leave.faculty_id.id
            if fid not in faculty_leave_summary:
                faculty_leave_summary[fid] = {}
            ltype = leave.leave_type
            faculty_leave_summary[fid][ltype] = (
                faculty_leave_summary[fid].get(ltype, 0.0) + leave.number_of_days
            )
        for faculty_id, balances in faculty_leave_summary.items():
            last_leave = self.search([
                ('faculty_id', '=', faculty_id),
                ('state', '=', 'approved'),
            ], limit=1, order='date_from desc')
            if last_leave:
                balance_lines = '\n'.join(
                    '  • %s: %.1f day(s)' % (
                        dict(self._fields['leave_type'].selection).get(k, k), v)
                    for k, v in sorted(balances.items())
                )
                last_leave.message_post(
                    body=_('<b>Monthly Leave Balance Update</b><br/>Academic Year: %s to %s<br/><pre>%s</pre>') % (
                        year_start, year_end, balance_lines),
                    subtype_xmlid='mail.mt_note',
                )
        return True