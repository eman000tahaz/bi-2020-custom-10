# -*- encoding: utf-8 -*-
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    standard_price_company_currency = fields.Float(string='Cost Price in Company Currency', readonly=True, digits=dp.get_precision('Product Price'))
    standard_price_invoice_currency = fields.Float(string='Cost Price in Invoice Currency', readonly=True, compute='_compute_margin', store=True, digits=dp.get_precision('Product Price'))
    margin_invoice_currency = fields.Float(string='Margin in Invoice Currency', readonly=True, store=True, compute='_compute_margin', digits=dp.get_precision('Account'))
    margin_company_currency = fields.Float(string='Margin in Company Currency', readonly=True, store=True, compute='_compute_margin', digits=dp.get_precision('Account'))
    margin_rate = fields.Float(string="Margin Rate", readonly=True, store=True, compute='_compute_margin', digits=(16, 2), help="Margin rate in percentage of the sale price")
    is_commission = fields.Boolean('Is Commission', default=True)


    @api.one
    @api.depends(
        'standard_price_company_currency', 'invoice_id.currency_id',
        'invoice_id.type', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'quantity', 'price_subtotal')
    def _compute_margin(self):
        standard_price_inv_cur = 0.0
        margin_inv_cur = 0.0
        margin_comp_cur = 0.0
        margin_rate = 0.0
        if (
                self.invoice_id and
                self.invoice_id.type in ('in_invoice', 'in_refund')):
            standard_price_inv_cur =\
                self.invoice_id.company_id.currency_id.with_context(
                    date=self.invoice_id.date_invoice).compute(
                        self.standard_price_company_currency,
                        self.invoice_id.currency_id)
            margin_inv_cur = \
                self.quantity * self.product_id.last_sale_price - self.price_subtotal
            margin_comp_cur = self.invoice_id.currency_id.with_context(
                date=self.invoice_id.date_invoice).compute(
                    margin_inv_cur, self.invoice_id.company_id.currency_id)
            if self.price_subtotal:
                margin_rate = 100 * margin_inv_cur / self.price_subtotal
            # for a refund, margin should be negative
            # but margin rate should stay positive
            if self.invoice_id.type == 'in_refund':
                margin_inv_cur *= -1
                margin_comp_cur *= -1

        if self.invoice_id.is_commission or self.is_commission:
            self.standard_price_invoice_currency = self.product_id.last_sale_price
            self.margin_invoice_currency = margin_inv_cur
            self.margin_company_currency = margin_comp_cur
            self.margin_rate = margin_rate

    @api.model
    def create(self, vals):
        if vals.get('product_id'):
            pp = self.env['product.product'].browse(vals['product_id'])
            std_price = pp.last_sale_price
            inv_uom_id = vals.get('uos_id')
            # if inv_uom_id and inv_uom_id != pp.uom_id.id:
            #     std_price = self.env['product.uom']._compute_price(
            #         pp.uom_id.id, std_price, inv_uom_id)
            vals['standard_price_company_currency'] = std_price
        return super(AccountInvoiceLine, self).create(vals)

    @api.multi
    def write(self, vals):
        if not vals:
            vals = {}
        if 'product_id' in vals or 'uos_id' in vals:
            for il in self:
                if 'product_id' in vals:
                    if vals.get('product_id'):
                        pp = self.env['product.product'].browse(
                            vals['product_id'])
                    else:
                        pp = False
                else:
                    pp = il.product_id or False
                # uos_id is NOT a required field
                if 'uos_id' in vals:
                    if vals.get('uos_id'):
                        inv_uom = self.env['product.uom'].browse(
                            vals['uos_id'])
                    else:
                        inv_uom = False
                # else:
                    # inv_uom = il.uos_id or False
                std_price = 0.0
                if pp:
                    std_price = pp.last_sale_price
                    # if inv_uom and inv_uom != pp.uom_id:
                    #     std_price = self.env['product.uom']._compute_price(
                    #         pp.uom_id.id, std_price, inv_uom.id)
                il.write({'standard_price_company_currency': std_price})
        return super(AccountInvoiceLine, self).write(vals)


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    @api.onchange('partner_id')
    def onchange_invoice_partner(self):
        if self.partner_id:
            self.commission_rate = self.partner_id.commission_rate
            # self.commission_account = self.partner_id.commission_account
            self.commission_value = self.commission_rate/100 * self.margin_invoice_currency

    margin_invoice_currency = fields.Float(string='Margin in Invoice Currency', readonly=True, compute='_compute_margin', store=True, digits=dp.get_precision('Account'))
    margin_company_currency = fields.Float(string='Margin in Company Currency', readonly=True, compute='_compute_margin', store=True, digits=dp.get_precision('Account'))
    commission_value = fields.Float(string="Commission Value", compute='_compute_margin', store=True, digits=dp.get_precision('Account'))
    commission_rate = fields.Float(string="Commission Rate (%)",compute='_compute_margin', store=True, digits=dp.get_precision('Account'))
    is_commission = fields.Boolean('Is Commission', default=True)


    @api.one
    @api.depends('type', 'invoice_line_ids.margin_invoice_currency', 'invoice_line_ids.margin_company_currency')
    def _compute_margin(self):
        margin_inv_cur = 0.0
        margin_comp_cur = 0.0
        if self.type in ('in_invoice', 'in_refund'):
            for il in self.invoice_line_ids:
                margin_inv_cur += il.margin_invoice_currency
                margin_comp_cur += il.margin_company_currency
        self.margin_invoice_currency = margin_inv_cur
        self.margin_company_currency = margin_comp_cur
        if self.partner_id:
            self.commission_rate = self.partner_id.commission_rate
        self.commission_value = self.commission_rate/100 * self.margin_invoice_currency


    @api.multi
    def action_invoice_open(self):
        if self.type == 'in_invoice' and self.commission_value > 0:
            self.write({'is_commission':False})
            self.env['account.invoice.line'].create({
                'name':self.partner_id.name,
                'account_id':self.partner_id.commission_account.id,
                'quantity':1,
                'price_unit':self.commission_value,
                'invoice_id':self.id,
                'partner_id':self.partner_id.id,
                'is_commission': False
            })
        self._compute_amounts()
        return super(AccountInvoice, self).action_invoice_open()