# wizards/change_work_schedule_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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