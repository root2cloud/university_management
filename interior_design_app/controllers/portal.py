from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import json
import logging

_logger = logging.getLogger(__name__)


class DesignPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'design_count' in counters:
            user = request.env.user
            domain = [('partner_id', '=', user.partner_id.id)]
            values['design_count'] = request.env['design.project'].search_count(domain)
        return values

    @http.route('/test-route', type='http', auth="public", website=True)
    def test_route(self, **kwargs):
        return "Test route is working!"

    @http.route(['/my/designs', '/my/designs/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_designs(self, page=1, **kwargs):
        DesignProject = request.env['design.project']
        user = request.env.user
        domain = [('partner_id', '=', user.partner_id.id)]
        design_count = DesignProject.search_count(domain)
        pager = request.website.pager(
            url='/my/designs',
            total=design_count,
            page=page,
            step=10,
        )
        designs = DesignProject.search(domain, limit=10, offset=pager['offset'])
        values = {
            'designs': designs,
            'pager': pager,
            'default_url': '/my/designs',
        }
        return request.render("interior_design.portal_my_designs", values)

    @http.route('/my/designs/<int:design_id>', type='http', auth="user", website=True)
    def portal_my_design_detail(self, design_id, **kwargs):
        DesignProject = request.env['design.project']
        user = request.env.user
        design = DesignProject.search([
            ('id', '=', design_id),
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)
        if not design:
            return request.not_found()
        values = {
            'design': design,
        }
        _logger.info("Rendering portal_my_design_detail with values: %s", values)
        return request.render("interior_design.portal_my_design_detail", values)

    @http.route('/my/designs/<int:design_id>/request_service', type='http', auth="user", website=True)
    def portal_request_service(self, design_id, **kwargs):
        DesignProject = request.env['design.project']
        user = request.env.user
        design = DesignProject.search([
            ('id', '=', design_id),
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)
        if not design:
            return request.not_found()
        if design.state != 'expired':
            return request.redirect(f'/my/designs/{design_id}')
        values = {
            'design': design,
        }
        return request.render("interior_design.portal_request_service_form", values)

    @http.route('/my/designs/<int:design_id>/request_service/submit', type='http', auth="user", website=True,
                methods=['POST'], csrf=True)
    def portal_request_service_submit(self, design_id, **kwargs):
        DesignProject = request.env['design.project']
        user = request.env.user
        design = DesignProject.search([
            ('id', '=', design_id),
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)
        if not design:
            return request.not_found()
        if design.state != 'expired':
            return request.redirect(f'/my/designs/{design_id}')

        description = kwargs.get('description')
        if not description:
            return request.redirect(f'/my/designs/{design_id}/request_service')

        request.env['design.service.request'].create({
            'project_id': design_id,
            'description': description,
            'request_date': fields.Date.today(),
            'state': 'draft',
        })
        return request.redirect(f'/my/designs/{design_id}')

    # API Endpoints (Added from old portal code)
    @http.route('/api/design.project', type='http', auth='api_key', methods=['GET'])
    def get_design_projects(self, **kwargs):
        _logger.info("Starting GET /api/design.project with kwargs: %s", kwargs)
        try:
            # Check if model exists
            if 'design.project' not in request.env:
                _logger.error("Model design.project not found")
                return http.Response(
                    json.dumps({'error': 'Model design.project not found'}),
                    content_type='application/json',
                    status=500
                )
            # Fetch projects with minimal fields
            projects = request.env['design.project'].sudo().search_read(
                domain=[],
                fields=['name', 'room_name', 'document_name']
            )
            _logger.info("Fetched %s design projects: %s", len(projects), projects)
            result = []
            for project in projects:
                # Check if design.component model exists
                if 'design.component' not in request.env:
                    _logger.error("Model design.component not found")
                    project['components'] = []
                else:
                    components = request.env['design.component'].sudo().search_read(
                        domain=[('project_id', '=', project['id'])],
                        fields=['name', 'component_type', 'quantity', 'dimensions']
                    )
                    project['components'] = components
                    _logger.info("Project %s has %s components", project['name'], len(components))
                result.append(project)
            _logger.info("Returning %s projects: %s", len(result), result)
            return http.Response(
                json.dumps(result, default=str),
                content_type='application/json',
                status=200
            )
        except Exception as e:
            _logger.error("Error in GET /api/design.project: %s", str(e), exc_info=True)
            return http.Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=500
            )

    @http.route('/api/design.component', type='http', auth='api_key', methods=['GET'])
    def get_design_components(self, **kwargs):
        _logger.info("Starting GET /api/design.component with kwargs: %s", kwargs)
        try:
            # Check if model exists
            if 'design.component' not in request.env:
                _logger.error("Model design.component not found")
                return http.Response(
                    json.dumps({'error': 'Model design.component not found'}),
                    content_type='application/json',
                    status=500
                )
            components = request.env['design.component'].sudo().search_read(
                domain=[],
                fields=['name', 'component_type', 'quantity', 'dimensions', 'project_id']
            )
            _logger.info("Fetched %s design components: %s", len(components), components)
            return http.Response(
                json.dumps(components, default=str),
                content_type='application/json',
                status=200
            )
        except Exception as e:
            _logger.error("Error in GET /api/design.component: %s", str(e), exc_info=True)
            return http.Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=500
            )
