# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ExamEvaluation(models.Model):
    _name = 'examination.evaluation'
    _description = 'Exam Answer Sheet Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_date desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Examination & Subject
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True)
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True, tracking=True)

    # Evaluator
    evaluator_id = fields.Many2one('faculty.faculty', string='Evaluator',
                                   required=True, tracking=True)

    # Evaluation Details
    evaluation_date = fields.Date(string='Evaluation Date', default=fields.Date.today())

    # Papers
    total_papers = fields.Integer(string='Total Papers Assigned')
    papers_evaluated = fields.Integer(string='Papers Evaluated')
    papers_pending = fields.Integer(string='Papers Pending',
                                    compute='_compute_pending', store=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='assigned', tracking=True)

    # Completion
    completion_percentage = fields.Float(string='Completion %',
                                         compute='_compute_completion')

    # Notes
    notes = fields.Text(string='Notes')

    @api.depends('examination_id', 'subject_id', 'evaluator_id')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.examination_id.name} - {record.subject_id.name} - {record.evaluator_id.name}"

    @api.depends('total_papers', 'papers_evaluated')
    def _compute_pending(self):
        for record in self:
            record.papers_pending = record.total_papers - record.papers_evaluated

    @api.depends('total_papers', 'papers_evaluated')
    def _compute_completion(self):
        for record in self:
            if record.total_papers > 0:
                record.completion_percentage = (record.papers_evaluated / record.total_papers) * 100
            else:
                record.completion_percentage = 0.0

    def action_assign(self):
        self.write({'state': 'assigned'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})
