# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACCriterion(models.Model):
    _name = 'naac.criterion'
    _description = 'NAAC Criterion'
    _order = 'criterion_number'

    criterion_number = fields.Integer(string='Criterion Number', required=True)
    name = fields.Char(string='Criterion Name', required=True)
    description = fields.Text(string='Description')
    weightage = fields.Float(string='Weightage (%)')

    metric_ids = fields.One2many('naac.metric', 'criterion_id', string='Metrics')
    activity_ids = fields.One2many('naac.department.activity', 'criterion_id', string='Activities')
    evidence_ids = fields.One2many('naac.evidence', 'criterion_id', string='Evidence')

    total_metrics = fields.Integer(string='Total Metrics', compute='_compute_stats', store=True)
    completed_metrics = fields.Integer(string='Completed Metrics', compute='_compute_stats', store=True)
    readiness_score = fields.Float(string='Readiness Score (%)', compute='_compute_stats', store=True)
    evidence_count = fields.Integer(string='Evidence Count', compute='_compute_stats', store=True)

    color = fields.Integer(string='Color Index')
    key_indicators = fields.Text(string='Key Indicators')
    achieved_metrics = fields.Integer(string='Achieved Metrics', compute='_compute_stats', store=True)
    achievement_pct = fields.Float(string='Achievement %', compute='_compute_stats', store=True)

    @api.depends('metric_ids', 'metric_ids.actual_value', 'metric_ids.target_value', 'evidence_ids')
    def _compute_stats(self):
        for rec in self:
            metrics = rec.metric_ids
            rec.total_metrics = len(metrics)
            completed = metrics.filtered(lambda m: m.actual_value >= m.target_value and m.target_value > 0)
            rec.completed_metrics = len(completed)
            rec.readiness_score = (len(completed) / len(metrics) * 100) if metrics else 0.0
            rec.evidence_count = len(rec.evidence_ids)
            rec.achieved_metrics = len(completed)
            rec.achievement_pct = (len(completed) / len(metrics) * 100) if metrics else 0.0

    def action_view_activities(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Activities',
            'res_model': 'naac.department.activity',
            'view_mode': 'list,form',
            'domain': [('criterion_id', '=', self.id)],
            'context': {'default_criterion_id': self.id},
        }

    def action_view_evidence(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Evidence',
            'res_model': 'naac.evidence',
            'view_mode': 'list,form',
            'domain': [('criterion_id', '=', self.id)],
            'context': {'default_criterion_id': self.id},
        }

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, f"Criterion {rec.criterion_number}: {rec.name}"))
        return result