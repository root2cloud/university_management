# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class NBAGenerateSARWizard(models.TransientModel):
    _name = 'nba.generate.sar.wizard'
    _description = 'Generate NBA SAR PDF Wizard'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True)
    include_part_a = fields.Boolean(string='Include Part A – Institutional Info', default=True)
    include_criteria = fields.Many2many(
        'ir.model.fields',
        string='Criteria to Include',
    )
    include_all_criteria = fields.Boolean(string='Include All 9 Criteria', default=True)
    include_evidence_index = fields.Boolean(string='Include Evidence Index', default=True)
    include_score_summary = fields.Boolean(string='Include Score Summary Page', default=True)
    output_format = fields.Selection([
        ('pdf', 'PDF'),
    ], string='Output Format', default='pdf')
    cover_style = fields.Selection([
        ('standard', 'Standard NBA Format'),
        ('minimal', 'Minimal Cover'),
    ], string='Cover Style', default='standard')

    def action_generate(self):
        self.ensure_one()
        return self.env.ref('university_management.action_report_nba_sar').report_action(self.sar_id)