#-*- coding:utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Work Entries - Contract Enterprise',
    'category': 'Human Resources/Employees',
    'sequence': 39,
    'summary': 'Manage work entries',
    'installable': True,
    'depends': [
        'hr_work_entry_contract',
    ],
    'data': [
        'views/hr_payroll_menu.xml',
    ],
    'auto_install': True,
    'license': 'LGPL-3',
}
