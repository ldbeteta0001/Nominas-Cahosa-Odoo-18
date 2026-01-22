# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, time
import logging
import pytz

_logger = logging.getLogger(__name__)


class HrExtraHoursRequest(models.Model):
    _name = 'hr.extra.hours.request'
    _description = 'Solicitud de Horas Extra'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Nuevo')
    )
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        tracking=True,
        index=True
    )
    
    attendance_id = fields.Many2one(
        'hr.attendance',
        string='Registro de Asistencia',
        readonly=True,
        help='Registro de asistencia que generó esta solicitud'
    )
    
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    check_in = fields.Datetime(
        string='Hora de Entrada',
        required=True,
        tracking=True
    )
    
    check_out = fields.Datetime(
        string='Hora de Salida',
        tracking=True
    )
    
    type = fields.Selection([
        ('early', 'Entrada Anticipada'),
        ('late', 'Salida Tardía'),
        ('both', 'Entrada Anticipada y Salida Tardía')
    ], string='Tipo', required=True, tracking=True)
    
    duration_hours = fields.Float(
        string='Duración (Horas)',
        compute='_compute_duration_hours',
        store=True,
        help='Duración calculada automáticamente'
    )
    
    payable_hours = fields.Float(
        string='Horas Pagables',
        compute='_compute_payable_hours',
        store=True,
        readonly=False,
        tracking=True,
        help='Horas que serán pagadas (modificable por el jefe) - por defecto es la suma de horas extra'
    )
    
    hours_25 = fields.Float(
        string='Horas 25%',
        default=0.0,
        tracking=True,
        help='Horas extra con recargo del 25%'
    )
    
    hours_50 = fields.Float(
        string='Horas 50%',
        default=0.0,
        tracking=True,
        help='Horas extra con recargo del 50%'
    )
    
    hours_75 = fields.Float(
        string='Horas 75%',
        default=0.0,
        tracking=True,
        help='Horas extra con recargo del 75%'
    )
    
    hours_normal = fields.Float(
        string='Horas Normales',
        compute='_compute_hours_normal',
        store=True,
        help='Horas trabajadas en horario normal (sin recargo) - calculado según horario del empleado'
    )
    
    validated_overtime_hours = fields.Float(
        string='Horas Extra Validadas',
        compute='_compute_validated_overtime_hours',
        store=True,
        help='Horas extra validadas (solo horas extra, no incluye horas normales) - calculado como payable_hours'
    )
    
    overtime_hours = fields.Float(
        string='Horas Extra',
        compute='_compute_overtime_hours',
        store=True,
        help='Horas extra (solo horas extra, no incluye horas normales) - calculado como payable_hours'
    )
    
    expected_check_in = fields.Datetime(
        string='Entrada Esperada',
        compute='_compute_expected_schedule',
        store=True,
        help='Hora de entrada esperada según el horario del empleado'
    )
    
    expected_check_out = fields.Datetime(
        string='Salida Esperada',
        compute='_compute_expected_schedule',
        store=True,
        help='Hora de salida esperada según el horario del empleado'
    )
    
    reason_id = fields.Many2one(
        'hr.extra.hours.reason',
        string='Motivo',
        required=True,
        tracking=True
    )
    
    justification = fields.Text(
        string='Justificación',
        required=True,
        tracking=True,
        help='Justificación detallada de las horas extra'
    )
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('to_approve', 'Por Aprobar'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada')
    ], string='Estado', default='draft', tracking=True, index=True)
    
    manager_id = fields.Many2one(
        'hr.employee',
        string='Jefe Inmediato',
        compute='_compute_manager_id',
        store=True,
        help='Jefe inmediato que debe aprobar la solicitud'
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Aprobado por',
        readonly=True,
        tracking=True
    )
    
    approved_date = fields.Datetime(
        string='Fecha de Aprobación',
        readonly=True,
        tracking=True
    )
    
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        readonly=True,
        tracking=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        related='employee_id.company_id',
        store=True,
        readonly=True
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Departamento',
        related='employee_id.department_id',
        store=True,
        readonly=True
    )
    
    # Campos calculados para reportes
    month = fields.Char(
        string='Mes',
        compute='_compute_month',
        store=True,
        help='Mes para agrupación en reportes'
    )
    
    year = fields.Integer(
        string='Año',
        compute='_compute_year',
        store=True,
        help='Año para agrupación en reportes'
    )

    @api.depends('check_in', 'check_out')
    def _compute_duration_hours(self):
        for record in self:
            if record.check_in and record.check_out:
                duration = record.check_out - record.check_in
                record.duration_hours = duration.total_seconds() / 3600
            else:
                record.duration_hours = 0.0
    
    @api.depends('employee_id', 'date', 'check_in', 'check_out')
    def _compute_expected_schedule(self):
        """Calcular horario esperado según el calendario del empleado"""
        for record in self:
            if not record.employee_id or not record.date or not record.check_in:
                record.expected_check_in = False
                record.expected_check_out = False
                continue
            
            # Obtener calendario del empleado
            calendar = record._get_employee_calendar()
            if not calendar:
                record.expected_check_in = False
                record.expected_check_out = False
                continue
            
            # Obtener horario para el día de la semana
            weekday = record.check_in.weekday()
            attendances = calendar.attendance_ids.filtered(
                lambda x: x.dayofweek == str(weekday)
            )
            
            if not attendances:
                record.expected_check_in = False
                record.expected_check_out = False
                continue
            
            # Convertir hour_from y hour_to (float) a objetos time
            def float_to_time(hour_float):
                """Convierte un float de horas a un objeto time"""
                hours = int(hour_float)
                minutes = int((hour_float - hours) * 60)
                return time(hours, minutes)
            
            date_obj = record.date
            
            # Obtener el primer check_in (del primer período) y el último check_out (del último período)
            first_attendance = attendances[0]
            last_attendance = attendances[-1]
            
            # Crear datetime en zona horaria local (sin timezone info)
            # Usar la zona horaria del usuario para crear el datetime correctamente
            expected_check_in_naive = datetime.combine(date_obj, float_to_time(first_attendance.hour_from))
            expected_check_out_naive = datetime.combine(date_obj, float_to_time(last_attendance.hour_to))
            
            # Convertir a zona horaria local del usuario
            # Primero localizar en la zona horaria del usuario, luego quitar timezone info
            user_tz_name = record.env.user.tz or (record.employee_id.user_id.tz if record.employee_id and record.employee_id.user_id else None) or 'America/Tegucigalpa'
            user_tz = pytz.timezone(user_tz_name)
            
            # Localizar el datetime naive en la zona horaria del usuario
            expected_check_in_local = user_tz.localize(expected_check_in_naive)
            expected_check_out_local = user_tz.localize(expected_check_out_naive)
            
            # Convertir a UTC para almacenar en la base de datos (Odoo almacena en UTC)
            expected_check_in_utc = expected_check_in_local.astimezone(pytz.UTC).replace(tzinfo=None)
            expected_check_out_utc = expected_check_out_local.astimezone(pytz.UTC).replace(tzinfo=None)
            
            record.expected_check_in = expected_check_in_utc
            record.expected_check_out = expected_check_out_utc
    
    def _convert_to_local_timezone(self, dt):
        """Convertir datetime de UTC a zona horaria local del usuario"""
        if not dt:
            return dt
        
        # Obtener zona horaria del usuario o usar la del empleado
        user_tz_name = self.env.user.tz or (self.employee_id.user_id.tz if self.employee_id and self.employee_id.user_id else None) or 'America/Tegucigalpa'
        user_tz = pytz.timezone(user_tz_name)
        
        # Si el datetime no tiene timezone, asumir que es UTC (como Odoo lo almacena)
        if dt.tzinfo is None:
            dt_utc = pytz.UTC.localize(dt)
        else:
            dt_utc = dt
        
        # Convertir a zona horaria local y quitar timezone info
        dt_local = dt_utc.astimezone(user_tz).replace(tzinfo=None)
        return dt_local
    
    def _get_employee_calendar(self):
        """Obtener calendario laboral del empleado"""
        if not self.employee_id:
            return False
        
        # Buscar calendario en el contrato activo
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
            ('date_start', '<=', self.date),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', self.date)
        ], limit=1)
        
        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id
        
        # Si no hay contrato, usar calendario por defecto de la compañía
        return self.employee_id.company_id.resource_calendar_id
    
    @api.depends('check_in', 'check_out', 'expected_check_in', 'expected_check_out')
    def _compute_hours_normal(self):
        """
        Calcular horas normales (100%) basándose en el horario esperado del empleado
        Las horas normales son las horas trabajadas dentro del horario laboral esperado
        Considera todos los períodos del día (mañana, tarde, etc.)
        """
        for record in self:
            if not record.check_in or not record.check_out:
                record.hours_normal = 0.0
                continue
            
            # Obtener calendario del empleado
            calendar = record._get_employee_calendar()
            if not calendar:
                _logger.warning('No se encontró calendario para empleado %s', record.employee_id.name if record.employee_id else 'N/A')
                record.hours_normal = 0.0
                continue
            
            # Obtener todos los períodos del día
            weekday = record.check_in.weekday()
            attendances = calendar.attendance_ids.filtered(
                lambda x: x.dayofweek == str(weekday)
            )
            
            if not attendances:
                _logger.warning('No se encontraron períodos de asistencia para el día %s (weekday=%s)', record.date, weekday)
                record.hours_normal = 0.0
                continue
            
            # Convertir hour_from y hour_to (float) a objetos time
            def float_to_time(hour_float):
                """Convierte un float de horas a un objeto time"""
                hours = int(hour_float)
                minutes = int((hour_float - hours) * 60)
                return time(hours, minutes)
            
            # Usar la fecha del campo date si está disponible, sino usar la fecha del check_in
            if record.date:
                date_obj = record.date
            else:
                date_obj = record.check_in.date() if record.check_in else fields.Date.today()
            
            total_normal_hours = 0.0
            
            _logger.info('=== DEBUG: Cálculo de horas normales ===')
            _logger.info('Empleado: %s', record.employee_id.name if record.employee_id else 'N/A')
            _logger.info('Fecha: %s (del campo date: %s)', date_obj, record.date)
            _logger.info('Check-in: %s, Check-out: %s', record.check_in, record.check_out)
            _logger.info('Períodos encontrados: %d', len(attendances))
            
            # Calcular horas normales para cada período del día
            # Si el check-in es después del inicio del primer período pero el check-out es después del fin del último período,
            # se consideran todos los períodos completos que están entre el check-in y check-out
            first_period_start = None
            last_period_end = None
            
            # Obtener el primer y último período
            if attendances:
                first_attendance = attendances[0]
                last_attendance = attendances[-1]
                first_period_start = datetime.combine(date_obj, float_to_time(first_attendance.hour_from))
                last_period_end = datetime.combine(date_obj, float_to_time(last_attendance.hour_to))
            
            _logger.info('Primer período inicia: %s, Último período termina: %s', first_period_start, last_period_end)
            
            for idx, attendance in enumerate(attendances):
                period_start = datetime.combine(date_obj, float_to_time(attendance.hour_from))
                period_end = datetime.combine(date_obj, float_to_time(attendance.hour_to))
                
                _logger.info('Período %d: %s - %s (hour_from=%.2f, hour_to=%.2f)', 
                           idx + 1, period_start, period_end, attendance.hour_from, attendance.hour_to)
                
                # Calcular intersección entre horas trabajadas y este período
                normal_start = max(record.check_in, period_start)
                normal_end = min(record.check_out, period_end)
                
                _logger.info('  Intersección calculada: %s - %s', normal_start, normal_end)
                _logger.info('  Comparación: check_in=%s, period_start=%s, max=%s', 
                           record.check_in, period_start, normal_start)
                _logger.info('  Comparación: check_out=%s, period_end=%s, min=%s', 
                           record.check_out, period_end, normal_end)
                
                # Si hay intersección directa, sumar las horas
                if normal_start < normal_end:
                    duration = normal_end - normal_start
                    period_hours = duration.total_seconds() / 3600
                    total_normal_hours += period_hours
                    _logger.info('  ✓ Horas normales en este período (intersección directa): %.2f', period_hours)
                else:
                    # Si no hay intersección directa, verificar casos especiales:
                    # Si el check-out es después del fin del último período, contar TODOS los períodos completos del día
                    # (asumiendo que si el check-out es después del último período, el empleado trabajó todos los períodos del día)
                    if record.check_out > last_period_end:
                        # El check-out es después del último período, contar este período completo
                        if period_start < period_end:
                            # El período está completamente antes del check-out, contarlo completo
                            duration = period_end - period_start
                            period_hours = duration.total_seconds() / 3600
                            total_normal_hours += period_hours
                            _logger.info('  ✓ Período completo contado (check-out después del último período): %.2f', period_hours)
                        else:
                            _logger.info('  ✗ Período inválido')
                    elif record.check_in <= period_start and record.check_out >= period_end:
                        # El período está completamente dentro del rango trabajado
                        duration = period_end - period_start
                        period_hours = duration.total_seconds() / 3600
                        total_normal_hours += period_hours
                        _logger.info('  ✓ Período completo contado (check-in antes, check-out después): %.2f', period_hours)
                    else:
                        _logger.info('  ✗ No hay intersección (normal_start >= normal_end)')
            
            _logger.info('=== Total horas normales calculadas: %.2f ===', total_normal_hours)
            record.hours_normal = total_normal_hours
    
    @api.depends('hours_25', 'hours_50', 'hours_75')
    def _compute_payable_hours(self):
        """
        Calcular horas pagables como la suma de horas extra
        El aprobador puede modificar este valor manualmente
        """
        for record in self:
            # Si el campo ya tiene un valor y fue modificado manualmente, no lo sobrescribimos
            # Pero si es la primera vez o las horas extra cambiaron, actualizamos
            total_extra = record.hours_25 + record.hours_50 + record.hours_75
            # Solo actualizar si no hay valor o si el valor actual es diferente al calculado
            # (esto permite que el aprobador modifique manualmente)
            if not record.payable_hours or record.payable_hours == 0.0:
                record.payable_hours = total_extra
    
    @api.depends('payable_hours', 'state')
    def _compute_validated_overtime_hours(self):
        """
        Calcular horas extra validadas usando payable_hours (solo horas extra, no incluye horas normales)
        Este campo corrige el cálculo incorrecto de duration_hours - hours_normal
        """
        for record in self:
            # Usar payable_hours que es la suma correcta de hours_25 + hours_50 + hours_75
            # Solo cuando está aprobada
            if record.state == 'approved':
                record.validated_overtime_hours = record.payable_hours
            else:
                record.validated_overtime_hours = 0.0
    
    @api.depends('payable_hours')
    def _compute_overtime_hours(self):
        """
        Calcular horas extra usando payable_hours (solo horas extra, no incluye horas normales)
        Este campo corrige el cálculo incorrecto de duration_hours - hours_normal
        """
        for record in self:
            # Usar payable_hours que es la suma correcta de hours_25 + hours_50 + hours_75
            record.overtime_hours = record.payable_hours

    @api.depends('employee_id.parent_id')
    def _compute_manager_id(self):
        for record in self:
            if record.employee_id and record.employee_id.parent_id:
                record.manager_id = record.employee_id.parent_id
            else:
                record.manager_id = False

    @api.depends('date')
    def _compute_month(self):
        for record in self:
            if record.date:
                record.month = record.date.strftime('%Y-%m')
            else:
                record.month = False

    @api.depends('date')
    def _compute_year(self):
        for record in self:
            if record.date:
                record.year = record.date.year
            else:
                record.year = False

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.extra.hours.request') or _('Nuevo')
        
        # Si no se especifican horas por rangos, calcularlas
        if vals.get('check_in') and vals.get('check_out') and not vals.get('hours_25') and not vals.get('hours_50') and not vals.get('hours_75'):
            check_in = fields.Datetime.from_string(vals['check_in'])
            check_out = fields.Datetime.from_string(vals['check_out'])
            
            # Obtener empleado para calcular horario esperado
            employee_id = vals.get('employee_id')
            if employee_id:
                employee = self.env['hr.employee'].browse(employee_id)
                # Calcular horas por rangos basándose en el horario del empleado
                hours_25, hours_50, hours_75 = self._calculate_overtime_hours_for_request(
                    employee, check_in, check_out, vals.get('date')
                )
                vals['hours_25'] = hours_25
                vals['hours_50'] = hours_50
                vals['hours_75'] = hours_75
        
        # Si no se especifican horas pagables, usar solo las horas extra
        if not vals.get('payable_hours'):
            total_extra = (vals.get('hours_25', 0.0) + 
                          vals.get('hours_50', 0.0) + 
                          vals.get('hours_75', 0.0))
            vals['payable_hours'] = total_extra if total_extra > 0 else 0.0
        
        return super(HrExtraHoursRequest, self).create(vals)
    
    def _calculate_overtime_hours_for_request(self, employee, check_in, check_out, date):
        """
        Calcular horas extra por rangos para una solicitud manual
        Retorna: (hours_25, hours_50, hours_75)
        """
        # Convertir date a objeto date si es string
        if isinstance(date, str):
            date = fields.Date.from_string(date)
        elif date is None:
            date = check_in.date() if hasattr(check_in, 'date') else fields.Date.today()
        
        # Obtener calendario del empleado
        calendar = self._get_calendar_for_employee(employee, date)
        if not calendar:
            # Si no hay calendario, retornar todo como horas extra
            duration = (check_out - check_in).total_seconds() / 3600
            return (duration, 0.0, 0.0)
        
        # Obtener horario esperado
        weekday = check_in.weekday()
        attendances = calendar.attendance_ids.filtered(
            lambda x: x.dayofweek == str(weekday)
        )
        
        if not attendances:
            duration = (check_out - check_in).total_seconds() / 3600
            return (duration, 0.0, 0.0)
        
        attendance = attendances[0]
        date_obj = check_in.date() if hasattr(check_in, 'date') else date
        
        def float_to_time(hour_float):
            hours = int(hour_float)
            minutes = int((hour_float - hours) * 60)
            return time(hours, minutes)
        
        expected_check_in = datetime.combine(date_obj, float_to_time(attendance.hour_from))
        expected_check_out = datetime.combine(date_obj, float_to_time(attendance.hour_to))
        
        # Determinar qué horas son extra
        if check_in < expected_check_in:
            # Entrada anticipada
            start_time = check_in
            end_time = min(check_out, expected_check_in)
        elif check_out > expected_check_out:
            # Salida tardía
            start_time = max(check_in, expected_check_out)
            end_time = check_out
        else:
            # No hay horas extra
            return (0.0, 0.0, 0.0)
        
        # Calcular horas por rangos
        return self._calculate_overtime_hours_by_ranges(start_time, end_time)
    
    def _get_calendar_for_employee(self, employee, date):
        """Obtener calendario laboral del empleado para una fecha"""
        if not employee:
            return False
        
        # Convertir date a objeto date si es string
        if isinstance(date, str):
            date = fields.Date.from_string(date)
        elif date is None:
            date = fields.Date.today()
        
        # Buscar calendario en el contrato activo
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open'),
            ('date_start', '<=', date),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date)
        ], limit=1)
        
        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id
        
        # Si no hay contrato, usar calendario por defecto de la compañía
        return employee.company_id.resource_calendar_id
    
    def _calculate_overtime_hours_by_ranges(self, start_time, end_time):
        """
        Calcular horas extra según los rangos configurados (25%, 50%, 75%)
        Solo calcula las horas entre start_time y end_time, distribuyéndolas según los rangos
        Retorna: (hours_25, hours_50, hours_75)
        """
        # Obtener configuración activa de horas extra
        try:
            config = self.env['config.overtime.hours'].search([
                ('state', '=', 'active')
            ], limit=1)
        except Exception:
            # Si el modelo no existe (módulo no instalado), retornar todo como horas normales
            total_hours = (end_time - start_time).total_seconds() / 3600
            return (total_hours, 0.0, 0.0)
        
        if not config:
            # Si no hay configuración, retornar todo como horas normales
            total_hours = (end_time - start_time).total_seconds() / 3600
            return (total_hours, 0.0, 0.0)
        
        # Convertir valores de configuración a horas y minutos
        def parse_hour(hour_str):
            """Convierte '8.5' a (8, 30) o '8' a (8, 0)"""
            hour_float = float(hour_str)
            hour_int = int(hour_float)
            minute_int = int((hour_float - hour_int) * 60)
            return hour_int, minute_int
        
        hour_25_from_h, hour_25_from_m = parse_hour(config.hour_25_from)
        hour_25_to_h, hour_25_to_m = parse_hour(config.hour_25_to)
        hour_50_from_h, hour_50_from_m = parse_hour(config.hour_50_from)
        hour_50_to_h, hour_50_to_m = parse_hour(config.hour_50_to)
        hour_75_from_h, hour_75_from_m = parse_hour(config.hour_75_from)
        hour_75_to_h, hour_75_to_m = parse_hour(config.hour_75_to)
        
        # Inicializar contadores
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        
        # Calcular horas en cada rango, considerando que end_time puede ser del día siguiente
        current_time = start_time
        while current_time < end_time:
            # Obtener la fecha del current_time para crear los rangos del día correspondiente
            current_date = current_time.date()
            
            # Crear objetos datetime para los rangos del día actual
            start_25 = datetime.combine(current_date, time(hour_25_from_h, hour_25_from_m))
            end_25 = datetime.combine(current_date, time(hour_25_to_h, hour_25_to_m))
            start_50 = datetime.combine(current_date, time(hour_50_from_h, hour_50_from_m))
            end_50 = datetime.combine(current_date, time(hour_50_to_h, hour_50_to_m))
            start_75 = datetime.combine(current_date, time(hour_75_from_h, hour_75_from_m))
            end_75 = datetime.combine(current_date, time(hour_75_to_h, hour_75_to_m))
            
            # Si el rango cruza medianoche, ajustar end_75 al día siguiente
            if hour_75_to_h < hour_75_from_h or (hour_75_to_h == hour_75_from_h and hour_75_to_m < hour_75_from_m):
                end_75 = datetime.combine(current_date + timedelta(days=1), time(hour_75_to_h, hour_75_to_m))
            
            # Determinar qué rango aplica al current_time y calcular hasta el límite
            if start_25 <= current_time < end_25:
                # Está en el rango del 25%
                next_time = min(end_time, end_25)
                hours_25 += (next_time - current_time).total_seconds() / 3600
                current_time = next_time
            elif start_50 <= current_time < end_50:
                # Está en el rango del 50%
                next_time = min(end_time, end_50)
                hours_50 += (next_time - current_time).total_seconds() / 3600
                current_time = next_time
            elif start_75 <= current_time < end_75:
                # Está en el rango del 75%
                next_time = min(end_time, end_75)
                hours_75 += (next_time - current_time).total_seconds() / 3600
                current_time = next_time
            else:
                # current_time no está en ningún rango configurado
                # Buscar el siguiente punto de cambio (inicio de algún rango o end_time)
                # IMPORTANTE: Solo considerar rangos del mismo día que current_time, o del día siguiente si end_time es del día siguiente
                next_times = []
                end_time_date = end_time.date()
                
                # Solo agregar rangos que estén antes de end_time y en el mismo día o día siguiente si end_time es del día siguiente
                if start_25 > current_time and start_25 <= end_time:
                    # Verificar que el rango esté en el mismo día que current_time o en el día siguiente si end_time es del día siguiente
                    start_25_date = start_25.date()
                    if start_25_date == current_date or (start_25_date == current_date + timedelta(days=1) and end_time_date > current_date):
                        next_times.append(start_25)
                if start_50 > current_time and start_50 <= end_time:
                    start_50_date = start_50.date()
                    if start_50_date == current_date or (start_50_date == current_date + timedelta(days=1) and end_time_date > current_date):
                        next_times.append(start_50)
                if start_75 > current_time and start_75 <= end_time:
                    start_75_date = start_75.date()
                    if start_75_date == current_date or (start_75_date == current_date + timedelta(days=1) and end_time_date > current_date):
                        next_times.append(start_75)
                next_times.append(end_time)
                
                if next_times:
                    # Avanzar al siguiente punto de cambio, pero no más allá de end_time
                    next_time = min(next_times)
                    if next_time >= end_time:
                        # Si el siguiente punto está en o después de end_time, terminar
                        break
                    current_time = next_time
                else:
                    # No hay más rangos, terminar
                    break
        
        return (hours_25, hours_50, hours_75)

    def action_submit(self):
        """Enviar solicitud para aprobación"""
        for record in self:
            if not record.manager_id:
                raise UserError(_('No se puede enviar la solicitud: el empleado no tiene jefe asignado.'))
            
            record.state = 'to_approve'
            
            # Crear actividad para el jefe
            record.activity_schedule(
                'hr_extra_hours_request.mail_activity_approve_extra_hours',
                user_id=record.manager_id.user_id.id if record.manager_id.user_id else False,
                summary=_('Solicitud de Horas Extra Pendiente'),
                note=_('El empleado %s ha solicitado %s horas extra para el %s. Motivo: %s') % (
                    record.employee_id.name,
                    record.payable_hours,
                    record.date,
                    record.reason_id.name
                )
            )

    def action_approve(self):
        """Aprobar solicitud"""
        for record in self:
            if not self.env.user.has_group('hr_extra_hours_request.group_hr_extra_hours_manager'):
                raise UserError(_('No tiene permisos para aprobar solicitudes de horas extra.'))
            
            record.state = 'approved'
            record.approved_by = self.env.user
            record.approved_date = fields.Datetime.now()

    def action_reject(self):
        """Rechazar solicitud"""
        for record in self:
            if not self.env.user.has_group('hr_extra_hours_request.group_hr_extra_hours_manager'):
                raise UserError(_('No tiene permisos para rechazar solicitudes de horas extra.'))
            
            return {
                'name': _('Rechazar Solicitud'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.extra.hours.rejection.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_request_id': record.id}
            }

    def action_reject_confirm(self, rejection_reason):
        """Confirmar rechazo con motivo"""
        for record in self:
            record.state = 'rejected'
            record.rejection_reason = rejection_reason
            record.approved_by = self.env.user
            record.approved_date = fields.Datetime.now()

    def action_reset_to_draft(self):
        """Resetear a borrador"""
        for record in self:
            record.state = 'draft'
            record.approved_by = False
            record.approved_date = False
            record.rejection_reason = False

    def action_view_attendance(self):
        """Ver registro de asistencia relacionado"""
        self.ensure_one()
        if not self.attendance_id:
            raise UserError(_('No hay registro de asistencia asociado a esta solicitud.'))
        
        return {
            'name': _('Registro de Asistencia'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'res_id': self.attendance_id.id,
            'view_mode': 'form',
            'target': 'new'
        }

    @api.model
    def _cron_cleanup_old_requests(self):
        """Limpieza automática de solicitudes antiguas (opcional)"""
        # Eliminar solicitudes rechazadas de más de 1 año
        cutoff_date = fields.Date.today() - timedelta(days=365)
        old_rejected = self.search([
            ('state', '=', 'rejected'),
            ('date', '<', cutoff_date)
        ])
        old_rejected.unlink()
        
        _logger.info('Limpieza automática: %d solicitudes antiguas eliminadas', len(old_rejected))

    @api.constrains('check_in', 'check_out')
    def _check_dates(self):
        for record in self:
            if record.check_in and record.check_out and record.check_out <= record.check_in:
                raise ValidationError(_('La hora de salida debe ser posterior a la hora de entrada.'))

    @api.constrains('payable_hours')
    def _check_payable_hours(self):
        for record in self:
            if record.payable_hours < 0:
                raise ValidationError(_('Las horas pagables no pueden ser negativas.'))


class HrExtraHoursReason(models.Model):
    _name = 'hr.extra.hours.reason'
    _description = 'Motivos de Horas Extra'
    _order = 'sequence, name'

    name = fields.Char(
        string='Motivo',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Código',
        required=True,
        help='Código único para el motivo'
    )
    
    sequence = fields.Integer(
        string='Secuencia',
        default=10
    )
    
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    
    description = fields.Text(
        string='Descripción',
        help='Descripción detallada del motivo'
    )

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'El código del motivo debe ser único!')
    ]
