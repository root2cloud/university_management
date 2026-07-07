# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentAssignment(models.Model):
    _name = 'student.assignment'
    _description = 'Student Assignment / Homework'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'deadline asc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Title', required=True, tracking=True)
    code = fields.Char(string='Assignment Code', copy=False, readonly=True)
    active = fields.Boolean(string='Active', default=True)

    assignment_type = fields.Selection([
        ('assignment', 'Assignment'),
        ('homework', 'Homework'),
        ('project', 'Mini Project'),
        ('lab', 'Lab Work'),
        ('quiz', 'Quiz'),
        ('case_study', 'Case Study'),
    ], string='Type', required=True, default='assignment', tracking=True)

    # Academic Details
    academic_year_id = fields.Many2one(
        'university.academic.year', string='Academic Year',
        required=True, tracking=True, index=True)
    semester_id = fields.Many2one(
        'university.semester', string='Semester',
        required=True, tracking=True, index=True)
    department_id = fields.Many2one(
        'university.department', string='Department', index=True)
    program_id = fields.Many2one(
        'university.program', string='Program', index=True)
    batch_id = fields.Many2one(
        'university.batch', string='Batch', index=True)
    subject_id = fields.Many2one(
        'university.subject', string='Subject',
        required=True, tracking=True, index=True)

    # FIXED: correct model name is faculty.faculty
    faculty_id = fields.Many2one(
        'faculty.faculty', string='Assigned By',
        required=True, tracking=True, index=True)

    # Dates
    assigned_date = fields.Date(
        string='Assigned Date', default=fields.Date.today, required=True)
    deadline = fields.Date(
        string='Deadline', required=True, tracking=True)
    extended_deadline = fields.Date(
        string='Extended Deadline', tracking=True)
    is_overdue = fields.Boolean(
        string='Overdue', compute='_compute_is_overdue', store=False)

    # Marks
    max_marks = fields.Float(
        string='Maximum Marks', default=10.0, required=True)
    passing_marks = fields.Float(string='Passing Marks', default=5.0)
    weightage = fields.Float(
        string='Weightage (%)', default=0.0,
        help='Contribution to internal assessment marks')

    # Description
    description = fields.Html(string='Description / Instructions')
    # FIXED: explicit relation name to avoid ir.attachment M2M conflicts
    attachment_ids = fields.Many2many(
        'ir.attachment',
        relation='student_assignment_ref_attachment_rel',
        column1='assignment_id',
        column2='attachment_id',
        string='Reference Attachments')

    # Submission Settings
    submission_type = fields.Selection([
        ('online', 'Online (Portal)'),
        ('offline', 'Offline (Physical)'),
        ('both', 'Both'),
    ], string='Submission Mode', default='online')
    allow_late_submission = fields.Boolean(
        string='Allow Late Submission', default=False)
    late_submission_penalty = fields.Float(
        string='Late Penalty (%)', default=0.0)

    # Grading
    use_rubric_grading = fields.Boolean(
        string='Use Rubric / Criteria Grading', default=False,
        help='When enabled, marks are derived from per-criterion scores')
    enable_plagiarism_flag = fields.Boolean(
        string='Enable Plagiarism Flagging', default=False)

    # Criteria
    criteria_ids = fields.One2many(
        'student.assignment.criteria', 'assignment_id',
        string='Grading Criteria')

    # Submissions
    submission_ids = fields.One2many(
        'student.assignment.submission', 'assignment_id',
        string='Submissions')
    submission_count = fields.Integer(
        string='Submitted', compute='_compute_submission_stats', store=True)
    graded_count = fields.Integer(
        string='Graded', compute='_compute_submission_stats', store=True)
    pending_count = fields.Integer(
        string='Pending', compute='_compute_submission_stats', store=True)
    average_marks = fields.Float(
        string='Class Average', compute='_compute_submission_stats', store=True,
        digits=(6, 2))
    submission_rate = fields.Float(
        string='Submission Rate (%)', compute='_compute_submission_stats',
        store=True, digits=(6, 1))

    # Reminder settings
    send_reminder = fields.Boolean(string='Send Deadline Reminder', default=True)
    reminder_days_before = fields.Integer(
        string='Remind (days before deadline)', default=2)

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('graded', 'Graded'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Internal Notes')

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.state == 'published'
                and bool(rec.deadline)
                and rec.deadline < today
            )

    @api.depends('submission_ids', 'submission_ids.state',
                 'submission_ids.marks_obtained')
    def _compute_submission_stats(self):
        for rec in self:
            all_subs = rec.submission_ids
            submitted = all_subs.filtered(lambda s: s.state != 'draft')
            graded = all_subs.filtered(lambda s: s.state == 'graded')
            pending = all_subs.filtered(
                lambda s: s.state in ('submitted', 'under_review'))
            total = len(all_subs)

            rec.submission_count = len(submitted)
            rec.graded_count = len(graded)
            rec.pending_count = len(pending)
            rec.submission_rate = (len(submitted) / total * 100) if total else 0.0
            rec.average_marks = (
                sum(graded.mapped('marks_obtained')) / len(graded)
            ) if graded else 0.0

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('assigned_date', 'deadline')
    def _check_dates(self):
        for rec in self:
            if rec.assigned_date and rec.deadline:
                if rec.deadline < rec.assigned_date:
                    raise ValidationError(
                        _('Deadline must be after the assigned date.'))

    @api.constrains('passing_marks', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if rec.passing_marks > rec.max_marks:
                raise ValidationError(
                    _('Passing marks cannot exceed maximum marks.'))

    @api.constrains('reminder_days_before')
    def _check_reminder_days(self):
        for rec in self:
            if rec.reminder_days_before < 0:
                raise ValidationError(
                    _('Reminder days must be a positive number.'))

    # -------------------------------------------------------------------------
    # Sequence
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('student.assignment')
                    or 'NEW')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # State Actions
    # -------------------------------------------------------------------------

    def action_publish(self):
        self.write({'state': 'published'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_mark_graded(self):
        self.write({'state': 'graded'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_submissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Submissions — %s') % self.name,
            'res_model': 'student.assignment.submission',
            'view_mode': 'list,form',
            'domain': [('assignment_id', '=', self.id)],
            'context': {'default_assignment_id': self.id},
        }

    def action_bulk_create_submissions(self):
        """Auto-create draft submission records for all enrolled/active students in batch."""
        self.ensure_one()
        if not self.batch_id:
            raise ValidationError(
                _('Please set a Batch before using bulk submission creation.'))
        students = self.env['student.student'].search([
            ('batch_id', '=', self.batch_id.id),
            ('state', 'in', ('enrolled', 'active')),
        ])
        existing_students = self.submission_ids.mapped('student_id')
        new_students = students - existing_students
        if not new_students:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to create'),
                    'message': _('All students in this batch already have submission records.'),
                    'sticky': False,
                    'type': 'warning',
                },
            }
        self.env['student.assignment.submission'].create([
            {'assignment_id': self.id, 'student_id': student.id}
            for student in new_students
        ])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Done'),
                'message': _('%d submission records created for batch %s.')
                           % (len(new_students), self.batch_id.name),
                'sticky': False,
                'type': 'success',
            },
        }