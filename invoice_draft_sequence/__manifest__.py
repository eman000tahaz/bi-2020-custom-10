# -*- coding: utf-8 -*-
{
    'name': 'Draft Invoice Sequence',
    'category': 'Accounting',
    'author': "Maha Hamza <mahasaeedhamza@gmail.com>",
    'depends': ['account'],
    'data': [
        'views/account_invoice_view.xml',
        'reports/account_invoice_template.xml',
             ],
    'installable': True,
}
