# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OnlineExamResponse(models.Model):
    _name = 'online.exam.response'
    _description = 'Online Exam Response'
    _order = 'attempt_id, sequence'

    attempt_id = fields.Many2one('online.exam.attempt', string='Attempt',
                                  required=True, ondelete='cascade', index=True)
    online_exam_id = fields.Many2one('online.exam',
                                      related='attempt_id.online_exam_id',
                                      string='Online Exam', store=True)
    student_id = fields.Many2one('student.student',
                                  related='attempt_id.student_id',
                                  string='Student', store=True)
    sequence = fields.Integer(string='Question No.', default=1)

    question_id = fields.Many2one('mcq.question', string='Question',
                                   required=True, ondelete='restrict')
    question_type = fields.Selection(related='question_id.question_type',
                                      string='Question Type', store=True)
    max_marks = fields.Float(related='question_id.marks', string='Max Marks', store=True)

    # Student's answer
    selected_option_ids = fields.Many2many(
        'mcq.question.option',
        string='Selected Options',
        relation='response_option_rel',
        column1='response_id',
        column2='option_id',
    )
    text_answer = fields.Text(string='Text Answer')

    # Evaluation
    marks_awarded = fields.Float(string='Marks Awarded', default=0.0)
    is_correct = fields.Boolean(string='Correct', default=False)
    is_evaluated = fields.Boolean(string='Evaluated', default=False)
    evaluator_notes = fields.Text(string='Evaluator Notes')
    evaluated_by = fields.Many2one('res.users', string='Evaluated By', readonly=True)
    evaluated_on = fields.Datetime(string='Evaluated On', readonly=True)

    # Flags
    is_skipped = fields.Boolean(string='Skipped', default=False)
    is_flagged = fields.Boolean(string='Flagged for Review', default=False)

    @api.constrains('marks_awarded', 'max_marks')
    def _check_marks(self):
        for rec in self:
            if rec.marks_awarded > rec.max_marks:
                raise ValidationError(_(
                    'Marks awarded (%s) cannot exceed maximum marks (%s) for this question.'
                ) % (rec.marks_awarded, rec.max_marks))

    def action_manual_evaluate(self, marks, notes=''):
        """Manually evaluate a short-answer response."""
        self.ensure_one()
        if marks > self.max_marks:
            raise ValidationError(_('Awarded marks exceed the maximum allowed for this question.'))
        self.write({
            'marks_awarded': marks,
            'evaluator_notes': notes,
            'is_evaluated': True,
            'evaluated_by': self.env.user.id,
            'evaluated_on': fields.Datetime.now(),
            'is_correct': marks >= self.max_marks,
        })