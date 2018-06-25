from datetime import datetime, date
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _, exceptions


class Stage(models.Model):

    _name = "property.stage"
    _description = "Stage of case"
    _rec_name = 'name'
    _order = "sequence, name, id"

    name = fields.Char('Stage Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=1, help="Used to order stages. Lower is better.")
    fold = fields.Boolean('Folded in Pipeline',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    is_default = fields.Boolean('Set as Default Stage')


    @api.onchange('is_default')
    def set_default(self):
        obj = self.env['property.stage'].search([])
        if self.is_default is True:
            for each in obj:
                if each.id != self.id:
                    each.write({'is_default': False})


class ResCity(models.Model):
    _name = 'res.city'

    name = fields.Char('Name')

class Property(models.Model):
    _inherit = 'product.template'

    property_code = fields.Char('')
    grouped = fields.Boolean(
        string="Is a Parent", help="parent property can contain multiple properties")
    parent_id = fields.Many2one(
        comodel_name='product.template', string='Parent Property', domain=[('grouped', '=', True)])
    rent_ok = fields.Boolean('Is Rental Product')
    property_ids = fields.One2many(
        comodel_name='product.template', string='Child Properties', inverse_name='parent_id', readonly=False, required=False)
    property_type = fields.Many2one('property.type', 'Property Type')
    property_manager = fields.Many2one('res.users', 'Property Manager')
    furnishing = fields.Selection([('none', 'None'), ('semi_furnished', 'Semi Furnished'), ('full_furnished', 'Full Furnished')], string="Furnishing")
    bed_rooms = fields.Integer('Bedrooms')
    bath_rooms = fields.Integer('Bathrooms')
    garages = fields.Integer('Garages')
    facing = fields.Selection([('north', 'North'), ('south', 'South'), ('east', 'East'),('west','West')], string="Facing")
    ownership = fields.Selection([('leasehold','Leasehold')],string='Ownership')
    condition = fields.Char('Conditions')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    property_account_income_id = fields.Many2one('account.account', company_dependent=True,
                                                 string="Income Account",
                                                 help="This account will be used for invoices instead of the default one to value sales for the current product.")
    property_account_expense_id = fields.Many2one('account.account', company_dependent=True,
                                                  string="Expense Account",
                                                  help="This account will be used for invoices instead of the default one to value expenses for the current product.")
    property_account_deferred_id = fields.Many2one('account.account', company_dependent=True,
                                                  string="Deferred Income Account",
                                                  help="This account will be used for invoices instead of the default one to value expenses for the current product.")


    # Fields for address
    street = fields.Char('Street')
    street2 = fields.Char('Street2')
    zip = fields.Char('Zip', change_default=True)
    city_id = fields.Many2one('res.city','City',required=True)
    state_id = fields.Many2one("res.country.state", string='State')
    country_id = fields.Many2one('res.country', string='Country')

    property_age = fields.Date('Age of Property')
    area = fields.Char('Area (m)')
    monthly_rent = fields.Float('Monthly Rent', compute='compute_monthly_rent')
    annual_rent = fields.Float('Annual Rent')


    annual_service_fees = fields.Float(string='Annual Service Fees')
    extra_annual_fees = fields.Float(string='Annual Extra Fees')
    maintenance_annual_fees = fields.Float('Annual Maintenance Fees')
    total_annual_fees = fields.Float('Total Annual Fees', compute='compute_total_annual_fees')

    tenancy_ids = fields.One2many('rental.tenancy','property_id',string='')

    asset_id = fields.Many2one('account.asset.asset',string="Asset")
    depreciation_line_ids = fields.One2many('account.asset.depreciation.line', 'property_id',related='asset_id.depreciation_line_ids', string='Depreciation Lines', readonly=True)
    salvage_value = fields.Float(string='Salvage Value', digits=0, help="It is the amount you plan to have that you cannot depreciate.")
    value = fields.Float(string='Gross Value',digits=0)
    value_residual = fields.Float(compute='_amount_residual', method=True, digits=0, string='Residual Value')
    tenancy_count = fields.Integer(string='# of Tenancy', compute='_get_tenancy_count', readonly=True)


    stage_id = fields.Many2one('property.stage', string='Stage', track_visibility='onchange',
                               default=lambda self: self._default_stage_id())
    _sql_constraints = {('unique_name', 'unique(name)', 'Name of property must be unique.')}


    @api.multi
    def _get_tenancy_count(self):
        for order in self:
            order.update({
                'tenancy_count': len(self.env['rental.tenancy'].sudo().search([('property_id', '=', order.id)])),
            })

    @api.multi
    def action_view_contract(self):
        tenancies = self.env['rental.tenancy'].sudo().search([('property_id', '=', self.id)])
        action = self.env.ref('property_rent_managemnet.view_tenancy_action').read()[0]
        if len(tenancies) > 1:
            action['domain'] = [('id', 'in', tenancies.ids)]
        elif len(tenancies) == 1:
            action['views'] = [(self.env.ref('property_rent_managemnet.view_tenancy_form').id, 'form')]
            action['res_id'] = tenancies.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    @api.constrains('name')
    def _check_name_length(self):
        for record in self:
            if len(record.name) > 21:
                raise ValidationError("Your property name is too long: %s" % record.name)

    @api.one
    @api.depends('value', 'salvage_value', 'depreciation_line_ids.move_check', 'depreciation_line_ids.amount')
    def _amount_residual(self):
        total_amount = 0.0
        for line in self.depreciation_line_ids:
            if line.move_check:
                total_amount += line.amount
        self.value_residual = self.value - total_amount - self.salvage_value


    @api.onchange('rent_ok')
    def set_rent_stage(self):
        for record in self:
            if record.rent_ok:
                record.sale_ok = False
                stage_id = self.env['property.stage'].search([('name', '=', "Available")])
                if record.stage_id.name != "On Lease":
                    record.stage_id = stage_id


    @api.onchange('sale_ok')
    def set_sale_stage(self):
        for record in self:
            if record.sale_ok:
                record.rent_ok = False
                stage_id = self.env['property.stage'].search([('name', '=', "Sale")])
                if record.stage_id.name != "Sold":
                    record.stage_id = stage_id


    def compute_depreciation_board(self):
        for record in self:
            if not record.asset_category_id or not record.value:
                raise exceptions.ValidationError('Please define the Asset type and Gross value in General Information Tab')
            account_asset_data = {
                'name': record.name,
                'category_id': record.asset_category_id.id ,
                'date': date.today(),
                'value': record.value,
                'salvage_value':record.salvage_value,
                # 'line_ids': [(0, 0, journal_item_credit),(0,0,journal_item_debit)]
            }
            asset_id = self.env['account.asset.asset'].create(account_asset_data)
            self.asset_id = asset_id.id


    def _default_stage_id(self):
        return self.env['property.stage'].search([('is_default','=',True)])

    @api.onchange('annual_rent')
    def compute_monthly_rent(self):
        for each in self:
            if each.annual_rent:
                each.monthly_rent = each.annual_rent/12

    @api.onchange('annual_service_fees','extra_annual_fees','maintenance_annual_fees')
    def compute_total_annual_fees(self):
        for each in self:
            each.total_annual_fees = each.annual_service_fees + each.extra_annual_fees + each.maintenance_annual_fees


    @api.onchange('parent_id')
    def set_address(self):
        for each in self:
            if each.parent_id:
                each.street = each.parent_id.street
                each.street2 = each.parent_id.street2
                each.zip = each.parent_id.zip
                each.city = each.parent_id.city
                each.state_id = each.parent_id.state_id
                each.country_id = each.parent_id.country_id



class PropertyType (models.Model):
    _name = 'property.type'
    _description = 'Property Type'

    name = fields.Char(string='Name', size=64, required=True)

class RentType (models.Model):
    _name = 'rent.type'
    _description = 'Rent Type'

    name = fields.Char(string='Name', size=64, required=True)
    repeat_number = fields.Integer('Repeat every', required=True)

class RoomType (models.Model):
    _name = 'room.type'
    _description = 'Room Type'

    name = fields.Char(string='Name', size=64, required=True)

class UtilityType (models.Model):
    _name = 'utility.type'
    _description = 'Utility Type'

    name = fields.Char(string='Name', size=64, required=True)

class MaintenanceType (models.Model):
    _name = 'maintenance.type'
    _description = 'Maintenance Type'

    name = fields.Char(string='Name', size=64, required=True)


class AccountAssetDepreciationLineInherit(models.Model):
    _inherit = 'account.asset.depreciation.line'

    property_id = fields.Many2one('account.asset.asset', string='Property', ondelete='cascade')