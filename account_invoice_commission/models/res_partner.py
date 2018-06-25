# -*- encoding: utf-8 -*-
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp


class ResPartnerCommission(models.Model):
    _inherit = 'res.partner'

    commission_rate = fields.Float(string='Commission Rate (%)')
    commission_account = fields.Many2one('account.account', string='Commission Account')