# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class HrEmployeeShiftHistory(models.Model):
    _name = 'hr.employee.shift.history'
    _description = 'Historial de Turnos de Empleados (Día/Noche)'
    _order = 'employee_id, date_from desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        ondelete='cascade',
        index=True
    )
    rotation_id = fields.Many2one(
        'hr.shift.rotation',
        string='Rotación',
        ondelete='set null',
        index=True,
        help='Rotación que generó este registro de historial'
    )
    shift_period = fields.Selection([
        ('dia', 'Día'),
        ('noche', 'Noche')
    ], string='Turno Asignado',
        required=True,
        help='Turno asignado al empleado para este período'
    )
    date_from = fields.Date(
        string='Fecha desde',
        required=True,
        default=fields.Date.today
    )
    date_to = fields.Date(
        string='Fecha hasta',
        help='Dejar vacío si es el turno actual'
    )
    is_current = fields.Boolean(
        string='Es actual',
        compute='_compute_is_current',
        store=True,
        index=True
    )
    reason = fields.Text(
        string='Motivo del cambio',
        help='Descripción del por qué se cambió el turno'
    )
    changed_by = fields.Many2one(
        'res.users',
        string='Cambiado por',
        default=lambda self: self.env.user,
        required=True
    )
    display_name = fields.Char(
        string='Nombre',
        compute='_compute_display_name'
    )

    @api.depends('date_to')
    def _compute_is_current(self):
        for record in self:
            record.is_current = not record.date_to

    @api.depends('employee_id', 'shift_period', 'date_from', 'date_to')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.shift_period:
                date_range = f"desde {record.date_from}"
                if record.date_to:
                    date_range = f"{record.date_from} - {record.date_to}"
                turno_str = 'Día' if record.shift_period == 'dia' else 'Noche'
                record.display_name = f"{record.employee_id.name} - {turno_str} ({date_range})"
            else:
                record.display_name = "Nuevo registro"

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_to and record.date_from > record.date_to:
                raise ValidationError(
                    _('La fecha desde no puede ser mayor que la fecha hasta.'))

    @api.constrains('employee_id', 'date_from', 'date_to')
    def _check_overlapping_periods(self):
        # Permitir bypass de validación si se está ajustando desde el sistema
        if self.env.context.get('skip_overlap_check'):
            return
            
        for record in self:
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('id', '!=', record.id)
            ]
            if record.date_to:
                domain.extend([
                    '|',
                    '&', ('date_from', '<=', record.date_from),
                    '|', ('date_to', '>=', record.date_from), ('date_to', '=', False),
                    '&', ('date_from', '<=', record.date_to),
                    '|', ('date_to', '>=', record.date_to), ('date_to', '=', False)
                ])
            else:
                domain.extend([
                    '&', ('date_from', '<=', record.date_from),
                    '|', ('date_to', '>=', record.date_from), ('date_to', '=', False)
                ])
            
            overlapping_records = self.search(domain)
            if overlapping_records:
                raise ValidationError(
                    _('Los períodos de turno para el empleado %s se solapan con un registro existente.') % record.employee_id.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        # Si se está creando en modo excepción, usar el método helper
        if self.env.context.get('create_exception_mode') and not self.env.context.get('from_manual_change') and vals_list:
            vals = vals_list[0]
            employee_id = vals.get('employee_id')
            shift_period = vals.get('shift_period')
            date_from = vals.get('date_from')
            date_to = vals.get('date_to')
            reason = vals.get('reason') or _('Excepción de turno registrada manualmente')
            
            if employee_id and shift_period and date_from:
                return self.create_manual_change(employee_id, shift_period, date_from, date_to, reason)
        
        records = super().create(vals_list)
        
        # Si no es modo excepción pero hay solapamientos, ajustarlos
        if not self.env.context.get('skip_overlap_check'):
            for record in records:
                record.adjust_overlapping_periods()
        
        for record in records:
            if not record.date_to:  # Si es el turno actual
                record.employee_id.write({
                    'current_shift_period': record.shift_period,
                    'last_shift_change': record.date_from
                })
        return records

    def write(self, vals):
        result = super().write(vals)
        for record in self:
            if 'date_to' in vals and not vals['date_to'] and record.is_current:
                record.employee_id.write({
                    'current_shift_period': record.shift_period,
                    'last_shift_change': fields.Date.today()
                })
        return result

    @api.model
    def get_shift_period_at_date(self, employee_id, target_date):
        """
        Obtiene el turno asignado para un empleado en una fecha específica.
        """
        history = self.search([
            ('employee_id', '=', employee_id),
            ('date_from', '<=', target_date),
            '|',
            ('date_to', '>=', target_date),
            ('date_to', '=', False)
        ], limit=1, order='date_from desc')
        return history.shift_period if history else False

    def adjust_overlapping_periods(self):
        """
        Ajusta períodos existentes cuando se registra un cambio manual o excepción.
        Este método se llama cuando se crea o modifica un registro que sobrescribe
        períodos existentes.
        """
        for record in self:
            # Buscar períodos que se solapan con este registro
            overlapping = self.search([
                ('employee_id', '=', record.employee_id.id),
                ('id', '!=', record.id),
                '|',
                # Caso 1: Período que empieza antes o en date_from y termina después o en date_from
                '&', ('date_from', '<=', record.date_from),
                '|', ('date_to', '>=', record.date_from), ('date_to', '=', False),
                # Caso 2: Período dentro del nuevo período (si tiene date_to)
                '&', ('date_from', '>=', record.date_from) if record.date_to else ('date_from', '>', record.date_from),
                '|', ('date_to', '<=', record.date_to) if record.date_to else ('date_to', '=', False),
                ('date_to', '=', False)
            ])
            
            for overlap in overlapping:
                if overlap.date_from < record.date_from:
                    # El período existente empieza antes, cerrarlo antes del inicio del nuevo
                    overlap.write({
                        'date_to': record.date_from - timedelta(days=1),
                        'reason': (overlap.reason or '') + _('\n[Ajustado automáticamente por cambio de turno el %s]') % fields.Date.today()
                    })
                elif record.date_to:
                    if overlap.date_from >= record.date_from and (not overlap.date_to or overlap.date_to <= record.date_to):
                        # El período existente está completamente dentro del nuevo, eliminarlo
                        overlap.unlink()
                    elif overlap.date_from < record.date_to:
                        # El período existente empieza dentro pero termina después, ajustarlo
                        overlap.write({
                            'date_from': record.date_to + timedelta(days=1),
                            'reason': (overlap.reason or '') + _('\n[Ajustado automáticamente por cambio de turno el %s]') % fields.Date.today()
                        })
                else:
                    # El nuevo período no tiene fecha fin, eliminar o ajustar el existente
                    if overlap.date_from >= record.date_from:
                        overlap.unlink()
                    else:
                        overlap.write({
                            'date_to': record.date_from - timedelta(days=1),
                            'reason': (overlap.reason or '') + _('\n[Ajustado automáticamente por cambio de turno el %s]') % fields.Date.today()
                        })

    @api.model
    def create_manual_change(self, employee_id, shift_period, date_from, date_to=None, reason=None):
        """
        Método helper para crear un cambio manual de turno que ajusta automáticamente
        los períodos existentes.
        
        :param employee_id: ID del empleado
        :param shift_period: 'dia' o 'noche'
        :param date_from: Fecha de inicio del nuevo turno
        :param date_to: Fecha de fin (opcional, None para turno actual)
        :param reason: Motivo del cambio
        :return: Record creado
        """
        # Desactivar temporalmente la validación de solapamiento
        record = self.with_context(skip_overlap_check=True, from_manual_change=True, create_exception_mode=False).create({
            'employee_id': employee_id,
            'shift_period': shift_period,
            'date_from': date_from,
            'date_to': date_to,
            'reason': reason or _('Cambio manual de turno'),
            'changed_by': self.env.user.id
        })
        
        # Ajustar períodos solapados
        record.adjust_overlapping_periods()
        
        # Actualizar el empleado
        if not date_to:
            employee = self.env['hr.employee'].browse(employee_id)
            employee.write({
                'current_shift_period': shift_period,
                'last_shift_change': date_from
            })
            employee.shift_history_ids.invalidate_recordset(['is_current'])
            employee.shift_history_ids._compute_is_current()
            employee.invalidate_recordset(['current_shift_period'])
            employee._compute_current_shift_period()
        
        return record

    def action_open_exception_form(self):
        """Acción para crear una excepción de turno desde la interfaz"""
        employee_id = self.employee_id.id if hasattr(self, 'employee_id') and self.employee_id else self.env.context.get('default_employee_id', False)
        return {
            'name': _('Registrar Excepción de Turno'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.shift.history',
            'view_mode': 'form',
            'view_id': False,
            'target': 'new',
            'context': {
                'default_employee_id': employee_id,
                'default_date_from': fields.Date.today(),
                'create_exception_mode': True
            }
        }
    
    def action_confirm_exception(self):
        """Confirmar y guardar la excepción"""
        self.ensure_one()
        if not self.employee_id or not self.shift_period or not self.date_from:
            raise ValidationError(_('Debe completar todos los campos requeridos.'))
        
        # Crear la excepción usando create_manual_change
        self.env['hr.employee.shift.history'].create_manual_change(
            self.employee_id.id,
            self.shift_period,
            self.date_from,
            self.date_to,
            self.reason or _('Excepción de turno registrada manualmente')
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Excepción Registrada'),
                'message': _('La excepción de turno se ha registrado exitosamente.'),
                'type': 'success',
                'sticky': False,
            },
            'context': {'reload': True}
        }
