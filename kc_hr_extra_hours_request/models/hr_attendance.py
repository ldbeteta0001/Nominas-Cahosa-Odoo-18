# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, time
import logging
import pytz

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    extra_hours_request_id = fields.One2many(
        'hr.extra.hours.request',
        'attendance_id',
        string='Solicitud de Horas Extra',
        readonly=True
    )
    
    has_extra_hours_request = fields.Boolean(
        string='Tiene Solicitud de Horas Extra',
        compute='_compute_has_extra_hours_request',
        store=True
    )
    
    # Campo Many2one para acceder fácilmente a la solicitud de horas extra
    extra_hours_request = fields.Many2one(
        'hr.extra.hours.request',
        string='Solicitud de Horas Extra',
        compute='_compute_extra_hours_request',
        store=False,
        readonly=True,
        help='Solicitud de horas extra asociada a esta asistencia'
    )
    
    # Campos relacionados desde la solicitud de horas extra
    hours_normal = fields.Float(
        string='Horas Normales',
        related='extra_hours_request.hours_normal',
        readonly=True,
        store=False,
        help='Horas trabajadas en horario normal'
    )
    
    hours_25 = fields.Float(
        string='Horas 25%',
        related='extra_hours_request.hours_25',
        readonly=True,
        store=False,
        help='Horas extra con recargo del 25%'
    )
    
    hours_50 = fields.Float(
        string='Horas 50%',
        related='extra_hours_request.hours_50',
        readonly=True,
        store=False,
        help='Horas extra con recargo del 50%'
    )
    
    hours_75 = fields.Float(
        string='Horas 75%',
        related='extra_hours_request.hours_75',
        readonly=True,
        store=False,
        help='Horas extra con recargo del 75%'
    )
    
    payable_hours = fields.Float(
        string='Horas Pagables',
        related='extra_hours_request.payable_hours',
        readonly=True,
        store=False,
        help='Horas que serán pagadas'
    )
    
    total_extra_hours = fields.Float(
        string='Total Horas Extra',
        compute='_compute_total_extra_hours',
        store=False,
        help='Suma total de horas extra (25% + 50% + 75%)'
    )

    @api.depends('extra_hours_request_id')
    def _compute_has_extra_hours_request(self):
        for attendance in self:
            try:
                if 'hr.extra.hours.request' in self.env:
                    attendance.has_extra_hours_request = bool(attendance.extra_hours_request_id)
                else:
                    attendance.has_extra_hours_request = False
            except (KeyError, AttributeError):
                attendance.has_extra_hours_request = False
    
    @api.depends('extra_hours_request_id')
    def _compute_extra_hours_request(self):
        """Obtener el primer registro de la solicitud de horas extra"""
        for attendance in self:
            try:
                if 'hr.extra.hours.request' in self.env:
                    attendance.extra_hours_request = attendance.extra_hours_request_id[:1] if attendance.extra_hours_request_id else False
                else:
                    attendance.extra_hours_request = False
            except (KeyError, AttributeError):
                attendance.extra_hours_request = False
    
    @api.depends('hours_25', 'hours_50', 'hours_75')
    def _compute_total_extra_hours(self):
        for attendance in self:
            attendance.total_extra_hours = attendance.hours_25 + attendance.hours_50 + attendance.hours_75

    @api.model
    def create(self, vals):
        """Override create para detectar horas extra automáticamente"""
        attendance = super(HrAttendance, self).create(vals)
        
        # Solo procesar si es un check-out (tiene check_in y check_out)
        if attendance.check_in and attendance.check_out:
            attendance._detect_extra_hours()
        
        return attendance

    def write(self, vals):
        """Override write para detectar horas extra cuando se actualiza"""
        result = super(HrAttendance, self).write(vals)
        
        # Solo procesar si se actualizó check_out
        if 'check_out' in vals:
            for attendance in self:
                if attendance.check_in and attendance.check_out:
                    attendance._detect_extra_hours()
        
        return result

    def _detect_extra_hours(self):
        """Detectar si hay horas extra y crear solicitud automática"""
        self.ensure_one()
        
        # Verificar si el modelo está disponible
        if 'hr.extra.hours.request' not in self.env:
            return
        
        if not self.employee_id or not self.check_in or not self.check_out:
            return
        
        # Verificar si ya existe una solicitud para esta asistencia
        try:
            existing_request = self.env['hr.extra.hours.request'].search([
                ('attendance_id', '=', self.id)
            ], limit=1)
        except (KeyError, AttributeError):
            return
        
        if existing_request:
            return
        
        # Obtener calendario laboral del empleado
        calendar = self._get_employee_calendar()
        if not calendar:
            return
        
        # Calcular horario esperado
        expected_schedule = self._get_expected_schedule(calendar)
        if not expected_schedule:
            return
        
        # Convertir check_in y check_out a zona horaria local
        check_in_local = self._convert_to_local_timezone(self.check_in)
        check_out_local = self._convert_to_local_timezone(self.check_out)
        expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
        expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
        
        # Detectar tipo de horas extra usando valores locales
        early_check_in = check_in_local < expected_check_in_local if expected_check_in_local else False
        late_check_out = check_out_local > expected_check_out_local if expected_check_out_local else False
        
        if early_check_in and late_check_out:
            extra_hours_type = 'both'
        elif early_check_in:
            extra_hours_type = 'early'
        elif late_check_out:
            extra_hours_type = 'late'
        else:
            extra_hours_type = False
        
        if not extra_hours_type:
            return
        
        # Calcular duración de horas extra usando valores locales
        if extra_hours_type == 'early':
            duration = (expected_check_in_local - check_in_local).total_seconds() / 3600
        elif extra_hours_type == 'late':
            duration = (check_out_local - expected_check_out_local).total_seconds() / 3600
        elif extra_hours_type == 'both':
            early_duration = (expected_check_in_local - check_in_local).total_seconds() / 3600
            late_duration = (check_out_local - expected_check_out_local).total_seconds() / 3600
            duration = early_duration + late_duration
        else:
            duration = 0.0
        
        # Aplicar tolerancia
        tolerance_minutes = self.employee_id.extra_hours_tolerance or 15.0
        if duration < (tolerance_minutes / 60.0):
            return
        
        # Calcular horas por rangos (25%, 50%, 75%)
        # NOTA: Los rangos 25%, 50%, 75% solo se aplican a horas DESPUÉS del horario laboral
        # Las horas de entrada anticipada se consideran todas como 25% (o se pueden configurar diferente)
        if extra_hours_type == 'early':
            # Entrada anticipada: todas las horas se consideran al 25% (o se puede configurar)
            start_time = check_in_local
            end_time = expected_check_in_local
            early_duration = (end_time - start_time).total_seconds() / 3600
            hours_25 = early_duration
            hours_50 = 0.0
            hours_75 = 0.0
        elif extra_hours_type == 'late':
            # Salida tardía: aplicar rangos 25%, 50%, 75%
            start_time = expected_check_out_local
            end_time = check_out_local
            hours_25, hours_50, hours_75 = self._calculate_overtime_hours_by_ranges(start_time, end_time)
        else:  # both
            # Para 'both', calcular por separado entrada anticipada y salida tardía
            early_start = check_in_local
            early_end = expected_check_in_local
            late_start = expected_check_out_local
            late_end = check_out_local
            
            # Entrada anticipada: todas al 25%
            early_duration = (early_end - early_start).total_seconds() / 3600
            hours_25_early = early_duration
            hours_50_early = 0.0
            hours_75_early = 0.0
            
            # Salida tardía: aplicar rangos
            hours_25_late, hours_50_late, hours_75_late = self._calculate_overtime_hours_by_ranges(late_start, late_end)
            
            hours_25 = hours_25_early + hours_25_late
            hours_50 = hours_50_early + hours_50_late
            hours_75 = hours_75_early + hours_75_late
            
            # Crear solicitud automática con rangos
            self._create_extra_hours_request(extra_hours_type, duration, hours_25, hours_50, hours_75)
            return
        
        # Crear solicitud automática
        self._create_extra_hours_request(extra_hours_type, duration, hours_25, hours_50, hours_75)

    def _convert_to_local_timezone(self, dt):
        """Convertir datetime de UTC a zona horaria local del usuario"""
        if not dt:
            return dt
        
        # Obtener zona horaria del usuario o usar la del empleado
        user_tz_name = self.env.user.tz or (self.employee_id.user_id.tz if self.employee_id and self.employee_id.user_id else None) or 'America/Tegucigalpa'
        user_tz = pytz.timezone(user_tz_name)
        
        # Si el datetime no tiene timezone, asumir que es UTC
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
            ('date_start', '<=', self.check_in.date()),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', self.check_in.date())
        ], limit=1)
        
        if contract and contract.resource_calendar_id:
            return contract.resource_calendar_id
        
        # Si no hay contrato, usar calendario por defecto de la compañía
        return self.employee_id.company_id.resource_calendar_id

    def _get_expected_schedule(self, calendar):
        """Obtener horario esperado para la fecha de la asistencia
        Retorna el primer check_in y el último check_out de todos los períodos del día
        Usa la fecha local del check_in
        """
        if not calendar:
            return False
        
        # Convertir check_in a zona horaria local para obtener la fecha correcta
        check_in_local = self._convert_to_local_timezone(self.check_in)
        
        # Obtener horario para el día de la semana usando la fecha local
        weekday = check_in_local.weekday()
        attendances = calendar.attendance_ids.filtered(
            lambda x: x.dayofweek == str(weekday)
        )
        
        if not attendances:
            return False
        
        # Convertir hour_from y hour_to (float) a objetos time
        def float_to_time(hour_float):
            """Convierte un float de horas a un objeto time"""
            hours = int(hour_float)
            minutes = int((hour_float - hours) * 60)
            return time(hours, minutes)
        
        # Obtener el primer check_in (del primer período) y el último check_out (del último período)
        # Usar la fecha local
        date = check_in_local.date()
        first_attendance = attendances[0]
        last_attendance = attendances[-1]
        
        expected_check_in = datetime.combine(date, float_to_time(first_attendance.hour_from))
        expected_check_out = datetime.combine(date, float_to_time(last_attendance.hour_to))
        
        return {
            'check_in': expected_check_in,
            'check_out': expected_check_out,
            'attendances': attendances  # Guardar todos los períodos para cálculos posteriores
        }

    def _detect_extra_hours_type(self, expected_schedule):
        """Detectar tipo de horas extra"""
        if not expected_schedule:
            return False
        
        early_check_in = self.check_in < expected_schedule['check_in']
        late_check_out = self.check_out > expected_schedule['check_out']
        
        if early_check_in and late_check_out:
            return 'both'
        elif early_check_in:
            return 'early'
        elif late_check_out:
            return 'late'
        
        return False

    def _calculate_extra_duration(self, expected_schedule, extra_type):
        """Calcular duración de horas extra"""
        if extra_type == 'early':
            duration = (expected_schedule['check_in'] - self.check_in).total_seconds() / 3600
        elif extra_type == 'late':
            duration = (self.check_out - expected_schedule['check_out']).total_seconds() / 3600
        elif extra_type == 'both':
            early_duration = (expected_schedule['check_in'] - self.check_in).total_seconds() / 3600
            late_duration = (self.check_out - expected_schedule['check_out']).total_seconds() / 3600
            duration = early_duration + late_duration
        else:
            return 0.0
        
        return duration
    
    def _calculate_overtime_hours_by_ranges(self, start_time, end_time):
        """
        Calcular horas extra según los rangos configurados (25%, 50%, 75%)
        Solo calcula las horas entre start_time y end_time, distribuyéndolas según los rangos
        Retorna: (hours_25, hours_50, hours_75)
        """
        _logger.info('=== DEBUG: Cálculo de horas extra por rangos ===')
        _logger.info('Start_time: %s, End_time: %s', start_time, end_time)
        total_hours_between = (end_time - start_time).total_seconds() / 3600
        _logger.info('Total horas entre start_time y end_time: %.2f', total_hours_between)
        
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
        
        _logger.info('Rangos configurados:')
        _logger.info('  25%%: %02d:%02d - %02d:%02d', hour_25_from_h, hour_25_from_m, hour_25_to_h, hour_25_to_m)
        _logger.info('  50%%: %02d:%02d - %02d:%02d', hour_50_from_h, hour_50_from_m, hour_50_to_h, hour_50_to_m)
        _logger.info('  75%%: %02d:%02d - %02d:%02d', hour_75_from_h, hour_75_from_m, hour_75_to_h, hour_75_to_m)
        
        # Inicializar contadores
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        
        # Calcular horas en cada rango, considerando que end_time puede ser del día siguiente
        current_time = start_time
        iteration = 0
        while current_time < end_time:
            iteration += 1
            _logger.info('Iteración %d: current_time = %s', iteration, current_time)
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
                hours_to_add = (next_time - current_time).total_seconds() / 3600
                hours_25 += hours_to_add
                _logger.info('  → Rango 25%%: %.2f horas (de %s a %s)', hours_to_add, current_time, next_time)
                current_time = next_time
            elif start_50 <= current_time < end_50:
                # Está en el rango del 50%
                next_time = min(end_time, end_50)
                hours_to_add = (next_time - current_time).total_seconds() / 3600
                hours_50 += hours_to_add
                _logger.info('  → Rango 50%%: %.2f horas (de %s a %s)', hours_to_add, current_time, next_time)
                current_time = next_time
            elif start_75 <= current_time < end_75:
                # Está en el rango del 75%
                next_time = min(end_time, end_75)
                hours_to_add = (next_time - current_time).total_seconds() / 3600
                hours_75 += hours_to_add
                _logger.info('  → Rango 75%%: %.2f horas (de %s a %s)', hours_to_add, current_time, next_time)
                current_time = next_time
            else:
                # current_time no está en ningún rango configurado
                _logger.info('  → current_time no está en ningún rango configurado')
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
                    _logger.info('  → Avanzando a: %s (end_time: %s)', next_time, end_time)
                    if next_time >= end_time:
                        # Si el siguiente punto está en o después de end_time, terminar
                        _logger.info('  → next_time >= end_time, terminando')
                        break
                    current_time = next_time
                else:
                    # No hay más rangos, terminar
                    _logger.info('  → No hay más rangos, terminando')
                    break
        
        _logger.info('=== Total horas extra calculadas: 25%%=%.2f, 50%%=%.2f, 75%%=%.2f, Total=%.2f ===',
                    hours_25, hours_50, hours_75, hours_25 + hours_50 + hours_75)
        return (hours_25, hours_50, hours_75)

    def _create_extra_hours_request(self, extra_type, duration, hours_25=0.0, hours_50=0.0, hours_75=0.0):
        """Crear solicitud automática de horas extra"""
        # Obtener motivo por defecto
        default_reason = self.env['hr.extra.hours.reason'].search([
            ('code', '=', 'automatic')
        ], limit=1)
        
        if not default_reason:
            # Crear motivo por defecto si no existe
            default_reason = self.env['hr.extra.hours.reason'].create({
                'name': 'Detección Automática',
                'code': 'automatic',
                'description': 'Solicitud generada automáticamente por el sistema'
            })
        
        # Convertir check_in y check_out a zona horaria local para cálculos
        check_in_local = self._convert_to_local_timezone(self.check_in)
        check_out_local = self._convert_to_local_timezone(self.check_out)
        
        # Obtener zona horaria del usuario para convertir de vuelta a UTC
        user_tz_name = self.env.user.tz or (self.employee_id.user_id.tz if self.employee_id and self.employee_id.user_id else None) or 'America/Tegucigalpa'
        user_tz = pytz.timezone(user_tz_name)
        
        # Localizar los datetimes locales en la zona horaria del usuario
        check_in_local_tz = user_tz.localize(check_in_local)
        check_out_local_tz = user_tz.localize(check_out_local)
        
        # Convertir a UTC para almacenar en la base de datos (Odoo almacena en UTC)
        check_in_utc = check_in_local_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        check_out_utc = check_out_local_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Calcular horas pagables (solo horas extra)
        total_extra_hours = hours_25 + hours_50 + hours_75
        
        # Crear solicitud usando valores en UTC (Odoo los mostrará correctamente en la zona local)
        request_vals = {
            'employee_id': self.employee_id.id,
            'attendance_id': self.id,
            'date': check_in_local.date(),
            'check_in': check_in_utc,
            'check_out': check_out_utc,
            'type': extra_type,
            'duration_hours': duration,
            'payable_hours': total_extra_hours,  # Solo horas extra, no horas normales
            'hours_25': hours_25,
            'hours_50': hours_50,
            'hours_75': hours_75,
            'reason_id': default_reason.id,
            'justification': _('Solicitud generada automáticamente por detección de horas extra. '
                             'Horas 25%%: %.2f, Horas 50%%: %.2f, Horas 75%%: %.2f') % (
                             hours_25, hours_50, hours_75),
            'state': 'to_approve'
        }
        
        try:
            request = self.env['hr.extra.hours.request'].create(request_vals)
        except (KeyError, AttributeError):
            # El modelo no está disponible, no crear solicitud
            return
        
        # Crear actividad para el jefe
        if request.manager_id and request.manager_id.user_id:
            request.activity_schedule(
                'hr_extra_hours_request.mail_activity_approve_extra_hours',
                user_id=request.manager_id.user_id.id,
                summary=_('Solicitud Automática de Horas Extra'),
                note=_('Se ha detectado automáticamente %s horas extra para %s. Por favor revise y apruebe.') % (
                    duration,
                    self.employee_id.name
                )
            )
        
        _logger.info('Solicitud automática de horas extra creada: %s', request.name)

    def action_recalculate_hours(self):
        """Recalcular horas normales y extra para la solicitud asociada"""
        self.ensure_one()
        
        if not self.extra_hours_request_id:
            raise UserError(_('No hay una solicitud de horas extra asociada a esta asistencia.'))
        
        if not self.check_in or not self.check_out:
            raise UserError(_('La asistencia debe tener hora de entrada y salida para recalcular.'))
        
        request = self.extra_hours_request_id[0]
        
        _logger.info('=== DEBUG: Iniciando recálculo de horas ===')
        _logger.info('Asistencia - Check-in (UTC): %s, Check-out (UTC): %s', self.check_in, self.check_out)
        
        # Convertir check_in y check_out a zona horaria local
        check_in_local = self._convert_to_local_timezone(self.check_in)
        check_out_local = self._convert_to_local_timezone(self.check_out)
        
        _logger.info('Asistencia - Check-in (Local): %s, Check-out (Local): %s', check_in_local, check_out_local)
        _logger.info('Solicitud actual - Check-in: %s, Check-out: %s', request.check_in, request.check_out)
        
        # Obtener zona horaria del usuario para convertir de vuelta a UTC
        user_tz_name = self.env.user.tz or (self.employee_id.user_id.tz if self.employee_id and self.employee_id.user_id else None) or 'America/Tegucigalpa'
        user_tz = pytz.timezone(user_tz_name)
        
        # Localizar los datetimes locales en la zona horaria del usuario
        check_in_local_tz = user_tz.localize(check_in_local)
        check_out_local_tz = user_tz.localize(check_out_local)
        
        # Convertir a UTC para almacenar en la base de datos (Odoo almacena en UTC)
        check_in_utc = check_in_local_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        check_out_utc = check_out_local_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Actualizar check_in y check_out de la solicitud con los valores en UTC (Odoo los mostrará correctamente en la zona local)
        request.write({
            'check_in': check_in_utc,
            'check_out': check_out_utc,
            'date': check_in_local.date(),
        })
        
        _logger.info('Solicitud actualizada - Check-in: %s, Check-out: %s', request.check_in, request.check_out)
        
        # Forzar recálculo de los campos computed
        # Esto recalculará expected_check_in, expected_check_out y hours_normal
        request._compute_expected_schedule()
        _logger.info('Expected schedule - Check-in: %s, Check-out: %s', request.expected_check_in, request.expected_check_out)
        
        request._compute_hours_normal()
        _logger.info('Horas normales calculadas: %.2f', request.hours_normal)
        
        # Recalcular horas extra por rangos
        # Obtener calendario del empleado
        calendar = self._get_employee_calendar()
        if not calendar:
            raise UserError(_('No se encontró calendario laboral para el empleado.'))
        
        expected_schedule = self._get_expected_schedule(calendar)
        if not expected_schedule:
            raise UserError(_('No se pudo determinar el horario esperado para esta fecha.'))
        
        _logger.info('Expected schedule del calendario: Check-in: %s, Check-out: %s', 
                    expected_schedule.get('check_in'), expected_schedule.get('check_out'))
        _logger.info('Número de períodos en el horario: %d', len(expected_schedule.get('attendances', [])))
        
        # Detectar tipo de horas extra (usar valores locales)
        # Crear expected_schedule con valores locales
        expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
        expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
        
        # Detectar tipo de horas extra usando valores locales
        early_check_in = check_in_local < expected_check_in_local if expected_check_in_local else False
        late_check_out = check_out_local > expected_check_out_local if expected_check_out_local else False
        
        if early_check_in and late_check_out:
            extra_hours_type = 'both'
        elif early_check_in:
            extra_hours_type = 'early'
        elif late_check_out:
            extra_hours_type = 'late'
        else:
            extra_hours_type = False
        
        _logger.info('Tipo de horas extra detectado: %s', extra_hours_type)
        
        # Inicializar variables para el mensaje
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        
        if not extra_hours_type:
            # No hay horas extra, poner todo en 0
            request.write({
                'hours_25': 0.0,
                'hours_50': 0.0,
                'hours_75': 0.0,
                'payable_hours': 0.0,
            })
        else:
            # Calcular horas por rangos (usar valores locales)
            # NOTA: Los rangos 25%, 50%, 75% solo se aplican a horas DESPUÉS del horario laboral
            if extra_hours_type == 'early':
                # Entrada anticipada: todas al 25%
                start_time = check_in_local
                end_time = expected_check_in_local
                early_duration = (end_time - start_time).total_seconds() / 3600
                hours_25 = early_duration
                hours_50 = 0.0
                hours_75 = 0.0
            elif extra_hours_type == 'late':
                # Salida tardía: aplicar rangos
                start_time = expected_check_out_local
                end_time = check_out_local
                hours_25, hours_50, hours_75 = self._calculate_overtime_hours_by_ranges(start_time, end_time)
            else:  # both
                early_start = check_in_local
                early_end = expected_check_in_local
                late_start = expected_check_out_local
                late_end = check_out_local
                
                # Entrada anticipada: todas al 25%
                early_duration = (early_end - early_start).total_seconds() / 3600
                hours_25_early = early_duration
                hours_50_early = 0.0
                hours_75_early = 0.0
                
                # Salida tardía: aplicar rangos
                hours_25_late, hours_50_late, hours_75_late = self._calculate_overtime_hours_by_ranges(late_start, late_end)
                
                hours_25 = hours_25_early + hours_25_late
                hours_50 = hours_50_early + hours_50_late
                hours_75 = hours_75_early + hours_75_late
            
            # Actualizar la solicitud con las horas calculadas
            total_extra_hours = hours_25 + hours_50 + hours_75
            _logger.info('Horas extra calculadas - 25%%: %.2f, 50%%: %.2f, 75%%: %.2f, Total: %.2f',
                        hours_25, hours_50, hours_75, total_extra_hours)
            
            request.write({
                'hours_25': hours_25,
                'hours_50': hours_50,
                'hours_75': hours_75,
                'payable_hours': total_extra_hours,
            })
        
        # Refrescar la solicitud para que se actualicen los campos computed
        request.invalidate_recordset(['hours_normal', 'expected_check_in', 'expected_check_out'])
        request._compute_expected_schedule()
        request._compute_hours_normal()
        
        # Refrescar la asistencia para que se actualicen los campos relacionados
        # Los campos relacionados se actualizarán automáticamente cuando se recargue la vista
        self.invalidate_recordset(['hours_normal', 'hours_25', 'hours_50', 'hours_75', 'total_extra_hours', 'payable_hours'])
        
        # Forzar recálculo de campos relacionados en la asistencia
        self._compute_extra_hours_request()
        
        # Preparar mensaje de debug usando los valores calculados (no los de la BD que pueden estar desactualizados)
        calendar = self._get_employee_calendar()
        debug_info = []
        if calendar:
            # Usar la fecha local para obtener el weekday correcto
            check_in_local = self._convert_to_local_timezone(self.check_in)
            weekday = check_in_local.weekday()
            attendances = calendar.attendance_ids.filtered(
                lambda x: x.dayofweek == str(weekday)
            )
            debug_info.append(_('Períodos encontrados: %d') % len(attendances))
            for idx, att in enumerate(attendances):
                debug_info.append(_('Período %d: %.2f - %.2f') % (idx + 1, att.hour_from, att.hour_to))
        
        # Usar los valores calculados localmente para el mensaje
        final_hours_normal = request.hours_normal
        final_hours_25 = hours_25
        final_hours_50 = hours_50
        final_hours_75 = hours_75
        final_total_extra = final_hours_25 + final_hours_50 + final_hours_75
        
        message = _('Las horas han sido recalculadas correctamente.\n\n'
                   'Horas Normales: %.2f\n'
                   'Horas 25%%: %.2f\n'
                   'Horas 50%%: %.2f\n'
                   'Horas 75%%: %.2f\n'
                   'Total Horas Extra: %.2f\n\n'
                   '%s') % (
            final_hours_normal,
            final_hours_25,
            final_hours_50,
            final_hours_75,
            final_total_extra,
            '\n'.join(debug_info) if debug_info else ''
        )
        
        # Agregar mensaje al registro para que el usuario vea el resultado
        self.message_post(body=message)
        
        # Recargar la vista para que se actualicen los valores
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',  # Esto recarga la vista actual automáticamente
        }
    
    def action_view_extra_hours_request(self):
        """Ver solicitud de horas extra relacionada"""
        self.ensure_one()
        if not self.extra_hours_request_id:
            raise UserError(_('No hay solicitud de horas extra asociada a esta asistencia.'))
        
        return {
            'name': _('Solicitud de Horas Extra'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.extra.hours.request',
            'res_id': self.extra_hours_request_id.id,
            'view_mode': 'form',
            'target': 'new'
        }
