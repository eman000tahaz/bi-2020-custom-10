from datetime import datetime, date

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, Warning


class Tenancy(models.Model):
    _name = 'rental.tenancy'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _rec_name = 'id'

    @api.depends('state')
    def _get_invoice_count(self):
        for order in self:
            invoices = self.env['account.invoice'].sudo().search([('tenancy_id', '=', order.id)])
            order.update({
                'invoice_count': len(invoices),
            })

    image = fields.Binary(related='property_id.image', string="Logo")
    name = fields.Char(string="Account/Contract Name", required=True)
    tenant_id = fields.Many2one('res.partner', required=True, string='Tanent', help="Tenant")
    property_id = fields.Many2one('product.template', string="Property", required=True, help="Property")
    reference =fields.Char('Reference')
    company_id = fields.Many2one('res.company', string='Company')
    sale_id = fields.Many2one('sale.order')

    annual_rent = fields.Float(string='Annual Rent', required=True)
    annual_cleaning_fees = fields.Float(string='Annual Cleaning Fees')
    brokerage_fees = fields.Float(string='Brokerage Fees (%)')
    annual_service_fees = fields.Float(string='Annual Service Fees')
    extra_annual_fees = fields.Float(string='Extra Annual Fees')
    brokerage_fees_amount = fields.Float(string='Brokerage fees',compute='compute_total_rent')

    cost_frequency = fields.Many2one('rent.type', string="Recurrency", help='Frequency of the recurring cost', required=True)
    first_payment_date = fields.Date(string='First Payment',required=True, track_visibility='onchange')
    period = fields.Integer('Period (months)')

    total_rent = fields.Float('Total Amount Due',compute='compute_total_rent')
    total_fees = fields.Float('Total Fees',compute='compute_total_rent')
    rent_start_date = fields.Date(string="Start Date", required=True, default=datetime.today(),help="Starting date of your contract", track_visibility='onchange')
    rent_end_date = fields.Date(string="Expiration Date", required=True, help="Ending date of your contract", track_visibility='onchange')

    state = fields.Selection([('draft', 'New'), ('running', 'In Progress'), ('cancel', 'Cancelled'),('done', 'Closed')], string="State", default="draft", copy=False, track_visibility='onchange')
    previous_state = fields.Char('Previous State')
    notes = fields.Text(string="")
    attachment_ids = fields.Many2many('ir.attachment', 'tenancy_rent_ir_attachments_rel','rental_id', 'attachment_id', string="Tenancy Contract",help="Images of the contract/any attachments")
    recurring_line = fields.One2many('rent.schedule', 'rental_schedule', help="Rent Schedule")

    is_scheduled = fields.Boolean('is scheduled')
    invoice_count = fields.Integer(string='# Invoice', compute='_get_invoice_count', readonly=True)
    sales_person = fields.Many2one('res.users', string='Sales Person', default=lambda self: self.env.uid,
                                   track_visibility='always')

    # invoice_id = fields.Many2one('account.invoice')
    journal_id = fields.Many2one('account.journal',string='Journal',default=lambda s: s._default_journal(),
        domain="[('type', '=', 'sale'),('company_id', '=', company_id)]",
    )
    # journal_entry_id = fields.Many2one('account.move',related='invoice_id.move_id', string='Journal Entry')
    # journal_item_ids = fields.One2many('account.move.line', 'tenancy_id', string="Journal Items")

    @api.multi
    def action_view_invoices(self):
        invoices = self.env['account.invoice'].sudo().search([('tenancy_id', '=', self.id)])
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


    @api.model
    def _default_journal(self):
        company_id = self.env.context.get(
            'company_id', self.env.user.company_id.id)
        domain = [
            ('type', '=', 'sale'),
            ('company_id', '=', company_id)]
        return self.env['account.journal'].search(domain, limit=1)

    @api.constrains('rent_start_date', 'rent_end_date')
    def validate_dates(self):
        if self.rent_end_date <= self.rent_start_date:
            raise Warning("Please select a valid end date.")

    @api.onchange('annual_rent','annual_cleaning_fees','brokerage_fees','annual_service_fees','extra_annual_fees')
    def compute_total_rent(self):
        for each in self:
            each.brokerage_fees_amount = each.annual_rent * each.brokerage_fees /100
            each.total_fees = each.annual_cleaning_fees + each.annual_service_fees + each.extra_annual_fees + each.brokerage_fees_amount
            each.total_rent = each.total_fees + each.annual_rent

    @api.onchange('rent_start_date','period')
    def compute_end_rent_date(self):
        for each in self:
            each.rent_end_date = str(datetime.strptime(each.rent_start_date, '%Y-%m-%d').date() + relativedelta(months=+each.period))

    @api.onchange('property_id')
    def set_property_details(self):
        for each in self:
            each.annual_rent = each.property_id.annual_rent
            each.extra_annual_fees = each.property_id.extra_annual_fees
            each.annual_service_fees = each.property_id.annual_service_fees
            each.company_id = each.property_id.company_id
            each.annual_rent = each.property_id.annual_rent

    @api.multi
    def set_to_done(self):
        invoice_ids = self.env['account.invoice'].search([('origin', '=', self.name)])
        f = 0
        for each in invoice_ids:
            if each.state != 'paid':
                f = 1
                break
        if f == 0:
            self.state = 'done'
        else:
            raise UserError("Some Invoices are pending")

    @api.multi
    def action_contract_cancel(self):
        for contract in self:
            contract.previous_state = contract.state
            contract.state = 'cancel'

    @api.multi
    def action_contract_reset(self):
        for contract in self:
            contract.state = contract.previous_state
        

    @api.constrains('state')
    def state_changer(self):
        if self.state == "running":
            stage_id = self.env['property.stage'].search([('name', '=', "On Lease")]).id
            self.property_id.write({'stage_id': stage_id})
        elif self.state == "done":
            stage_id = self.env['property.stage'].search([('name', '=', "Available")]).id
            self.property_id.write({'stage_id': stage_id})


    @api.multi
    def action_confirm(self):
        self.state = "running"
        sequence_code = 'contract.rental.sequence'
        order_date = self.create_date
        order_date = order_date[0:10]
        self.name = self.env['ir.sequence'].with_context(ir_sequence_date=order_date).next_by_code(sequence_code)
        # if self.property_id.property_account_deferred_id.id:
        #     deferred_account = self.property_id.property_account_deferred_id.id
        # elif self.property_id.parent_id.property_account_deferred_id.id:
        #     deferred_account = self.property_id.parent_id.property_account_deferred_id.id
        # else:
        #     raise UserError(_('Please define deferred income account for this property'))
        if not self.tenant_id.property_account_receivable_id:
            raise UserError(_('Please define Receivable account for this tenant'))

        invoice = self.create_order_invoice()
        invoice.action_invoice_open()
        # journal_item_credit = {
        #     'name': self.property_id.name +" - Annual rent",
        #     'account_id': deferred_account,
        #     'partner_id': self.tenant_id.id,
        #     'credit':self.total_rent,
        #     'date':date.today(),
        #     'tenancy_id':self.id,
        # }
        # journal_item_debit = {
        #     'name': self.property_id.name + " - Annual rent",
        #     'account_id': self.tenant_id.property_account_receivable_id.id,
        #     'partner_id': self.tenant_id.id,
        #     'debit':self.total_rent,
        #     'date': date.today(),
        #     'tenancy_id': self.id,
        # }
        # account_move_data = {
        #     'ref': self.name,
        #     'journal_id': self.journal_id.id,
        #     'date': date.today(),
        #     'line_ids': [(0, 0, journal_item_credit),(0,0,journal_item_debit)]
        # }
        # move_id = self.env['account.move'].create(account_move_data)
        # move_id.post()
        # self.journal_entry_id = move_id.id


    @api.multi
    def create_order_invoice(self):
        self.ensure_one()
        for order in self:
            invoice_vals = order._prepare_invoice()
            invoice = self.env['account.invoice'].create(invoice_vals)
            invoice_line_vals = order._prepare_invoice_line(invoice.id)
            self.env['account.invoice.line'].create(invoice_line_vals)
            invoice.compute_taxes()
            return invoice


    @api.multi
    def _prepare_invoice(self):
        if not self.journal_id:
            journal = self.env['account.journal'].search([('type', '=', 'sale'),('company_id', '=', self.company_id.id)],limit=1)
        else:
            journal = self.journal_id
        if not journal:
            raise UserError(_("Please define a sale journal for the company '%s'.") %(self.company_id.name or '',))
        currency = (
            self.tenant_id.property_product_pricelist.currency_id or
            self.company_id.currency_id
        )
        invoice_vals = ({
            'reference': False,
            'name': self.name,
            'type': 'out_invoice',
            'partner_id': self.tenant_id.address_get(['invoice'])['invoice'],
            'account_id': self.tenant_id.property_account_receivable_id.id,
            'currency_id': currency.id,
            # 'partner_shipping_id': self.partner_shipping_id.id,
            'journal_id': journal.id,
            # 'payment_term_id': self.payment_term_id.id,
            # 'fiscal_position_id': self.fiscal_position_id.id or self.partner_id.property_account_position_id.id,
            # 'team_id': self.team_id.id,
            # 'comment': self.note,
            'date_invoice': self.rent_start_date,
            'origin': self.name,
            'company_id': self.company_id.id,
            'tenancy_id':self.id
            # 'user_id': self.user_id.id,
        })
        return invoice_vals


    @api.model
    def _prepare_invoice_line(self, invoice_id):
        self.ensure_one()
        res = {}
        ir_property_obj = self.env['ir.property']

        account_id = self.property_id.property_account_income_id or self.property_id.categ_id.property_account_income_categ_id
        if not account_id:
            raise UserError(
                _('There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') %
                (self.property_id.name,))

        # fpos = self.partner_id.property_account_position_id
        # if fpos:
        #     account = fpos.map_account(account_id)

        # if self.fiscal_position_id and line.product_id.taxes_id:
        #     tax_ids = self.fiscal_position_id.map_tax(line.product_id.taxes_id).ids
        # else:
        #     tax_ids = line.product_id.taxes_id.ids
        invoice_line_vals = ({
            'name': self.property_id.name,
            'origin': self.name,
            'account_id': account_id.id,
            'invoice_id': invoice_id,
            'price_unit': self.property_id.lst_price,
            'quantity': 1,
            # 'discount': line.discount,
            'uom_id': self.property_id.uom_id.id,
            'product_id': self.property_id.id,
            # 'invoice_line_tax_ids': [(6, 0, line.tax_id.ids)],
            # 'account_analytic_id': line.order_id.project_id.id or False,
            # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
        })
        return invoice_line_vals

    @api.multi
    def action_schedule(self):
        for each in self:
            start_date = datetime.strptime(each.rent_start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(each.rent_end_date, '%Y-%m-%d').date()
            if end_date > start_date:
                each.tenancy_scheduler(start_date,end_date)

    @api.model
    def tenancy_scheduler(self, start_date, end_date):
        recurring_obj = self.env['rent.schedule']
        for tenancy in self:
            if tenancy.rent_start_date:
                next_rent = str(datetime.strptime(tenancy.rent_start_date, '%Y-%m-%d').date() + relativedelta(months=+tenancy.cost_frequency.repeat_number))
            if tenancy.cost_frequency.repeat_number:
                recurring_number = 12/ tenancy.cost_frequency.repeat_number
                recurring_amount = tenancy.total_rent / recurring_number

                while next_rent <= tenancy.rent_end_date:
                    recurring_data = {
                        # 'name': records.property_id.name,
                        'schedule_date': next_rent,
                        # 'account_info': income_account.name,
                        'rental_schedule': tenancy.id,
                        'recurring_amount': recurring_amount,
                    }
                    recurring_obj.create(recurring_data)
                    next_rent = str(datetime.strptime(next_rent, '%Y-%m-%d').date() + relativedelta(months=+tenancy.cost_frequency.repeat_number))
                tenancy.is_scheduled = True
                mail_content = _(
                    '<h3>Reminder Recurrent Payment!</h3><br/>Hi %s, <br/> This is to remind you that the '
                    'recurrent payment for the '
                    'rental contract has to be done.'
                    'Please make the payment at the earliest.'
                    '<br/><br/>'
                    'Please find the details below:<br/><br/>'
                    '<table><tr><td>Contract Ref<td/><td> %s<td/><tr/>'
                    ) % \
                    (self.tenant_id.name, self.name)
                main_content = {
                    'subject': "Reminder Recurrent Payment!",
                    'author_id': self.env.user.partner_id.id,
                    'body_html': mail_content,
                    'email_to': self.tenant_id.email,
                }
                self.env['mail.mail'].create(main_content).send()

    @api.multi
    def action_contract_send(self):
        self.ensure_one()
        template = self.env.ref(
            'property_rent_managemnet.email_contract_template',
            False,
        )
        compose_form = self.env.ref('mail.email_compose_message_wizard_form')
        ctx = dict(
            default_model='account.analytic.account',
            default_res_id=self.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }



    @api.multi
    def name_get(self):
        res = []
        for occ in self:
            name = "Contract for %s" % (occ.tenant_id.name)
            res += [(occ.id, name)]
        return res

    # @api.onchange('product_id')
    # def on_change_product_id(self):
    #     if self.product_id:
    #         self.deposit_paid = self.product_id.rent_amount
    #     else:
    #         self.deposit_paid = 0
    #
    # @api.constrains('deposit_paid')
    # def validate_deposit_paid(self):
    #     if self.deposit_paid < 0:
    #         raise exceptions.ValidationError('Deposit paid cannot be a negative value')


class JournalItemInherit(models.Model):
    _inherit = 'account.move.line'

    tenancy_id = fields.Many2one('rent.tenancy')

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    partner_type = fields.Selection([('customer', 'Tenant'), ('supplier', 'Vendor')])
    schedule_id = fields.Many2one('rent.schedule')

    @api.multi
    def post(self):
        parent = super(AccountPayment, self).post()
        for record in self:
            schedule_id = self.env['rent.schedule'].search([('id', '=', record.schedule_id.id)])
            schedule_id.write({'is_posted':True})
        return parent



class RentSchedule(models.Model):
    _name = 'rent.schedule'

    name = fields.Char('Description')
    schedule_date = fields.Date('Date')
    # account_info = fields.Char('Account')
    recurring_amount = fields.Float('Amount')
    cheque_detail = fields.Char('Cheque Detail')
    assign_to = fields.Char('Assign to')
    is_posted = fields.Boolean('Posted')
    notes = fields.Char('Notes')
    rental_schedule = fields.Many2one('rental.tenancy', string='Tenancy Number')
    tenant_id = fields.Many2one('res.partner', related="rental_schedule.tenant_id")
    property_id = fields.Many2one('product.template', related="rental_schedule.property_id")
    journal_entry_id = fields.Many2one('account.move', string='Journal Entry')
    payment_entry_id = fields.Many2one('account.payment',compute='compute_payment', string='Payment')

    payment_info = fields.Char(compute='paid_info', string='Payment Stage', default='draft')


    def create_journal_entry(self):
        for record in self:
            if record.rental_schedule.property_id.property_account_income_id.id:
                income_account = record.rental_schedule.property_id.property_account_income_id.id
            elif record.rental_schedule.property_id.parent_id.property_account_income_id.id:
                income_account = record.rental_schedule.property_id.parent_id.property_account_income_id.id
            else:
                raise UserError(
                    _('Please define income account for this property'))

            if record.rental_schedule.property_id.property_account_deferred_id.id:
                deferred_account = record.rental_schedule.property_id.property_account_deferred_id.id
            elif record.rental_schedule.property_id.parent_id.property_account_deferred_id.id:
                deferred_account = record.rental_schedule.property_id.parent_id.property_account_deferred_id.id
            else:
                raise UserError(
                    _('Please define deferred income account for this property'))

            journal_item_credit = {
                'name': record.rental_schedule.property_id.name +" - " + record.rental_schedule.cost_frequency.name +"rent",
                'account_id': income_account,
                'partner_id': record.rental_schedule.tenant_id.id,
                'credit': record.recurring_amount,
                'date':record.schedule_date,
            }
            journal_item_debit = {
                'name': record.rental_schedule.property_id.name +" - " + record.rental_schedule.cost_frequency.name +"rent",
                'account_id':  deferred_account,
                'partner_id': record.rental_schedule.tenant_id.id,
                'debit':record.recurring_amount,
                'date':record.schedule_date,
            }
            account_move_data = {
                'ref': record.rental_schedule.name,
                'journal_id': record.rental_schedule.journal_id.id,
                'date': date.today(),
                'line_ids': [(0, 0, journal_item_credit),(0,0,journal_item_debit)]
            }
            move_id = self.env['account.move'].create(account_move_data)
            move_id.post()
            record.journal_entry_id = move_id.id


    @api.multi
    def pay_amount(self):
        # purchases = self.env['purchase.order'].search([('sale_production_id', '=', self.id)])
        # action = self.env.ref('purchase.purchase_rfq').read()[0]
        # if len(purchases) > 1:
        #     action['domain'] = [('id', 'in', purchases.ids)]
        # elif len(purchases) == 1:
        #     action['views'] = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
        #     action['res_id'] = purchases.ids[0]
        # else:
        action = {'type': 'ir.actions.act_window_close'}
        return {
        'name': 'Register Payment',
        'domain': [],
        'res_model': 'account.payment',
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'view_type': 'form',
        'context': {'default_payment_date':self.schedule_date,
                    'default_payment_type':'inbound',
                    'default_amount':self.recurring_amount,
                    'default_partner_type':'customer',
                    'default_partner_id':self.rental_schedule.tenant_id.id,
                    'default_schedule_id':self.id,
                    },
        'target': 'current',
        }
        # return action

    @api.multi
    def button_payment_entry(self):
        payment_id = self.env['account.payment'].search([('schedule_id', '=', self.id)])
        action = self.env.ref('account.action_account_payments').read()[0]
        action['views'] = [(self.env.ref('account.view_account_payment_form').id, 'form')]
        action['res_id'] = payment_id.id
        return action

    @api.multi
    def compute_payment(self):
        for record in self:
            payment_id = self.env['account.payment'].search([('schedule_id', '=', record.id)])
            record.payment_entry_id = payment_id.id


    @api.multi
    @api.depends('payment_info')
    def paid_info(self):
        for each in self:
            return True
            # if self.env['account.invoice'].browse(each.invoice_number):
            #     each.payment_info = self.env['account.invoice'].browse(each.invoice_number).state
            # else:
            #     each.payment_info = 'Record Deleted'


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    tenancy_id = fields.Many2one('rental.tenancy', string="Tenancy")
