import datetime
from odoo import api, fields, models, _


class hr_payslip_attendance(models.Model):
    _inherit = 'hr.payslip'

    late_in_days = fields.Integer(compute='_comute_late_days',string="Check In Late Days")
    late_out_days = fields.Integer(compute='_comute_late_days',string="Check Out Early Days")

    unpaid_days = fields.Integer(compute='_compute_unpaid_days',string="Unpaid Days")

    @api.multi
    def _comute_late_days(self):
        for record in self:
            late_days = self.env['hr.attendance'].search(
                [('check_in', '>=', record.date_from),('check_in', '<=', record.date_to), ('employee_id', '=', record.employee_id.id)])
            late_conf = self.env['base.config.settings'].search([('id', '>', 0)], order="id desc", limit=1)
            late_in_count = 0
            late_out_count = 0
            if late_days:
                for day in late_days:
                    date_1 = datetime.datetime.strptime(day.check_in, "%Y-%m-%d %H:%M:%S") + datetime.timedelta(hours=4)
                    date_2 = datetime.datetime.strptime(day.check_out, "%Y-%m-%d %H:%M:%S")+ datetime.timedelta(hours=4)
                    date_1 = date_1 - datetime.timedelta(minutes=late_conf.late_in_limit)
                    date_2 = date_2 + datetime.timedelta(minutes=late_conf.late_out_limit)
                    if date_1.time() > datetime.datetime.strptime(day.branch_id.date_from, "%H:%M:%S").time():
                        late_in_count += 1
                    if date_2.time() < datetime.datetime.strptime(day.branch_id.date_to, "%H:%M:%S").time():
                        late_out_count += 1
            record.late_in_days = late_in_count
            record.late_out_days = late_out_count


    @api.multi
    def _compute_unpaid_days(self):
        DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
        DATE_FORMAT = "%Y-%m-%d"
        for record in self:
            payslip_date_from = datetime.datetime.strptime(record.date_from, DATE_FORMAT).date()
            payslip_date_to = datetime.datetime.strptime(record.date_to, DATE_FORMAT).date()
            ts = []
            date_from = []
            date_to = []
            ts.append(record.employee_id.id)
            date_from.append(record.date_from)
            date_to.append(record.date_to)
            ts = map(str, ts)
            date_from = map(str, date_from)
            date_to = map(str, date_to)
            self.env.cr.execute("""SELECT
                            h.employee_id,
                            h.date_from,
                            h.date_to
                        from
                            hr_holidays h
                            join hr_holidays_status s on (s.id=h.holiday_status_id)
                        where
                            ((date(h.date_from) >= %s and date(h.date_from) <= %s) or (date(h.date_to) >= %s and date(h.date_to) <= %s)) and
                            h.state='validate' and
                            s.deduct=True and
                            h.employee_id = %s
                        """, (tuple(date_from),tuple(date_to),tuple(date_from),tuple(date_to),tuple(ts),))
            res = self.env.cr.dictfetchall()
            unpaid_days = 0
            for r in res:
                from_dt = datetime.datetime.strptime(r['date_from'], DATETIME_FORMAT).date()
                to_dt = datetime.datetime.strptime(r['date_to'], DATETIME_FORMAT).date()
                from_day = from_dt
                to_day = to_dt

                while from_day <= to_day:
                    if from_day >= payslip_date_from and from_day <= payslip_date_to:
                        unpaid_days += 1
                    from_day = from_day + datetime.timedelta(days=1)

            record.unpaid_days = unpaid_days


# class hr_employee_attendance(models.Model):
#     _inherit = 'hr.employee'
#
#     attend_time = fields.Char('Attend At')
#     leave_time = fields.Char('Leave At')


class hr_holidays_status_attendance(models.Model):
    _inherit = 'hr.holidays.status'

    deduct = fields.Boolean("Allow to deduct on payslips")

class hr_attendance_inherit(models.Model):
    _inherit = 'hr.attendance'

    branch_id = fields.Many2one("hr.branch",string="Branch",required=True)

class hr_branches(models.Model):
    _name = "hr.branch"
    _description = "HR Branches"

    name = fields.Char(string="Name",required=True)
    date_from = fields.Char("Work From",required=True)
    date_to = fields.Char("Work To",required=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Branch name already exists !"),
    ]


class YourSettings(models.TransientModel):
    _inherit = 'base.config.settings'

    late_in_limit = fields.Integer('Check in late limit')
    late_out_limit = fields.Integer('Check out late limit')

    def get_default_company_values(self, fields):
        return {
            'late_in_limit': self.env['base.config.settings'].search([('id', '>', 0)], order="id desc", limit=1).late_in_limit,
            'late_out_limit': self.env['base.config.settings'].search([('id', '>', 0)], order="id desc", limit=1).late_out_limit,
        }
