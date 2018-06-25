# -*- encoding: utf-8 -*-

from odoo import api, fields, models


class ProductProductInherits(models.Model):
    _inherit = 'product.product'

    @api.one
    def _get_last_sale(self):
        lines = self.env['sale.order.line'].search(
            [('product_id', '=', self.id),
             ('state', 'in', ['sale', 'done'])]).sorted(
            key=lambda l: l.order_id.date_order, reverse=True)

        pos_lines = self.env['pos.order.line'].search(
            [('product_id', '=', self.id)]).sorted(
            key=lambda l: l.order_id.date_order, reverse=True)

        discount_share = 0
        for s in self.env['account.invoice'].search([('origin','=',lines[:1].order_id.name)],order="id desc",limit=1):
            self._cr.execute(""" select COUNT(*) from account_invoice_line where invoice_id = %s """ % s.id)
            res = self._cr.fetchone()
            if res[0] >0:
                if self.type =='product':
                    discount_share =  s.discounted_amount

        if lines[:1].product_uom_qty ==0:
            sal_price = lines[:1].price_subtotal - discount_share
        else:
            sal_price = (lines[:1].price_subtotal - discount_share) / lines[:1].product_uom_qty
        if pos_lines[:1].qty ==0:
            pos_price = pos_lines[:1].price_subtotal
        else:
            pos_price = pos_lines[:1].price_subtotal / pos_lines[:1].qty

        if sal_price> pos_price:
            self.last_sale_price = sal_price
        else:
            self.last_sale_price = pos_price

    last_sale_price = fields.Float(
        string='Last Sale Price', compute='_get_last_sale')
