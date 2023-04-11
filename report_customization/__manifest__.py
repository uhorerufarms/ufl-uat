# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Accounting Report Customization",
    'summary': 'Print Payable, Receivale Ageing report and Partner Ledger in USD',

    'description': """
        Display all active currencies on accounting reports Partner Ledger, Aged Receivable and Aged Payable. Based on the selected currency change the report
        Ticket ID: 3234580
    """,
    'author': "Odoo",
    'website': "http://www.odoo.com",
    'category': 'Customization',
    'version': '1.0.1',
    'depends': ['account', 'account_reports'],
    'data': [
        'views/account_report_view.xml',
        'views/account_report.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'report_customization/static/src/js/*.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True
}
