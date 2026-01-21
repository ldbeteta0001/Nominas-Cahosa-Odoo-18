# wizards/change_work_schedule_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class ChangeWorkScheduleWizard(models.TransientModel):
    _name = 'hr.change.work.schedule.wizard'
    _description = 'Cambiar horario de trabajo con historial'

    old_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Horario actual',
        required=True,
        help='Horario que queremos reemplazar'
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        help='Lista de empleados con el horario seleccionado'
    )
    new_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Nuevo horario',
        required=True,
        help='Horario que se asignará a los empleados seleccionados'
    )
    change_date = fields.Date(
        string='Fecha desde',
        required=False,
        default=fields.Date.today,
        help='Fecha desde la cual aplicará el nuevo horario'
    )
    change_date_to = fields.Date(
        string='Fecha hasta',
        help='Fecha hasta la cual aplicará el nuevo horario. Dejar vacío para cambio permanente.'
    )
    reason = fields.Text(
        string='Motivo del cambio',
        help='Descripción del por qué se está cambiando el horario'
    )
    update_contracts = fields.Boolean(
        string='Actualizar contratos activos',
        default=True,
        help='Si está marcado, también actualizará los contratos activos'
    )
    preview_mode = fields.Boolean(
        string='Modo vista previa',
        default=True,
        help='Mostrar vista previa antes de aplicar cambios'
    )

    @api.constrains('change_date', 'change_date_to')
    def _check_dates(self):
        for record in self:
            if record.change_date_to and record.change_date > record.change_date_to:
                raise ValidationError(
                    _('La fecha desde no puede ser mayor que la fecha hasta.'))

    @api.onchange('change_date')
    def _onchange_change_date(self):
        if self.change_date and self.change_date < fields.Date.today():
            return {
                'warning': {
                    'title': _('Fecha en el pasado'),
                    'message': _('Has seleccionado una fecha en el pasado. '
                                 'Esto creará un registro histórico.')
                }
            }

    @api.onchange('change_date')
    def _onchange_change_date_suggest_week(self):
        """Sugerir el domingo de la semana cuando se selecciona fecha desde"""
        if self.change_date and not self.change_date_to:
            from datetime import timedelta
            weekday = self.change_date.weekday()
            sunday = self.change_date + timedelta(days=(6 - weekday))
            self.change_date_to = sunday

    @api.onchange('old_calendar_id')
    def _onchange_old_calendar_id(self):
        # Ya no auto-cargar empleados, solo limpiar la lista
        self.employee_ids = [(5, 0, 0)]

    def _onchange_employee_ids(self):
        """Método para forzar actualización de la vista"""
        pass

    def search_employees(self):
        """Buscar empleados basado únicamente en el horario actual"""
        if not self.old_calendar_id:
            raise ValidationError(_('Debe seleccionar un horario actual primero.'))

        # Buscar TODOS los empleados que tienen el horario seleccionado
        empleados = self.env['hr.employee'].search([
            ('resource_calendar_id', '=', self.old_calendar_id.id)
        ])

        # Actualizar la lista de empleados
        self.write({'employee_ids': [(6, 0, empleados.ids)]})

        # FORZAR actualización de la vista
        self._onchange_employee_ids()

        # Mostrar resultado
        count = len(empleados)

        if count > 0:
            message = _('✅ Encontrados: %d empleado(s) con horario "%s"') % (
                      count, self.old_calendar_id.name
                  )

            # Retornar acción para reabrir el wizard y mostrar los empleados
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cambiar horario de trabajo'),
                'res_model': 'hr.change.work.schedule.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'active_id': self.id,
                    'search_completed': True,
                    'search_message': message
                }
            }
        else:
            message = _(
                '❌ No se encontraron empleados con horario "%s".') % (
                      self.old_calendar_id.name
                  )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sin resultados'),
                    'message': message,
                    'type': 'warning'
                }
            }

    def preview_changes(self):
        """Mostrar vista previa de los cambios a realizar"""
        self.preview_mode = True
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vista previa de cambios'),
            'res_model': 'hr.change.work.schedule.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'preview_mode': True}
        }

    def apply_changes(self):
        """Aplicar los cambios de horario"""
        if not self.employee_ids:
            raise ValidationError(_('Debe seleccionar al menos un empleado.'))

        affected_employees = []
        errors = []

        for employee in self.employee_ids:
            try:
                # Cerrar registro actual si existe
                current_history = employee.schedule_history_ids.filtered('is_current')
                if current_history:
                    from datetime import timedelta
                    current_history.write(
                        {'date_to': self.change_date - timedelta(days=1)})

                # Crear UN SOLO registro de historial - DIRECTAMENTE, sin usar create_schedule_history()
                self.env['hr.employee.schedule.history'].create({
                    'employee_id': employee.id,
                    'resource_calendar_id': self.new_calendar_id.id,
                    'previous_calendar_id': employee.resource_calendar_id.id if employee.resource_calendar_id else False,
                    'date_from': self.change_date,
                    'date_to': self.change_date_to,
                    'reason': self.reason or f'Cambio de horario desde {self.change_date}'
                })

                # SIEMPRE actualizar el empleado actual (cambio permanente)
                employee.write({
                    'resource_calendar_id': self.new_calendar_id.id,
                    'last_schedule_change': self.change_date
                })

                # Actualizar contratos activos si está habilitado
                if self.update_contracts:
                    contratos = self.env['hr.contract'].search([
                        ('employee_id', '=', employee.id),
                        ('state', '=', 'open'),
                    ])
                    if contratos:
                        contratos.write({'resource_calendar_id': self.new_calendar_id.id})
                
                # Determinar turno según el nuevo horario y actualizar historial de turnos si es necesario
                # Obtener turno del empleado actual
                current_shift_period = employee.current_shift_period
                
                # Determinar turno del nuevo calendario analizando las horas
                new_shift_period = self._determine_shift_period_from_calendar(self.new_calendar_id)
                
                # Si el turno cambió o no hay turno asignado, crear/actualizar historial de turnos
                if new_shift_period and new_shift_period != current_shift_period:
                    # Crear registro en historial de turnos
                    history_model = self.env['hr.employee.shift.history']
                    history_model.with_context(skip_overlap_check=True).create({
                        'employee_id': employee.id,
                        'shift_period': new_shift_period,
                        'date_from': self.change_date,
                        'date_to': self.change_date_to if self.change_date_to else False,
                        'reason': self.reason or _('Cambio de turno por cambio de horario desde %s') % self.change_date,
                        'changed_by': self.env.user.id
                    })
                    
                    # Recalcular el current_shift_period del empleado
                    employee.invalidate_recordset(['current_shift_period'])
                    employee._compute_current_shift_period()
                    
                    _logger.info('Turno actualizado para empleado %s: %s -> %s', 
                                employee.name, current_shift_period, new_shift_period)

                range_text = f"{self.change_date}"
                if self.change_date_to:
                    range_text += f" - {self.change_date_to}"
                affected_employees.append(f"{employee.name} ({range_text})")

            except Exception as e:
                errors.append(f"{employee.name}: {str(e)}")

        # Mostrar resultado
        if errors:
            message = _('Algunos cambios no pudieron aplicarse:\n') + '\n'.join(errors)
            if affected_employees:
                message += _('\n\nCambios aplicados exitosamente a:\n') + '\n'.join(
                    affected_employees)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cambios parcialmente aplicados'),
                    'message': message,
                    'type': 'warning',
                    'sticky': True
                }
            }
        else:
            change_type = "con rango específico" if self.change_date_to else "permanente"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Cambios aplicados exitosamente'),
                    'message': _('Se aplicó el cambio %s a %d empleado(s)') % (
                    change_type, len(affected_employees)),
                    'type': 'success'
                }
            }
    
    def _determine_shift_period_from_calendar(self, calendar):
        """
        Determinar el turno (día/noche) basándose en las horas del calendario
        
        Lógica:
        - Turno día: Horario principal entre 06:00-18:00
        - Turno noche: Horario principal entre 18:00-06:00
        
        Retorna: 'dia', 'noche' o False
        """
        if not calendar or not calendar.attendance_ids:
            return False
        
        # Buscar períodos que crucen medianoche (00:00-06:00)
        night_periods = calendar.attendance_ids.filtered(
            lambda x: x.hour_from >= 18.0 or (x.hour_from < 6.0 and x.hour_to <= 6.0) or
                     (x.hour_from >= 18.0 and x.hour_to <= 24.0) or
                     (x.hour_from >= 0.0 and x.hour_to <= 6.0)
        )
        
        # Si hay períodos que cruzan medianoche o están entre 18:00-06:00, es turno noche
        if night_periods:
            # Verificar si el período principal es nocturno
            for att in calendar.attendance_ids:
                # Si hay un período que empieza a las 18:00 o después, es turno noche
                if att.hour_from >= 18.0 or (att.hour_from < 6.0):
                    return 'noche'
        
        # Por defecto, es turno día
        return 'dia'