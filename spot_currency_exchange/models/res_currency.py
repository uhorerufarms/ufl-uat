# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _


class ResCurrency(models.Model):
    _inherit = 'res.currency'    

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company, date):
        if self._context.get('is_spot_currency'):
            return self._context.get('spot_rate', 1)
        return super(ResCurrency, self)._get_conversion_rate(from_currency, to_currency, company, date)

    def _get_rates_at_date(self, company, date):
        if not self.ids:
            return {}
        self.env['res.currency.rate'].flush_model(['rate', 'currency_id', 'company_id', 'name'])
        query = """SELECT c.id,
                          COALESCE((SELECT r.rate FROM res_currency_rate r
                                  WHERE r.currency_id = c.id AND r.name = %s
                                    AND (r.company_id IS NULL OR r.company_id = %s)
                               ORDER BY r.company_id, r.name DESC
                                  LIMIT 1)) AS rate
                   FROM res_currency c
                   WHERE c.id IN %s"""
        self._cr.execute(query, (date, company.id, tuple(self.ids)))
        currency_rates = dict(self._cr.fetchall())
        return currency_rates
