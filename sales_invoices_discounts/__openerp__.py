# -*- coding: utf-8 -*-
{
    'name': 'Sales & Invoices Discount',
    'category': 'Accounting',
    'author': 'Maha Hamza <mahasaeedhamza@gmail.com>',
    'depends': ['base', 'account', 'account_accountant', 'sale'],
    'data': ['invoice_discount/invoice_discount_view.xml',
             'sale_discount/sale_discount_view.xml',
             'reports/invoice_report_edit.xml',
             'reports/saleorder_report_edit.xml', ],
    'installable': True,
    'auto_install': False,
    'application': True,
}
