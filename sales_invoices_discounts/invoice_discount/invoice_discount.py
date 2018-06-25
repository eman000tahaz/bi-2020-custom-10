from __future__ import division
from odoo import fields, models, api, _
import odoo.addons.decimal_precision as dp
from odoo.tools import amount_to_text_en
from odoo.tools import float_is_zero, float_compare
from odoo.exceptions import UserError


class invoice_discount(models.Model):
    _inherit = 'account.invoice'

    discount_view = fields.Selection([('After Tax', 'After Tax'), ('Before Tax', 'Before Tax')], string='Discount Type',
                                     states={'draft': [('readonly', False)]},
                                     help='Choose If After or Before applying Taxes type of the Discount')

    discount_type = fields.Selection([('Fixed', 'Fixed'), ('Percentage', 'Percentage')], string='Discount Method',
                                     states={'draft': [('readonly', False)]},
                                     help='Choose the type of the Discount')
    discount_value = fields.Float(string='Discount Value', states={'draft': [('readonly', False)]},
                                  help='Choose the value of the Discount')
    discounted_amount = fields.Float(compute='disc_amount', string='Discounted Amount', readonly=True)
    amount_total = fields.Float(string='Total', digits=dp.get_precision('Account'),
                                store=True, readonly=True, compute='_compute_amounts')
    report_visible = fields.Boolean(string='Visible On Report',default=False)


    def get_amount(self, amt, row, bow):
        amount_in_word = amount_to_text_en.amount_to_text(amt, row, bow)
        return amount_in_word

    def button_dummy(self):
        self._compute_amounts()
        # self._compute_residual()
        return True

    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'discount_type', 'discount_value', 'discount_view')
    def _compute_amounts(self):
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(line.amount for line in self.tax_line_ids)
        if self.discount_view == 'After Tax':
            if self.discount_type == 'Fixed':
                self.amount_total = self.amount_untaxed + self.amount_tax - self.discount_value
                self.amount_total_signed = self.amount_untaxed + self.amount_tax - self.discount_value
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed + self.amount_tax) * (self.discount_value / 100)
                self.amount_total = (self.amount_untaxed + self.amount_tax) - amount_to_dis
                self.amount_total_signed = (self.amount_untaxed + self.amount_tax) - amount_to_dis
            else:
                self.amount_total = self.amount_untaxed + self.amount_tax - self.discounted_amount
                self.amount_total_signed = self.amount_untaxed + self.amount_tax - self.discounted_amount
        elif self.discount_view == 'Before Tax':
            if self.discount_type == 'Fixed':
                the_value_before = self.amount_untaxed - self.discount_value
                self.amount_total = the_value_before + self.amount_tax
                self.amount_total_signed = the_value_before + self.amount_tax
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed) * (self.discount_value / 100)
                self.amount_total = self.amount_untaxed + self.amount_tax - amount_to_dis
                self.amount_total_signed = self.amount_untaxed + self.amount_tax - amount_to_dis
            else:
                self.amount_total = self.amount_untaxed + self.amount_tax - self.discounted_amount
                self.amount_total_signed = self.amount_untaxed + self.amount_tax - self.discounted_amount
        else:
            self.amount_total = self.amount_untaxed + self.amount_tax - self.discounted_amount
            self.amount_total_signed = self.amount_untaxed + self.amount_tax - self.discounted_amount
        # self.amount_total = self.amount_untaxed + self.amount_tax - self.discounted_amount

    @api.one
    # @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'discount_type', 'discount_value')
    def disc_amount(self):
        if self.discount_view == 'After Tax':
            if self.discount_type == 'Fixed':
                self.discounted_amount = self.discount_value
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed + self.amount_tax) * (self.discount_value / 100)
                self.discounted_amount = amount_to_dis
            else:
                self.discounted_amount = 0
        elif self.discount_view == 'Before Tax':
            if self.discount_type == 'Fixed':
                self.discounted_amount = self.discount_value
            elif self.discount_type == 'Percentage':
                amount_to_dis = self.amount_untaxed * (self.discount_value / 100)
                self.discounted_amount = amount_to_dis
            else:
                self.discounted_amount = 0
        else:
            self.discounted_amount = 0
        self._compute_amounts()
        # self._compute_residual()

    # @api.multi
    # def action_invoice_open(self):
    #     # lots of duplicate calls to action_invoice_open, so we remove those already open
    #     to_open_invoices = self.filtered(lambda inv: inv.state != 'open')
    #     if to_open_invoices.filtered(lambda inv: inv.state not in ['proforma2', 'draft']):
    #         raise UserError(_("Invoice must be in draft or Pro-forma state in order to validate it."))
    #     self._compute_amounts()
    #     to_open_invoices.action_date_assign()
    #     to_open_invoices.action_move_create()
    #     return to_open_invoices.invoice_validate()

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = inv.invoice_line_move_line_get()
            iml += inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(ctx).compute_invoice_totals(company_currency, iml)

            name = inv.name or '/'
            if inv.payment_term_id:
                totlines = inv.with_context(ctx).payment_term_id.with_context(currency_id=company_currency.id).compute(total, date_invoice)[0]
                res_amount_currency = total_currency
                ctx['date'] = date_invoice
                for i, t in enumerate(totlines):
                    if inv.currency_id != company_currency:
                        amount_currency = company_currency.with_context(ctx).compute(t[1], inv.currency_id)
                    else:
                        amount_currency = False

                    # last line: add the diff
                    res_amount_currency -= amount_currency or 0
                    if i + 1 == len(totlines):
                        amount_currency += res_amount_currency

                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': t[1],
                        'account_id': inv.account_id.id,
                        'date_maturity': t[0],
                        'amount_currency': diff_currency and amount_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
            else:
                self._compute_amounts()
                print inv.amount_total
                print inv.discounted_amount
                if self.type == 'out_invoice':
                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': inv.amount_total,
                        'account_id': inv.account_id.id,
                        'date_maturity': inv.date_due,
                        'amount_currency': diff_currency and total_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })

                    iml.append({
                        'type': 'dest',
                        'name': "Discount",
                        'price': inv.discounted_amount,
                        'account_id': 214,
                        'date_maturity': inv.date_due,
                        'amount_currency': diff_currency and total_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })
                else:
                    iml.append({
                        'type': 'dest',
                        'name': name,
                        'price': total,
                        'account_id': inv.account_id.id,
                        'date_maturity': inv.date_due,
                        'amount_currency': diff_currency and total_currency,
                        'currency_id': diff_currency and inv.currency_id.id,
                        'invoice_id': inv.id
                    })

            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)
            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            line = inv.finalize_invoice_move_lines(line)

            date = inv.date or date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True


invoice_discount()
