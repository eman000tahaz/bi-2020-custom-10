# -*- coding: utf-8 -*-
{
    'name': 'Emraties Taxes',
    'summary': 'United Arab Emraties Tax.',
    'version': '10.0',
    'category': 'Accounting, Sale',
    'license': 'AGPL-3',
    'author': 'Mohamed Mtloob',
    'website': 'https://eg.linkedin.com/in/mohamed-mtloob-62b33b76',
    'depends': ['account','sale','purchase'],
    'data': [
             'views/sale_view.xml',
             'report/sale_order_templates.xml',
             'report/report_invoice.xml',
             ],
    "images": [
        'static/description/banner.png'
    ],
    'installable': True,
}
