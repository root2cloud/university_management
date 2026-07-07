# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProjectEvaluation(models.Model):
    _name = 'project.evaluation'
    _description = 'Project Evaluation/Assessment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_date desc'

    name = fields.Char(string='Evaluation Number', required=True, readonly=True,
                       copy=False, default='/')

    # Project
    project_id = fields.Many2one('student.project', string='Project',
                                 required=True, tracking=True, index=True)

    # Evaluation Type
    evaluation_type = fields.Selection([
        ('synopsis', 'Synopsis Review'),
        ('progress', 'Progress Review'),
        ('internal', 'Internal Evaluation'),
        ('external', 'External Evaluation'),
        ('final', 'Final Evaluation'),
    ], string='Evaluation Type', required=True, tracking=True)

    # Evaluator
    evaluator_id = fields.Many2one('faculty.faculty', string='Evaluator',
                                   required=True, tracking=True)
    is_external = fields.Boolean(string='External Evaluator')

    # Evaluation Date
    evaluation_date = fields.Date(string='Evaluation Date', default=fields.Date.today(),
                                  required=True)

    # Evaluation Criteria
    innovation = fields.Float(string='Innovation/Novelty (10)', default=0.0)
    technical_complexity = fields.Float(string='Technical Complexity (10)', default=0.0)
    implementation = fields.Float(string='Implementation Quality (10)', default=0.0)
    documentation = fields.Float(string='Documentation (10)', default=0.0)
    presentation = fields.Float(string='Presentation Skills (10)', default=0.0)

    total_marks = fields.Float(string='Total Marks', compute='_compute_total', store=True)
    max_marks = fields.Float(string='Maximum Marks', default=50.0)
    percentage = fields.Float(string='Percentage', compute='_compute_percentage', store=True)

    # Feedback
    strengths = fields.Html(string='Strengths')
    weaknesses = fields.Html(string='Areas of Improvement')
    suggestions = fields.Html(string='Suggestions')

    # Overall Comments
    comments = fields.Text(string='Comments')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Evaluation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('project.evaluation') or '/'
        return super(ProjectEvaluation, self).create(vals)

    @api.depends('innovation', 'technical_complexity', 'implementation',
                 'documentation', 'presentation')
    def _compute_total(self):
        for record in self:
            record.total_marks = (record.innovation + record.technical_complexity +
                                  record.implementation + record.documentation +
                                  record.presentation)

    @api.depends('total_marks', 'max_marks')
    def _compute_percentage(self):
        for record in self:
            if record.max_marks:
                record.percentage = (record.total_marks / record.max_marks) * 100.0
            else:
                record.percentage = 0.0

    @api.constrains('innovation', 'technical_complexity', 'implementation',
                    'documentation', 'presentation')
    def _check_marks(self):
        for record in self:
            fields_to_check = ['innovation', 'technical_complexity', 'implementation',
                               'documentation', 'presentation']
            for field in fields_to_check:
                value = getattr(record, field)
                if value < 0 or value > 10:
                    raise ValidationError(_('Marks must be between 0 and 10!'))

    # Workflow actions
    def action_submit(self):
        """Submit the evaluation for approval."""
        self.write({'state': 'submitted'})

    def action_approve(self):
        """Approve the evaluation."""
        self.write({'state': 'approved'})

    def action_reset_to_draft(self):
        """Reset evaluation back to draft state."""
        self.write({'state': 'draft'})

    def action_view_project(self):
        """Open the related student project."""
        self.ensure_one()
        return {
            'name': _('Project'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'target': 'current',
        }
