# -*- coding: utf-8 -*-

import json
from odoo import http
from odoo.http import request


class NAACDashboardAPI(http.Controller):

    @http.route('/naac/api/dashboard', type='json', auth='user')
    def get_naac_dashboard(self, **kwargs):
        """JSON API endpoint for NAAC dashboard data."""
        data = request.env['naac.dashboard'].sudo().get_dashboard_data()
        return data

    @http.route('/iic/api/dashboard', type='json', auth='user')
    def get_iic_dashboard(self, **kwargs):
        """JSON API endpoint for IIC dashboard data."""
        data = request.env['iic.dashboard'].sudo().get_dashboard_data()
        return data

    @http.route('/naac/api/criterion/<int:criterion_id>', type='json', auth='user')
    def get_criterion_data(self, criterion_id, **kwargs):
        """Get detailed data for a specific NAAC criterion."""
        criterion = request.env['naac.criterion'].sudo().browse(criterion_id)
        if not criterion.exists():
            return {'error': 'Not found'}

        metrics = []
        for m in criterion.metric_ids:
            metrics.append({
                'code': m.metric_code,
                'name': m.name,
                'target': m.target_value,
                'actual': m.actual_value,
                'achievement': m.achievement_pct,
                'status': m.status,
                'evidence_count': m.evidence_count,
            })

        return {
            'id': criterion.id,
            'number': criterion.criterion_number,
            'name': criterion.name,
            'readiness_score': criterion.readiness_score,
            'metrics': metrics,
        }
