# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AccountBankStatementInherit(models.Model):
	_inherit = "account.bank.statement"
	_rec_name = 'name'

	name = fields.Char(string='Reference', readonly=True)
	state_type = fields.Selection([('rec', 'Receipt'), ('pay', 'Payment')], string="Type")
	image = fields.Binary("Image", attachment=True)
	b_total = fields.Monetary('Total', compute='_get_total', store=True)


	@api.depends('balance_end', 'balance_start')
	def _get_total(self):
		for statement in self:
			total = statement.balance_end - statement.balance_start
			statement.update({
								'b_total': total,
							}) 





	@api.onchange('company_id')
	def get_default_image(self):
		if self.company_id:
			self.image = self.company_id.logo

	@api.model
	def create(self, vals):
		sequence_code = self.company_id.statement_sequence_id.code
		sequence = self.env['ir.sequence'].sudo().next_by_code(sequence_code) or 'New'
		vals['name'] = sequence
		return super(AccountBankStatementInherit, self).create(vals)

class AccountBankStatementLineInherit(models.Model):
	_inherit = "account.bank.statement.line"

	check_no = fields.Char('Check No.')
	bank_id = fields.Many2one('res.bank', string="Bank")
	due_date = fields.Date('Due Date')
