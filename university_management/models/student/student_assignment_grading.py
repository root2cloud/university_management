# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentAssignmentCriteria(models.Model):
    _name = 'student.assignment.criteria'
    _description = 'Assignment Grading Criterion'
    _order = 'sequence, id'
    _rec_name = 'name'

    assignment_id = fields.Many2one(
        'student.assignment', string='Assignment',
        required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Criterion', required=True)
    description = fields.Text(string='Description / Expectation')
    max_marks = fields.Float(string='Max Marks', required=True, default=5.0)
    weightage = fields.Float(
        string='Weightage (%)', default=0.0,
        help='Percentage weight of this criterion in the total assignment marks')

    # Related for reporting/filtering — no lookup needed on criteria list
    subject_id = fields.Many2one(
        related='assignment_id.subject_id', string='Subject',
        store=True, readonly=True)
    faculty_id = fields.Many2one(
        related='assignment_id.faculty_id', string='Faculty',
        store=True, readonly=True)
    academic_year_id = fields.Many2one(
        related='assignment_id.academic_year_id', string='Academic Year',
        store=True, readonly=True)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('max_marks')
    def _check_max_marks(self):
        for rec in self:
            if rec.max_marks <= 0:
                raise ValidationError(
                    _('Max marks must be greater than zero.'))

    @api.constrains('weightage')
    def _check_weightage(self):
        for rec in self:
            if not (0.0 <= rec.weightage <= 100.0):
                raise ValidationError(
                    _('Weightage must be between 0 and 100.'))


class StudentAssignmentSubmissionScore(models.Model):
    _name = 'student.assignment.submission.score'
    _description = 'Submission Score per Grading Criterion'
    _order = 'criteria_id'
    _rec_name = 'display_name'

    submission_id = fields.Many2one(
        'student.assignment.submission', string='Submission',
        required=True, ondelete='cascade', index=True)
    criteria_id = fields.Many2one(
        'student.assignment.criteria', string='Criterion',
        required=True, ondelete='restrict')
    marks_obtained = fields.Float(string='Marks Obtained', default=0.0)
    remarks = fields.Char(string='Remarks')

    # Stored related for reporting
    max_marks = fields.Float(
        related='criteria_id.max_marks', string='Max Marks',
        store=True, readonly=True)
    student_id = fields.Many2one(
        related='submission_id.student_id', string='Student',
        store=True, readonly=True)
    assignment_id = fields.Many2one(
        related='submission_id.assignment_id', string='Assignment',
        store=True, readonly=True)
    subject_id = fields.Many2one(
        related='submission_id.subject_id', string='Subject',
        store=True, readonly=True)

    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('submission_id', 'criteria_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s' % (
                rec.submission_id.display_name or '',
                rec.criteria_id.name or '')

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        ('unique_submission_criteria',
         'UNIQUE(submission_id, criteria_id)',
         'Each criterion can only be scored once per submission.'),
    ]

    @api.constrains('marks_obtained', 'criteria_id')
    def _check_marks(self):
        for rec in self:
            if rec.marks_obtained < 0:
                raise ValidationError(_('Score cannot be negative.'))
            if (rec.criteria_id
                    and rec.marks_obtained > rec.criteria_id.max_marks):
                raise ValidationError(
                    _('Score (%.2f) cannot exceed criterion max marks (%.2f).')
                    % (rec.marks_obtained, rec.criteria_id.max_marks))