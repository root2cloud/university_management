# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentAssignmentSubmission(models.Model):
    _name = 'student.assignment.submission'
    _description = 'Student Assignment Submission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'
    _rec_name = 'display_name'

    assignment_id = fields.Many2one(
        'student.assignment', string='Assignment',
        required=True, ondelete='cascade', index=True, tracking=True)

    # FIXED: correct model is student.student (inherits res.partner)
    student_id = fields.Many2one(
        'student.student', string='Student',
        required=True, index=True, tracking=True)

    # FIXED: correct field is registration_number, not enrollment_number
    student_registration_no = fields.Char(
        related='student_id.registration_number',
        string='Registration No.', store=True)

    # Related convenience fields stored for filtering/reporting
    subject_id = fields.Many2one(
        related='assignment_id.subject_id', string='Subject',
        store=True, readonly=True)
    faculty_id = fields.Many2one(
        related='assignment_id.faculty_id', string='Faculty',
        store=True, readonly=True)
    batch_id = fields.Many2one(
        related='assignment_id.batch_id', string='Batch',
        store=True, readonly=True)
    deadline = fields.Date(
        related='assignment_id.deadline', string='Deadline',
        store=True, readonly=True)
    max_marks = fields.Float(
        related='assignment_id.max_marks', string='Max Marks',
        store=True, readonly=True)
    assignment_type = fields.Selection(
        related='assignment_id.assignment_type', string='Type',
        store=True, readonly=True)

    # Submission content
    submission_date = fields.Datetime(string='Submitted On', tracking=True)
    is_late = fields.Boolean(
        string='Late Submission', compute='_compute_is_late', store=True)

    # FIXED: explicit relation name to avoid clash with assignment attachment M2M
    submission_file_ids = fields.Many2many(
        'ir.attachment',
        relation='student_assignment_submission_file_rel',
        column1='submission_id',
        column2='attachment_id',
        string='Submitted Files')
    submission_text = fields.Html(string='Submission Content')
    submission_notes = fields.Text(string='Student Notes')

    # Plagiarism
    is_plagiarised = fields.Boolean(
        string='Plagiarism Flagged', default=False, tracking=True)
    plagiarism_note = fields.Text(string='Plagiarism Note')

    # Grading
    marks_obtained = fields.Float(string='Marks Obtained', tracking=True)
    percentage = fields.Float(
        string='Percentage', compute='_compute_percentage', store=True,
        digits=(6, 2))
    grade = fields.Char(
        string='Grade', compute='_compute_grade', store=True)
    feedback = fields.Html(string='Faculty Feedback')
    graded_by = fields.Many2one(
        'faculty.faculty', string='Graded By', tracking=True)
    graded_on = fields.Datetime(string='Graded On')

    # Score breakdown per rubric criterion
    score_ids = fields.One2many(
        'student.assignment.submission.score', 'submission_id',
        string='Score Breakdown')

    # State
    state = fields.Selection([
        ('draft', 'Not Submitted'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('graded', 'Graded'),
        ('returned', 'Returned for Revision'),
    ], string='Status', default='draft', tracking=True)

    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('assignment_id', 'student_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s' % (
                rec.assignment_id.name or '',
                rec.student_id.name or '')

    @api.depends('submission_date', 'assignment_id.deadline',
                 'assignment_id.extended_deadline')
    def _compute_is_late(self):
        for rec in self:
            if not rec.submission_date:
                rec.is_late = False
                continue
            effective_deadline = (
                rec.assignment_id.extended_deadline
                or rec.assignment_id.deadline)
            rec.is_late = bool(
                effective_deadline
                and rec.submission_date.date() > effective_deadline)

    @api.depends('marks_obtained', 'assignment_id.max_marks')
    def _compute_percentage(self):
        for rec in self:
            max_m = rec.assignment_id.max_marks
            rec.percentage = (
                (rec.marks_obtained / max_m * 100) if max_m else 0.0)

    @api.depends('percentage')
    def _compute_grade(self):
        for rec in self:
            pct = rec.percentage
            if pct >= 90:
                rec.grade = 'O'
            elif pct >= 80:
                rec.grade = 'A+'
            elif pct >= 70:
                rec.grade = 'A'
            elif pct >= 60:
                rec.grade = 'B+'
            elif pct >= 50:
                rec.grade = 'B'
            elif pct >= 40:
                rec.grade = 'C'
            elif pct > 0:
                rec.grade = 'F'
            else:
                rec.grade = ''

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        ('unique_student_assignment',
         'UNIQUE(assignment_id, student_id)',
         'A student can have only one submission per assignment.'),
    ]

    @api.constrains('marks_obtained', 'assignment_id')
    def _check_marks(self):
        for rec in self:
            if rec.marks_obtained < 0:
                raise ValidationError(_('Marks obtained cannot be negative.'))
            if (rec.assignment_id
                    and rec.marks_obtained > rec.assignment_id.max_marks):
                raise ValidationError(
                    _('Marks obtained (%.2f) cannot exceed maximum marks (%.2f).')
                    % (rec.marks_obtained, rec.assignment_id.max_marks))

    # -------------------------------------------------------------------------
    # State Actions
    # -------------------------------------------------------------------------

    def action_submit(self):
        for rec in self:
            rec.write({
                'state': 'submitted',
                'submission_date': fields.Datetime.now(),
            })

    def action_start_review(self):
        self.write({'state': 'under_review'})

    def action_grade(self):
        for rec in self:
            rec.write({
                'state': 'graded',
                'graded_on': fields.Datetime.now(),
            })

    def action_return_for_revision(self):
        self.write({'state': 'returned'})

    def action_reset_draft(self):
        self.write({'state': 'draft', 'submission_date': False})

    def action_flag_plagiarism(self):
        self.write({'is_plagiarised': True})

    def action_clear_plagiarism(self):
        self.write({'is_plagiarised': False, 'plagiarism_note': False})

    def action_compute_marks_from_rubric(self):
        """Sum up criterion scores and write to marks_obtained."""
        for rec in self:
            if not rec.score_ids:
                continue
            total = sum(rec.score_ids.mapped('marks_obtained'))
            rec.marks_obtained = min(total, rec.assignment_id.max_marks)