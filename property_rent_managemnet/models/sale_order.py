import re
import datetime

from odoo import models, fields, api, exceptions, _


class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'
    is_rent = fields.Boolean('Is Rent')
    tenancy = fields.Boolean('Tenancy', compute='compute_tenancy')
    tenancy_count = fields.Integer(string='# of Tenancy', compute='_get_tenancy_count', readonly=True)


    @api.multi
    def _get_tenancy_count(self):
        for order in self:
            order.update({
                'tenancy_count': len(self.env['rental.tenancy'].sudo().search([('sale_id', '=', order.id)])),
            })


    @api.multi
    def action_confirm(self):
        for order in self:
            for line in order.order_line:
                if line.product_id.sale_ok:
                    order.is_rent = False
                if line.product_id.rent_ok:
                    order.is_rent = True
            print order.is_rent
        return super(SaleOrderInherit, self).action_confirm()


    @api.multi
    def compute_tenancy(self):
        for record in self:
            tenancy = self.env['rental.tenancy'].search([('sale_id', '=', record.id)])
            if tenancy:
                record.tenancy = True
            else:
                record.tenancy = False

    @api.multi
    def action_create_contract(self):
        for order in self:
            # order.state = 'waiting'
            action = {'type': 'ir.actions.act_window_close'}
            for line in order.order_line:
                product = line.product_id
            print order
            print product
            return {
                'name': 'Tenancy',
                'domain': [],
                'res_model': 'rental.tenancy',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'view_type': 'form',
                'context': {'default_name': "Contract for " + order.partner_id.name,
                            'default_property_id': product.product_tmpl_id.id,
                            'default_tenant_id': order.partner_id.id,
                            'default_sale_id': order.id,
                            },
                'target': 'current',
            }


    @api.multi
    def action_view_contract(self):
        tenancies = self.env['rental.tenancy'].sudo().search([('sale_id', '=', self.id)])
        action = self.env.ref('property_rent_managemnet.view_tenancy_action').read()[0]
        if len(tenancies) > 1:
            action['domain'] = [('id', 'in', tenancies.ids)]
        elif len(tenancies) == 1:
            action['views'] = [(self.env.ref('property_rent_managemnet.view_tenancy_form').id, 'form')]
            action['res_id'] = tenancies.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
