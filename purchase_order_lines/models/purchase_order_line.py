# -*- encoding: utf-8 -*-
from odoo import models, fields, api
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _


class purchase_order_line_qty(models.Model):
    _inherit = 'purchase.order.line'

    invoice_id = fields.Many2one('account.invoice')

    @api.model
    def create_purchase_line_invoice(self):
        active_ids = self._context.get('active_ids')
        vendors = []
        for active_id in active_ids:
            line_obj = self.env['purchase.order.line'].browse(active_id)
            if line_obj.invoice_id.id:
                raise ValidationError(_('Validation Error! One of the lines you have selected is already invoiced - %s(%s)') %(line_obj.order_id.name, line_obj.name))
            if line_obj.partner_id.id not in vendors:
                vendors.append(line_obj.partner_id.id)

        data = {
            'product_id': '',
            'name': '',
            'account_id': '',
            'quantity': 'test',
            'price_unit': '',
            'price_subtotal': '',
        }

        for vendor in vendors:
            journal_id = self.env['account.journal'].search([('type', '=', 'purchase')])
            journal_id = journal_id and journal_id[0] or False
            vendor_obj = self.env['res.partner'].browse(vendor)
            print vendor_obj.name
            a = vendor_obj.property_account_payable_id.id
            if not a:
                raise ValidationError(_('Validation Error! Please configure %s\'s payable account!')% vendor_obj.name)
            if not journal_id:
                raise ValidationError(_('Validation Error! Please configure the journal account!'))

            acc_move = self.env['account.invoice'].create({
                'partner_id': vendor_obj.id,
                'reference_type': 'none',
                'reference': vendor_obj.ref,
                'account_id': a,
                'journal_id': journal_id.id,
                'type': 'in_invoice',
                'fiscal_position': vendor_obj.property_account_position_id.id
            })
            for active_id in active_ids:
                purchase_line_obj = self.env['purchase.order.line'].browse(active_id)
                if purchase_line_obj.partner_id.id == vendor_obj.id:
                    if not purchase_line_obj.product_id.property_account_expense_id.id:
                        if not purchase_line_obj.product_id.categ_id.property_account_expense_categ_id.id:
                            raise ValidationError(
                                _('Validation Error! Please configure the expense account for %s or its category!') % purchase_line_obj.product_id.name)
                    exp_account_default = purchase_line_obj.product_id.property_account_expense_id.id or purchase_line_obj.product_id.categ_id.property_account_expense_categ_id.id
                    data['product_id'] = purchase_line_obj.product_id.id
                    data['name'] = purchase_line_obj.product_id.name
                    data['account_id'] = exp_account_default
                    data['quantity'] = purchase_line_obj.product_qty
                    data['price_unit'] = purchase_line_obj.price_unit
                    data['price_subtotal'] = purchase_line_obj.price_unit * purchase_line_obj.product_qty
                    data['invoice_id'] = acc_move.id
                    self.env['account.invoice.line'].create(data)
                    purchase_line_obj.write({'invoice_id': acc_move.id})