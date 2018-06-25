from openerp import models, fields, api


class Tenant(models.Model):
    _inherit = 'res.partner'

    national_id_no = fields.Char(string='National ID Number')
    tenancy_count = fields.Integer(string='# of Tenancy', compute='_get_tenancy_count', readonly=True)
    # is_current = fields.Boolean(string='Is Current', default=False, compute='compute_occupation_status', store=True)
    # one2many relations
    # occupation_ids = fields.One2many('rental.occupation', 'tenant_id', string='Occupations')

    _sql_constraints = {('unique_national_id_no', 'unique(national_id_no)', 'National ID Number must be unique')}

    @api.multi
    def _get_tenancy_count(self):
        for order in self:
            order.update({
                'tenancy_count': len(self.env['rental.tenancy'].sudo().search([('tenant_id', '=', order.id)])),
            })

    @api.multi
    def action_view_contract(self):
        tenancies = self.env['rental.tenancy'].sudo().search([('tenant_id', '=', self.id)])
        action = self.env.ref('property_rent_managemnet.view_tenancy_action').read()[0]
        if len(tenancies) > 1:
            action['domain'] = [('id', 'in', tenancies.ids)]
        elif len(tenancies) == 1:
            action['views'] = [(self.env.ref('property_rent_managemnet.view_tenancy_form').id, 'form')]
            action['res_id'] = tenancies.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.one
    @api.depends('occupation_ids.move_out_date')
    def compute_tenancy_status(self):
        domain = ['&', ('move_out_date', '=', None), ('customer', '=', self.id)]
        num_tenancies = self.env['rental.occupation'].search_count(domain)
        if num_tenancies > 0:
            self.is_current = True
        else:
            self.is_current = False
