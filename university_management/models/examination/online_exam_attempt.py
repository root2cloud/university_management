# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class OnlineExamAttempt(models.Model):
    _name = 'online.exam.attempt'
    _description = 'Online Exam Attempt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_datetime desc'

    name = fields.Char(string='Attempt Reference', compute='_compute_name', store=True)

    online_exam_id = fields.Many2one('online.exam', string='Online Exam',
                                     required=True, index=True, ondelete='restrict', tracking=True)
    examination_id = fields.Many2one('examination.examination',
                                     related='online_exam_id.examination_id',
                                     string='Examination', store=True)
    subject_id = fields.Many2one('university.subject',
                                 related='online_exam_id.subject_id',
                                 string='Subject', store=True)

    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, index=True, tracking=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Reg. Number', store=True)
    program_id = fields.Many2one('university.program',
                                 related='student_id.program_id',
                                 string='Program', store=True)

    start_datetime = fields.Datetime(string='Started At', tracking=True)
    submit_datetime = fields.Datetime(string='Submitted At', tracking=True)
    expiry_datetime = fields.Datetime(string='Expires At')

    # Scoring
    total_score = fields.Float(string='Score Obtained', compute='_compute_scores',
                                store=True, digits=(16, 2))
    max_score = fields.Float(related='online_exam_id.total_marks',
                              string='Maximum Score', store=True)
    percentage = fields.Float(string='Percentage', compute='_compute_scores',
                               store=True, digits=(16, 2))
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('pending', 'Pending Evaluation'),
    ], string='Result', compute='_compute_scores', store=True, tracking=True)

    state = fields.Selection([
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('evaluated', 'Evaluated'),
        ('expired', 'Expired'),
    ], string='Status', default='in_progress', tracking=True)

    response_ids = fields.One2many('online.exam.response', 'attempt_id', string='Responses')
    answered_count = fields.Integer(compute='_compute_answered_count', string='Answered')
    total_questions = fields.Integer(related='online_exam_id.question_count',
                                      string='Total Questions')

    ip_address = fields.Char(string='IP Address', readonly=True)
    remarks = fields.Text(string='Remarks')

    @api.depends('student_id', 'online_exam_id', 'start_datetime')
    def _compute_name(self):
        for rec in self:
            student = rec.student_id.registration_number or (rec.student_id.name if rec.student_id else 'Unknown')
            exam = rec.online_exam_id.code if rec.online_exam_id else ''
            rec.name = f"{student}/{exam}"

    @api.depends('response_ids', 'response_ids.marks_awarded', 'state')
    def _compute_scores(self):
        for rec in self:
            if rec.state in ('submitted', 'evaluated'):
                score = sum(rec.response_ids.mapped('marks_awarded'))
                rec.total_score = score
                rec.percentage = (score / rec.max_score * 100) if rec.max_score else 0.0
                passing = rec.online_exam_id.passing_marks if rec.online_exam_id else 0
                has_pending = rec.response_ids.filtered(
                    lambda r: not r.is_evaluated and r.question_id.question_type == 'short_answer'
                )
                if has_pending:
                    rec.result = 'pending'
                elif rec.total_score >= passing:
                    rec.result = 'pass'
                else:
                    rec.result = 'fail'
            else:
                rec.total_score = 0.0
                rec.percentage = 0.0
                rec.result = 'pending'

    def _compute_answered_count(self):
        for rec in self:
            rec.answered_count = len(rec.response_ids.filtered(
                lambda r: r.selected_option_ids or r.text_answer
            ))

    def auto_evaluate(self):
        """Auto-evaluate MCQ and True/False responses."""
        for attempt in self:
            for response in attempt.response_ids:
                q = response.question_id
                if q.question_type == 'short_answer':
                    continue  # Skip — manual evaluation needed

                correct_options = q.option_ids.filtered('is_correct')
                correct_ids = set(correct_options.ids)
                selected_ids = set(response.selected_option_ids.ids)

                if q.question_type in ('mcq', 'true_false'):
                    if selected_ids and selected_ids == correct_ids:
                        response.write({'marks_awarded': q.marks, 'is_correct': True, 'is_evaluated': True})
                    elif selected_ids and attempt.online_exam_id.negative_marking:
                        response.write({'marks_awarded': -q.negative_marks, 'is_correct': False, 'is_evaluated': True})
                    else:
                        response.write({'marks_awarded': 0.0, 'is_correct': False, 'is_evaluated': True})

                elif q.question_type == 'multi_select':
                    if selected_ids == correct_ids:
                        response.write({'marks_awarded': q.marks, 'is_correct': True, 'is_evaluated': True})
                    elif selected_ids and attempt.online_exam_id.negative_marking:
                        response.write({'marks_awarded': -q.negative_marks, 'is_correct': False, 'is_evaluated': True})
                    else:
                        response.write({'marks_awarded': 0.0, 'is_correct': False, 'is_evaluated': True})

            # Mark as evaluated if all objective questions are done
            has_pending_subjective = attempt.response_ids.filtered(
                lambda r: not r.is_evaluated and r.question_id.question_type == 'short_answer'
            )
            if not has_pending_subjective:
                attempt.write({'state': 'evaluated'})
            else:
                attempt.write({'state': 'submitted'})

    def action_expire(self):
        self.write({'state': 'expired'})

    def action_submit(self):
        """Submit attempt and trigger auto-evaluation."""
        self.ensure_one()
        self.write({'state': 'submitted', 'submit_datetime': fields.Datetime.now()})
        self.auto_evaluate()

    def is_expired(self):
        """Check if this attempt has passed the allowed duration."""
        self.ensure_one()
        if self.expiry_datetime and fields.Datetime.now() > self.expiry_datetime:
            return True
        return False