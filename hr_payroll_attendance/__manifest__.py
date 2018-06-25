# -*- coding: utf-8 -*-

{
    'name': 'HR Payroll Attendance',
    'category': 'Human Resources',
    'author': 'Maha Hamza <mahasaeedhamza@gmail.com>',
    'depends': ['hr_payroll','hr_attendance','hr_holidays'],
    'data': [
        'views/hr_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
