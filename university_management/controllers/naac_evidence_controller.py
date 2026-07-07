# -*- coding: utf-8 -*-

import base64
from odoo import http
from odoo.http import request


class NAACEvidenceController(http.Controller):

    @http.route('/naac/evidence/upload', type='http', auth='user', methods=['POST'], csrf=True)
    def upload_evidence(self, **post):
        """Handle NAAC evidence file upload from portal."""
        criterion_id = int(post.get('criterion_id', 0))
        metric_id = int(post.get('metric_id', 0)) if post.get('metric_id') else False
        department_id = int(post.get('department_id', 0)) if post.get('department_id') else False
        academic_year_id = int(post.get('academic_year_id', 0)) if post.get('academic_year_id') else False
        doc_type = post.get('doc_type', 'pdf_report')
        name = post.get('name', 'Untitled Evidence')

        ufile = post.get('document')
        if not ufile or not criterion_id:
            return request.redirect('/naac/evidence/upload?error=1')

        file_content = base64.b64encode(ufile.read())

        evidence = request.env['naac.evidence'].sudo().create({
            'name': name,
            'criterion_id': criterion_id,
            'metric_id': metric_id or False,
            'department_id': department_id or False,
            'academic_year_id': academic_year_id or False,
            'doc_type': doc_type,
            'document': file_content,
            'document_filename': ufile.filename,
        })

        return request.redirect(f'/web#id={evidence.id}&model=naac.evidence&view_type=form')

    @http.route('/naac/evidence/upload', type='http', auth='user', website=True)
    def evidence_upload_form(self, **kwargs):
        """Render evidence upload form."""
        criteria = request.env['naac.criterion'].sudo().search([])
        departments = request.env['university.department'].sudo().search([])
        return request.render('university_management.naac_evidence_upload_portal', {
            'criteria': criteria,
            'departments': departments,
            'error': kwargs.get('error'),
        })
