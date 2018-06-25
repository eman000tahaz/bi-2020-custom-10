from __future__ import division
from odoo import fields, models, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError



class saleorder_discount(models.Model):
    _inherit = 'sale.order'
    sale_tag_ids = fields.Char(related='tag_ids.name',string="Sales Tags", readonly=True, store=True)
    discount_view = fields.Selection([('After Tax', 'After Tax'), ('Before Tax', 'Before Tax')], string='Discount Type',
                                     states={'draft': [('readonly', False)]},
                                     help='Choose If After or Before applying Taxes type of the Discount')
    discount_type = fields.Selection([('Fixed', 'Fixed'), ('Percentage', 'Percentage')], string='Discount Method',
                                     states={'draft': [('readonly', False)]})
    discount_value = fields.Float(string='Discount Value', states={'draft': [('readonly', False)]},
                                  help='Choose the value of the Discount')
    discounted_amount = fields.Float(compute='disc_amount', string='Discounted Amount', readonly=True)
    amount_total = fields.Float(string='Total', digits=dp.get_precision('Account'),
                                store=True, readonly=True, compute='_compute_amounts')
    report_visible = fields.Boolean(string='Visible On Report',default=False)


    @api.one
    @api.depends('order_line.price_subtotal', 'discount_type', 'discount_value')
    def _compute_amounts(self):
        self.amount_untaxed = sum(line.price_subtotal for line in self.order_line)
        val = 0
        if self.amount_tax:
            val = self.amount_tax
        if self.discount_view == 'After Tax':
            if self.discount_type == 'Fixed':
                self.amount_total = self.amount_untaxed + val - self.discount_value
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed + val) * (self.discount_value / 100)
                self.amount_total = (self.amount_untaxed+ val) - amount_to_dis
            else:
                self.amount_total = self.amount_untaxed + val
        elif self.discount_view == 'Before Tax':
            if self.discount_type == 'Fixed':
                the_value_before = self.amount_untaxed - self.discount_value
                self.amount_total = the_value_before + val
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed) * (self.discount_value / 100)
                self.amount_total = self.amount_untaxed + val - amount_to_dis
            else:
                self.amount_total = self.amount_untaxed + val
        else:
            self.amount_total = self.amount_untaxed + val

    def button_dummy(self):
        self._compute_amounts()
        return True

    @api.multi
    def _prepare_invoice(self):
        """
        Prepare the dict of values to create the new invoice for a sales order. This method may be
        overridden to implement custom invoice generation (making sure to call super() to establish
        a clean extension chain).
        """
        self.ensure_one()
        journal_id = self.env['account.invoice'].default_get(['journal_id'])['journal_id']
        if not journal_id:
            raise UserError(_('Please define an accounting sale journal for this company.'))
        invoice_vals = {
            'name': self.client_order_ref or '',
            'origin': self.name,
            'type': 'out_invoice',
            'account_id': self.partner_invoice_id.property_account_receivable_id.id,
            'partner_id': self.partner_invoice_id.id,
            'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'comment': self.note,
            'payment_term_id': self.payment_term_id.id,
            'fiscal_position_id': self.fiscal_position_id.id or self.partner_invoice_id.property_account_position_id.id,
            'company_id': self.company_id.id,
            'user_id': self.user_id and self.user_id.id,
            'team_id': self.team_id.id,
            'discount_view': self.discount_view,
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'discounted_amount': self.discounted_amount,
            'report_visible': self.report_visible,
        }
        return invoice_vals

    @api.one
    @api.depends('order_line.price_subtotal', 'discount_type', 'discount_value')
    def disc_amount(self):
        val = 0
        # for line in self.order_line:
        #     val += self._amount_line_tax(line)
        if self.amount_tax:
            val = self.amount_tax
        if self.discount_view == 'After Tax':
            if self.discount_type == 'Fixed':
                self.discounted_amount = self.discount_value
            elif self.discount_type == 'Percentage':
                amount_to_dis = (self.amount_untaxed + val) * (self.discount_value / 100)
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


saleorder_discount()
