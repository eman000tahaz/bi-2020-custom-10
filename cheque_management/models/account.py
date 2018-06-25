# -*- coding: utf-8 -*-

from odoo import _, api, exceptions, fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    jrnl_is_cheque = fields.Boolean(string="Cheques?",
    help="On Cash/Misc journals this will be a Cheques wallet. \n\
    On Bank accounts, this will mean that you have Chequebook from this bank." )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    aml_is_cheque = fields.Boolean(string="Is Cheque", store=True, compute="_is_cheque")
    aml_is_cash = fields.Boolean(string="Is Cash", store=True, compute="_is_cheque")
    cheque_bank = fields.Char(string="Cheque Bank",related='payment_id.cheque_bank')
    cheque_date = fields.Date(string="Cheque Date",related='payment_id.date')
    cheque_no = fields.Char(string="Cheque No",related='payment_id.cheque_no')

    @api.depends('payment_id')
    def _is_cheque(self):
        for aml in self:
            if aml.payment_id.is_cheque == '1':
                aml.aml_is_cheque = True
            elif aml.payment_id.is_cheque == '2':
                aml.aml_is_cash = True
    # @api.model
    # def create(self, vals):
    #     res = super(AccountMoveLine, self).create(vals)
    #     for aml in res:
    #         if not aml.aml_is_cheque:
    #             aml.aml_is_cheque = aml.journal_id.jrnl_is_cheque
    #     return res

    def _prepare_writeoff_first_line_values(self, values):
        line_values = super(AccountMoveLine, self)._prepare_writeoff_first_line_values(values)
        line_values.update({
        'payment_id': self.payment_id.id,
        'amount_currency': -abs(self.amount_currency) if line_values['credit'] > 0 else abs(self.amount_currency),
        'currency_id': self.currency_id.id and self.currency_id.id,
        })
        return line_values

    def _prepare_writeoff_second_line_values(self, values):
        line_values = super(AccountMoveLine, self)._prepare_writeoff_second_line_values(values)
        line_values.update({
        'payment_id': self.payment_id.id,
        'amount_currency': -abs(self.amount_currency) if line_values['credit'] > 0 else abs(self.amount_currency),
        'currency_id': self.currency_id.id and self.currency_id.id,
        })
        return line_values

class AccountPayment_lines(models.Model):
    _name = "account.payment.lines1"
    
    cheque_no = fields.Char(string="Cheque No", required=True)
    cheque_bank = fields.Char(string="Cheque Bank", required=True)
    date = fields.Date(string="Date" , required=True)
    cheque_amount = fields.Float('Amount', required=True)
    payme_id = fields.Many2one('account.payment', 'Payment')
    
    _sql_constraints = [
        ('cheque_no_uniq', 'unique (cheque_no)', 'The cheque number must be unique.!'),
    ]
    
class res_partner(models.Model):
    _inherit = "res.partner"
     
    partner_vat = fields.Char('TRN')
class AccountPayment(models.Model):
    _inherit = "account.payment"
    
    @api.depends('partner_id')
    def _get_partner_vat(self):
        if self.partner_id:
            if self.partner_id.partner_vat:
                self.partner_vat = self.partner_id.partner_vat
    
    @api.onchange('lines_ids')
    def _change_lines_ids(self):
        am_total=0.0
        if self.lines_ids:
            for lines_id in self.lines_ids:
                am_total += lines_id.cheque_amount
            self.amount = am_total
    communication = fields.Char(string="Payment Reference", )
    lines_ids = fields.One2many('account.payment.lines1','payme_id', 'Lines')
    cheque_no = fields.Char(string="Cheque No")
    cheque_bank = fields.Char(string="Cheque Bank")
    date = fields.Date(string="Date" )
    cheque_journal_id = fields.Many2one(
        string="Journal",
        comodel_name="account.journal",
    )
    is_cheque = fields.Selection([('1','Cheque'),('2','Cash')], 'Voucher Type', default='1')
#     is_cheque = fields.Boolean(string="Is Cheque", )
    partner_vat = fields.Char('TRN', compute="_get_partner_vat")
    notes = fields.Text("Notes")
    _sql_constraints = [
        ('chq_no_uniq', 'unique (cheque_no)', 'The cheque number must be unique.!'),
    ]

    @api.depends('cheque_journal_id')
    @api.onchange('cheque_journal_id','currency_id')
    def _change_journal(self):
        for pay in self:
            if pay.cheque_journal_id:
                pay.journal_id = pay.cheque_journal_id
            pay.currency_id = pay.journal_id.currency_id or pay.company_id.currency_id
