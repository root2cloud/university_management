# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class NBAComputeWizard(models.TransientModel):
    _name = 'nba.compute.wizard'
    _description = 'NBA Auto-Compute Criteria Wizard'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True)
    compute_c1 = fields.Boolean(string='C1 – Curriculum', default=True)
    compute_c2 = fields.Boolean(string='C2 – Teaching-Learning', default=True)
    compute_c3 = fields.Boolean(string='C3 – CO/PO Attainment', default=True)
    compute_c4 = fields.Boolean(string='C4 – Students Performance', default=True)
    compute_c5 = fields.Boolean(string='C5 – Faculty SFR/FQI', default=True)
    compute_c6 = fields.Boolean(string='C6 – Faculty Contributions', default=True)
    pull_from_admissions = fields.Boolean(string='Pull Admission Data', default=True)
    pull_from_placements = fields.Boolean(string='Pull Placement Data', default=True)
    pull_from_exams = fields.Boolean(string='Pull Exam Results', default=True)

    # Preview scores (readonly)
    preview_c4_er = fields.Float(string='Enrolment Ratio (preview)', readonly=True)
    preview_c5_sfr = fields.Float(string='SFR (preview)', readonly=True)
    preview_total = fields.Float(string='Estimated Total Score', readonly=True)

    def action_compute(self):
        self.ensure_one()
        sar = self.sar_id

        if self.compute_c4:
            sar._pull_c4_student_data()
        if self.compute_c5:
            sar._pull_c5_faculty_data()
        if self.compute_c3:
            for co in sar.co_ids:
                co._compute_attainment()
        if self.compute_c6:
            self.env['nba.c6.contributions'].compute_from_research(sar.id)

        sar.write({'last_computed_on': fields.Datetime.now()})
        # Trigger recompute of scores
        sar._compute_c4_score()
        sar._compute_c5_score()
        sar._compute_total_score()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Computation Complete'),
                'message': _('Selected criteria have been recomputed. Total Score: %.1f/1000') % sar.total_score,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_preview(self):
        """Quick preview before full compute."""
        self.ensure_one()
        sar = self.sar_id
        # Show current values
        self.preview_total = sar.total_score
        if sar.c5_faculty_ids:
            self.preview_c5_sfr = sar.c5_faculty_ids[0].sfr_value
        if sar.c4_student_ids:
            cay = sar.c4_student_ids.filtered(lambda r: r.year_label == 'CAY')
            if cay:
                self.preview_c4_er = cay[0].enrolment_ratio
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}