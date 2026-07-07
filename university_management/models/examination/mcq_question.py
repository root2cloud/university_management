# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class McqQuestionOption(models.Model):
    _name = 'mcq.question.option'
    _description = 'MCQ Question Option'
    _order = 'sequence, id'

    question_id = fields.Many2one('mcq.question', string='Question',
                                  required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    option_text = fields.Char(string='Option Text', required=True)
    is_correct = fields.Boolean(string='Correct Answer', default=False)


class McqQuestion(models.Model):
    _name = 'mcq.question'
    _description = 'MCQ Question'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Question Code', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('mcq.question'))
    active = fields.Boolean(default=True)

    question_text = fields.Html(string='Question', required=True)
    question_image = fields.Binary(string='Question Image')

    question_type = fields.Selection([
        ('mcq', 'Multiple Choice (Single Answer)'),
        ('multi_select', 'Multiple Choice (Multi Answer)'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short Answer'),
    ], string='Question Type', required=True, default='mcq', tracking=True)

    # Classification
    bank_id = fields.Many2one('mcq.question.bank', string='Question Bank', index=True)
    subject_id = fields.Many2one('university.subject', string='Subject', index=True)
    department_id = fields.Many2one('university.department', string='Department')
    topic = fields.Char(string='Topic / Unit')

    difficulty = fields.Selection([
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ], string='Difficulty', default='medium', required=True, tracking=True)

    marks = fields.Float(string='Marks', required=True, default=1.0)
    negative_marks = fields.Float(string='Negative Marks', default=0.0,
                                  help='Marks deducted for wrong answer (enter as positive value)')

    # Options — only used for mcq / multi_select / true_false
    option_ids = fields.One2many('mcq.question.option', 'question_id', string='Options')

    # Explanation shown to students after exam (if allow_review is True)
    explanation = fields.Html(string='Explanation / Solution')

    # Tags for search
    tag_ids = fields.Many2many('mcq.question.tag', string='Tags')

    # Usage stats
    used_in_exam_count = fields.Integer(string='Used in Exams', compute='_compute_usage', store=False)

    @api.onchange('question_type')
    def _onchange_question_type(self):
        """Pre-populate True/False options when type is changed."""
        if self.question_type == 'true_false':
            self.option_ids = [(5, 0, 0)]
            self.option_ids = [
                (0, 0, {'option_text': 'True', 'is_correct': True, 'sequence': 1}),
                (0, 0, {'option_text': 'False', 'is_correct': False, 'sequence': 2}),
            ]
        elif self.question_type in ('mcq', 'multi_select') and not self.option_ids:
            self.option_ids = [
                (0, 0, {'option_text': '', 'is_correct': False, 'sequence': 1}),
                (0, 0, {'option_text': '', 'is_correct': False, 'sequence': 2}),
                (0, 0, {'option_text': '', 'is_correct': False, 'sequence': 3}),
                (0, 0, {'option_text': '', 'is_correct': False, 'sequence': 4}),
            ]

    @api.constrains('question_type', 'option_ids')
    def _check_options(self):
        for rec in self:
            if rec.question_type in ('mcq', 'true_false', 'multi_select'):
                if not rec.option_ids:
                    raise ValidationError(_('Please add at least 2 options for this question type.'))
                correct = rec.option_ids.filtered('is_correct')
                if not correct:
                    raise ValidationError(_('At least one option must be marked as correct.'))
                if rec.question_type == 'mcq' and len(correct) > 1:
                    raise ValidationError(_('MCQ (Single Answer) must have exactly one correct option.'))

    def _compute_usage(self):
        for rec in self:
            rec.used_in_exam_count = self.env['online.exam'].search_count(
                [('question_ids', 'in', rec.id)]
            )


class McqQuestionTag(models.Model):
    _name = 'mcq.question.tag'
    _description = 'MCQ Question Tag'
    _order = 'name'

    name = fields.Char(string='Tag', required=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Tag name must be unique!'),
    ]