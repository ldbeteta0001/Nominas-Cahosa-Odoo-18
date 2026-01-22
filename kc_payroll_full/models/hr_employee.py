# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    """Extender modelo de empleado para integrar historial"""
    _inherit = 'hr.employee'

    schedule_history_ids = fields.One2many(
        'hr.employee.schedule.history',
        'employee_id',
        string='Historial de horarios'
    )
    current_schedule_history_id = fields.Many2one(
        'hr.employee.schedule.history',
        string='Horario actual',
        compute='_compute_current_schedule_history'
    )
    last_schedule_change = fields.Date(
        string='Último cambio de horario',
        help='Fecha del último cambio de horario'
    )
    
    # Campos para historial de turnos día/noche
    shift_history_ids = fields.One2many(
        'hr.employee.shift.history',
        'employee_id',
        string='Historial de turnos',
        help='Historial de cambios de turno día/noche (legacy, usar shift_assignment_ids)'
    )
    
    shift_assignment_ids = fields.One2many(
        'hr.employee.shift.assignment',
        'employee_id',
        string='Asignaciones de turnos',
        help='Asignaciones diarias de turnos día/noche'
    )
    
    current_shift_history_id = fields.Many2one(
        'hr.employee.shift.history',
        string='Turno actual',
        compute='_compute_current_shift_history',
        store=False
    )
    
    current_shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno Actual',
        compute='_compute_current_shift_period',
        store=True,
        readonly=True,
        help='Turno actual del empleado: Día (06:00-18:00) o Noche (18:00-06:00)'
    )
    
    contract_current_shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno Actual (Contrato)',
        compute='_compute_contract_current_shift_period',
        store=False,
        readonly=True,
        help='Turno actual del empleado desde el contrato activo'
    )
    
    last_shift_change = fields.Date(
        string='Último cambio de turno',
        help='Fecha del último cambio de turno día/noche'
    )

    @api.depends('schedule_history_ids.is_current')
    def _compute_current_schedule_history(self):
        for employee in self:
            current = employee.schedule_history_ids.filtered('is_current')
            employee.current_schedule_history_id = current[0] if current else False
    
    @api.depends('shift_history_ids.is_current')
    def _compute_current_shift_history(self):
        for employee in self:
            current = employee.shift_history_ids.filtered('is_current')
            employee.current_shift_history_id = current[0] if current else False

    @api.depends('shift_assignment_ids.date', 'shift_assignment_ids.shift_period')
    def _compute_current_shift_period(self):
        """Calcula el turno actual desde las asignaciones diarias"""
        for employee in self:
            # Buscar asignación para hoy
            today = fields.Date.today()
            assignment = self.env['hr.employee.shift.assignment'].search([
                ('employee_id', '=', employee.id),
                ('date', '=', today)
            ], limit=1)
            
            if assignment:
                employee.current_shift_period = assignment.shift_period
            else:
                # Si no hay asignación para hoy, buscar en el historial (compatibilidad)
                if employee.shift_history_ids:
                    current_shift = employee.shift_history_ids.filtered('is_current')
                    if current_shift:
                        employee.current_shift_period = current_shift[0].shift_period
                    else:
                        # Si no hay turno actual, buscar el último registro por fecha
                        all_shifts = employee.shift_history_ids.sorted('date_from', reverse=True)
                        if all_shifts:
                            employee.current_shift_period = all_shifts[0].shift_period
                        else:
                            employee.current_shift_period = False
                else:
                    employee.current_shift_period = False

    @api.depends('contract_ids', 'contract_ids.state', 'contract_ids.current_shift_period')
    def _compute_contract_current_shift_period(self):
        for employee in self:
            # Buscar el contrato activo del empleado
            active_contract = employee.contract_ids.filtered(lambda c: c.state == 'open')
            if active_contract:
                # Obtener el current_shift_period del contrato activo
                employee.contract_current_shift_period = active_contract[0].current_shift_period
            else:
                employee.contract_current_shift_period = False

    def create_schedule_history(self, calendar_id, date_from, reason=None):
        """Crea un registro de historial de horario"""
        # Obtener el horario anterior
        previous_calendar = self.resource_calendar_id

        # Cerrar el registro actual si existe
        current_history = self.schedule_history_ids.filtered('is_current')
        if current_history:
            from datetime import timedelta
            current_history.write({'date_to': date_from - timedelta(days=1)})

        # Crear nuevo registro con horario anterior guardado
        new_record = self.env['hr.employee.schedule.history'].create({
            'employee_id': self.id,
            'resource_calendar_id': calendar_id,
            'previous_calendar_id': previous_calendar.id if previous_calendar else False,
            'date_from': date_from,
            'reason': reason or _('Cambio de horario')
        })

        # Actualizar fecha de último cambio
        self.write({'last_schedule_change': date_from})

        return new_record

    def get_shift_period_at_date(self, target_date):
        """Obtiene el turno asignado para este empleado en una fecha específica"""
        self.ensure_one()
        # Primero buscar en asignaciones diarias
        assignment = self.env['hr.employee.shift.assignment'].get_shift_period_for_date(self.id, target_date)
        if assignment:
            return assignment
        
        # Si no hay en asignaciones, buscar en historial (compatibilidad)
        return self.env['hr.employee.shift.history'].get_shift_period_at_date(self.id, target_date)
    
    def get_shift_period_for_date(self, target_date):
        """Método utilitario para obtener turno en una fecha específica"""
        self.ensure_one()
        return self.get_shift_period_at_date(target_date)

    def action_create_shift_exception(self):
        """Abrir formulario para registrar una excepción de turno"""
        self.ensure_one()
        return {
            'name': _('Registrar Excepción de Turno'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.shift.history',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
                'default_date_from': fields.Date.today(),
                'create_exception_mode': True
            }
        }