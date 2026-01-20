# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class BiometricAttendance(models.Model):
    _name = 'biometric.attendance'
    _description = 'Registro de Asistencia Biométrica'
    _order = 'punch_time desc'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True,
        ondelete='cascade'
    )
    
    employee_biometric_id = fields.Integer(
        string='ID Biométrico del Empleado',
        required=True,
        help='ID del empleado en el dispositivo biométrico'
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        compute='_compute_employee_id',
        store=True,
        help='Empleado asociado basado en el ID biométrico'
    )
    
    punch_time = fields.Datetime(
        string='Fecha y Hora del Registro',
        required=True,
        help='Fecha y hora del registro en el dispositivo biométrico'
    )
    
    punch_state = fields.Selection([
        ('check_in', 'Entrada'),
        ('check_out', 'Salida'),
    ], string='Tipo de Registro', required=True)
    
    status = fields.Integer(
        string='Estado',
        help='Estado del registro en el dispositivo'
    )
    
    verify_mode = fields.Integer(
        string='Modo de Verificación',
        help='Modo de verificación usado (huella, tarjeta, etc.)'
    )
    
    # Relación con hr.attendance
    attendance_id = fields.Many2one(
        'hr.attendance',
        string='Registro de Asistencia',
        readonly=True,
        help='Registro de asistencia creado en Odoo'
    )
    
    is_synced = fields.Boolean(
        string='Sincronizado',
        default=False,
        help='Indica si este registro ya fue sincronizado a hr.attendance'
    )
    
    sync_date = fields.Datetime(
        string='Fecha de Sincronización',
        readonly=True,
        help='Fecha y hora en que se sincronizó este registro'
    )
    
    @api.depends('employee_biometric_id')
    def _compute_employee_id(self):
        """Buscar el empleado basado en el ID biométrico"""
        for record in self:
            employee = self.env['hr.employee'].search([
                ('biometric_user_id', '=', record.employee_biometric_id)
            ], limit=1)
            record.employee_id = employee.id if employee else False
    
    def create_attendance_record(self):
        """Crear registro en hr.attendance basado en este registro biométrico"""
        self.ensure_one()
        
        if not self.employee_id:
            raise UserError(_('No se encontró un empleado asociado al ID biométrico %s') % self.employee_biometric_id)
        
        if self.is_synced and self.attendance_id:
            raise UserError(_('Este registro ya fue sincronizado anteriormente'))
        
        # Buscar cualquier registro previo sin check_out (sin restricción de fecha)
        # Odoo no permite crear un nuevo check_in si hay un registro previo sin check_out
        open_attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_out', '=', False),
        ], order='check_in desc', limit=1)
        
        # Si hay un registro abierto previo, cerrarlo primero
        if open_attendance:
            # Si el nuevo registro es posterior al check_in anterior, usar el nuevo tiempo como check_out
            # Si es anterior, usar el check_in anterior como check_out (mínimo 1 segundo después)
            if self.punch_time > open_attendance.check_in:
                check_out_time = self.punch_time - timedelta(seconds=1)
            else:
                # Si el nuevo registro es anterior, cerrar con el check_in anterior
                check_out_time = open_attendance.check_in + timedelta(seconds=1)
            
            # Asegurar que check_out sea al menos 1 segundo después de check_in
            if check_out_time <= open_attendance.check_in:
                check_out_time = open_attendance.check_in + timedelta(seconds=1)
            
            _logger.warning(
                "Cerrando registro de asistencia previo sin salida para %s. "
                "Check_in: %s, Check_out: %s",
                self.employee_id.name,
                open_attendance.check_in,
                check_out_time
            )
            
            open_attendance.write({
                'check_out': check_out_time,
            })
            # Forzar flush para asegurar que el cambio se persista antes de crear nuevo registro
            self.env.flush_all()
        
        # Verificar nuevamente que no haya registros abiertos después de cerrar el anterior
        remaining_open = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_out', '=', False),
        ], limit=1)
        
        if remaining_open:
            # Si encontramos un registro abierto (puede ser el mismo que cerramos si no se guardó, u otro)
            if not open_attendance or remaining_open.id != open_attendance.id:
                _logger.warning(
                    "Aún existe registro abierto después de cerrar el anterior para %s. "
                    "Cerrando registro adicional con ID %s. Check_in: %s",
                    self.employee_id.name,
                    remaining_open.id,
                    remaining_open.check_in
                )
                check_out_time_remaining = self.punch_time - timedelta(seconds=1) if self.punch_time > remaining_open.check_in else remaining_open.check_in + timedelta(seconds=1)
                if check_out_time_remaining <= remaining_open.check_in:
                    check_out_time_remaining = remaining_open.check_in + timedelta(seconds=1)
                remaining_open.write({
                    'check_out': check_out_time_remaining
                })
                self.env.flush_all()
        
        # Buscar el último registro de asistencia del empleado para el mismo día
        date_start = self.punch_time.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start.replace(hour=23, minute=59, second=59)
        
        last_attendance = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end),
        ], order='check_in desc', limit=1)
        
        attendance_vals = {
            'employee_id': self.employee_id.id,
            'biometric_device_id': self.device_id.id,
            'biometric_punch_time': self.punch_time,
            'is_biometric': True,
        }
        
        if not last_attendance or last_attendance.check_out:
            # No hay registro del día o ya tiene check_out, crear nuevo check_in
            attendance_vals['check_in'] = self.punch_time
            attendance = self.env['hr.attendance'].create(attendance_vals)
            self.write({
                'attendance_id': attendance.id,
                'is_synced': True,
                'sync_date': fields.Datetime.now(),
                'punch_state': 'check_in'
            })
        else:
            # Ya hay check_in sin check_out, actualizar con check_out
            if last_attendance.check_in > self.punch_time:
                # El check_out es anterior al check_in, crear nuevo registro
                attendance_vals['check_in'] = self.punch_time
                attendance = self.env['hr.attendance'].create(attendance_vals)
            else:
                # Actualizar el registro existente con check_out
                last_attendance.write({
                    'check_out': self.punch_time,
                    'biometric_punch_time': self.punch_time,
                    'is_biometric': True,
                })
                attendance = last_attendance
            
            self.write({
                'attendance_id': attendance.id,
                'is_synced': True,
                'sync_date': fields.Datetime.now(),
                'punch_state': 'check_out'
            })
        
        return attendance

