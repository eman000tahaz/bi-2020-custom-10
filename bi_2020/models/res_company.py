# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    statement_sequence_id = fields.Many2one('ir.sequence', string='Statement Sequence', copy=False)
    