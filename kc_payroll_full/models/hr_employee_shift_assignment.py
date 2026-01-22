# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class HrEmployeeShiftAssignment(models.Model):
    _name = 'hr.employee.shift.assignment'
    _description = 'Asignación Diaria de Turnos de Empleados'
    _order = 'employee_id, date desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    date = fields.Date(
        string='Fecha',
        required=True,
        index=True,
        default=fields.Date.today,
        help='Fecha del día asignado'
    )
    
    shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno',
        required=True,
        help='Turno asignado: Día (06:00-18:00) o Noche (18:00-06:00)'
    )
    
    rotation_id = fields.Many2one(
        'hr.shift.rotation',
        string='Rotación',
        ondelete='set null',
        help='Rotación que generó esta asignación'
    )
    
    rotation_line_id = fields.Many2one(
        'hr.shift.rotation.line',
        string='Línea de Rotación',
        ondelete='set null',
        help='Línea de rotación que generó esta asignación'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('applied', 'Aplicado')
    ], string='Estado',
        default='draft',
        help='Estado de la asignación'
    )
    
    reason = fields.Text(
        string='Motivo',
        help='Razón del cambio de turno o asignación (opcional)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='employee_id.company_id',
        store=True,
        readonly=True
    )
    
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name'
    )

    _sql_constraints = [
        ('unique_employee_date', 'UNIQUE(employee_id, date)',
         'Un empleado solo puede tener una asignación por día.')
    ]

    @api.depends('employee_id', 'shift_period', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.shift_period and record.date:
                turno_str = 'Día' if record.shift_period == 'dia' else 'Noche'
                record.display_name = f"{record.employee_id.name} - {turno_str} ({record.date})"
            else:
                record.display_name = "Nueva asignación"

    @api.model
    def get_shift_period_for_date(self, employee_id, target_date):
        """
        Obtiene el turno asignado para un empleado en una fecha específica.
        
        :param employee_id: ID del empleado
        :param target_date: Fecha objetivo
        :return: 'dia', 'noche' o False
        """
        assignment = self.search([
            ('employee_id', '=', employee_id),
            ('date', '=', target_date)
        ], limit=1)
        return assignment.shift_period if assignment else False

    @api.model
    def get_current_shift_period(self, employee_id):
        """
        Obtiene el turno actual del empleado (hoy).
        
        :param employee_id: ID del empleado
        :return: 'dia', 'noche' o False
        """
        return self.get_shift_period_for_date(employee_id, fields.Date.today())

    @api.model
    def create_or_update(self, employee_id, date, shift_period, **kwargs):
        """
        Crea o actualiza una asignación para un empleado en una fecha específica.
        
        :param employee_id: ID del empleado
        :param date: Fecha
        :param shift_period: 'dia' o 'noche'
        :param kwargs: Otros campos opcionales (rotation_id, rotation_line_id, reason, state)
        :return: Record creado o actualizado
        """
        assignment = self.search([
            ('employee_id', '=', employee_id),
            ('date', '=', date)
        ], limit=1)
        
        vals = {
            'employee_id': employee_id,
            'date': date,
            'shift_period': shift_period,
            **kwargs
        }
        
        if assignment:
            assignment.write(vals)
            _logger.debug(f"Actualizada asignación para empleado {employee_id} en fecha {date}")
            return assignment
        else:
            assignment = self.create(vals)
            _logger.debug(f"Creada nueva asignación para empleado {employee_id} en fecha {date}")
            return assignment
