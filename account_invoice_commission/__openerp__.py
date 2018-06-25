# -*- encoding: utf-8 -*-
{
    'name': 'Supplier Invoice Margin and Commissions',
    'category': 'Accounting & Finance',
    'author': 'Maha Hamza <mahasaeedhamza@gmail.com>',
    'depends': ['account'],
    'data': [
        'views/account_invoice_view.xml',
        'views/res_partner_view.xml',
        'views/product_view.xml',
    ],
    'installable': True,
}
