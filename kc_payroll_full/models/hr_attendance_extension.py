# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta, time
import logging
import pytz

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    """Extender hr.attendance para calcular horas extra directamente"""
    _inherit = 'hr.attendance'

    # Campos de horas extra
    hours_25 = fields.Float(
        string='HE 25%',
        compute='_compute_overtime_hours',
        store=True,
        help='Horas extra al 25%'
    )
    hours_50 = fields.Float(
        string='HE 50%',
        compute='_compute_overtime_hours',
        store=True,
        help='Horas extra al 50%'
    )
    hours_75 = fields.Float(
        string='HE 75%',
        compute='_compute_overtime_hours',
        store=True,
        help='Horas extra al 75%'
    )
    sunday_hours = fields.Float(
        string='Horas Domingo',
        compute='_compute_overtime_hours',
        store=True,
        help='Horas trabajadas en domingo (se pagan al doble)'
    )

    # Campos de diferencias con horario
    check_in_schedule = fields.Datetime(
        string='Entrada según Horario',
        help='Hora de entrada según el horario del empleado'
    )
    check_out_schedule = fields.Datetime(
        string='Salida según Horario',
        help='Hora de salida según el horario del empleado'
    )
    check_in_difference = fields.Float(
        string='Diferencia Entrada (horas)',
        compute='_compute_schedule_differences',
        store=True,
        help='Diferencia en horas entre entrada real y entrada programada. '
             'Negativo = entrada temprana, Positivo = entrada tardía'
    )
    check_out_difference = fields.Float(
        string='Diferencia Salida (horas)',
        compute='_compute_schedule_differences',
        store=True,
        help='Diferencia en horas entre salida real y salida programada. '
             'Positivo = salida tardía'
    )

    # Campos para entrada temprana como horas extra
    count_early_check_in_overtime = fields.Boolean(
        string="Contar Entrada Temprana como HE",
        default=False,
        help="Marcar para contar las horas de entrada temprana (antes del horario) como horas extra."
    )
    early_check_in_overtime_rate = fields.Selection([
        ('25', '25%'),
        ('50', '50%'),
        ('75', '75%'),
    ], string="Tasa HE Entrada Temprana", default='25',
        help="Tasa a aplicar a las horas extra por entrada temprana.")

    # Campos auxiliares
    is_sunday = fields.Boolean(
        string='Es Domingo',
        compute='_compute_is_sunday',
        store=True
    )
    is_saturday = fields.Boolean(
        string='Es Sábado',
        compute='_compute_is_saturday',
        store=True
    )
    is_night_shift = fields.Boolean(
        string='Es Turno Nocturno',
        compute='_compute_is_night_shift',
        store=True
    )

    @api.depends('check_in')
    def _compute_is_sunday(self):
        for record in self:
            if record.check_in:
                record.is_sunday = record.check_in.weekday() == 6
            else:
                record.is_sunday = False

    @api.depends('check_in')
    def _compute_is_saturday(self):
        for record in self:
            if record.check_in:
                record.is_saturday = record.check_in.weekday() == 5
            else:
                record.is_saturday = False

    @api.depends('employee_id', 'check_in')
    def _compute_is_night_shift(self):
        for record in self:
            if record.employee_id and record.employee_id.resource_calendar_id:
                record.is_night_shift = record.employee_id.resource_calendar_id.nocturna
            else:
                record.is_night_shift = False

    @api.depends('check_in', 'check_out', 'check_in_schedule', 'check_out_schedule')
    def _compute_schedule_differences(self):
        for record in self:
            check_in_diff = 0.0
            check_out_diff = 0.0

            if record.check_in and record.check_in_schedule:
                delta = record.check_in - record.check_in_schedule
                check_in_diff = delta.total_seconds() / 3600.0

            if record.check_out and record.check_out_schedule:
                delta = record.check_out - record.check_out_schedule
                check_out_diff = delta.total_seconds() / 3600.0

            record.check_in_difference = check_in_diff
            record.check_out_difference = check_out_diff

    def action_update_schedule_times(self):
        """Actualizar check_in_schedule y check_out_schedule basado en el horario del empleado"""
        for record in self:
            _logger.info("=== ACTUALIZAR HORARIOS ===")
            _logger.info("Empleado: %s (ID: %s)", record.employee_id.name if record.employee_id else 'N/A', record.employee_id.id if record.employee_id else 'N/A')
            _logger.info("Asistencia ID: %s", record.id)
            _logger.info("Check-in real: %s", record.check_in)
            _logger.info("Check-out real: %s", record.check_out)
            
            if not record.employee_id or not record.check_in:
                _logger.warning("No se puede actualizar: falta empleado o check-in")
                continue

            schedule = record._get_expected_schedule()
            if schedule:
                record.check_in_schedule = schedule.get('check_in')
                record.check_out_schedule = schedule.get('check_out')
                _logger.info("Check-in programado: %s", record.check_in_schedule)
                _logger.info("Check-out programado: %s", record.check_out_schedule)
            else:
                _logger.warning("No se encontró horario programado para este empleado")

    def action_recalculate_overtime_hours(self):
        """Recalcular horas extra y actualizar horarios programados"""
        self.ensure_one()
        _logger.info("=== RECALCULAR HORAS EXTRA ===")
        _logger.info("Empleado: %s (ID: %s)", self.employee_id.name, self.employee_id.id)
        _logger.info("Asistencia ID: %s", self.id)
        _logger.info("Check-in: %s, Check-out: %s", self.check_in, self.check_out)
        _logger.info("Es domingo: %s, Es sábado: %s, Es nocturno: %s", 
                    self.is_sunday, self.is_saturday, self.is_night_shift)
        
        # Actualizar horarios programados primero
        _logger.info("Paso 1: Actualizando horarios programados...")
        self.action_update_schedule_times()

        # Forzar recálculo de diferencias
        _logger.info("Paso 2: Calculando diferencias con horario...")
        self._compute_schedule_differences()
        _logger.info("Diferencia entrada: %.2f horas, Diferencia salida: %.2f horas",
                    self.check_in_difference, self.check_out_difference)
        
        # Forzar recálculo de horas extra
        _logger.info("Paso 3: Calculando horas extra...")
        self._compute_overtime_hours()
        _logger.info("Horas calculadas - HE25: %.2f, HE50: %.2f, HE75: %.2f, Domingo: %.2f",
                    self.hours_25, self.hours_50, self.hours_75, self.sunday_hours)
        
        # Invalidar campos para que se recalculen
        self.invalidate_recordset(['hours_25', 'hours_50', 'hours_75', 'sunday_hours',
                                   'check_in_difference', 'check_out_difference'])
        
        # Mostrar mensaje de confirmación
        message = _('Horas extra recalculadas correctamente.\n\n'
                   'HE 25%%: %.2f horas\n'
                   'HE 50%%: %.2f horas\n'
                   'HE 75%%: %.2f horas\n'
                   'Horas Domingo: %.2f horas') % (
            self.hours_25,
            self.hours_50,
            self.hours_75,
            self.sunday_hours
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Horas Extra Recalculadas'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_expected_schedule(self):
        """Obtener el horario esperado para esta asistencia"""
        self.ensure_one()
        if not self.employee_id or not self.check_in:
            _logger.warning("_get_expected_schedule: falta empleado o check-in")
            return None

        employee = self.employee_id
        calendar = employee.resource_calendar_id
        if not calendar:
            _logger.warning("_get_expected_schedule: empleado %s no tiene calendario", employee.name)
            return None
        
        # Convertir check_in a zona horaria local
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')
        check_in_utc = self.check_in.replace(tzinfo=pytz.UTC)
        check_in_local = check_in_utc.astimezone(user_tz)
        weekday = check_in_local.weekday()
        
        _logger.info("_get_expected_schedule: Calendario: %s, Nocturno: %s, Semanal: %s", 
                    calendar.name, calendar.nocturna, calendar.es_nomina_semanal)
        _logger.info("_get_expected_schedule: Check-in local: %s, Weekday: %s", check_in_local, weekday)

        # Buscar horario para este día
        attendances = calendar.attendance_ids.filtered(
            lambda x: int(x.dayofweek) == weekday
        )
        
        # Guardar el weekday original para casos especiales (sábado/domingo)
        original_weekday = weekday
        _logger.info("_get_expected_schedule: Encontradas %d líneas de horario para weekday %s", len(attendances), weekday)
        
        if not attendances:
            # Si no hay horario para este día, buscar el más cercano
            # Para turnos nocturnos, preferir buscar hacia atrás (día anterior)
            # porque los turnos nocturnos suelen tener horario el día anterior
            if calendar.nocturna:
                # Buscar primero hacia atrás
                for i in range(1, 7):
                    prev_day = (weekday - i) % 7
                    prev_attendances = calendar.attendance_ids.filtered(
                        lambda x: int(x.dayofweek) == prev_day
                    )
                    if prev_attendances:
                        attendances = prev_attendances
                        weekday = prev_day  # Actualizar weekday para buscar el día siguiente correcto
                        _logger.info("_get_expected_schedule: No hay horario para weekday %s, usando horario del día anterior %s", 
                                    original_weekday, prev_day)
                        break
                # Si no encontramos hacia atrás, buscar hacia adelante
                if not attendances:
                    for i in range(1, 7):
                        next_day = (original_weekday + i) % 7
                        next_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == next_day
                        )
                        if next_attendances:
                            attendances = next_attendances
                            weekday = next_day
                            break
            else:
                # Para turnos diurnos, buscar el más cercano
                for i in range(1, 7):
                    next_day = (weekday + i) % 7
                    prev_day = (weekday - i) % 7
                    next_attendances = calendar.attendance_ids.filtered(
                        lambda x: int(x.dayofweek) == next_day
                    )
                    prev_attendances = calendar.attendance_ids.filtered(
                        lambda x: int(x.dayofweek) == prev_day
                    )
                    if next_attendances:
                        attendances = next_attendances
                        weekday = next_day
                        break
                    if prev_attendances:
                        attendances = prev_attendances
                        weekday = prev_day
                        break
        
        if not attendances:
            return None

        # Para turnos nocturnos, agrupar por shift_group
        if calendar.nocturna:
            _logger.info("_get_expected_schedule: Es turno nocturno, agrupando por shift_group")
            # Buscar grupos de turnos del día actual
            shift_groups = {}
            for att in attendances:
                group = att.shift_group or 'default'
                if group not in shift_groups:
                    shift_groups[group] = []
                shift_groups[group].append(att)
            _logger.info("_get_expected_schedule: Encontrados %d grupos de turnos: %s", 
                        len(shift_groups), list(shift_groups.keys()))

            # Identificar el grupo de turno correcto
            # Para turnos nocturnos que cruzan medianoche, necesitamos:
            # 1. Línea de tarde/noche del día actual (ej: 18:00-24:00)
            # 2. Línea de madrugada del día siguiente (ej: 00:00-06:00) con el mismo shift_group
            target_group = None
            first_attendance = None
            last_attendance = None

            # Buscar en cada grupo del día actual
            for group, atts in shift_groups.items():
                sorted_atts = sorted(atts, key=lambda x: x.hour_from)
                
                # Buscar línea de tarde/noche (que empieza alrededor de las 18:00 o termina en 24:00)
                evening_line = None
                # Primero buscar líneas que empiecen específicamente alrededor de las 18:00 (16:00-20:00)
                for att in sorted_atts:
                    if 16.0 <= att.hour_from <= 20.0:
                        evening_line = att
                        break
                # Si no encontramos, buscar líneas que terminen en 24:00 o crucen medianoche
                if not evening_line:
                    for att in sorted_atts:
                        if att.hour_to >= 24.0 or (att.hour_to < att.hour_from and att.hour_from >= 16.0):
                            evening_line = att
                            break
                # Si aún no encontramos, buscar cualquier línea que empiece después de las 16:00
                if not evening_line:
                    for att in sorted_atts:
                        if att.hour_from >= 16.0:
                            evening_line = att
                            break
                # Si no encontramos línea de tarde, usar la última línea del día
                if not evening_line and sorted_atts:
                    evening_line = sorted_atts[-1]
                
                if evening_line:
                    # Buscar línea de madrugada del día siguiente con el mismo shift_group
                    # Si encontramos horario del día anterior (weekday != original_weekday),
                    # buscar primero la línea de mañana del día siguiente del weekday encontrado
                    # (ej: si weekday=viernes, buscar sábado)
                    # Si no encontramos, buscar el día siguiente del check_in original
                    found_morning_line = False
                    
                    # Primero: Si weekday != original_weekday, buscar línea de mañana del día siguiente del weekday encontrado
                    if weekday != original_weekday:
                        next_day_from_found = (weekday + 1) % 7
                        next_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == next_day_from_found and (x.shift_group or 'default') == group
                        )
                        if next_attendances:
                            morning_att = next_attendances.filtered(lambda x: x.hour_from <= 8.0)
                            if morning_att:
                                morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                target_group = group
                                first_attendance = evening_line
                                last_attendance = morning_sorted[0]
                                found_morning_line = True
                                _logger.info("_get_expected_schedule: Encontrado grupo %s (día anterior %s->%s) - Línea tarde: %s-%s, Línea mañana: %s-%s",
                                            group, weekday, next_day_from_found, evening_line.hour_from, evening_line.hour_to,
                                            last_attendance.hour_from, last_attendance.hour_to)
                    
                    # Segundo: Si no encontramos, buscar línea de mañana del día siguiente del check_in original
                    if not found_morning_line:
                        next_day_from_check_in = (original_weekday + 1) % 7
                        next_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == next_day_from_check_in and (x.shift_group or 'default') == group
                        )
                        
                        if next_attendances:
                            # Buscar línea de madrugada (00:00-06:00)
                            morning_att = next_attendances.filtered(lambda x: x.hour_from <= 8.0)
                            if morning_att:
                                # Ordenar por hour_from y tomar la primera (normalmente 00:00)
                                morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                target_group = group
                                first_attendance = evening_line
                                last_attendance = morning_sorted[0]
                                found_morning_line = True
                                _logger.info("_get_expected_schedule: Encontrado grupo %s - Línea tarde: %s-%s, Línea mañana: %s-%s",
                                            group, evening_line.hour_from, evening_line.hour_to,
                                            last_attendance.hour_from, last_attendance.hour_to)
                    
                    if found_morning_line:
                        break
                    
                    # Si no encontramos en el día siguiente inmediato, buscar en días siguientes
                    # Caso especial: Si el check_in es sábado y encontramos horario del viernes,
                    # la línea de mañana debería estar en el sábado (día siguiente del viernes)
                    # pero si el sábado no tiene horario, buscar en el domingo
                    # Para sábado->domingo, si domingo no tiene horario, buscar en lunes
                    # Para domingo->lunes, si lunes no tiene horario, buscar en martes
                    for i in range(1, 4):  # Buscar hasta 3 días adelante
                        search_day = (original_weekday + i) % 7
                        search_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == search_day and (x.shift_group or 'default') == group
                        )
                        if search_attendances:
                            morning_att = search_attendances.filtered(lambda x: x.hour_from <= 8.0)
                            if morning_att:
                                morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                target_group = group
                                first_attendance = evening_line
                                last_attendance = morning_sorted[0]
                                _logger.info("_get_expected_schedule: Encontrado grupo %s en día %s - Línea tarde: %s-%s, Línea mañana: %s-%s",
                                            group, search_day, evening_line.hour_from, evening_line.hour_to,
                                            last_attendance.hour_from, last_attendance.hour_to)
                                break
                    if target_group:
                        break
                    
                    # Caso especial: Si encontramos horario del día anterior (ej: viernes cuando check_in es sábado)
                    # y no encontramos línea de mañana del día siguiente, buscar la línea de mañana
                    # del día siguiente del weekday encontrado (ej: sábado si weekday=viernes)
                    if weekday != original_weekday:
                        next_day_from_found = (weekday + 1) % 7
                        next_attendances_from_found = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == next_day_from_found and (x.shift_group or 'default') == group
                        )
                        if next_attendances_from_found:
                            morning_att = next_attendances_from_found.filtered(lambda x: x.hour_from <= 8.0)
                            if morning_att:
                                morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                target_group = group
                                first_attendance = evening_line
                                last_attendance = morning_sorted[0]
                                _logger.info("_get_expected_schedule: Encontrado grupo %s (día anterior) - Línea tarde: %s-%s, Línea mañana: %s-%s",
                                            group, evening_line.hour_from, evening_line.hour_to,
                                            last_attendance.hour_from, last_attendance.hour_to)
                                break
            
            # Si no encontramos un grupo con línea de mañana, usar el primero disponible
            if not target_group and shift_groups:
                target_group = list(shift_groups.keys())[0]
                atts = shift_groups[target_group]
                sorted_atts = sorted(atts, key=lambda x: x.hour_from)
                
                # Buscar línea de tarde/noche
                evening_line = None
                for att in sorted_atts:
                    if att.hour_from >= 16.0 or att.hour_to >= 24.0:
                        evening_line = att
                        break
                if not evening_line and sorted_atts:
                    evening_line = sorted_atts[-1]
                
                first_attendance = evening_line if evening_line else sorted_atts[0]
                
                # Buscar línea de mañana en el día siguiente con el mismo shift_group
                # Usar el día siguiente del check_in original, no del weekday encontrado
                next_day_from_check_in = (original_weekday + 1) % 7
                next_attendances = calendar.attendance_ids.filtered(
                    lambda x: int(x.dayofweek) == next_day_from_check_in and (x.shift_group or 'default') == target_group
                )
                if next_attendances:
                    morning_att = next_attendances.filtered(lambda x: x.hour_from <= 8.0)
                    if morning_att:
                        morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                        last_attendance = morning_sorted[0]
                    else:
                        # Buscar en días siguientes
                        for i in range(1, 4):
                            search_day = (original_weekday + i) % 7
                            search_attendances = calendar.attendance_ids.filtered(
                                lambda x: int(x.dayofweek) == search_day and (x.shift_group or 'default') == target_group
                            )
                            if search_attendances:
                                morning_att = search_attendances.filtered(lambda x: x.hour_from <= 8.0)
                                if morning_att:
                                    morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                    last_attendance = morning_sorted[0]
                                    break
                        if not last_attendance:
                            last_attendance = sorted_atts[-1]
                else:
                    # Buscar en días siguientes si no hay horario del día siguiente
                    for i in range(1, 4):
                        search_day = (original_weekday + i) % 7
                        search_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == search_day and (x.shift_group or 'default') == target_group
                        )
                        if search_attendances:
                            morning_att = search_attendances.filtered(lambda x: x.hour_from <= 8.0)
                            if morning_att:
                                morning_sorted = sorted(morning_att, key=lambda x: x.hour_from)
                                last_attendance = morning_sorted[0]
                                break
                    if not last_attendance:
                        last_attendance = sorted_atts[-1]
        else:
            # Turno diurno: usar el primero y último
            sorted_attendances = sorted(attendances, key=lambda x: x.hour_from)
            first_attendance = sorted_attendances[0]
            last_attendance = sorted_attendances[-1]

        if not first_attendance or not last_attendance:
            _logger.warning("_get_expected_schedule: No se encontraron first_attendance o last_attendance")
            return None

        _logger.info("_get_expected_schedule: first_attendance - dayofweek: %s, hour_from: %s, hour_to: %s, shift_group: %s",
                    first_attendance.dayofweek, first_attendance.hour_from, first_attendance.hour_to, first_attendance.shift_group)
        _logger.info("_get_expected_schedule: last_attendance - dayofweek: %s, hour_from: %s, hour_to: %s, shift_group: %s",
                    last_attendance.dayofweek, last_attendance.hour_from, last_attendance.hour_to, last_attendance.shift_group)

        # Construir fechas de check_in y check_out esperadas
        check_in_date = check_in_local.date()
        check_out_date = check_in_date

        # Hora de entrada esperada
        hour_from = int(first_attendance.hour_from)
        minute_from = int((first_attendance.hour_from - hour_from) * 60)
        check_in_time = time(hour_from, minute_from)
        check_in_schedule_local = datetime.combine(check_in_date, check_in_time)
        check_in_schedule_utc = user_tz.localize(check_in_schedule_local).astimezone(pytz.UTC).replace(tzinfo=None)
        _logger.info("_get_expected_schedule: check_in_schedule calculado: %s (local: %s)", 
                    check_in_schedule_utc, check_in_schedule_local)

        # Hora de salida esperada
        hour_to_float = last_attendance.hour_to
        
        # Determinar si last_attendance viene del día siguiente
        # Para turnos nocturnos, si encontramos last_attendance del día siguiente, siempre es del día siguiente
        last_attendance_from_next_day = False
        if calendar.nocturna:
            # Verificar si last_attendance es del día siguiente comparando dayofweek
            # Usar original_weekday (día del check_in) para comparar
            last_attendance_day = int(last_attendance.dayofweek)
            if last_attendance_day != original_weekday:
                # Si el día de last_attendance es diferente al día de check_in, verificar si es el día siguiente
                # Para casos especiales: sábado(5)->domingo(6), domingo(6)->lunes(0)
                expected_next_day = (original_weekday + 1) % 7
                if last_attendance_day == expected_next_day:
                    last_attendance_from_next_day = True
                # También considerar si está en días siguientes (hasta 3 días adelante)
                elif last_attendance_day in [(original_weekday + i) % 7 for i in range(1, 4)]:
                    last_attendance_from_next_day = True
        
        # Si hour_to es 24 o mayor, es medianoche del día siguiente
        if hour_to_float >= 24.0:
            hour_to = 0
            minute_to = int((hour_to_float - 24.0) * 60)
            check_out_date = check_in_date + timedelta(days=1)
        else:
            hour_to = int(hour_to_float)
            minute_to = int((hour_to_float - hour_to) * 60)
            # Si last_attendance viene del día siguiente, check_out_date debe ser del día siguiente
            if last_attendance_from_next_day:
                check_out_date = check_in_date + timedelta(days=1)
            # Si hour_to < hour_from, es un turno que cruza medianoche
            elif hour_to < hour_from or (hour_to == hour_from and minute_to < minute_from):
                check_out_date = check_in_date + timedelta(days=1)
        else:
                check_out_date = check_in_date

        # Validar que hour_to esté en rango válido (0-23)
        if hour_to < 0:
            hour_to = 0
        elif hour_to > 23:
            hour_to = 23
            minute_to = 59

        check_out_time = time(hour_to, minute_to)
        check_out_schedule_local = datetime.combine(check_out_date, check_out_time)
        check_out_schedule_utc = user_tz.localize(check_out_schedule_local).astimezone(pytz.UTC).replace(tzinfo=None)
        _logger.info("_get_expected_schedule: check_out_schedule calculado: %s (local: %s, fecha: %s)", 
                    check_out_schedule_utc, check_out_schedule_local, check_out_date)
        
        return {
            'check_in': check_in_schedule_utc,
            'check_out': check_out_schedule_utc
        }

    @api.depends('check_in', 'check_out', 'employee_id', 'check_in_difference', 
                 'check_out_difference', 'count_early_check_in_overtime', 
                 'early_check_in_overtime_rate', 'is_sunday', 'is_saturday', 'is_night_shift')
    def _compute_overtime_hours(self):
        """Calcular horas extra según diferentes escenarios"""
        for record in self:
            _logger.info("=== _compute_overtime_hours ===")
            _logger.info("Asistencia ID: %s, Empleado: %s", record.id, record.employee_id.name if record.employee_id else 'N/A')
            _logger.info("Check-in: %s, Check-out: %s", record.check_in, record.check_out)
            _logger.info("Es domingo: %s, Es sábado: %s, Es nocturno: %s", 
                        record.is_sunday, record.is_saturday, record.is_night_shift)
            
            # Inicializar valores
            record.hours_25 = 0.0
            record.hours_50 = 0.0
            record.hours_75 = 0.0
            record.sunday_hours = 0.0

            if not record.check_in or not record.check_out:
                _logger.warning("_compute_overtime_hours: Falta check-in o check-out")
                continue

            if not record.employee_id:
                _logger.warning("_compute_overtime_hours: Falta empleado")
                continue

            # Si es domingo, calcular horas de domingo
            if record.is_sunday:
                delta = record.check_out - record.check_in
                record.sunday_hours = delta.total_seconds() / 3600.0
                _logger.info("_compute_overtime_hours: Es domingo, horas domingo: %.2f", record.sunday_hours)
                # Las horas de domingo no se cuentan en HE25
                continue

            # Si es sábado sin horario configurado, todo es HE25
            if record.is_saturday:
                calendar = record.employee_id.resource_calendar_id
                if calendar:
                    weekday = record.check_in.weekday()
                    saturday_attendances = calendar.attendance_ids.filtered(
                        lambda x: int(x.dayofweek) == weekday
                    )
                    if not saturday_attendances:
                        # No hay horario para sábado, todo es HE25
                        delta = record.check_out - record.check_in
                        record.hours_25 = delta.total_seconds() / 3600.0
                        _logger.info("_compute_overtime_hours: Sábado sin horario, todo HE25: %.2f", record.hours_25)
                        continue

            # Calcular horas trabajadas
            delta = record.check_out - record.check_in
            worked_hours = delta.total_seconds() / 3600.0
            _logger.info("_compute_overtime_hours: Horas trabajadas: %.2f", worked_hours)

            # Si es turno nocturno
            if record.is_night_shift:
                _logger.info("_compute_overtime_hours: Procesando turno nocturno")
                # Obtener el horario esperado que ya usa shift_group
                schedule = record._get_expected_schedule()
                if not schedule:
                    _logger.warning("_compute_overtime_hours: No se encontró horario para turno nocturno")
                    # Si no hay horario, no calcular horas extra
                    continue

                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                check_in_utc = record.check_in.replace(tzinfo=pytz.UTC)
                check_in_local = check_in_utc.astimezone(user_tz)
                check_out_utc = record.check_out.replace(tzinfo=pytz.UTC)
                check_out_local = check_out_utc.astimezone(user_tz)
                _logger.info("_compute_overtime_hours: check_in_local: %s, check_out_local: %s", 
                            check_in_local, check_out_local)

                # Obtener el calendario y las líneas de horario agrupadas por shift_group
                calendar = record.employee_id.resource_calendar_id
                if not calendar:
                    continue

                weekday = check_in_local.weekday()
                original_weekday = weekday
                attendances = calendar.attendance_ids.filtered(
                    lambda x: int(x.dayofweek) == weekday
                )

                # Si no hay horario para este día, buscar el más cercano
                if not attendances:
                    for i in range(1, 7):
                        next_day = (weekday + i) % 7
                        prev_day = (weekday - i) % 7
                        next_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == next_day
                        )
                        prev_attendances = calendar.attendance_ids.filtered(
                            lambda x: int(x.dayofweek) == prev_day
                        )
                        if next_attendances:
                            attendances = next_attendances
                            weekday = next_day
                            break
                        if prev_attendances:
                            attendances = prev_attendances
                            weekday = prev_day
                            break

                if not attendances:
                    continue

                # Agrupar por shift_group para turnos nocturnos
                # IMPORTANTE: Para turnos nocturnos, también buscar líneas del día siguiente
                shift_groups = {}
                for att in attendances:
                    group = att.shift_group or 'default'
                    if group not in shift_groups:
                        shift_groups[group] = []
                    shift_groups[group].append(att)
                
                # Buscar líneas del día siguiente con el mismo shift_group
                next_day = (original_weekday + 1) % 7
                next_attendances = calendar.attendance_ids.filtered(
                    lambda x: int(x.dayofweek) == next_day
                )
                for att in next_attendances:
                    group = att.shift_group or 'default'
                    # Solo agregar si el grupo ya existe (mismo shift_group)
                    if group in shift_groups:
                        shift_groups[group].append(att)
                        _logger.info("_compute_overtime_hours: Agregada línea del día siguiente al grupo %s: dayofweek=%s, hour_from=%s, hour_to=%s",
                                    group, att.dayofweek, att.hour_from, att.hour_to)
                _logger.info("_compute_overtime_hours: Agrupados %d grupos de turnos nocturnos: %s", 
                            len(shift_groups), list(shift_groups.keys()))

                # Encontrar el grupo de turno que corresponde a esta asistencia
                # Para turnos nocturnos, buscar el grupo que tiene líneas que cruzan medianoche
                target_group = None
                for group, atts in shift_groups.items():
                    sorted_atts = sorted(atts, key=lambda x: x.hour_from)
                    # Verificar si este grupo tiene líneas que cruzan medianoche
                    for att in sorted_atts:
                        if att.hour_to < att.hour_from or att.hour_to <= 8.0:
                            # Este grupo cruza medianoche
                            target_group = group
                            _logger.info("_compute_overtime_hours: Encontrado grupo que cruza medianoche: %s", group)
                            break
                    if target_group:
                        break

                # Si no encontramos un grupo que cruza medianoche, usar el primero
                if not target_group and shift_groups:
                    target_group = list(shift_groups.keys())[0]
                    _logger.info("_compute_overtime_hours: Usando primer grupo disponible: %s", target_group)

                if target_group and target_group in shift_groups:
                    group_attendances = sorted(shift_groups[target_group], key=lambda x: x.hour_from)
                    _logger.info("_compute_overtime_hours: Grupo seleccionado %s tiene %d líneas", 
                                target_group, len(group_attendances))
                    
                    # Identificar las líneas del turno
                    # Primera línea: del día actual (ej: 18:00 a 00:00 o 24:00)
                    # Segunda línea: del día siguiente (ej: 00:00 a 06:00) - esta es HE75
                    first_line = None
                    second_line = None
                    
                    # Buscar línea de tarde/noche (del día actual, original_weekday)
                    for att in group_attendances:
                        if int(att.dayofweek) == original_weekday and (att.hour_from >= 16.0 or att.hour_to >= 24.0):
                            first_line = att
                            _logger.info("_compute_overtime_hours: Primera línea encontrada: dayofweek=%s, hour_from=%s, hour_to=%s",
                                        att.dayofweek, att.hour_from, att.hour_to)
                            break
                    
                    # Si no encontramos primera línea, usar la primera del grupo del día actual
                    if not first_line:
                        for att in group_attendances:
                            if int(att.dayofweek) == original_weekday:
                                first_line = att
                                break
                        # Si aún no encontramos, usar la primera del grupo
                        if not first_line and group_attendances:
                            first_line = group_attendances[0]
                    
                    # Buscar línea de madrugada (del día siguiente, next_day, hour_from <= 8.0)
                    for att in group_attendances:
                        # La segunda línea debe ser del día siguiente y empezar temprano (00:00-08:00)
                        if int(att.dayofweek) == next_day and att.hour_from <= 8.0:
                            second_line = att
                            _logger.info("_compute_overtime_hours: Segunda línea encontrada: dayofweek=%s, hour_from=%s, hour_to=%s",
                                        att.dayofweek, att.hour_from, att.hour_to)
                            break
                    
                    # Si hay segunda línea, calcular HE75 desde su hour_from hasta su hour_to
                    if second_line:
                        _logger.info("_compute_overtime_hours: Segunda línea encontrada - hour_from: %s, hour_to: %s",
                                    second_line.hour_from, second_line.hour_to)
                        # Obtener la hora de inicio de HE75 (normalmente 00:00)
                        he75_start_hour = int(second_line.hour_from)
                        he75_start_minute = int((second_line.hour_from - he75_start_hour) * 60)
                        
                        # Obtener la hora de fin de HE75
                        he75_end_hour_float = second_line.hour_to
                        if he75_end_hour_float >= 24.0:
                            he75_end_hour = 0
                            he75_end_minute = int((he75_end_hour_float - 24.0) * 60)
                        else:
                            he75_end_hour = int(he75_end_hour_float)
                            he75_end_minute = int((he75_end_hour_float - he75_end_hour) * 60)

                        # Calcular horas trabajadas en el rango HE75
                        next_day = check_in_local.date() + timedelta(days=1)
                        he75_start_time = user_tz.localize(datetime.combine(next_day, time(he75_start_hour, he75_start_minute)))
                        he75_end_time = user_tz.localize(datetime.combine(next_day, time(he75_end_hour, he75_end_minute)))
                        _logger.info("_compute_overtime_hours: Rango HE75 - inicio: %s, fin: %s", 
                                    he75_start_time, he75_end_time)

                        # Si el check_out está dentro del rango HE75
                        if check_out_local >= he75_start_time:
                            start_he75 = max(he75_start_time, check_in_local)
                            end_he75 = min(he75_end_time, check_out_local)
                            if end_he75 > start_he75:
                                he75_delta = end_he75 - start_he75
                                record.hours_75 = he75_delta.total_seconds() / 3600.0
                                _logger.info("_compute_overtime_hours: HE75 calculado antes de restar diferencia: %.2f", record.hours_75)

                                # Restar check_in_difference de HE75 si es positivo (llegada tardía)
                                if record.check_in_difference > 0:
                                    record.hours_75 = max(0.0, record.hours_75 - record.check_in_difference)
                                    _logger.info("_compute_overtime_hours: HE75 después de restar diferencia entrada (%.2f): %.2f",
                                                record.check_in_difference, record.hours_75)
                        else:
                            _logger.info("_compute_overtime_hours: check_out (%s) no está en rango HE75", check_out_local)
                    else:
                        _logger.warning("_compute_overtime_hours: No se encontró segunda línea para turno nocturno")

                record.hours_25 = 0.0
                record.hours_50 = 0.0
                _logger.info("_compute_overtime_hours: Turno nocturno - HE25: %.2f, HE50: %.2f, HE75: %.2f",
                            record.hours_25, record.hours_50, record.hours_75)
            else:
                # Turno diurno: calcular horas extra por rangos
                _logger.info("_compute_overtime_hours: Procesando turno diurno")
                if record.check_out_difference > 0:
                    # Hay salida tardía, calcular horas extra
                    _logger.info("_compute_overtime_hours: Diferencia salida: %.2f horas", record.check_out_difference)
                    hours_25, hours_50, hours_75 = record._calculate_overtime_hours_by_ranges(
                        record.check_out_difference
                    )
                    _logger.info("_compute_overtime_hours: Horas extra por rangos - HE25: %.2f, HE50: %.2f, HE75: %.2f",
                                hours_25, hours_50, hours_75)

                    # Restar check_in_difference si es positivo (llegada tardía)
                    if record.check_in_difference > 0:
                        remaining = record.check_in_difference
                        # Restar primero de HE25
                        if hours_25 > 0:
                            if remaining >= hours_25:
                                remaining -= hours_25
                                hours_25 = 0.0
                            else:
                                hours_25 -= remaining
                                remaining = 0.0

                        # Luego de HE50
                        if remaining > 0 and hours_50 > 0:
                            if remaining >= hours_50:
                                remaining -= hours_50
                                hours_50 = 0.0
                            else:
                                hours_50 -= remaining
                                remaining = 0.0

                        # Finalmente de HE75
                        if remaining > 0 and hours_75 > 0:
                            hours_75 = max(0.0, hours_75 - remaining)

                    record.hours_25 = hours_25
                    record.hours_50 = hours_50
                    record.hours_75 = hours_75

                # Si hay entrada temprana y está marcado para contar como HE
                if record.check_in_difference < 0 and record.count_early_check_in_overtime:
                    early_hours = abs(record.check_in_difference)
                    rate = record.early_check_in_overtime_rate
                    _logger.info("_compute_overtime_hours: Entrada temprana detectada: %.2f horas, tasa: %s", early_hours, rate)
                    if rate == '25':
                        record.hours_25 += early_hours
                    elif rate == '50':
                        record.hours_50 += early_hours
                    elif rate == '75':
                        record.hours_75 += early_hours
            
            _logger.info("_compute_overtime_hours: RESULTADO FINAL - HE25: %.2f, HE50: %.2f, HE75: %.2f, Domingo: %.2f",
                        record.hours_25, record.hours_50, record.hours_75, record.sunday_hours)

    def _calculate_overtime_hours_by_ranges(self, extra_hours):
        """Calcular horas extra según rangos configurados"""
        # Obtener configuración de rangos
        try:
            config = self.env['config.overtime.hours'].search([
                ('state', '=', 'active')
            ], limit=1)
        except Exception:
            # Si no existe el modelo, retornar todo como HE25
            return (extra_hours, 0.0, 0.0)
        
        if not config:
            return (extra_hours, 0.0, 0.0)

        hours_25 = 0.0
        hours_50 = 0.0
        hours_75 = 0.0
        
        # Obtener hora actual para determinar en qué rango estamos
        if self.check_out:
            user_tz = pytz.timezone(self.env.user.tz or 'UTC')
            check_out_utc = self.check_out.replace(tzinfo=pytz.UTC)
            check_out_local = check_out_utc.astimezone(user_tz)
            current_hour = check_out_local.hour + (check_out_local.minute / 60.0)

            # Calcular horas en cada rango
            hour_25_from = float(config.hour_25_from)
            hour_25_to = float(config.hour_25_to)
            hour_50_from = float(config.hour_50_from)
            hour_50_to = float(config.hour_50_to)
            hour_75_from = float(config.hour_75_from)
            hour_75_to = float(config.hour_75_to)
            
            # Distribuir las horas extra según el rango
            if hour_25_from <= current_hour < hour_25_to:
                hours_25 = extra_hours
            elif hour_50_from <= current_hour < hour_50_to:
                hours_50 = extra_hours
            elif hour_75_from <= current_hour < hour_75_to or (hour_75_to < hour_75_from and current_hour >= hour_75_from):
                hours_75 = extra_hours
            else:
                # Por defecto, HE25
                hours_25 = extra_hours
                else:
            # Si no hay check_out, todo como HE25
            hours_25 = extra_hours
        
        return (hours_25, hours_50, hours_75)

