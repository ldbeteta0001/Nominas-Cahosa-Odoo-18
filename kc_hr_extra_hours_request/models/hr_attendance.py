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
    
    hours_100 = fields.Float(
        string='Horas Domingo (100%)',
        related='extra_hours_request.hours_100',
        readonly=True,
        store=False,
        help='Horas extra con recargo del 100% (domingos)'
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
    
    is_partial = fields.Boolean(
        string='Asistencia Parcial',
        default=False,
        help='Indica si la asistencia es parcial (solo entrada o solo salida)'
    )
    
    partial_type = fields.Selection(
        [
            ('entry_only', 'Solo Entrada'),
            ('exit_only', 'Solo Salida'),
            ('complete', 'Completa')
        ],
        string='Tipo de Asistencia Parcial',
        default='complete',
        help='Tipo de asistencia parcial'
    )
    
    check_in_schedule = fields.Datetime(
        string='Entrada Programada',
        help='Hora de entrada según el horario de trabajo programado'
    )
    
    check_out_schedule = fields.Datetime(
        string='Salida Programada',
        help='Hora de salida según el horario de trabajo programado'
    )

    @api.depends('extra_hours_request_id')
    def _compute_has_extra_hours_request(self):
        for attendance in self:
            attendance.has_extra_hours_request = bool(attendance.extra_hours_request_id)
    
    @api.depends('extra_hours_request_id')
    def _compute_extra_hours_request(self):
        """Obtener el primer registro de la solicitud de horas extra"""
        for attendance in self:
            attendance.extra_hours_request = attendance.extra_hours_request_id[:1] if attendance.extra_hours_request_id else False
    
    @api.depends('hours_25', 'hours_50', 'hours_75', 'hours_100')
    def _compute_total_extra_hours(self):
        for attendance in self:
            attendance.total_extra_hours = attendance.hours_25 + attendance.hours_50 + attendance.hours_75 + attendance.hours_100

    @api.model
    def create(self, vals):
        """Override create para detectar horas extra automáticamente"""
        attendance = super(HrAttendance, self).create(vals)
        
        # Solo procesar si es un check-out (tiene check_in y check_out)
        # Y si no se está saltando la detección (por ejemplo, durante importación masiva)
        if not self.env.context.get('skip_extra_hours_detection'):
            if attendance.check_in and attendance.check_out:
                try:
                    attendance._detect_extra_hours()
                except Exception as e:
                    _logger.error(f"Error al detectar horas extra para asistencia {attendance.id}: {str(e)}", exc_info=True)
                    # No lanzar excepción para no abortar la creación de la asistencia
        
        return attendance

    def write(self, vals):
        """Override write para detectar horas extra cuando se actualiza"""
        result = super(HrAttendance, self).write(vals)
        
        # Solo procesar si se actualizó check_out
        # Y si no se está saltando la detección (por ejemplo, durante importación masiva)
        if not self.env.context.get('skip_extra_hours_detection'):
            if 'check_out' in vals:
                for attendance in self:
                    if attendance.check_in and attendance.check_out:
                        try:
                            attendance._detect_extra_hours()
                        except Exception as e:
                            _logger.error(f"Error al detectar horas extra para asistencia {attendance.id}: {str(e)}", exc_info=True)
                            # No lanzar excepción para no abortar la actualización
        
        return result

    def _detect_extra_hours(self):
        """Detectar si hay horas extra y crear solicitud automática"""
        self.ensure_one()
        
        if not self.employee_id or not self.check_in or not self.check_out:
            return
        
        # Verificar si ya existe una solicitud para esta asistencia
        existing_request = self.env['hr.extra.hours.request'].search([
            ('attendance_id', '=', self.id)
        ], limit=1)
        
        if existing_request:
            return
        
        # Convertir check_in y check_out a zona horaria local
        check_in_local = self._convert_to_local_timezone(self.check_in)
        check_out_local = self._convert_to_local_timezone(self.check_out)
        date_local = check_in_local.date()
        weekday = date_local.weekday()  # 0=Lunes, 5=Sábado, 6=Domingo
        
        # Detectar si es sábado o domingo
        is_saturday = weekday == 5
        is_sunday = weekday == 6
        
        # Obtener turno del empleado y es_mecanico del contrato
        shift_period = self.employee_id.current_shift_period  # 'dia' o 'noche'
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
            ('date_start', '<=', date_local),
            '|', ('date_end', '=', False), ('date_end', '>=', date_local)
        ], limit=1)
        es_mecanico = contract.es_mecanico if contract else False
        
        # Obtener calendario laboral del empleado
        calendar = self._get_employee_calendar()
        if not calendar:
            return
        
        # Calcular horario esperado
        expected_schedule = self._get_expected_schedule(calendar)
        if not expected_schedule:
            return
        
        expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
        expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
        
        # Calcular duración total trabajada
        total_worked_hours = (check_out_local - check_in_local).total_seconds() / 3600
        
        # Inicializar variables
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        hours_100 = 0.0
        extra_hours_type = False
        
        # LÓGICA SEGÚN DÍA DE LA SEMANA
        if is_sunday:
            # DOMINGO: Todas las horas trabajadas son extra al 100%
            hours_100 = total_worked_hours
            extra_hours_type = 'late' if check_out_local > expected_check_out_local else 'early'
            duration = total_worked_hours
        elif is_saturday:
            # SÁBADO: Todas las horas trabajadas son extra
            # Mecánicos: 50%, Otros: 25%
            if es_mecanico:
                hours_50 = total_worked_hours
            else:
                hours_25 = total_worked_hours
            extra_hours_type = 'late' if check_out_local > expected_check_out_local else 'early'
            duration = total_worked_hours
        else:
            # DÍAS LABORALES (L-V): Calcular horas extra según exceso del horario diario
            # Para turnos nocturnos, usar el horario esperado del calendario
            if shift_period == 'noche' and calendar and calendar.nocturna:
                # TURNO NOCTURNO: Usar horario esperado del calendario
                # El expected_check_in debería ser 18:00 y expected_check_out 06:00 del día siguiente
                expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
                expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
                
                if not expected_check_in_local or not expected_check_out_local:
                    return
                
                # Calcular horas base trabajadas (del horario esperado)
                base_start = expected_check_in_local
                base_end = expected_check_out_local
                
                # Calcular horas base trabajadas (dentro del horario esperado)
                base_worked_start = max(check_in_local, base_start)
                base_worked_end = min(check_out_local, base_end)
                base_worked_hours = max(0, (base_worked_end - base_worked_start).total_seconds() / 3600)
                
                # Calcular horas extra (después del horario esperado, en el rango 00:00-06:00)
                if check_out_local > base_end:
                    # Hay horas después del horario esperado
                    extra_start = base_end
                    extra_end = check_out_local
                    
                    if extra_end > extra_start:
                        hours_75 = (extra_end - extra_start).total_seconds() / 3600
                        extra_hours_type = 'late'
                        duration = hours_75
                    else:
                        return  # No hay horas extra
                else:
                    return  # Check_out antes del fin del horario esperado, no hay horas extra
            else:
                # TURNO DÍA: Lógica normal
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
                
                # Calcular horas por rangos según turno
                if extra_hours_type == 'early':
                    # Entrada anticipada: NO cuenta como extra por defecto
                    hours_25 = 0.0
                    hours_50 = 0.0
                    hours_75 = 0.0
                elif extra_hours_type == 'late':
                    # Salida tardía: aplicar rangos según turno
                    start_time = expected_check_out_local
                    end_time = check_out_local
                    hours_25, hours_50, hours_75 = self._calculate_overtime_hours_by_ranges(
                        start_time, end_time, shift_period, calendar, date_local
                    )
                else:  # both
                    # Para 'both', calcular por separado entrada anticipada y salida tardía
                    early_start = check_in_local
                    early_end = expected_check_in_local
                    late_start = expected_check_out_local
                    late_end = check_out_local
                    
                    # Entrada anticipada: NO cuenta como extra por defecto
                    hours_25_early = 0.0
                    hours_50_early = 0.0
                    hours_75_early = 0.0
                    
                    # Salida tardía: aplicar rangos según turno
                    hours_25_late, hours_50_late, hours_75_late = self._calculate_overtime_hours_by_ranges(
                        late_start, late_end, shift_period, calendar, date_local
                    )
                    
                    hours_25 = hours_25_early + hours_25_late
                    hours_50 = hours_50_early + hours_50_late
                    hours_75 = hours_75_early + hours_75_late
        
        # Crear solicitud automática
        self._create_extra_hours_request(extra_hours_type, duration, hours_25, hours_50, hours_75, hours_100)

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
        Para turnos nocturnos, considera períodos que cruzan medianoche
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
            """Convierte un float de horas a un objeto time, manejando valores >= 24"""
            if hour_float >= 24.0:
                # Si es 24.0 o mayor, usar 23:59:59 como máximo
                hours = 23
                minutes = 59
                seconds = 59
            else:
                hours = int(hour_float)
                minutes = int((hour_float - hours) * 60)
                seconds = int(((hour_float - hours) * 60 - minutes) * 60)
            return time(hours, minutes, seconds)
        
        # Usar la fecha local
        date = check_in_local.date()
        first_attendance = attendances[0]
        last_attendance = attendances[-1]
        
        # Para turnos nocturnos, considerar períodos del día siguiente
        if calendar.nocturna:
            # El check_in es del primer período del día (ej: 18:00)
            expected_check_in = datetime.combine(date, float_to_time(first_attendance.hour_from))
            
            # El check_out puede ser del día siguiente si hay períodos de madrugada
            # Buscar períodos del día siguiente que sean de madrugada (00:00-06:00)
            next_weekday = (weekday + 1) % 7
            next_attendances = calendar.attendance_ids.filtered(
                lambda x: x.dayofweek == str(next_weekday)
            )
            
            # Si hay períodos del día siguiente y alguno es de madrugada (hour_from < 12), usarlo
            if next_attendances:
                morning_attendances = next_attendances.filtered(lambda x: x.hour_from < 12.0)
                if morning_attendances:
                    # Usar el último período de madrugada del día siguiente
                    last_morning = max(morning_attendances, key=lambda x: x.hour_to)
                    expected_check_out_time = float_to_time(last_morning.hour_to)
                    expected_check_out = datetime.combine(date + timedelta(days=1), expected_check_out_time)
                else:
                    # Si no hay períodos de madrugada, usar el último período del día actual
                    expected_check_out_time = float_to_time(last_attendance.hour_to)
                    if last_attendance.hour_to >= 24.0:
                        expected_check_out = datetime.combine(date + timedelta(days=1), expected_check_out_time)
                    else:
                        expected_check_out = datetime.combine(date, expected_check_out_time)
            else:
                # No hay períodos del día siguiente, usar el último del día actual
                expected_check_out_time = float_to_time(last_attendance.hour_to)
                if last_attendance.hour_to >= 24.0:
                    expected_check_out = datetime.combine(date + timedelta(days=1), expected_check_out_time)
                else:
                    expected_check_out = datetime.combine(date, expected_check_out_time)
        else:
            # Turno diurno: lógica normal
            expected_check_in = datetime.combine(date, float_to_time(first_attendance.hour_from))
            expected_check_out_time = float_to_time(last_attendance.hour_to)
            
            # Si hour_to es >= 24, el check_out es del día siguiente
            if last_attendance.hour_to >= 24.0:
                expected_check_out = datetime.combine(date + timedelta(days=1), expected_check_out_time)
            else:
                expected_check_out = datetime.combine(date, expected_check_out_time)
        
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
    
    def _calculate_overtime_hours_by_ranges(self, start_time, end_time, shift_period=False, calendar=False, date_local=False):
        """
        Calcular horas extra según los rangos configurados según el turno
        Solo calcula las horas entre start_time y end_time, distribuyéndolas según los rangos
        Retorna: (hours_25, hours_50, hours_75)
        
        Rangos por turno:
        - Turno día (60 horas): 14:00-18:00 = 25%, 18:00-22:00 = 50%, 22:00+ = 75%
        - Turno día (otros): desde fin del horario normal hasta 18:00 = 25%, 18:00-22:00 = 50%, 22:00+ = 75%
        - Turno noche: 00:00-06:00 = 75%
        """
        _logger.info('=== DEBUG: Cálculo de horas extra por rangos ===')
        _logger.info('Start_time: %s, End_time: %s, Turno: %s', start_time, end_time, shift_period)
        total_hours_between = (end_time - start_time).total_seconds() / 3600
        _logger.info('Total horas entre start_time y end_time: %.2f', total_hours_between)
        
        # Determinar rangos según turno
        if shift_period == 'noche':
            # TURNO NOCHE: 00:00-06:00 = 75%
            # Las horas entre 00:00 y 06:00 son al 75%
            if not date_local:
                date_local = start_time.date()
            
            hours_25 = 0.0
            hours_50 = 0.0
            hours_75 = 0.0
            
            current_time = start_time
            while current_time < end_time:
                current_date = current_time.date()
                
                # Rango de 00:00 a 06:00
                night_start = datetime.combine(current_date, time(0, 0))
                night_end = datetime.combine(current_date, time(6, 0))
                
                # Si el rango cruza medianoche, ajustar
                if current_time >= night_end and current_time < datetime.combine(current_date + timedelta(days=1), time(0, 0)):
                    # Está fuera del rango nocturno (06:00-23:59), avanzar al siguiente día
                    current_time = datetime.combine(current_date + timedelta(days=1), time(0, 0))
                    continue
                
                # Calcular horas en el rango nocturno
                range_start = max(current_time, night_start)
                range_end = min(end_time, night_end)
                
                if range_start < range_end:
                    hours_in_range = (range_end - range_start).total_seconds() / 3600
                    hours_75 += hours_in_range
                    _logger.info('  → Rango 75%% (noche): %.2f horas (de %s a %s)', hours_in_range, range_start, range_end)
                    current_time = range_end
                else:
                    # No está en rango nocturno, avanzar
                    if current_time < night_start:
                        current_time = night_start
                    else:
                        current_time = datetime.combine(current_date + timedelta(days=1), time(0, 0))
            
            return (hours_25, hours_50, hours_75)
        
        # TURNO DÍA: Rangos específicos
        # Determinar si es calendario de 60 horas
        is_60_hours = False
        if calendar and date_local:
            weekday = date_local.weekday()
            attendances = calendar.attendance_ids.filtered(lambda x: x.dayofweek == str(weekday))
            if attendances:
                # Sumar todas las horas del día
                total_hours_day = sum(att.hour_to - att.hour_from for att in attendances)
                is_60_hours = total_hours_day >= 10.0  # 60 horas / 6 días = 10 horas/día
        
        # Rangos para turno día
        if is_60_hours:
            # Turno día de 60 horas: 14:00-18:00 = 25%, 18:00-22:00 = 50%, 22:00+ = 75%
            hour_25_from_h, hour_25_from_m = 14, 0
            hour_25_to_h, hour_25_to_m = 18, 0
        else:
            # Turno día otros: desde fin del horario normal hasta 18:00 = 25%
            # Necesitamos obtener el fin del horario normal del calendario
            if calendar and date_local:
                weekday = date_local.weekday()
                attendances = calendar.attendance_ids.filtered(lambda x: x.dayofweek == str(weekday))
                if attendances:
                    # Obtener la última hora de salida del día
                    last_attendance = max(attendances, key=lambda x: x.hour_to)
                    hour_25_from_h = int(last_attendance.hour_to)
                    hour_25_from_m = int((last_attendance.hour_to - hour_25_from_h) * 60)
                else:
                    hour_25_from_h, hour_25_from_m = 18, 0
            else:
                hour_25_from_h, hour_25_from_m = 18, 0
            hour_25_to_h, hour_25_to_m = 18, 0
        
        hour_50_from_h, hour_50_from_m = 18, 0
        hour_50_to_h, hour_50_to_m = 22, 0
        hour_75_from_h, hour_75_from_m = 22, 0
        hour_75_to_h, hour_75_to_m = 23, 59
        
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

    def _create_extra_hours_request(self, extra_type, duration, hours_25=0.0, hours_50=0.0, hours_75=0.0, hours_100=0.0):
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
        total_extra_hours = hours_25 + hours_50 + hours_75 + hours_100
        
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
            'hours_100': hours_100,
            'reason_id': default_reason.id,
            'justification': _('Solicitud generada automáticamente por detección de horas extra. '
                             'Horas 25%%: %.2f, Horas 50%%: %.2f, Horas 75%%: %.2f, Horas Domingo (100%%): %.2f') % (
                             hours_25, hours_50, hours_75, hours_100),
            'state': 'to_approve'
        }
        
        request = self.env['hr.extra.hours.request'].create(request_vals)
        
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

    def _calculate_extra_hours_only(self):
        """Calcular horas extra sin crear solicitud (solo cálculo)"""
        self.ensure_one()
        
        if not self.employee_id or not self.check_in or not self.check_out:
            return None
        
        # Convertir check_in y check_out a zona horaria local
        check_in_local = self._convert_to_local_timezone(self.check_in)
        check_out_local = self._convert_to_local_timezone(self.check_out)
        date_local = check_in_local.date()
        weekday = date_local.weekday()  # 0=Lunes, 5=Sábado, 6=Domingo
        
        # Detectar si es sábado o domingo
        is_saturday = weekday == 5
        is_sunday = weekday == 6
        
        # Obtener turno del empleado y es_mecanico del contrato
        shift_period = self.employee_id.current_shift_period  # 'dia' o 'noche'
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
            ('date_start', '<=', date_local),
            '|', ('date_end', '=', False), ('date_end', '>=', date_local)
        ], limit=1)
        es_mecanico = contract.es_mecanico if contract else False
        
        # Obtener calendario laboral del empleado
        calendar = self._get_employee_calendar()
        if not calendar:
            return None
        
        # Calcular horario esperado
        expected_schedule = self._get_expected_schedule(calendar)
        if not expected_schedule:
            return None
        
        expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
        expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
        
        # Calcular duración total trabajada
        total_worked_hours = (check_out_local - check_in_local).total_seconds() / 3600
        
        # Inicializar variables
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        hours_100 = 0.0
        
        # LÓGICA SEGÚN DÍA DE LA SEMANA (igual que _detect_extra_hours pero sin crear solicitud)
        if is_sunday:
            # DOMINGO: Todas las horas trabajadas son extra al 100%
            hours_100 = total_worked_hours
        elif is_saturday:
            # SÁBADO: Todas las horas trabajadas son extra
            # Mecánicos: 50%, Otros: 25%
            if es_mecanico:
                hours_50 = total_worked_hours
            else:
                hours_25 = total_worked_hours
        else:
            # DÍAS LABORALES (L-V): Calcular horas extra según exceso del horario diario
            # Para turnos nocturnos, usar el horario esperado del calendario
            if shift_period == 'noche' and calendar and calendar.nocturna:
                # TURNO NOCTURNO: Usar horario esperado del calendario
                # El expected_check_in debería ser 18:00 y expected_check_out 06:00 del día siguiente
                expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
                expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
                
                if not expected_check_in_local or not expected_check_out_local:
                    return None
                
                # Calcular horas base trabajadas (del horario esperado)
                base_start = expected_check_in_local
                base_end = expected_check_out_local
                
                # Calcular horas base trabajadas (dentro del horario esperado)
                base_worked_start = max(check_in_local, base_start)
                base_worked_end = min(check_out_local, base_end)
                base_worked_hours = max(0, (base_worked_end - base_worked_start).total_seconds() / 3600)
                
                # Calcular horas extra (después del horario esperado, en el rango 00:00-06:00)
                if check_out_local > base_end:
                    # Hay horas después del horario esperado
                    extra_start = base_end
                    extra_end = check_out_local
                    
                    if extra_end > extra_start:
                        hours_75 = (extra_end - extra_start).total_seconds() / 3600
                    else:
                        return None  # No hay horas extra
                else:
                    return None  # Check_out antes del fin del horario esperado, no hay horas extra
            else:
                # TURNO DÍA: Lógica normal
                early_check_in = check_in_local < expected_check_in_local if expected_check_in_local else False
                late_check_out = check_out_local > expected_check_out_local if expected_check_out_local else False
                
                if not (early_check_in or late_check_out):
                    return None
                
                # Calcular horas por rangos según turno
                if late_check_out:
                    # Salida tardía: aplicar rangos según turno
                    start_time = expected_check_out_local
                    end_time = check_out_local
                    hours_25, hours_50, hours_75 = self._calculate_overtime_hours_by_ranges(
                        start_time, end_time, shift_period, calendar, date_local
                    )
                # Entrada anticipada: NO cuenta como extra por defecto
        
        return {
            'hours_25': hours_25,
            'hours_50': hours_50,
            'hours_75': hours_75,
            'hours_100': hours_100,
            'total': hours_25 + hours_50 + hours_75 + hours_100
        }
    
    def action_update_work_schedule(self):
        """Actualizar horario de trabajo programado según el calendario del empleado"""
        self.ensure_one()
        
        if not self.employee_id or not self.check_in:
            raise UserError(_('La asistencia debe tener empleado y hora de entrada para actualizar el horario.'))
        
        # Obtener calendario del empleado
        calendar = self._get_employee_calendar()
        if not calendar:
            raise UserError(_('No se encontró calendario laboral para el empleado.'))
        
        # Calcular horario esperado
        expected_schedule = self._get_expected_schedule(calendar)
        if not expected_schedule:
            raise UserError(_('No se pudo determinar el horario esperado para esta fecha.'))
        
        # Convertir a UTC para almacenar en la base de datos
        expected_check_in = expected_schedule.get('check_in')
        expected_check_out = expected_schedule.get('check_out')
        
        if not expected_check_in:
            raise UserError(_('No se pudo calcular la hora de entrada programada.'))
        
        # Obtener zona horaria del usuario para convertir a UTC
        user_tz_name = self.env.user.tz or (self.employee_id.user_id.tz if self.employee_id and self.employee_id.user_id else None) or 'America/Tegucigalpa'
        user_tz = pytz.timezone(user_tz_name)
        
        # Localizar los datetimes en la zona horaria del usuario
        check_in_local_tz = user_tz.localize(expected_check_in)
        check_out_local_tz = user_tz.localize(expected_check_out) if expected_check_out else None
        
        # Convertir a UTC para almacenar en la base de datos
        check_in_utc = check_in_local_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        check_out_utc = check_out_local_tz.astimezone(pytz.UTC).replace(tzinfo=None) if check_out_local_tz else False
        
        # Actualizar campos
        self.write({
            'check_in_schedule': check_in_utc,
            'check_out_schedule': check_out_utc
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Horario Actualizado'),
                'message': _('Horario de trabajo actualizado:\nEntrada: %s\nSalida: %s') % (
                    expected_check_in.strftime('%d/%m/%Y %H:%M:%S'),
                    expected_check_out.strftime('%d/%m/%Y %H:%M:%S') if expected_check_out else _('No definida')
                ),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_calculate_extra_hours(self):
        """Calcular horas extra desde la asistencia (solo cálculo, sin crear solicitud)"""
        self.ensure_one()
        
        if not self.check_in or not self.check_out:
            raise UserError(_('La asistencia debe tener hora de entrada y salida para calcular horas extra.'))
        
        # Calcular horas extra sin crear solicitud
        result = self._calculate_extra_hours_only()
        
        if not result or result['total'] == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Información'),
                    'message': _('No se detectaron horas extra para esta asistencia.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Verificar si ya existe una solicitud para actualizar
        existing_request = self.env['hr.extra.hours.request'].search([
            ('attendance_id', '=', self.id)
        ], limit=1)
        
        if existing_request:
            # Si ya existe, actualizar con los valores calculados
            existing_request.write({
                'hours_25': result['hours_25'],
                'hours_50': result['hours_50'],
                'hours_75': result['hours_75'],
                'hours_100': result['hours_100'],
            })
            # Forzar recálculo de campos computed
            existing_request._compute_payable_hours()
            existing_request._compute_overtime_hours()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Horas Extra Calculadas'),
                    'message': _('Horas extra calculadas: 25%%=%.2f, 50%%=%.2f, 75%%=%.2f, Domingo=%.2f, Total=%.2f') % (
                        result['hours_25'], result['hours_50'], result['hours_75'], result['hours_100'], result['total']
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Si no existe solicitud, solo mostrar el resultado
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Horas Extra Calculadas'),
                    'message': _('Horas extra calculadas: 25%%=%.2f, 50%%=%.2f, 75%%=%.2f, Domingo=%.2f, Total=%.2f\n\nNota: No se creó solicitud automática.') % (
                        result['hours_25'], result['hours_50'], result['hours_75'], result['hours_100'], result['total']
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
    
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
        
        # Detectar día de la semana
        date_local = check_in_local.date()
        weekday = date_local.weekday()  # 0=Lunes, 5=Sábado, 6=Domingo
        is_saturday = weekday == 5
        is_sunday = weekday == 6
        
        # Obtener turno del empleado y es_mecanico del contrato
        shift_period = self.employee_id.current_shift_period  # 'dia' o 'noche'
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'open'),
            ('date_start', '<=', date_local),
            '|', ('date_end', '=', False), ('date_end', '>=', date_local)
        ], limit=1)
        es_mecanico = contract.es_mecanico if contract else False
        
        # Calcular duración total trabajada
        total_worked_hours = (check_out_local - check_in_local).total_seconds() / 3600
        
        # Crear expected_schedule con valores locales
        expected_check_in_local = self._convert_to_local_timezone(expected_schedule['check_in']) if expected_schedule.get('check_in') else None
        expected_check_out_local = self._convert_to_local_timezone(expected_schedule['check_out']) if expected_schedule.get('check_out') else None
        
        # Inicializar variables
        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        hours_100 = 0.0
        extra_hours_type = False
        
        # LÓGICA SEGÚN DÍA DE LA SEMANA (igual que _detect_extra_hours)
        if is_sunday:
            # DOMINGO: Todas las horas trabajadas son extra al 100%
            hours_100 = total_worked_hours
            extra_hours_type = 'late' if check_out_local > expected_check_out_local else 'early'
            duration = total_worked_hours
        elif is_saturday:
            # SÁBADO: Todas las horas trabajadas son extra
            if es_mecanico:
                hours_50 = total_worked_hours
            else:
                hours_25 = total_worked_hours
            extra_hours_type = 'late' if check_out_local > expected_check_out_local else 'early'
            duration = total_worked_hours
        else:
            # DÍAS LABORALES (L-V): Calcular horas extra según exceso del horario diario
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
            
            # Calcular horas por rangos según turno
            if extra_hours_type == 'early':
                # Entrada anticipada: NO cuenta como extra por defecto
                hours_25 = 0.0
                hours_50 = 0.0
                hours_75 = 0.0
            elif extra_hours_type == 'late':
                # Salida tardía: aplicar rangos según turno
                start_time = expected_check_out_local
                end_time = check_out_local
                hours_25, hours_50, hours_75 = self._calculate_overtime_hours_by_ranges(
                    start_time, end_time, shift_period, calendar, date_local
                )
            elif extra_hours_type == 'both':
                # Para 'both', calcular por separado entrada anticipada y salida tardía
                early_start = check_in_local
                early_end = expected_check_in_local
                late_start = expected_check_out_local
                late_end = check_out_local
                
                # Entrada anticipada: NO cuenta como extra por defecto
                hours_25_early = 0.0
                hours_50_early = 0.0
                hours_75_early = 0.0
                
                # Salida tardía: aplicar rangos según turno
                hours_25_late, hours_50_late, hours_75_late = self._calculate_overtime_hours_by_ranges(
                    late_start, late_end, shift_period, calendar, date_local
                )
                
                hours_25 = hours_25_early + hours_25_late
                hours_50 = hours_50_early + hours_50_late
                hours_75 = hours_75_early + hours_75_late
        
        # Actualizar la solicitud con las horas calculadas
        total_extra_hours = hours_25 + hours_50 + hours_75 + hours_100
        _logger.info('Horas extra calculadas - 25%%: %.2f, 50%%: %.2f, 75%%: %.2f, Domingo (100%%): %.2f, Total: %.2f',
                    hours_25, hours_50, hours_75, hours_100, total_extra_hours)
        
        request.write({
            'hours_25': hours_25,
            'hours_50': hours_50,
            'hours_75': hours_75,
            'hours_100': hours_100,
            'payable_hours': total_extra_hours,
        })
        
        # Refrescar la solicitud para que se actualicen los campos computed
        request.invalidate_recordset(['hours_normal', 'expected_check_in', 'expected_check_out'])
        request._compute_expected_schedule()
        request._compute_hours_normal()
        
        # Refrescar la asistencia para que se actualicen los campos relacionados
        # Los campos relacionados se actualizarán automáticamente cuando se recargue la vista
        self.invalidate_recordset(['hours_normal', 'hours_25', 'hours_50', 'hours_75', 'hours_100', 'total_extra_hours', 'payable_hours'])
        
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
        final_hours_100 = hours_100
        final_total_extra = final_hours_25 + final_hours_50 + final_hours_75 + final_hours_100
        
        message = _('Las horas han sido recalculadas correctamente.\n\n'
                   'Horas Normales: %.2f\n'
                   'Horas 25%%: %.2f\n'
                   'Horas 50%%: %.2f\n'
                   'Horas 75%%: %.2f\n'
                   'Horas Domingo (100%%): %.2f\n'
                   'Total Horas Extra: %.2f\n\n'
                   '%s') % (
            final_hours_normal,
            final_hours_25,
            final_hours_50,
            final_hours_75,
            final_hours_100,
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
