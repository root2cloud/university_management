# -*- coding: utf-8 -*-
{
    'name': 'LMS eLearning with ORA',
    'description': 'Open Response Assessment',
    'category': 'Website/eLearning',
    'summary': 'Manage and publish an eLearning platform',
    'sequence': 10,
    'version': '2.2',
    'website': 'https://www.manprax.com',
    'author': 'ManpraX Software LLP',
    'depends': ['website_slides'],
    'data': [
        'data/ir_cron_data.xml',
        'security/ir.model.access.csv',
        'views/slide_assessment_view.xml',
        'views/templates.xml',
        'views/slide_fullscreen_view.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'website_ora_elearning/static/src/scss/website_slides.scss',
            'website_ora_elearning/static/src/js/ora_fullscreen.js',
            'website_ora_elearning/static/src/js/website_ora.js',
            'website_ora_elearning/static/src/xml/slide_ora.xml',
        ],
    },
    'qweb': [],
    'images': ["static/description/images/banner.png"],
    'application': True,
    'license': 'AGPL-3',
}
