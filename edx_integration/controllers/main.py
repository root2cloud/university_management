from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class EdxCourseController(http.Controller):

    @http.route('/slides', type='http', auth='public', website=True)
    def edx_courses(self, **kwargs):
        """Render a webpage displaying eDX courses"""
        courses = request.env['elearning.course'].sudo().search([('source', '=', 'eDX')])
        return request.render('edx_integration.edx_courses_template', {
            'courses': courses,
        })

    @http.route('/edx/api/courses', type='json', auth='public', methods=['GET'])
    def edx_courses_api(self, **kwargs):
        """API endpoint to return eDX courses as JSON"""
        try:
            courses = request.env['elearning.course'].sudo().search_read(
                [('source', '=', 'eDX')],
                ['name', 'description', 'course_url', 'external_id', 'last_sync', 'video_url']
            )
            return {
                'status': 'success',
                'courses': courses,
                'count': len(courses)
            }
        except Exception as e:
            _logger.error(f"Error fetching eDX courses: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }