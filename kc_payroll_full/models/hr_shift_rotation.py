# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta, date
from odoo import fields as fields_module
import logging

_logger = logging.getLogger(__name__)


class HrShiftRotationLine(models.Model):
    _name = 'hr.shift.rotation.line'
    _description = 'Línea de rotación de turnos'
    _order = 'rotation_id, sequence, date_from'

    rotation_id = fields.Many2one(
        'hr.shift.rotation',
        string='Rotación',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )

    shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno',
        required=True,
        help='Turno a asignar: Día (06:00-18:00) o Noche (18:00-06:00)'
    )

    date_from = fields.Date(
        string='Fecha desde',
        required=True
    )

    date_to = fields.Date(
        string='Fecha hasta',
        required=True
    )

    reason = fields.Text(
        string='Motivo',
        help='Razón del cambio de turno (opcional)'
    )

    weeks = fields.Float(
        string='Semanas',
        compute='_compute_weeks',
        store=False,
        help='Número de semanas en este período'
    )

    @api.depends('date_from', 'date_to')
    def _compute_weeks(self):
        for record in self:
            if record.date_from and record.date_to:
                delta = record.date_to - record.date_from
                record.weeks = round((delta.days + 1) / 7.0, 1)
            else:
                record.weeks = 0.0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError(
                    _('La fecha desde no puede ser mayor que la fecha hasta.'))


class HrShiftRotation(models.Model):
    _name = 'hr.shift.rotation'
    _description = 'Programación de Rotación de Turnos Día/Noche'
    _order = 'name desc, date_created desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        default=lambda self: _('Rotación de Turnos - %s') % fields.Date.today(),
        help='Nombre descriptivo para esta programación de rotación'
    )

    employee_ids = fields.Many2many(
        'hr.employee',
        'hr_shift_rotation_employee_rel',
        'rotation_id',
        'employee_id',
        string='Empleados',
        required=True,
        help='Empleados para los que se programarán los turnos'
    )

    rotation_line_ids = fields.One2many(
        'hr.shift.rotation.line',
        'rotation_id',
        string='Períodos de Rotación',
        required=True
    )

    date_created = fields.Datetime(
        string='Fecha de creación',
        default=fields.Datetime.now,
        readonly=True
    )

    created_by = fields.Many2one(
        'res.users',
        string='Creado por',
        default=lambda self: self.env.user,
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('applied', 'Aplicado'),
        ('cancelled', 'Cancelado')
    ], string='Estado',
        default='draft',
        required=True,
        help='Estado de la programación de rotación'
    )

    employee_count = fields.Integer(
        string='Número de Empleados',
        compute='_compute_employee_count',
        store=False
    )

    period_count = fields.Integer(
        string='Número de Períodos',
        compute='_compute_period_count',
        store=False
    )

    assignment_count = fields.Integer(
        string='Número de Asignaciones',
        compute='_compute_assignment_count',
        store=False
    )

    notes = fields.Text(
        string='Notas',
        help='Notas adicionales sobre esta programación'
    )

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.employee_ids)

    @api.depends('rotation_line_ids')
    def _compute_period_count(self):
        for record in self:
            record.period_count = len(record.rotation_line_ids)
    
    @api.depends('employee_ids', 'rotation_line_ids')
    def _compute_assignment_count(self):
        for record in self:
            if not record.employee_ids or not record.rotation_line_ids:
                record.assignment_count = 0
            else:
                # Calcular total de días que se generarán
                total_days = 0
                for line in record.rotation_line_ids:
                    if line.date_from and line.date_to:
                        total_days += (line.date_to - line.date_from).days + 1
                    elif line.date_from:
                        total_days += 1
                record.assignment_count = total_days * len(record.employee_ids)

    def action_add_period(self):
        """Agregar un nuevo período de rotación"""
        self.ensure_one()
        last_line = self.rotation_line_ids and self.rotation_line_ids.sorted('sequence')[-1]
        new_date_from = last_line.date_to + timedelta(days=1) if last_line and last_line.date_to else date.today()
        
        # Alternar turno
        next_shift = 'noche' if last_line and last_line.shift_period == 'dia' else 'dia'

        self.rotation_line_ids = [(0, 0, {
            'sequence': (last_line.sequence + 10) if last_line else 10,
            'shift_period': next_shift,
            'date_from': new_date_from,
            'date_to': new_date_from + timedelta(weeks=2) - timedelta(days=1),  # Sugerir 2 semanas
            'reason': _('Rotación automática')
        })]
        return True

    def action_preview(self):
        """Mostrar vista previa de los cambios a realizar"""
        self.ensure_one()
        if not self.rotation_line_ids:
            raise ValidationError(_('Debe definir al menos un período de rotación.'))

        message = _("Se aplicarán los siguientes cambios de turno:\n\n")
        for employee in self.employee_ids:
            message += f"Empleado: {employee.name}\n"
            for line in self.rotation_line_ids.sorted('sequence'):
                message += f"  - {line.shift_period.capitalize()}: {line.date_from} - {line.date_to} ({line.weeks} semanas)\n"
            message += "\n"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Vista Previa de Rotación de Turnos'),
                'message': message,
                'type': 'info',
                'sticky': True
            }
        }

    def _iter_dates(self, date_from, date_to):
        """Genera todas las fechas en un rango (incluye ambas fechas)"""
        if not date_from:
            return []
        if not date_to:
            return [date_from]
        
        current_date = date_from
        dates = []
        while current_date <= date_to:
            dates.append(current_date)
            current_date += timedelta(days=1)
        return dates

    def action_apply(self):
        """Aplicar los cambios de rotación de turno a los empleados - Genera asignaciones diarias"""
        self.ensure_one()
        if not self.employee_ids:
            raise ValidationError(_('Debe seleccionar al menos un empleado.'))
        if not self.rotation_line_ids:
            raise ValidationError(_('Debe definir al menos un período de rotación.'))

        affected_employees = []
        errors = []
        total_days_created = 0
        total_days_updated = 0
        
        assignment_model = self.env['hr.employee.shift.assignment']
        history_model = self.env['hr.employee.shift.history']

        for employee in self.employee_ids:
            try:
                # Usar savepoint por empleado para evitar lotes inconsistentes
                with self.env.cr.savepoint():
                    days_created = 0
                    days_updated = 0
                    
                    # Primero cerrar el turno actual si existe
                    current_history = history_model.search([
                        ('employee_id', '=', employee.id),
                        ('is_current', '=', True)
                    ], limit=1)
                    
                    # Obtener la primera fecha de la rotación para cerrar el período anterior
                    first_line = self.rotation_line_ids.sorted('sequence')[0]
                    first_rotation_date = first_line.date_from
                    
                    if current_history and current_history.date_from < first_rotation_date:
                        # Cerrar el período anterior un día antes de la nueva rotación
                        close_date = first_rotation_date - timedelta(days=1)
                        current_history.write({
                            'date_to': close_date,
                            'is_current': False
                        })
                        _logger.debug(f"Cerrado período anterior para empleado {employee.name} hasta {close_date}")
                    
                    for line in self.rotation_line_ids.sorted('sequence'):
                        # Generar todas las fechas del rango
                        dates = self._iter_dates(line.date_from, line.date_to or line.date_from)
                        
                        for date_val in dates:
                            # Buscar asignación existente
                            existing = assignment_model.search([
                                ('employee_id', '=', employee.id),
                                ('date', '=', date_val)
                            ], limit=1)
                            
                            vals = {
                                'employee_id': employee.id,
                                'date': date_val,
                                'shift_period': line.shift_period,
                                'rotation_id': self.id,
                                'rotation_line_id': line.id,
                                'reason': line.reason or _('Rotación de turno programada desde %s') % self.name,
                                'state': 'applied'
                            }
                            
                            if existing:
                                existing.write(vals)
                                days_updated += 1
                                _logger.debug(f"Actualizada asignación para empleado {employee.name} en fecha {date_val}")
                            else:
                                assignment_model.create(vals)
                                days_created += 1
                                _logger.debug(f"Creada asignación para empleado {employee.name} en fecha {date_val}")
                    
                    # Crear o actualizar registros en el historial de turnos basándose en las líneas de rotación
                    for line in self.rotation_line_ids.sorted('sequence'):
                        # Buscar si ya existe un registro de historial para este período
                        existing_history = history_model.search([
                            ('employee_id', '=', employee.id),
                            ('shift_period', '=', line.shift_period),
                            ('date_from', '=', line.date_from),
                            ('date_to', '=', line.date_to)
                        ], limit=1)
                        
                        if not existing_history:
                            # Verificar si hay un período actual que podamos extender
                            if line.date_to:  # Período con fecha fin
                                # Crear nuevo registro de historial para este período
                                history_model.with_context(skip_overlap_check=True).create({
                                    'employee_id': employee.id,
                                    'shift_period': line.shift_period,
                                    'date_from': line.date_from,
                                    'date_to': line.date_to,
                                    'reason': line.reason or _('Rotación de turno programada desde %s') % self.name,
                                    'changed_by': self.env.user.id
                                })
                                _logger.debug(f"Creado registro de historial para empleado {employee.name}: {line.shift_period} del {line.date_from} al {line.date_to}")
                            else:  # Período actual (sin fecha fin)
                                # Cerrar períodos anteriores y crear uno nuevo como actual
                                history_model.with_context(skip_overlap_check=True).create({
                                    'employee_id': employee.id,
                                    'shift_period': line.shift_period,
                                    'date_from': line.date_from,
                                    'date_to': False,  # Sin fecha fin = turno actual
                                    'reason': line.reason or _('Rotación de turno programada desde %s') % self.name,
                                    'changed_by': self.env.user.id
                                })
                                _logger.debug(f"Creado registro de historial actual para empleado {employee.name}: {line.shift_period} desde {line.date_from}")
                        else:
                            # Actualizar si ya existe
                            existing_history.write({
                                'reason': line.reason or _('Rotación de turno programada desde %s') % self.name,
                                'changed_by': self.env.user.id
                            })
                            _logger.debug(f"Actualizado registro de historial para empleado {employee.name}")
                    
                    # Recalcular el current_shift_period del empleado
                    employee.invalidate_recordset(['current_shift_period', 'shift_history_ids'])
                    employee._compute_current_shift_period()
                    
                    # Actualizar last_shift_change con la primera fecha de la rotación
                    employee.write({
                        'last_shift_change': first_line.date_from
                    })
                    
                    total_days_created += days_created
                    total_days_updated += days_updated
                    
                    affected_employees.append({
                        'name': employee.name,
                        'created': days_created,
                        'updated': days_updated
                    })

            except Exception as e:
                errors.append(f"{employee.name}: {str(e)}")
                _logger.error("Error al aplicar rotación para empleado %s: %s", employee.name, str(e))

        # Construir mensaje con resumen
        if errors:
            message = _('Algunos cambios no pudieron aplicarse:\n') + '\n'.join(errors)
            if affected_employees:
                emp_names = [emp['name'] if isinstance(emp, dict) else emp for emp in affected_employees]
                message += _('\n\nCambios aplicados exitosamente a:\n') + '\n'.join(emp_names)
            emp_details = ''  # No mostrar detalles si hay errores
        else:
            # Marcar como aplicado
            self.write({'state': 'applied'})
            
            if affected_employees:
                emp_details = '\n'.join([
                    f"  - {emp['name']}: {emp['created']} días creados, {emp['updated']} días actualizados"
                    for emp in affected_employees
                ])
                message = _('Rotación de turnos aplicada exitosamente:\n\n') + \
                         _('Empleados afectados: %d\n') % len(affected_employees) + \
                         _('Total días creados: %d\n') % total_days_created + \
                         _('Total días actualizados: %d\n\n') % total_days_updated + \
                         _('Detalle por empleado:\n') + emp_details
            else:
                message = _('No se generaron asignaciones.')
        
        _logger.info(f"Rotación aplicada: {len(affected_employees)} empleados, {total_days_created} días creados, {total_days_updated} días actualizados")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rotación de Turnos Aplicada') if not errors else _('Cambios parcialmente aplicados'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True
            }
        }

    def action_cancel(self):
        """Cancelar la programación"""
        self.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        """Resetear a borrador"""
        self.write({'state': 'draft'})
        return True

    def action_view_employees(self):
        """Acción para ver empleados desde rotación"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Empleados'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.employee_ids.ids)],
            'context': {'default_employee_ids': self.employee_ids.ids}
        }

    def action_view_periods(self):
        """Acción para ver períodos desde rotación"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Períodos de Rotación'),
            'res_model': 'hr.shift.rotation.line',
            'view_mode': 'list,form',
            'domain': [('rotation_id', '=', self.id)],
            'context': {'default_rotation_id': self.id}
        }

    def action_view_assignments_calendar(self):
        """Acción para ver calendario de asignaciones desde rotación"""
        self.ensure_one()
        if not self.rotation_line_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No hay períodos de rotación definidos.'),
                    'type': 'info'
                }
            }
        
        # Calcular rango de fechas desde las líneas
        min_date = min(line.date_from for line in self.rotation_line_ids)
        max_date = max(line.date_to or line.date_from for line in self.rotation_line_ids)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Calendario de Turnos - %s') % self.name,
            'res_model': 'hr.employee.shift.assignment',
            'view_mode': 'calendar,list,form',
            'domain': [
                ('employee_id', 'in', self.employee_ids.ids),
                ('date', '>=', min_date),
                ('date', '<=', max_date)
            ],
            'context': {
                'default_rotation_id': self.id,
                'search_default_group_employee': 1
            }
        }

    def action_search_employees_without_shift(self):
        """Buscar empleados sin turno asignado basándose en contratos activos"""
        self.ensure_one()
        
        _logger.info("=== INICIO action_search_employees_without_shift ===")
        _logger.info("Rotación ID: %s, Nombre: %s", self.id, self.name)
        _logger.info("Empleados actualmente en la rotación: %s", len(self.employee_ids))
        if self.employee_ids:
            _logger.info("IDs de empleados actuales: %s", self.employee_ids.ids)
        
        # Buscar empleados que tienen contratos activos pero no tienen turno asignado
        _logger.info("Buscando contratos activos...")
        active_contracts = self.env['hr.contract'].search([
            ('state', '=', 'open')
        ])
        _logger.info("Total contratos activos encontrados: %s", len(active_contracts))
        
        # Obtener empleados con contratos activos que no tienen turno asignado
        employees_without_shift = active_contracts.filtered(
            lambda c: not c.employee_id.current_shift_period
        ).mapped('employee_id')
        
        _logger.info("=== RESUMEN ===")
        _logger.info("Total empleados SIN turno encontrados: %s", len(employees_without_shift))
        if employees_without_shift:
            _logger.info("IDs de empleados SIN turno: %s", employees_without_shift.ids)
        
        # Obtener empleados existentes
        current_employee_ids = self.employee_ids.ids
        _logger.info("Empleados actuales en la rotación: %s", current_employee_ids)
        
        # Obtener IDs de empleados sin turno
        new_employee_ids = employees_without_shift.ids
        
        # Agregar los nuevos empleados (evitar duplicados)
        all_employee_ids = list(set(current_employee_ids + new_employee_ids))
        _logger.info("Empleados después de agregar: %s", all_employee_ids)
        
        # Calcular cuántos se agregaron
        added_count = len(all_employee_ids) - len(current_employee_ids)
        
        # Actualizar el campo employee_ids
        self.write({
            'employee_ids': [(6, 0, all_employee_ids)]
        })
        
        _logger.info("Empleados agregados automáticamente: %s", added_count)
        _logger.info("=== FIN action_search_employees_without_shift ===")
        
        # Mostrar notificación
        if added_count > 0:
            message = _('Se agregaron automáticamente %d empleado(s) sin turno a la rotación.') % added_count
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Empleados Agregados'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            message = _('No se encontraron empleados sin turno para agregar.')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': message,
                    'type': 'info',
                    'sticky': False,
                }
            }

    def action_add_selected_employees(self, employee_ids):
        """Agregar empleados seleccionados a la rotación"""
        self.ensure_one()
        
        _logger.info("=== INICIO action_add_selected_employees ===")
        _logger.info("Rotación ID: %s", self.id)
        _logger.info("Empleados a agregar: %s", employee_ids)
        
        if not employee_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Advertencia'),
                    'message': _('No se seleccionaron empleados.'),
                    'type': 'warning'
                }
            }
        
        # Convertir employee_ids a lista si no lo es
        if isinstance(employee_ids, (int, str)):
            employee_ids = [int(employee_ids)]
        else:
            employee_ids = [int(eid) for eid in employee_ids]
        
        # Obtener empleados existentes
        current_employee_ids = self.employee_ids.ids
        _logger.info("Empleados actuales en la rotación: %s", current_employee_ids)
        
        # Agregar los nuevos empleados (evitar duplicados)
        new_employee_ids = list(set(current_employee_ids + employee_ids))
        _logger.info("Empleados después de agregar: %s", new_employee_ids)
        
        # Actualizar el campo employee_ids
        self.write({
            'employee_ids': [(6, 0, new_employee_ids)]
        })
        
        added_count = len(new_employee_ids) - len(current_employee_ids)
        _logger.info("Empleados agregados: %s", added_count)
        _logger.info("=== FIN action_add_selected_employees ===")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleados Agregados'),
                'message': _('Se agregaron %d empleado(s) a la rotación de turnos.') % added_count,
                'type': 'success'
            }
        }
