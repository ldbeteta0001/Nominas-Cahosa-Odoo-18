# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    extra_hours_request_ids = fields.One2many(
        'hr.extra.hours.request',
        'employee_id',
        string='Solicitudes de Horas Extra'
    )
    
    extra_hours_request_count = fields.Integer(
        string='Número de Solicitudes',
        compute='_compute_extra_hours_request_count'
    )
    
    extra_hours_tolerance = fields.Float(
        string='Tolerancia de Horas Extra (minutos)',
        default=15.0,
        help='Tolerancia en minutos antes de generar solicitud automática'
    )

    @api.depends('extra_hours_request_ids')
    def _compute_extra_hours_request_count(self):
        for employee in self:
            employee.extra_hours_request_count = len(employee.extra_hours_request_ids)

    def action_view_extra_hours_requests(self):
        """Abrir vista de solicitudes de horas extra del empleado"""
        self.ensure_one()
        return {
            'name': _('Solicitudes de Horas Extra'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.extra.hours.request',
            'view_mode': 'list,form,kanban',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id}
        }
