# -*- coding: utf-8 -*-
{
    'name': "DashBoat",
    'summary': "Turn your Odoo data into smart, actionable insights with an AI-powered dashboard and conversational assistant",
    'description': """
        DashBoat is your intelligent business companion that transforms complex Odoo data into clear, real-time, and predictive insights. With AI-powered analytics and a natural language chatbot interface, it enables business users and decision-makers to query sales, revenue, customer or inventory metrics using simple questions - no SQL or technical skills required.
        Built for fast-growing teams, DashBoat helps forecast trends, identify anomalies and guide strategic decisions using smart visualizations and conversation-driven data exploration.
        Whether you're in sales, finance or operations, DashBoat is designed to help you work smarter, not harder.
    """,
    'author': 'Sufalam Technologies',
    'website': 'https://www.sufalamtech.com',
    'license': 'LGPL-3',
    'version': '1.1',
    'depends': [
        'base',
        'purchase',
        'contacts',
        'web',
        'sale',
        'sale_management',
        'crm'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/predictive_engine_views.xml',
        'views/predictive_registration_views.xml',
        'views/data_analysis_views.xml',
        'views/data_analysis_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # 'a_predictive_engine/static/src/js/predictive_engine_chat.js',
            'DashBoat/static/src/js/chatbot_enter_send.js',
            # 'a_predictive_engine/static/src/js/chat_enter_key.js',
            
        ],
    },
    'images': [
         'static/description/banner.jpg',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'post_init_hook': 'post_init_prediction_analysis',
    'uninstall_hook': 'unregister_prediction_analysis',
 
    'external_dependencies': {
        'python': ['pandas', 'matplotlib', 'seaborn', 'reportlab', 'openai', 'numpy', 'plotly'],
    },
}
