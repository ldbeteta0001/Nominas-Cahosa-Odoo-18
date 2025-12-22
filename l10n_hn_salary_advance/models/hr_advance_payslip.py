# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, Command, fields, api, tools, _


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    @api.depends('employee_id', 'contract_id', 'struct_id', 'date_from', 'date_to', 'struct_id')
    def _compute_input_line_ids(self):
        super(HrPayslip, self)._compute_input_line_ids()
        input_line_vals = []
        attachment_types = self._get_attachment_types_advance()
        attachment_type_ids = [f.id for f in attachment_types.values()]
        lines_to_remove = self.input_line_ids.filtered(lambda x: x.input_type_id.id in attachment_type_ids)
        input_line_vals = [Command.unlink(line.id) for line in lines_to_remove]
        for payslip in self:
            if payslip.employee_id:
                structure_13avo = self.env.ref('l10n_hn_hr_payroll.structure_type_13avo')
                structure_14avo = self.env.ref('l10n_hn_hr_payroll.structure_type_14avo')
                if payslip.struct_id.id == structure_13avo.id:
                    adv_salary = payslip.env['salary.advance'].search(
                        [('employee_id', '=', payslip.employee_id.id),
                         ('state', '=', 'approve'),
                         ('advance_thirteen_avo', '=', True)
                         ], limit=1, order='date')
                elif payslip.struct_id.id == structure_14avo.id:
                    adv_salary = payslip.env['salary.advance'].search(
                        [('employee_id', '=', payslip.employee_id.id),
                         ('state', '=', 'approve'),
                         ('advance_fourteen_avo', '=', True)
                         ], limit=1, order='date')
                else:
                    adv_salary = payslip.env['salary.advance'].search(
                        [('employee_id', '=', payslip.employee_id.id),
                         ('state', '=', 'approve'),
                         ('advance_thirteen_avo', '=', False),
                         ('advance_fourteen_avo', '=', False)
                         ], limit=1, order='date')
                for adv_obj in adv_salary:
                    current_date = payslip.date_from.month
                    date = adv_obj.date
                    existing_date = date.month
                    if adv_obj.advance_thirteen_avo:
                        try:
                            input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance_13avo')
                            input_line_vals.append(Command.create({
                                'name': adv_obj.reason,
                                'amount': adv_obj.advance,
                                'input_type_id': input_type.id,
                            }))
                        except ValueError:
                            pass  # Si el tipo de entrada no existe, omitir
                    elif adv_obj.advance_fourteen_avo:
                        try:
                            input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance_14avo')
                            input_line_vals.append(Command.create({
                                'name': adv_obj.reason,
                                'amount': adv_obj.advance,
                                'input_type_id': input_type.id,
                            }))
                        except ValueError:
                            pass  # Si el tipo de entrada no existe, omitir
                    else:
                        if current_date == existing_date:
                            try:
                                input_type = payslip.env.ref('l10n_hn_salary_advance.payslip_input_type_advance')
                                input_line_vals.append(Command.create({
                                    'name': adv_obj.reason,
                                    'amount': adv_obj.advance,
                                    'input_type_id': input_type.id,
                                }))
                            except ValueError:
                                pass  # Si el tipo de entrada no existe, omitir

                    payslip.update({'input_line_ids': input_line_vals})
            else:
                payslip.update({'input_line_ids': input_line_vals})

    @api.model
    def _get_attachment_types_advance(self):
        try:
            return {
                'load': self.env.ref('l10n_hn_salary_advance.payslip_input_type_advance'),
            }
        except ValueError:
            # Si el registro no existe, retornar un diccionario vacío
            return {}
