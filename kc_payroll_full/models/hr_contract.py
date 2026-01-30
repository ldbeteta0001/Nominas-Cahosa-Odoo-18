# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    shift_history_ids = fields.One2many(
        'hr.employee.shift.history',
        'employee_id',
        string='Historial de turnos',
        related='employee_id.shift_history_ids',
        readonly=False
    )

    current_shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno Actual',
        compute='_compute_current_shift_period',
        store=False,
        help='Turno actual del empleado: Día (06:00-18:00) o Noche (18:00-06:00)'
    )

    es_mecanico = fields.Boolean(
        string='Es Mecánico',
        default=False,
        help='Marcar si el empleado es mecánico. Los sábados se calcularán al 50% en lugar de 25%.'
    )

    @api.depends('employee_id.shift_history_ids.is_current', 'employee_id.shift_history_ids.shift_period', 'employee_id.shift_history_ids.date_from', 'employee_id.current_shift_period')
    def _compute_current_shift_period(self):
        for contract in self:
            if contract.employee_id:
                # Usar directamente el valor del empleado, que ya tiene la lógica correcta
                contract.current_shift_period = contract.employee_id.current_shift_period
            else:
                contract.current_shift_period = False

    def action_update_shift_period(self):
        """Recalcula el turno actual desde las asignaciones diarias"""
        self.ensure_one()
        
        if not self.employee_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No hay empleado asociado a este contrato.'),
                    'type': 'warning'
                }
            }

        # Recalcular el turno actual desde las asignaciones diarias
        self.employee_id.invalidate_recordset(['current_shift_period'])
        self.employee_id._compute_current_shift_period()
        
        # Recalcular el turno en el contrato
        self.invalidate_recordset(['current_shift_period'])
        self._compute_current_shift_period()
        
        current_shift = self.employee_id.current_shift_period
        message = _('Turno actual recalculado: %s') % (
            'Día' if current_shift == 'dia' else 'Noche' if current_shift == 'noche' else 'Sin turno asignado'
        )
        
        _logger.info(f"Turno actual recalculado para empleado {self.employee_id.name}: {current_shift}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Turno Actualizado'),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
            'context': {'reload': True}
        }

    def action_create_shift_exception(self):
        """Abrir formulario para registrar una excepción de turno desde el contrato"""
        self.ensure_one()
        if not self.employee_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No hay empleado asociado a este contrato.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        return {
            'name': _('Registrar Excepción de Turno'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.shift.history',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_date_from': fields.Date.today(),
                'create_exception_mode': True,
                'skip_overlap_check': True
            }
        }
