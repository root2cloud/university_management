# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import random


class OnlineExam(models.Model):
    _name = 'online.exam'
    _description = 'Online Examination'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Online Exam Name', required=True, tracking=True)
    code = fields.Char(string='Exam Code', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('online.exam'))
    active = fields.Boolean(default=True)

    # Link to parent examination schedule
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True, index=True, ondelete='restrict')
    academic_year_id = fields.Many2one('university.academic.year',
                                       related='examination_id.academic_year_id',
                                       string='Academic Year', store=True)
    semester_id = fields.Many2one('university.semester',
                                  related='examination_id.semester_id',
                                  string='Semester', store=True)

    # Subject this online exam covers
    subject_id = fields.Many2one('university.subject', string='Subject', required=True,
                                 tracking=True, index=True)

    # Scheduling
    start_datetime = fields.Datetime(string='Start Date & Time', required=True, tracking=True)
    end_datetime = fields.Datetime(string='End Date & Time', required=True, tracking=True)
    duration_minutes = fields.Integer(string='Duration (minutes)', required=True, default=60)

    # Marks
    total_marks = fields.Float(string='Total Marks', compute='_compute_total_marks',
                               store=True, readonly=True)
    passing_marks = fields.Float(string='Passing Marks', default=0.0)

    # Questions
    question_ids = fields.Many2many('mcq.question', string='Questions',
                                    relation='online_exam_question_rel',
                                    column1='exam_id', column2='question_id')
    question_count = fields.Integer(compute='_compute_question_count', store=True)

    # Exam behaviour
    shuffle_questions = fields.Boolean(string='Shuffle Questions', default=False)
    shuffle_options = fields.Boolean(string='Shuffle Options', default=False)
    show_result_immediately = fields.Boolean(string='Show Result Immediately', default=True)
    allow_review = fields.Boolean(string='Allow Answer Review', default=True,
                                  help='Show correct answers and explanations after submission')
    negative_marking = fields.Boolean(string='Enable Negative Marking', default=False)
    allow_multiple_attempts = fields.Boolean(string='Allow Multiple Attempts', default=False)
    max_attempts = fields.Integer(string='Max Attempts Allowed', default=1)

    # Instructions
    instructions = fields.Html(string='Exam Instructions')

    # Target audience
    program_ids = fields.Many2many('university.program', string='Applicable Programs')
    batch_ids = fields.Many2many('university.batch', string='Applicable Batches')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('ongoing', 'Ongoing'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    # Attempts
    attempt_ids = fields.One2many('online.exam.attempt', 'online_exam_id', string='Attempts')
    attempt_count = fields.Integer(compute='_compute_attempt_count')

    @api.depends('question_ids', 'question_ids.marks')
    def _compute_total_marks(self):
        for rec in self:
            rec.total_marks = sum(rec.question_ids.mapped('marks'))

    @api.depends('question_ids')
    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)

    def _compute_attempt_count(self):
        for rec in self:
            rec.attempt_count = len(rec.attempt_ids)

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime:
                if rec.start_datetime >= rec.end_datetime:
                    raise ValidationError(_('End date/time must be after start date/time.'))

    @api.constrains('passing_marks', 'total_marks')
    def _check_passing_marks(self):
        for rec in self:
            if rec.passing_marks > rec.total_marks:
                raise ValidationError(_('Passing marks cannot exceed total marks.'))

    def action_publish(self):
        for rec in self:
            if not rec.question_ids:
                raise ValidationError(_('Please add at least one question before publishing.'))
        self.write({'state': 'published'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_set_ongoing(self):
        self.write({'state': 'ongoing'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_attempts(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Attempts'),
            'res_model': 'online.exam.attempt',
            'view_mode': 'list,form',
            'domain': [('online_exam_id', '=', self.id)],
            'context': {'default_online_exam_id': self.id},
        }

    def action_auto_evaluate_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Auto Evaluate Attempts'),
            'res_model': 'wizard.auto.evaluate.exam',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_online_exam_id': self.id},
        }

    def get_questions_for_student(self):
        """Return question list, shuffled if configured."""
        self.ensure_one()
        questions = list(self.question_ids)
        if self.shuffle_questions:
            random.shuffle(questions)
        return questions

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Online Exam Code must be unique!'),
    ]