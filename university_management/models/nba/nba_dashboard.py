# -*- coding: utf-8 -*-
from odoo import models, fields, api


class NBADashboard(models.Model):
    _name = 'nba.dashboard'
    _description = 'NBA Dashboard Data Model'

    @api.model
    def get_dashboard_data(self, sar_id=None):
        domain = [('state', 'not in', ['draft'])]
        if sar_id:
            domain = [('id', '=', sar_id)]
        sars = self.env['nba.sar'].search(domain, order='create_date desc', limit=10)
        if not sars:
            sars = self.env['nba.sar'].search([], order='create_date desc', limit=10)

        latest = sars[:1]
        criterion_scores = []
        max_marks = [120, 120, 120, 120, 100, 120, 100, 80, 120]
        labels = ['C1 Curriculum', 'C2 Teaching', 'C3 Assessment', 'C4 Students',
                  'C5 Faculty', 'C6 Contributions', 'C7 Facilities', 'C8 Improvement', 'C9 Governance']

        if latest:
            rec = latest[0]
            scores = [rec.c1_score, rec.c2_score, rec.c3_score, rec.c4_score,
                      rec.c5_score, rec.c6_score, rec.c7_score, rec.c8_score, rec.c9_score]
            for i, (label, score, mx) in enumerate(zip(labels, scores, max_marks)):
                pct = round(score / mx * 100, 1) if mx else 0
                criterion_scores.append({
                    'label': label, 'score': round(score, 1),
                    'max': mx, 'pct': pct,
                    'status': 'green' if pct >= 60 else ('orange' if pct >= 40 else 'red'),
                })

        sar_list = []
        for s in sars:
            sar_list.append({
                'id': s.id, 'name': s.name,
                'program': s.program_id.name if s.program_id else '',
                'total': round(s.total_score, 1),
                'readiness': round(s.readiness_pct, 1),
                'state': s.state,
            })

        total = round(latest[0].total_score, 1) if latest else 0
        readiness = round(latest[0].readiness_pct, 1) if latest else 0
        evidence_count = sum(len(s.evidence_ids) for s in sars)
        co_count = sum(len(s.co_ids) for s in sars)
        research_count = sum(len(s.research_ids) for s in sars)

        return {
            'total_score': total,
            'readiness_pct': readiness,
            'criterion_scores': criterion_scores,
            'sar_list': sar_list,
            'evidence_count': evidence_count,
            'co_count': co_count,
            'research_count': research_count,
            'active_sar_id': latest[0].id if latest else False,
            'active_sar_name': latest[0].name if latest else '',
            'active_program': latest[0].program_id.name if latest and latest[0].program_id else '',
        }