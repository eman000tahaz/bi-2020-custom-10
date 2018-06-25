# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AccountReportType(models.Model):
    _name = "account.report.type"

    date_range = fields.Boolean('Reports use a date range and not a single date', default=True)
    comparison = fields.Boolean('Reports allow comparisons', default=True)
    cash_basis = fields.Boolean('Reports always use cash basis', default=False)
    analytic = fields.Boolean('Reports enable the analytic filter', default=False)
    extra_options = fields.Boolean('Display the extra options dropdown (with cash basis and draft entries)', default=True)
