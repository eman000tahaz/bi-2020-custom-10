# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import datetime, date

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    @api.model
    def create(self, vals):
        res = super(AccountInvoice, self).create(vals)
        if vals.get('journal_id'):
            journal_id = vals['journal_id']
            journal = self.env['account.journal'].browse(journal_id)
            if journal.sequence_id:
                # If invoice is actually refund and journal has a refund_sequence then use that one or use the regular one
                sequence = journal.sequence_id
                if vals.get(type):
                    if vals['type'] in ['out_refund', 'in_refund'] and journal.refund_sequence:
                        if not journal.refund_sequence_id:
                            raise UserError(_('Please define a sequence for the refunds'))
                        sequence = journal.refund_sequence_id

                new_name = sequence.with_context().next_by_id()
            else:
                raise UserError(_('Please define a sequence on the journal.'))
            if new_name:
                self._cr.execute("update account_invoice set number = %s where id = %s", [new_name,res.id])
        return res