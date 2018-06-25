# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from datetime import datetime


class report_account_coa(models.AbstractModel):
    _name = "account.coa.report"
    _description = "Chart of Account Report"
    _inherit = "account.general.ledger"

    @api.model
    def get_lines(self, context_id, line_id=None):
        if type(context_id) == int:
            context_id = self.env['account.context.coa'].search([['id', '=', context_id]])
        new_context = dict(self.env.context)
        new_context.update({
            'date_from': context_id.date_from,
            'date_to': context_id.date_to,
            'state': context_id.all_entries and 'all' or 'posted',
            'cash_basis': context_id.cash_basis,
            'hierarchy_3': context_id.hierarchy_3,
            'context_id': context_id,
            'company_ids': context_id.company_ids.ids,
            'periods_number': context_id.periods_number,
            'periods': [[context_id.date_from, context_id.date_to]] + context_id.get_cmp_periods(),
        })
        return self.with_context(new_context)._lines(line_id)

    @api.model
    def _lines(self, line_id=None):
        lines = []
        context = self.env.context
        maxlevel = context['context_id'].hierarchy_3 and 3 or 1
        company_id = context.get('company_id') or self.env.user.company_id
        grouped_accounts = {}
        period_number = 0
        initial_balances = {}
        context['periods'].reverse()
        for period in context['periods']:
            res = self.with_context(date_from_aml=period[0], date_to=period[1], date_from=period[0] and company_id.compute_fiscalyear_dates(datetime.strptime(period[0], "%Y-%m-%d"))['date_from'] or None).group_by_account_id(line_id)  # Aml go back to the beginning of the user chosen range but the amount on the account line should go back to either the beginning of the fy or the beginning of times depending on the account
            if period_number == 0:
                initial_balances = dict([(k, res[k]['initial_bal']['balance']) for k in res])
            for account in res:
                if account not in grouped_accounts.keys():
                    grouped_accounts[account] = [{'balance': 0, 'debit': 0, 'credit': 0} for p in context['periods']]
                grouped_accounts[account][period_number]['balance'] = res[account]['balance'] - res[account]['initial_bal']['balance']
            period_number += 1
        sorted_accounts = sorted(grouped_accounts, key=lambda a: a.code)
        title_index = ''
        for account in sorted_accounts:
            non_zero = False
            for p in xrange(len(context['periods'])):
                if not company_id.currency_id.is_zero(grouped_accounts[account][p]['balance']) or not company_id.currency_id.is_zero(initial_balances.get(account, 0)):
                    non_zero = True
            if not non_zero:
                continue
            for level in range(maxlevel):
                if (account.code[:level+1] > title_index[:level+1]):
                    title_index = account.code[:level+1]
                    total = map(lambda x: 0.00, xrange(len(context['periods'])))
                    if maxlevel>1:
                        for account_sum in sorted_accounts:
                            if account_sum.code[:level+1] == title_index:
                                for p in xrange(len(context['periods'])):
                                    total[p] += grouped_accounts[account_sum][p]['balance']
                            if account_sum.code[:level+1] > title_index:
                                break
                        total2 = ['']
                        for p in total:
                            total2.append(p >= 0 and self._format(p) or '')
                            total2.append(p < 0 and self._format(-p) or '')
                        total2.append('')
                    else:
                        total2 = [''] + ['' for p in xrange(len(context['periods']))]*2 + ['']

                    lines.append({
                        'id': title_index,
                        'type': 'line',
                        'name': level and title_index or (_("Class %s") % title_index),
                        'footnotes': {},
                        'columns': total2,
                        'level': level+1,
                        'unfoldable': False,
                        'unfolded': True,
                    })
            lines.append({
                'id': account.id,
                'type': 'account_id',
                'name': account.code + " " + account.name,
                'footnotes': self.env.context['context_id']._get_footnotes('account_id', account.id),
                'columns': [account in initial_balances and self._format(initial_balances[account]) or self._format(0.0)] +
                            sum([[grouped_accounts[account][p]['balance'] > 0 and self._format(grouped_accounts[account][p]['balance']) or '',
                                 grouped_accounts[account][p]['balance'] < 0 and self._format(-grouped_accounts[account][p]['balance']) or '']
                                for p in xrange(len(context['periods']))], []) +
                            [self._format((account in initial_balances and initial_balances[account] or 0.0) + sum([grouped_accounts[account][p]['balance'] for p in xrange(len(context['periods']))]))],
                'level': 1,
                'unfoldable': False,
            })
        return lines

    @api.model
    def get_title(self):
        return _("Chart of Account")

    @api.model
    def get_name(self):
        return 'coa'

    @api.model
    def get_report_type(self):
        return self.env.ref('account_reports.account_report_type_date_range')


class account_context_coa(models.TransientModel):
    _name = "account.context.coa"
    _description = "A particular context for the chart of account"
    _inherit = "account.report.context.common"

    fold_field = 'unfolded_accounts'
    unfolded_accounts = fields.Many2many('account.account', 'context_to_account_coa', string='Unfolded lines')

    @api.model
    def _context_add(self):
        return {'has_hierarchy': True}

    def get_report_obj(self):
        return self.env['account.coa.report']

    def get_special_date_line_names(self):
        temp = self.get_full_date_names(self.date_to)
        if not isinstance(temp, unicode):
            temp = temp.decode("utf-8")
        columns = []
        if self.comparison and (self.periods_number == 1 or self.date_filter_cmp == 'custom'):
            columns += [self.get_cmp_date()]
        elif self.comparison:
            periods = self.get_cmp_periods(display=True)
            periods.reverse()
            for period in periods:
                columns += [str(period)]
        return columns + [temp]


    def get_columns_names(self):
        columns = [_('Initial Balance')]
        if self.comparison and (self.periods_number == 1 or self.date_filter_cmp == 'custom'):
            columns += [_('Debit'), _('Credit')]
        elif self.comparison:
            for period in self.get_cmp_periods(display=True):
                columns += [_('Debit'), _('Credit')]
        return columns + [_('Debit'), _('Credit'), _('Total')]

    @api.multi
    def get_columns_types(self):
        types = ['number']
        if self.comparison and (self.periods_number == 1 or self.date_filter_cmp == 'custom'):
            types += ['number', 'number']
        else:
            for period in self.get_cmp_periods(display=True):
                types += ['number', 'number']
        return types + ['number', 'number', 'number']
