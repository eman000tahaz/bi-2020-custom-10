'''
Created on May 11, 2018

@author: mtloob
'''
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import time

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    amount = fields.Monetary('Total Amount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    total_discount = fields.Monetary('Total Discount', store=True, readonly=True, compute='_amount_all', track_visibility='always')
    @api.depends('order_line.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = 0.0
            discount_amount_tax=0.0
            total_discount=0.0
            amount=0.0
            for line in order.order_line:
                amount_untaxed += line.price_subtotal
                amount += line.product_uom_qty*line.price_unit
                if line.discount_type == 'Percentage':
                    total_discount += (1 - (line.discount or 0.0) / 100.0)
                    if order.company_id.tax_calculation_rounding_method == 'round_globally':
                        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                        taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                        amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                    else:
                        price =  (1 - (line.discount or 0.0) / 100.0)
                        taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                        discount_amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                        amount_tax += line.price_tax
                elif line.discount_type == 'Fixed':
                    total_discount += line.discount or 0.0
                    if order.company_id.tax_calculation_rounding_method == 'round_globally':
                        price = line.price_unit 
                        taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                        amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                    else:
                        if line.discount_type == 'Fixed':
                            price = line.discount 
                            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                            discount_amount_tax += sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                            amount_tax += line.price_tax
            order.update({
                'amount':amount,
                'total_discount':total_discount,
                'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': order.pricelist_id.currency_id.round(amount_tax-discount_amount_tax),
                'amount_total': amount_untaxed + amount_tax,
                })

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            if line.discount_type == 'Percentage':
                price = line.price_unit * (1 - (line.discount) / 100.0)
                taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
                line.update({
                    'price_tax': taxes['total_included'] - taxes['total_excluded'],
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
                return True
            elif line.discount_type == 'Fixed':
                price = line.price_unit
                taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
                line.update({
                    'price_tax': taxes['total_included'] - taxes['total_excluded'],
                    'price_total': taxes['total_included'] - line.discount,
                    'price_subtotal': taxes['total_excluded'] - line.discount,
                })
                return True
            
    @api.one
    @api.depends('tax_id','price_subtotal')
    def _get_tax_amount(self):
        tax_amount=0.0
        if self.tax_id:
            for tax in self.tax_id:
                tax_type = tax.amount_type
                if tax_type == 'fixed':
                    tax_amount+=tax.amount
                elif tax_type == 'percent':
                    tax_amount+=(tax.amount*self.price_subtotal)/100
        self.tax_amount = tax_amount
                
    discount_type = fields.Selection([('Fixed', 'Fixed'), ('Percentage', 'Percentage')], string='Discount Method',default='Fixed')
    tax_amount=fields.Float('VAT Amount', compute="_get_tax_amount")

class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    
    amount = fields.Monetary(string='Total Amount',
        store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    total_discount = fields.Monetary(string='Total Discount',
        store=True, readonly=True, compute='_compute_amount', track_visibility='always')
    tax_invoice = fields.Boolean('IS Taxable Invoice')
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_amount(self):
        round_curr = self.currency_id.round
        total_discount=0.0
        for line in self.invoice_line_ids:
            if line.discount_type=='Fixed':
                total_discount += line.discount
            elif  line.discount_type=='Percentage':
                total_discount += (line.quantity * line.price_unit) * line.discount
        self.total_discount = total_discount
        self.amount = sum(line.quantity * line.price_unit for line in self.invoice_line_ids)
        self.amount_untaxed = sum(line.price_subtotal for line in self.invoice_line_ids)
        self.amount_tax = sum(line.tax_amount for line in self.invoice_line_ids)
        self.amount_total = self.amount_untaxed + self.amount_tax
        amount_total_company_signed = self.amount_total
        amount_untaxed_signed = self.amount_untaxed
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            amount_total_company_signed = currency_id.compute(self.amount_total, self.company_id.currency_id)
            amount_untaxed_signed = currency_id.compute(self.amount_untaxed, self.company_id.currency_id)
        sign = self.type in ['in_refund', 'out_refund'] and -1 or 1
        self.amount_total_company_signed = amount_total_company_signed * sign
        self.amount_total_signed = self.amount_total * sign
        self.amount_untaxed_signed = amount_untaxed_signed * sign

class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"
    @api.one
    @api.depends('invoice_line_tax_ids','price_subtotal')
    def _get_tax_amount(self):
        tax_amount=0.0
        if self.invoice_line_tax_ids:
            for tax in self.invoice_line_tax_ids:
                tax_type = tax.amount_type
                if tax_type == 'fixed':
                    tax_amount+=tax.amount
                elif tax_type == 'percent':
                    tax_amount+=(tax.amount*self.price_subtotal)/100
        self.tax_amount = tax_amount
    discount_type = fields.Selection([('Fixed', 'Fixed'), ('Percentage', 'Percentage')], string='Discount Method',default='Fixed')
    tax_amount=fields.Float('VAT Amount', compute="_get_tax_amount")
    price_subtotal_tax=fields.Float('Amount With VAT', compute="_get_price_subtotal_tax")
    @api.one
    @api.depends('tax_amount','price_subtotal')
    def _get_price_subtotal_tax(self):
        self.price_subtotal_tax=self.tax_amount+self.price_subtotal
        
        
        
    @api.one
    @api.depends('price_unit',  'discount','discount_type', 'invoice_line_tax_ids', 'quantity',
        'product_id', 'invoice_id.partner_id', 'invoice_id.currency_id', 'invoice_id.company_id',
        'invoice_id.date_invoice', 'invoice_id.date')
    def _compute_price(self):
        currency = self.invoice_id and self.invoice_id.currency_id or None
        if self.discount_type == 'Percentage':
            price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
            taxes = False
            if self.invoice_line_tax_ids:
                taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
            self.price_subtotal = price_subtotal_signed = taxes['total_excluded'] if taxes else self.quantity * price
            if self.invoice_id.currency_id and self.invoice_id.company_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
            sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
            self.price_subtotal_signed = price_subtotal_signed * sign
        elif self.discount_type == 'Fixed':
            price = self.price_unit
            taxes = False
            if self.invoice_line_tax_ids:
                taxes = self.invoice_line_tax_ids.compute_all(price, currency, self.quantity, product=self.product_id, partner=self.invoice_id.partner_id)
            self.price_subtotal = price_subtotal_signed = taxes['total_excluded']-self.discount if taxes else (self.quantity * price) -self.discount 
            if self.invoice_id.currency_id and self.invoice_id.company_id and self.invoice_id.currency_id != self.invoice_id.company_id.currency_id:
                price_subtotal_signed = self.invoice_id.currency_id.with_context(date=self.invoice_id._get_currency_rate_date()).compute(price_subtotal_signed, self.invoice_id.company_id.currency_id)
            sign = self.invoice_id.type in ['in_refund', 'out_refund'] and -1 or 1
            self.price_subtotal_signed = price_subtotal_signed * sign
        
        
class res_partner(models.Model):
    _inherit = 'res.partner'
    partner_vat = fields.Char('TRN')
    
    
class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"
    
    @api.multi
    def _create_invoice(self, order, so_line, amount):
        inv_obj = self.env['account.invoice']
        ir_property_obj = self.env['ir.property']

        account_id = False
        if self.product_id.id:
            account_id = self.product_id.property_account_income_id.id
        if not account_id:
            inc_acc = ir_property_obj.get('property_account_income_categ_id', 'product.category')
            account_id = order.fiscal_position_id.map_account(inc_acc).id if inc_acc else False
        if not account_id:
            raise UserError(
                _('There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') %
                (self.product_id.name,))

        if self.amount <= 0.00:
            raise UserError(_('The value of the down payment amount must be positive.'))
        if self.advance_payment_method == 'percentage':
            amount = order.amount_untaxed * self.amount / 100
            name = _("Down payment of %s%%") % (self.amount,)
        else:
            amount = self.amount
            name = _('Down Payment')
        taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
        if order.fiscal_position_id and taxes:
            tax_ids = order.fiscal_position_id.map_tax(taxes).ids
        else:
            tax_ids = taxes.ids

        invoice = inv_obj.create({
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_invoice',
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_invoice_id.id,
            'partner_shipping_id': order.partner_shipping_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'origin': order.name,
                'account_id': account_id,
                'price_unit': amount,
                'quantity': 1.0,
#                 'discount': self.discount,
#                 'discount_type':self.discount_type,
                'uom_id': self.product_id.uom_id.id,
                'product_id': self.product_id.id,
                'sale_line_ids': [(6, 0, [so_line.id])],
                'invoice_line_tax_ids': [(6, 0, tax_ids)],
                'account_analytic_id': order.project_id.id or False,
            })],
            'currency_id': order.pricelist_id.currency_id.id,
            'payment_term_id': order.payment_term_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'team_id': order.team_id.id,
            'user_id': order.user_id.id,
            'comment': order.note,
        })
        invoice.compute_taxes()
        invoice.message_post_with_view('mail.message_origin_link',
                    values={'self': invoice, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        return invoice

    @api.multi
    def create_invoices(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))

        if self.advance_payment_method == 'delivered':
            sale_orders.action_invoice_create()
        elif self.advance_payment_method == 'all':
            sale_orders.action_invoice_create(final=True)
        else:
            # Create deposit product if necessary
            if not self.product_id:
                vals = self._prepare_deposit_product()
                self.product_id = self.env['product.product'].create(vals)
                self.env['ir.values'].sudo().set_default('sale.config.settings', 'deposit_product_id_setting', self.product_id.id)

            sale_line_obj = self.env['sale.order.line']
            for order in sale_orders:
                if self.advance_payment_method == 'percentage':
                    amount = order.amount_untaxed * self.amount / 100
                else:
                    amount = self.amount
                if self.product_id.invoice_policy != 'order':
                    raise UserError(_('The product used to invoice a down payment should have an invoice policy set to "Ordered quantities". Please update your deposit product to be able to create a deposit invoice.'))
                if self.product_id.type != 'service':
                    raise UserError(_("The product used to invoice a down payment should be of type 'Service'. Please use another product or update this product."))
                taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
                if order.fiscal_position_id and taxes:
                    tax_ids = order.fiscal_position_id.map_tax(taxes).ids
                else:
                    tax_ids = taxes.ids
                so_line = sale_line_obj.create({
                    'name': _('Advance: %s') % (time.strftime('%m %Y'),),
                    'price_unit': amount,
                    'product_uom_qty': 0.0,
                    'order_id': order.id,
#                     'discount': self.discount,
#                     'discount_type':self.discount_type,
                    'product_uom': self.product_id.uom_id.id,
                    'product_id': self.product_id.id,
                    'tax_id': [(6, 0, tax_ids)],
                })
                self._create_invoice(order, so_line, amount)
        if self._context.get('open_invoices', False):
            return sale_orders.action_view_invoice()
        return {'type': 'ir.actions.act_window_close'}
