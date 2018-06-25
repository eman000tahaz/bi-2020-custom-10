# -*- coding: utf-8 -*-
{
    'name': 'BI 2020',
    'version': '10.0.1.0.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'summary': 'Bi 2020 accounting Customizations',
    'author': "Eman.taha@bisolutions.com",
    'depends': ['account'],
    'data': [
                'views/res_company_views.xml',
                'views/account_bank_statement_views.xml',
                'views/report_account_bank_statement.xml',
                'views/bi_report.xml',
        ],
    'application': True,
    'installable': True,
}
