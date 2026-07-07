# -*- coding: utf-8 -*-

from odoo import models, fields, api


class McqQuestionBank(models.Model):
    _name = 'mcq.question.bank'
    _description = 'MCQ Question Bank'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Bank Name', required=True, tracking=True)
    code = fields.Char(string='Bank Code', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('mcq.question.bank'))
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    subject_id = fields.Many2one('university.subject', string='Subject', index=True)
    department_id = fields.Many2one('university.department', string='Department', index=True)
    program_id = fields.Many2one('university.program', string='Program')
    semester_id = fields.Many2one('university.semester', string='Semester')

    question_ids = fields.One2many('mcq.question', 'bank_id', string='Questions')
    question_count = fields.Integer(compute='_compute_question_count', string='Questions', store=True)

    @api.depends('question_ids')
    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Question Bank Code must be unique!'),
    ]

    def action_mcq_questions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Questions',
            'res_model': 'mcq.question',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id)],
            'context': {
                'default_bank_id': self.id,
                'search_default_bank_id': self.id,
            },
        }