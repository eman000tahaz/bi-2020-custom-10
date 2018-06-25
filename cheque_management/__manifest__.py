# -*- coding: utf-8 -*-
{
    'name': 'Cheque Management',
    'summary': 'Full cheque life cycle Management.',
    'version': '10.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'author': 'Mohamed Mtloob',
    'website': 'https://eg.linkedin.com/in/mohamed-mtloob-62b33b76',
    'depends': ['account','account_check_printing'],
    'data': ['security/ir.model.access.csv',
             'views/payment_view.xml',
             'report/report_payment.xml'],
    "images": [
        'static/description/banner.png'
    ],
    'installable': True,
}
