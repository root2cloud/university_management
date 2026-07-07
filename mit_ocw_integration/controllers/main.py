from odoo import http
from odoo.http import request


class OCWController(http.Controller):
    @http.route('/ocw/sync', auth='user', type='json', methods=['POST'])
    def sync_ocw_courses(self):
        """Manually trigger OCW sync"""
        request.env['slide.channel'].sudo()._sync_ocw_courses()
        return {'status': 'success'}
