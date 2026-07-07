# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACDashboard(models.Model):
    _name = 'naac.dashboard'
    _description = 'NAAC Dashboard'

    name = fields.Char(default='NAAC Dashboard')

    @api.model
    def get_dashboard_data(self):
        """Return NAAC dashboard data for OWL component."""
        NAACCriterion = self.env['naac.criterion']
        NAACEvidence = self.env['naac.evidence']
        NAACActivity = self.env['naac.department.activity']
        NAACResearch = self.env['naac.faculty.research']
        NAACProgression = self.env['naac.student.progression']

        # Overall readiness
        criteria = NAACCriterion.search([])
        overall_readiness = sum(criteria.mapped('readiness_score')) / len(criteria) if criteria else 0

        # Per criterion scores
        criterion_scores = []
        for c in criteria:
            criterion_scores.append({
                'number': c.criterion_number,
                'name': c.name,
                'score': round(c.readiness_score, 1),
                'evidence_count': c.evidence_count,
                'activity_count': len(c.activity_ids),
            })

        # Evidence stats
        total_evidence = NAACEvidence.search_count([])
        verified_evidence = NAACEvidence.search_count([('is_verified', '=', True)])
        pending_evidence = total_evidence - verified_evidence

        # Activity stats
        total_activities = NAACActivity.search_count([])
        verified_activities = NAACActivity.search_count([('state', '=', 'verified')])
        pending_activities = NAACActivity.search_count([('state', '=', 'submitted')])

        # Research stats
        total_papers = NAACResearch.search_count([
            ('research_type', 'in', ['journal_paper', 'conference_paper'])
        ])
        total_patents = NAACResearch.search_count([
            ('research_type', 'in', ['patent_filed', 'patent_granted'])
        ])
        total_grants = NAACResearch.search_count([
            ('research_type', '=', 'research_grant')
        ])

        # Student progression
        placements = NAACProgression.search_count([('progression_type', '=', 'placement')])
        higher_studies = NAACProgression.search_count([('progression_type', '=', 'higher_study')])
        entrepreneurs = NAACProgression.search_count([('progression_type', '=', 'entrepreneur')])

        # Department readiness
        departments = self.env['university.department'].search([])
        dept_readiness = []
        for dept in departments:
            dept_acts = NAACActivity.search_count([
                ('department_id', '=', dept.id),
                ('state', '=', 'verified'),
            ])
            total_dept_acts = NAACActivity.search_count([('department_id', '=', dept.id)])
            pct = (dept_acts / total_dept_acts * 100) if total_dept_acts else 0
            dept_readiness.append({
                'dept': dept.name,
                'verified': dept_acts,
                'total': total_dept_acts,
                'pct': round(pct, 1),
            })

        # Recent activities
        recent_activities = NAACActivity.search([], order='date desc', limit=5)
        recent_list = []
        for act in recent_activities:
            recent_list.append({
                'id': act.id,
                'name': act.name,
                'dept': act.department_id.name if act.department_id else '',
                'criterion': act.criterion_id.display_name if act.criterion_id else '',
                'date': act.date.strftime('%d %b %Y') if act.date else '',
                'state': act.state,
            })

        return {
            'overall_readiness': round(overall_readiness, 1),
            'criterion_scores': criterion_scores,
            'total_evidence': total_evidence,
            'verified_evidence': verified_evidence,
            'pending_evidence': pending_evidence,
            'total_activities': total_activities,
            'verified_activities': verified_activities,
            'pending_activities': pending_activities,
            'total_papers': total_papers,
            'total_patents': total_patents,
            'total_grants': total_grants,
            'placements': placements,
            'higher_studies': higher_studies,
            'entrepreneurs': entrepreneurs,
            'dept_readiness': dept_readiness,
            'recent_activities': recent_list,
        }
