{
    'name': 'Interior Design',
    'version': '1.0',
    'depends': ['base', 'web', 'portal', 'rest_api_odoo', 'mail'],
    'external_dependencies': {
        'python': ['threestudio', 'torch', 'reportlab', 'Pillow', 'google-cloud-vision'],
    },
    'data': [
        'security/ir.model.access.csv',
        # 'views/design_project_views.xml',
        'views/design_service_request_views.xml',
        'templates/portal_my_designs.xml',
        'templates/portal_design_detail.xml',
        'templates/portal_request_service_form.xml',
    ],
    'qweb': [],
    'installable': True,
    'application': True,
}