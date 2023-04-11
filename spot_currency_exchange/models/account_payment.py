# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    spot_currency_rate = fields.Float(help='This is latest spot currency rate after negotiating with bank.')
    is_spot_currency = fields.Boolean('Spot Currency')
    is_same_currency = fields.Boolean("Is currency_id different from the company_currency_id", compute='_compute_is_same_currency', store=True)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None):
        if self.is_spot_currency:
            self = self.with_context(is_spot_currency=self.is_spot_currency, spot_rate=self.spot_currency_rate)
        return super(AccountPayment, self)._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals)

    @api.constrains('spot_currency_rate')
    def _check_spot_currency_rate(self):
        if any(payment.spot_currency_rate <= 0 and payment.is_spot_currency for payment in self):
            raise ValidationError(_('The value of Spot Currency Rate must be greater than 0.'))


    @api.model
    def _get_trigger_fields_to_synchronize(self):
        res = super(AccountPayment, self)._get_trigger_fields_to_synchronize()
        return res + ('spot_currency_rate', 'is_spot_currency')

    @api.depends('currency_id', 'destination_journal_id')
    def _compute_is_same_currency(self):
        for payment in self:
            payment.is_same_currency = bool(payment.currency_id and payment.destination_journal_id.currency_id\
                    and payment.currency_id != payment.destination_journal_id.currency_id and payment.destination_journal_id.type in ['bank', 'cash'])
