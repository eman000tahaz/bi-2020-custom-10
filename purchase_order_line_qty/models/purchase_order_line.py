# -*- encoding: utf-8 -*-
from openerp import models, fields, api
import openerp.addons.decimal_precision as dp


class purchase_order_line_qty(models.Model):
    _inherit = 'purchase.order.line'

    # @api.multi
    # @api.onchange('product_id')
    # def onchange_product_id(self):
    #     if self.product_id:
    #         self.outgoing_qty = self.product_id.outgoing_qty
    #         self.onhand_qty = self.product_id.qty_available

    @api.multi
    def _calculate_stock_qty(self):
        for line in self:
            if line.product_id:
                line.outgoing_qty = line.product_id.outgoing_qty
                line.onhand_qty = line.product_id.qty_available

    outgoing_qty = fields.Float(compute=_calculate_stock_qty,string='Outgoing Qty')
    onhand_qty = fields.Float(compute=_calculate_stock_qty,string='Onhand Qty')

class account_invoice_line_qty(models.Model):
    _inherit = 'account.invoice.line'

    @api.multi
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.outgoing_qty = self.product_id.outgoing_qty
            self.onhand_qty = self.product_id.qty_available


    @api.multi
    def _calculate_stock_qty(self):
        for line in self:
            if line.product_id:
                line.outgoing_qty = line.product_id.outgoing_qty
                line.onhand_qty = line.product_id.qty_available

    outgoing_qty = fields.Float(compute=_calculate_stock_qty,string='Outgoing Qty')
    onhand_qty = fields.Float(compute=_calculate_stock_qty,string='Onhand Qty')