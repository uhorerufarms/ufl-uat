# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict

from odoo import models, _, fields
from odoo.tools.misc import format_date


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _get_report_line_move_line(self, options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift=0):
        if not 'selected_currency_id' in options:
            return super()._get_report_line_move_line(options, aml_query_result, partner_line_id, init_bal_by_col_group, level_shift)
        else:
            custom_currency = self.env['res.currency'].browse(options['selected_currency_id'])
            if aml_query_result['payment_id']:
                caret_type = 'account.payment'
            else:
                caret_type = 'account.move.line'

            columns = []
            report = self.env['account.report']
            for column in options['columns']:
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                col_expr_label = column['expression_label']
                if col_expr_label == 'ref':
                    col_value = report._format_aml_name(aml_query_result['name'], aml_query_result['ref'], aml_query_result['move_name'])
                else:
                    col_value = aml_query_result[col_expr_label] if column['column_group_key'] == aml_query_result['column_group_key'] else None

                if col_value is None:
                    columns.append({})
                else:
                    col_class = 'number'

                    if col_expr_label == 'date_maturity':
                        formatted_value = format_date(self.env, fields.Date.from_string(col_value))
                        col_class = 'date'
                    elif col_expr_label == 'amount_currency':
                        currency = self.env['res.currency'].browse(aml_query_result['currency_id'])
                        currency_converted_amount = self.env.company.currency_id.with_context(date=aml_query_result['date']).compute(col_value, custom_currency)
                        formatted_value = report.format_value(currency_converted_amount, currency=custom_currency, figure_type=column['figure_type'])
                        report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    elif col_expr_label == 'balance':
                        col_value += init_bal_by_col_group[column['column_group_key']]
                        currency_converted_amount = self.env.company.currency_id.with_context(date=aml_query_result['date']).compute(col_value, custom_currency)
                        formatted_value = report.format_value(currency_converted_amount, figure_type=column['figure_type'], blank_if_zero=column['blank_if_zero'])
                        report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    else:
                        if col_expr_label == 'ref':
                            col_class = 'o_account_report_line_ellipsis'
                        elif col_expr_label not in ('debit', 'credit'):
                            col_class = ''
                        formatted_value = report.format_value(col_value, figure_type=column['figure_type'])
                        if column['figure_type'] == 'monetary':
                            report = report.with_context(selected_currency_id=options['selected_currency_id'])
                            currency_converted_amount = self.env.company.currency_id.with_context(date=aml_query_result['date']).compute(col_value, custom_currency)
                            formatted_value = report.format_value(currency_converted_amount,figure_type=column['figure_type'], blank_if_zero=column['blank_if_zero'])
                        else:
                            formatted_value = report.format_value(col_value, figure_type=column['figure_type'])

                    columns.append({
                        'name': formatted_value,
                        'no_format': col_value,
                        'class': col_class,
                    })

            return {
                'id': report._get_generic_line_id('account.move.line', aml_query_result['id'], parent_line_id=partner_line_id),
                'parent_id': partner_line_id,
                'name': format_date(self.env, aml_query_result['date']),
                'class': 'text-muted' if aml_query_result['key'] == 'indirectly_linked_aml' else 'text',  # do not format as date to prevent text centering
                'columns': columns,
                'caret_options': caret_type,
                'level': 2 + level_shift,
            }

    def _get_initial_balance_values(self, partner_ids, options):
        if not 'selected_currency_id' in options:
            return super()._get_initial_balance_values(partner_ids, options)
        else:
            report = self.env['account.report'].browse(options['report_id'])
            report = report.with_context(selected_currency_id=options['selected_currency_id'])
            custom_currency = self.env['res.currency'].browse(options['selected_currency_id'])
            queries = []
            params = []
            report = self.env.ref('account_reports.partner_ledger_report')
            ct_query = self.env['res.currency']._get_query_currency_table(options)
            for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                new_options = self._get_options_initial_balance(column_group_options)
                tables, where_clause, where_params = report._query_get(new_options, 'normal', domain=[('partner_id', 'in', partner_ids)])
                params.append(column_group_key)
                params += where_params
                queries.append(f"""
                    SELECT
                        account_move_line.partner_id,
                        %s                        AS column_group_key,
                        account_move_line.id      As move_line_id,
                        account_move_line.currency_id      As move_line_currency_id,
                        account_move_line.date    AS date,
                        account_move_line.debit   AS debit,
                        account_move_line.credit  AS credit,
                        account_move_line.balance AS balance
                    FROM {tables}
                    LEFT JOIN {ct_query} ON currency_table.company_id = account_move_line.company_id
                    WHERE {where_clause}
                    GROUP BY account_move_line.partner_id,
                    account_move_line.id,account_move_line.currency_id,account_move_line.date,account_move_line.debit,
                    account_move_line.credit,account_move_line.balance
                """)
            self._cr.execute(" UNION ALL ".join(queries), params)

            init_balance_by_col_group = {
                partner_id: {column_group_key: {} for column_group_key in options['column_groups']}
                for partner_id in partner_ids
            }
            for result in self._cr.dictfetchall():
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                result['debit'] = self.env.company.currency_id.with_context(\
                    date=result['date']).compute(result['debit'], custom_currency)
                result['credit'] = self.env.company.currency_id.with_context(\
                    date=result['date']).compute(result['credit'], custom_currency)
                result['balance'] = self.env.company.currency_id.with_context(\
                    date=result['date']).compute(result['balance'], custom_currency)
                init_balance_by_col_group[result['partner_id']][result['column_group_key']] = result
            return init_balance_by_col_group

    def _get_query_sums(self, options):
        if not 'selected_currency_id' in options:
            return super()._get_query_sums(options)
        else:
            params = []
            queries = []
            report = self.env.ref('account_reports.partner_ledger_report')
            report = report.with_context(selected_currency_id=options['selected_currency_id'])
            for column_group_key, column_group_options in report._split_options_per_column_group(options).items():
                tables, where_clause, where_params = report._query_get(column_group_options, 'normal')
                params.append(column_group_key)
                params += where_params
                queries.append(f"""
                    SELECT
                        account_move_line.partner_id    AS groupby,
                        account_move_line.date          AS date,
                        %s                              AS column_group_key,
                        account_move_line.debit         AS debit,
                        account_move_line.credit        AS credit,
                        account_move_line.balance       AS balance
                    FROM {tables}
                    WHERE {where_clause}
                    GROUP BY account_move_line.partner_id,account_move_line.date,
                    account_move_line.debit,account_move_line.credit,account_move_line.balance
                """)
            return ' UNION ALL '.join(queries), params

    def _query_partners(self, options):
        if not 'selected_currency_id' in options:
            return super()._query_partners(options)
        else:
            report = self.env['account.report'].browse(options.get('report_id'))
            report = report.with_context(selected_currency_id=options['selected_currency_id'])
            def assign_sum(row):
                custom_currency = self.env['res.currency'].browse(options['selected_currency_id'])
                row['debit'] = \
                    self.env.company.currency_id.with_context(\
                        date=row['date']).compute(row['debit'], custom_currency)
                row['credit'] = \
                    self.env.company.currency_id.with_context(\
                        date=row['date']).compute(row['credit'], custom_currency)
                row['balance'] = \
                    self.env.company.currency_id.with_context(\
                        date=row['date']).compute(row['balance'], custom_currency)
                fields_to_assign = ['balance', 'debit', 'credit']
                if any(not company_currency.is_zero(row[field]) for field in fields_to_assign):
                    groupby_partners.setdefault(row['groupby'], defaultdict(lambda: defaultdict(float)))
                    for field in fields_to_assign:
                        groupby_partners[row['groupby']][row['column_group_key']][field] += row[field]
            company_currency = self.env.company.currency_id
            query, params = self._get_query_sums(options)
            groupby_partners = {}
            self._cr.execute(query, params)
            for res in self._cr.dictfetchall():
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                assign_sum(res)
            query, params = self._get_sums_without_partner(options)
            self._cr.execute(query, params)
            totals = {}
            for total_field in ['debit', 'credit', 'balance']:
                totals[total_field] = \
                    {col_group_key: 0 for col_group_key in options['column_groups']}
            for row in self._cr.dictfetchall():
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                totals['debit'][row['column_group_key']] += row['debit']
                totals['credit'][row['column_group_key']] += row['credit']
                totals['balance'][row['column_group_key']] += row['balance']
                if row['groupby'] not in groupby_partners:
                    continue
                assign_sum(row)
            if None in groupby_partners:
                for column_group_key in options['column_groups']:
                    report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    groupby_partners[None][column_group_key]['debit'] += totals['credit'][column_group_key]
                    groupby_partners[None][column_group_key]['credit'] += totals['debit'][column_group_key]
                    groupby_partners[None][column_group_key]['balance'] -= totals['balance'][column_group_key]
            if groupby_partners:
                report = report.with_context(selected_currency_id=options['selected_currency_id'])
                partners = self.env['res.partner'].with_context(active_test=False).search([('id', 'in', list(groupby_partners.keys()))])
            else:
                partners = []
            if None in groupby_partners.keys():
                partners = [p for p in partners] + [None]
            return [(partner, groupby_partners[partner.id if partner else None]) for partner in partners]

    def _get_report_line_total(self, options, totals_by_column_group):
        if not 'selected_currency_id' in options:
            return super()._get_report_line_total(options, totals_by_column_group)
        else:
            column_values = []
            report = self.env['account.report'].browse(options.get('report_id'))
            for column in options['columns']:
                col_expr_label = column['expression_label']
                value = totals_by_column_group[column['column_group_key']].get(column['expression_label'])
                if col_expr_label in {'debit', 'credit', 'balance'}:
                    report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    formatted_value = report.format_value(value, figure_type=column['figure_type'], blank_if_zero=False)
                else:
                    report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    formatted_value = report.format_value(value, figure_type=column['figure_type']) if value else None
                column_values.append({
                    'name': formatted_value,
                    'no_format': value,
                    'class': 'number'
                })
            return {
                'id': report._get_generic_line_id(None, None, markup='total'),
                'name': _('Total'),
                'class': 'total',
                'level': 1,
                'columns': column_values,
            }

    def _get_report_line_partners(self, options, partner, partner_values, level_shift=0):
        if not 'selected_currency_id' in options:
            return super()._get_report_line_partners(options, partner, partner_values, level_shift)
        else:
            company_currency = self.env.company.currency_id
            unfold_all = (self._context.get('print_mode') and not options.get('unfolded_lines')) or options.get('unfold_all')

            unfoldable = False
            column_values = []
            report = self.env['account.report']
            for column in options['columns']:
                col_expr_label = column['expression_label']
                value = partner_values[column['column_group_key']].get(col_expr_label)

                if col_expr_label in {'debit', 'credit', 'balance'}:
                    report = report.with_context(selected_currency_id=options['selected_currency_id'])
                    formatted_value = report.format_value(value, figure_type=column['figure_type'], blank_if_zero=column['blank_if_zero'])
                else:
                    formatted_value = report.format_value(value, figure_type=column['figure_type']) if value is not None else value

                unfoldable = unfoldable or (col_expr_label in ('debit', 'credit') and not company_currency.is_zero(value))

                column_values.append({
                    'name': formatted_value,
                    'no_format': value,
                    'class': 'number'
                })

            line_id = report._get_generic_line_id('res.partner', partner.id) if partner else report._get_generic_line_id('res.partner', None, markup='no_partner')

            return {
                'id': line_id,
                'name': partner is not None and (partner.name or '')[:128] or self._get_no_partner_line_label(),
                'columns': column_values,
                'level': 2 + level_shift,
                'trust': partner.trust if partner else None,
                'unfoldable': unfoldable,
                'unfolded': line_id in options['unfolded_lines'] or unfold_all,
                'expand_function': '_report_expand_unfoldable_line_partner_ledger',
            }
