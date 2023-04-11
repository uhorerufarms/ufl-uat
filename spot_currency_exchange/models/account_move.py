# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo import models, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        for line in self.invoice_line_ids.filtered(lambda l: l.currency_id != l.company_currency_id and not self.payment_id.is_spot_currency):
            rate = line.currency_id._get_rates_at_date(line.company_id, line.move_id.invoice_date or line.move_id.date)
            if rate.get(line.currency_id.id) is None:
                raise UserError(_("The %s Exchange Rate for %s has not been updated, contact system administrator." % (line.currency_id.name, (line.move_id.invoice_date or line.move_id.date).strftime('%d-%m-%Y'))))
        return super(AccountMove, self)._post(soft)
