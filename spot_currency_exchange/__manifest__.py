# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Spot currency exchange',
    'version': '16.0.0.1',
    'category': 'Accounting',
    'sequence': 357,
    'summary': 'This module is for spot exchange rate.',
    'description': """Spot Currency Exchange""",
    'depends': ['account'],
    'data': [
        'views/account_payment_views.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
