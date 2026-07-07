{
    'name': 'MIT OCW Integration',
    'version': '1.0',
    'depends': ['website_slides'],
    'data': [
        'security/ir.model.access.csv',
        'views/slide_channel_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': False,
}