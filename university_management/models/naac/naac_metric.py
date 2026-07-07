# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACMetric(models.Model):
    _name = 'naac.metric'
    _description = 'NAAC Metric'
    _order = 'criterion_id, metric_code'

    criterion_id = fields.Many2one('naac.criterion', string='Criterion', required=True, ondelete='cascade')
    metric_code = fields.Char(string='Metric Code', required=True)
    name = fields.Char(string='Metric Name', required=True)
    description = fields.Text(string='Description')

    unit = fields.Char(string='Unit of Measurement', help='e.g., Number, %, INR Lakhs')
    target_value = fields.Float(string='Target Value')
    actual_value = fields.Float(string='Actual Value', compute='_compute_actual_value', store=True)
    manual_value = fields.Float(string='Manual Override Value')
    use_manual = fields.Boolean(string='Use Manual Value')

    auto_calculated = fields.Boolean(string='Auto-Calculated', default=False)
    calculation_method = fields.Selection([
        ('research_papers', 'Count Research Papers'),
        ('patents', 'Count Patents'),
        ('placements', 'Count Placements'),
        ('faculty_count', 'Count Faculty'),
        ('manual', 'Manual Entry'),
    ], string='Calculation Method', default='manual')

    achievement_pct = fields.Float(string='Achievement (%)', compute='_compute_achievement', store=True)
    status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('achieved', 'Achieved'),
        ('exceeded', 'Exceeded Target'),
    ], string='Status', compute='_compute_status', store=True)

    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    evidence_ids = fields.One2many('naac.evidence', 'metric_id', string='Evidence')
    evidence_count = fields.Integer(string='Evidence Count', compute='_compute_evidence_count')

    department_id = fields.Many2one('university.department', string='Department')
    notes = fields.Text(string='Notes')
    is_verified = fields.Boolean(string='Verified', default=False)
    doc_type = fields.Char(string='Document Type')
    upload_date = fields.Datetime(string='Upload Date')
    calculation_model = fields.Char(string='Calculation Model')
    calculation_domain = fields.Char(string='Calculation Domain')

    @api.depends('metric_ids' if False else 'manual_value', 'use_manual', 'calculation_method')
    def _compute_actual_value(self):
        for rec in self:
            if rec.use_manual:
                rec.actual_value = rec.manual_value
            elif rec.calculation_method == 'research_papers':
                count = self.env['naac.faculty.research'].search_count([
                    ('research_type', '=', 'paper'),
                    ('academic_year_id', '=', rec.academic_year_id.id),
                ])
                rec.actual_value = count
            elif rec.calculation_method == 'patents':
                count = self.env['naac.faculty.research'].search_count([
                    ('research_type', '=', 'patent'),
                    ('academic_year_id', '=', rec.academic_year_id.id),
                ])
                rec.actual_value = count
            elif rec.calculation_method == 'placements':
                count = self.env['naac.student.progression'].search_count([
                    ('progression_type', '=', 'placement'),
                    ('year', '=', rec.academic_year_id.name),
                ])
                rec.actual_value = count
            else:
                rec.actual_value = rec.manual_value

    @api.depends('actual_value', 'target_value')
    def _compute_achievement(self):
        for rec in self:
            if rec.target_value > 0:
                rec.achievement_pct = min((rec.actual_value / rec.target_value) * 100, 100)
            else:
                rec.achievement_pct = 0.0

    @api.depends('achievement_pct')
    def _compute_status(self):
        for rec in self:
            pct = rec.achievement_pct
            if pct == 0:
                rec.status = 'not_started'
            elif pct < 100:
                rec.status = 'in_progress'
            elif pct == 100:
                rec.status = 'achieved'
            else:
                rec.status = 'exceeded'

    @api.depends('evidence_ids')
    def _compute_evidence_count(self):
        for rec in self:
            rec.evidence_count = len(rec.evidence_ids)