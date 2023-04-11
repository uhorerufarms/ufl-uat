# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import json
from odoo import models, api, fields, _
from odoo.tools.misc import formatLang


class AccountReport(models.Model):
    _inherit = "account.report"

    filter_currency = fields.Boolean(
        string="Currency",
        compute=lambda x: x._compute_report_option_filter('filter_currency'),
        readonly=False, store=True, depends=['root_report_id'],)

    def _init_options_filter_currency(self, options, previous_options=None):
        if self.filter_currency is False:
            return
        options['currency'] = True
        options['currency_ids'] = previous_options and previous_options.get('currency_ids') or []
        options['selected_currency_id'] = \
            previous_options and previous_options.get('selected_currency_id') or None
        if len(options['currency_ids']) == 0:
            options['currency_ids'] = []
            for currency in  self.env['res.currency'].search([('active', '=', True)]):
                options['currency_ids'].append({
                    'id': currency.id,
                    'name': currency.name
                    })
            options['selected_currency_id'] = self.env.company.currency_id.id

    def _get_partner_and_general_ledger_initial_balance_line(self, options, parent_line_id, eval_dict, account_currency=None, level_shift=0):
        if not 'selected_currency_id' in options:
            return super()._get_partner_and_general_ledger_initial_balance_line(options, parent_line_id, eval_dict, account_currency, level_shift)
        else:
            line_columns = []
            for column in options['columns']:
                col_value = eval_dict[column['column_group_key']].get(column['expression_label'])
                col_expr_label = column['expression_label']

                if col_value is None or (col_expr_label == 'amount_currency' and not account_currency):
                    line_columns.append({})
                else:
                    if col_expr_label == 'amount_currency':
                        formatted_value = self.format_value(col_value, currency=account_currency, figure_type=column['figure_type'])
                    else:
                        formatted_value = self.format_value(col_value, figure_type=column['figure_type'])
                    self = self.with_context(selected_currency_id=options['selected_currency_id'])
                    line_columns.append({
                        'name': formatted_value,
                        'no_format': col_value,
                        'class': 'number',
                    })

            if not any(column.get('no_format') for column in line_columns):
                return None

            return {
                'id': self._get_generic_line_id(None, None, parent_line_id=parent_line_id, markup='initial'),
                'class': 'o_account_reports_initial_balance',
                'name': _("Initial Balance"),
                'level': 2 + level_shift,
                'parent_id': parent_line_id,
                'columns': line_columns,
            }

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=1):
        if not self.env.context.get('selected_currency_id'):
            return super().format_value(value, currency, blank_if_zero, figure_type, digits)
        else:
            if figure_type == 'monetary' or self.env.context.get('figure_type') == 'monetary':
                currency = \
                self.env['res.currency'].browse(self.env.context.get('selected_currency_id'))
                formatted_amount = formatLang(self.env, value, currency_obj=currency,
                                              digits=digits)
                if figure_type == 'percentage':
                    return f"{formatted_amount}%"
                return formatted_amount
            else:
                return super().format_value(value, currency, blank_if_zero, figure_type, digits)

    @api.model
    def _build_static_line_columns(self, line, options, all_column_groups_expression_totals):
        if not 'selected_currency_id' in options:
            return super()._build_static_line_columns(line, options,
                                                      all_column_groups_expression_totals)
        else:
            line_expressions_map = {expr.label: expr for expr in line.expression_ids}
            columns = []
            for column_data in options['columns']:
                current_group_expression_totals = \
                    all_column_groups_expression_totals[column_data['column_group_key']]
                target_line_res_dict = \
                {expr.label: current_group_expression_totals[expr] for expr in line.expression_ids}

                column_expr_label = column_data['expression_label']
                column_res_dict = target_line_res_dict.get(column_expr_label, {})
                column_value = column_res_dict.get('value')
                column_has_sublines = column_res_dict.get('has_sublines', False)
                column_expression = line_expressions_map.get(column_expr_label,
                                                             self.env['account.report.expression'])
                figure_type = column_expression.figure_type or column_data['figure_type']
                # Handle info popup
                info_popup_data = {}

                # Check carryover
                carryover_expr_label = '_carryover_%s' % column_expr_label
                carryover_value = target_line_res_dict.get(carryover_expr_label, {}).get('value', 0)
                if self.env.company.currency_id.compare_amounts(0, carryover_value) != 0:
                    info_popup_data['carryover'] = self.format_value(carryover_value,
                                                                     figure_type='monetary')
                    carryover_expression = line_expressions_map[carryover_expr_label]
                    if carryover_expression.carryover_target:
                        info_popup_data['carryover_target'] = \
                        carryover_expression._get_carryover_target_expression(options).display_name
                    # If it's not set, it means the carryover needs to target the same expression
                applied_carryover_value = \
                    target_line_res_dict.get('_applied_carryover_%s' % column_expr_label,
                                             {}).get('value', 0)
                if self.env.company.currency_id.compare_amounts(0, applied_carryover_value) != 0:
                    info_popup_data['applied_carryover'] = self.format_value(applied_carryover_value,
                                                                             figure_type='monetary')
                    info_popup_data['allow_carryover_audit'] = \
                                    self.user_has_groups('base.group_no_one')
                    info_popup_data['expression_id'] = \
                        line_expressions_map['_applied_carryover_%s' % column_expr_label]['id']
                # Handle manual edition popup
                edit_popup_data = {}
                if column_expression.engine == 'external' and column_expression.subformula \
                    and len(options.get('multi_company', [])) < 2 \
                    and (not options['available_vat_fiscal_positions'] or \
                        options['fiscal_position'] != 'all'):
                    # Compute rounding for manual values
                    rounding = None
                    rounding_opt_match = re.search(r"\Wrounding\W*=\W*(?P<rounding>\d+)", column_expression.subformula)
                    if rounding_opt_match:
                        rounding = int(rounding_opt_match.group('rounding'))
                    elif figure_type == 'monetary':
                        rounding = self.env.company.currency_id.rounding

                    if 'editable' in column_expression.subformula:
                        edit_popup_data = {
                            'column_group_key': column_data['column_group_key'],
                            'target_expression_id': column_expression.id,
                            'rounding': rounding,
                        }

                    formatter_params = {'digits': rounding}
                else:
                    formatter_params = {}

                # Build result
                blank_if_zero = column_expression.blank_if_zero or column_data.get('blank_if_zero')

                if column_value is None:
                    formatted_name = ''
                else:
                    self = self.with_context(selected_currency_id=options['selected_currency_id'],
                                             figure_type=figure_type)
                    formatted_name = self.format_value(
                        column_value,
                        figure_type=figure_type,
                        blank_if_zero=blank_if_zero,
                        **formatter_params
                    )

                column_data = {
                    'name': formatted_name,
                    'style': 'white-space:nowrap; text-align:right;',
                    'no_format': column_value,
                    'column_group_key': options['columns'][len(columns)]['column_group_key'],
                    'auditable': column_value is not None and column_expression.auditable,
                    'expression_label': column_expr_label,
                    'has_sublines': column_has_sublines,
                    'report_line_id': line.id,
                    'class': 'number' if isinstance(column_value, (int, float)) else '',
                    'is_zero': column_value is None or (figure_type in ('float', 'integer', 'monetary') and self.is_zero(column_value, figure_type=figure_type, **formatter_params)),
                }

                if info_popup_data:
                    column_data['info_popup_data'] = json.dumps(info_popup_data)

                if edit_popup_data:
                    column_data['edit_popup_data'] = json.dumps(edit_popup_data)
                columns.append(column_data)
            return columns
