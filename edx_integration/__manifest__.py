{
    'name': 'eDX Course Integration (Demo)',
    'version': '1.0',
    'summary': 'Demo: Integrate eDX courses into Odoo eLearning',
    'depends': ['website_slides', 'website', 'hr'],
    'category': 'Education',
    'data': [
        'security/ir.model.access.csv',
        'views/course_views.xml',
        'views/course_enrollment_report_views.xml',
        'views/edx_courses_template_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': True,
}