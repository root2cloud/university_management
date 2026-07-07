# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class InternshipEvaluation(models.Model):
    _name = 'internship.evaluation'
    _description = 'Internship Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_date desc'

    name = fields.Char(string='Evaluation Number', required=True, readonly=True,
                       copy=False, default='/')

    # Internship
    internship_id = fields.Many2one('internship.internship', string='Internship',
                                    required=True, tracking=True, index=True)
    student_id = fields.Many2one(related='internship_id.student_id', string='Student', store=True)

    # Evaluator
    evaluator_type = fields.Selection([
        ('faculty', 'Faculty Mentor'),
        ('company', 'Company Supervisor'),
        ('external', 'External Examiner'),
    ], string='Evaluator Type', required=True)

    evaluator_id = fields.Many2one('faculty.faculty', string='Faculty Evaluator')
    external_evaluator = fields.Char(string='External Evaluator Name')

    # Evaluation Date
    evaluation_date = fields.Date(string='Evaluation Date', default=fields.Date.today(),
                                  required=True)

    # Evaluation Criteria
    technical_skills = fields.Float(string='Technical Skills (20)', default=0.0)
    work_quality = fields.Float(string='Work Quality (20)', default=0.0)
    communication = fields.Float(string='Communication (15)', default=0.0)
    initiative = fields.Float(string='Initiative & Creativity (15)', default=0.0)
    teamwork = fields.Float(string='Teamwork (15)', default=0.0)
    professionalism = fields.Float(string='Professionalism (15)', default=0.0)

    total_marks = fields.Float(string='Total Marks', compute='_compute_total', store=True)
    max_marks = fields.Float(string='Maximum Marks', default=100.0)

    # Overall Rating
    overall_rating = fields.Selection([
        ('1', 'Poor'), ('2', 'Below Average'), ('3', 'Average'),
        ('4', 'Good'), ('5', 'Excellent'),
    ], string='Overall Rating')

    # Comments
    strengths = fields.Text(string='Strengths')
    areas_of_improvement = fields.Text(string='Areas of Improvement')
    comments = fields.Text(string='Overall Comments')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Evaluation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('internship.evaluation') or '/'
        return super(InternshipEvaluation, self).create(vals)

    @api.depends('technical_skills', 'work_quality', 'communication',
                 'initiative', 'teamwork', 'professionalism')
    def _compute_total(self):
        for record in self:
            record.total_marks = (record.technical_skills + record.work_quality +
                                  record.communication + record.initiative +
                                  record.teamwork + record.professionalism)

    @api.constrains('technical_skills', 'work_quality', 'communication',
                    'initiative', 'teamwork', 'professionalism')
    def _check_marks(self):
        for record in self:
            if record.technical_skills < 0 or record.technical_skills > 20:
                raise ValidationError(_('Technical Skills marks must be between 0 and 20!'))
            if record.work_quality < 0 or record.work_quality > 20:
                raise ValidationError(_('Work Quality marks must be between 0 and 20!'))
            if record.communication < 0 or record.communication > 15:
                raise ValidationError(_('Communication marks must be between 0 and 15!'))
            if record.initiative < 0 or record.initiative > 15:
                raise ValidationError(_('Initiative marks must be between 0 and 15!'))
            if record.teamwork < 0 or record.teamwork > 15:
                raise ValidationError(_('Teamwork marks must be between 0 and 15!'))
            if record.professionalism < 0 or record.professionalism > 15:
                raise ValidationError(_('Professionalism marks must be between 0 and 15!'))

    # Workflow action
    def action_submit(self):
        """Submit the evaluation."""
        self.write({'state': 'submitted'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
