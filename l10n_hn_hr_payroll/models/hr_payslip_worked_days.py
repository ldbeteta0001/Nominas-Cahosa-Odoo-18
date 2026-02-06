# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    l10n_hn_leave_id = fields.Many2one('hr.leave', string='Leave', readonly=True)

    @api.depends('is_paid', 'number_of_hours', 'payslip_id', 'contract_id', 'payslip_id.sum_worked_hours')
    def _compute_amount(self):
        worked_days = self.filtered(lambda wd: wd.payslip_id.struct_id.country_id.code == "HN")

        for worked_day in worked_days:
            if worked_day.payslip_id.edited or worked_day.payslip_id.state not in ['draft', 'verify']:
                continue
            if not worked_day.contract_id or worked_day.code == 'OUT' or not worked_day.is_paid or worked_day.is_credit_time:
                worked_days.amount = 0
                continue
            if worked_day.payslip_id.wage_type == "hourly":
                hourly_wage = worked_day.payslip_id.contract_id.hourly_wage
                worked_day.amount = hourly_wage * worked_day.number_of_hours
            else:
                payslip = worked_day.payslip_id
                if worked_day.l10n_hn_leave_id:
                    payslip = self.env['hr.payslip'].search([
                        ('employee_id', '=', worked_day.payslip_id.employee_id.id),
                        ('date_from', '<=', worked_day.l10n_hn_leave_id.date_from),
                        ('date_to', '>=', worked_day.l10n_hn_leave_id.date_from),
                        ('state', 'in', ['done', 'paid']),
                    ], limit=1) or worked_day.payslip_id
                sum_worked_days = worked_day.payslip_id.sum_worked_hours / worked_day.contract_id.resource_calendar_id.hours_per_day
                daily_wage = worked_day.contract_id.contract_wage / (sum_worked_days or 1)
                number_of_days = worked_day.number_of_hours / worked_day.contract_id.resource_calendar_id.hours_per_day
                worked_day.amount = daily_wage * number_of_days

        super(HrPayslipWorkedDays, self - worked_days)._compute_amount()

    @api.depends('work_entry_type_id', 'number_of_days', 'number_of_hours', 'payslip_id')
    def _compute_name(self):
        # Copia de la lógica base con protección ante llaves faltantes en work_entries.
        to_check_public_holiday = {
            res[0]: res[1]
            for res in self.env['resource.calendar.leaves']._read_group(
                [
                    ('resource_id', '=', False),
                    ('work_entry_type_id', 'in', self.mapped('work_entry_type_id').ids),
                    ('date_from', '<=', max(self.payslip_id.mapped('date_to'))),
                    ('date_to', '>=', min(self.payslip_id.mapped('date_from'))),
                ],
                ['work_entry_type_id'],
                ['id:recordset']
            )
        }
        work_entries = {
            (employee, date.date()): we
            for employee, date, we in self.env['hr.work.entry']._read_group(
                domain=[
                    ('date_start', '<=', max(self.payslip_id.mapped('date_to'))),
                    ('date_stop', '>=', min(self.payslip_id.mapped('date_from'))),
                    ('employee_id', 'in', self.payslip_id.employee_id.ids)
                ],
                groupby=['employee_id', 'date_start:day'],
                aggregates=['id:recordset'])
        }
        empty_entries = self.env['hr.work.entry']
        for worked_days in self:
            public_holidays = to_check_public_holiday.get(worked_days.work_entry_type_id, '')
            holidays = public_holidays and public_holidays.filtered(lambda p:
                (p.calendar_id.id == worked_days.payslip_id.contract_id.resource_calendar_id.id or not p.calendar_id.id)
                and p.date_from.date() <= worked_days.payslip_id.date_to
                and p.date_to.date() >= worked_days.payslip_id.date_from
                and p.company_id == worked_days.payslip_id.company_id)
            actual_holidays = self.env['resource.calendar.leaves']
            if holidays:
                for holiday in holidays:
                    day_entries = work_entries.get(
                        (worked_days.payslip_id.employee_id, holiday.date_from.date()),
                        empty_entries
                    )
                    if any(
                            we.code == holiday.work_entry_type_id.code
                            for we in day_entries):
                        actual_holidays |= holiday
            if actual_holidays:
                name = (', '.join(actual_holidays.mapped('name')))
            else:
                name = worked_days.work_entry_type_id.name
            half_day = worked_days._is_half_day()
            worked_days.name = name + (_(' (Half-Day)') if half_day else '')


