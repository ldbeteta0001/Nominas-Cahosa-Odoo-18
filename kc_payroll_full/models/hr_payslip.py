# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    """Extender hr.payslip para manejar horas normales limitadas a 44 horas semanales"""
    _inherit = 'hr.payslip'

    def _get_worked_day_lines_values(self, domain=None):
        """
        Sobrescribir para:
        1. Agregar horas extra (HE25, HE50, HE75, SUNDAY) desde asistencias
        2. Limitar horas normales a 44 horas semanales cuando es_nomina_semanal=True
        """
        res = super()._get_worked_day_lines_values(domain)
        
        self.ensure_one()
        contract = self.contract_id
        
        if not contract:
            return res

        # Obtener asistencias del período
        if self.date_from and self.date_to:
            attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', self.date_from),
                ('check_in', '<=', self.date_to),
        ])
        else:
            attendances = self.env['hr.attendance'].browse([])

        # Forzar recálculo de horas extra en asistencias
        if attendances:
            attendances._compute_overtime_hours()
            attendances.invalidate_recordset(['hours_25', 'hours_50', 'hours_75', 'sunday_hours'])

        # Separar asistencias de días laborables y domingos
        weekday_attendances = attendances.filtered(lambda a: not a.is_sunday)
        sunday_attendances = attendances.filtered(lambda a: a.is_sunday)

        # Sumar horas extra de días laborables
        total_hours_25 = sum(weekday_attendances.mapped('hours_25'))
        total_hours_50 = sum(weekday_attendances.mapped('hours_50'))
        total_hours_75 = sum(weekday_attendances.mapped('hours_75'))
        total_sunday_hours = sum(sunday_attendances.mapped('sunday_hours'))

        # Obtener o crear tipos de entrada de trabajo
        he25_type = self.env['hr.work.entry.type'].search([('code', '=', 'HE25')], limit=1)
        if not he25_type:
            he25_type = self.env['hr.work.entry.type'].create({
                'name': 'Horas Extra 25%',
                'code': 'HE25',
                'is_leave': False,
            })

        he50_type = self.env['hr.work.entry.type'].search([('code', '=', 'HE50')], limit=1)
        if not he50_type:
            he50_type = self.env['hr.work.entry.type'].create({
                'name': 'Horas Extra 50%',
                'code': 'HE50',
                'is_leave': False,
            })

        he75_type = self.env['hr.work.entry.type'].search([('code', '=', 'HE75')], limit=1)
        if not he75_type:
            he75_type = self.env['hr.work.entry.type'].create({
                'name': 'Horas Extra 75%',
                'code': 'HE75',
                'is_leave': False,
            })

        sunday_type = self.env['hr.work.entry.type'].search([('code', '=', 'SUNDAY')], limit=1)
        if not sunday_type:
            sunday_type = self.env['hr.work.entry.type'].create({
                'name': 'Horas Domingo',
                'code': 'SUNDAY',
                'is_leave': False,
            })

        # Agregar líneas de horas extra si existen
        if total_hours_25 > 0:
            # Verificar si ya existe línea HE25
            existing = False
            for line in res:
                if line.get('code') == 'HE25':
                    line['number_of_hours'] = line.get('number_of_hours', 0) + total_hours_25
                    existing = True
                    break
            if not existing:
                res.append({
                    'sequence': he25_type.sequence or 10,
                    'work_entry_type_id': he25_type.id,
                    'number_of_days': 0,
                    'number_of_hours': total_hours_25,
                    'code': 'HE25',
                })

        if total_hours_50 > 0:
            existing = False
            for line in res:
                if line.get('code') == 'HE50':
                    line['number_of_hours'] = line.get('number_of_hours', 0) + total_hours_50
                    existing = True
                    break
            if not existing:
                res.append({
                    'sequence': he50_type.sequence or 10,
                    'work_entry_type_id': he50_type.id,
                    'number_of_days': 0,
                    'number_of_hours': total_hours_50,
                    'code': 'HE50',
                })

        if total_hours_75 > 0:
            existing = False
            for line in res:
                if line.get('code') == 'HE75':
                    line['number_of_hours'] = line.get('number_of_hours', 0) + total_hours_75
                    existing = True
                    break
            if not existing:
                res.append({
                    'sequence': he75_type.sequence or 10,
                    'work_entry_type_id': he75_type.id,
                    'number_of_days': 0,
                    'number_of_hours': total_hours_75,
                    'code': 'HE75',
                })

        if total_sunday_hours > 0:
            existing = False
            for line in res:
                if line.get('code') == 'SUNDAY':
                    line['number_of_hours'] = line.get('number_of_hours', 0) + total_sunday_hours
                    existing = True
                    break
            if not existing:
                res.append({
                    'sequence': sunday_type.sequence or 10,
                    'work_entry_type_id': sunday_type.id,
                    'number_of_days': 0,
                    'number_of_hours': total_sunday_hours,
                    'code': 'SUNDAY',
                })

        # Lógica para nómina semanal: limitar horas normales a 44 por semana
        if not contract.resource_calendar_id:
            return res
        
        calendar = contract.resource_calendar_id
        
        # Solo aplicar lógica si es nómina semanal y NO es turno nocturno
        if not calendar.es_nomina_semanal or calendar.nocturna:
            return res
        
        # Obtener el total de horas trabajadas en el período (WORK100)
        total_worked_hours = sum(line.get('number_of_hours', 0) 
                                 for line in res 
                                 if line.get('code') == 'WORK100')
        
        if total_worked_hours <= 0:
            return res

        # Calcular el máximo de horas normales permitidas en el período
        if self.date_from and self.date_to:
            days_diff = (self.date_to - self.date_from).days + 1
            # Calcular semanas en el período (redondeado hacia arriba para ser conservador)
            weeks_in_period = days_diff / 7.0
            max_normal_hours = 44.0 * weeks_in_period
        else:
            # Si no hay fechas, usar el cálculo semanal estándar
            max_normal_hours = 44.0
        
        _logger.info(
            "Nómina Semanal - Empleado: %s, Período: %s a %s, "
            "Horas trabajadas: %.2f, Máximo horas normales: %.2f",
            self.employee_id.name, self.date_from, self.date_to,
            total_worked_hours, max_normal_hours
        )
        
        # Si se trabajaron más horas de las normales permitidas
        if total_worked_hours > max_normal_hours:
            excess_hours = total_worked_hours - max_normal_hours
            
            # Actualizar la línea WORK100 para limitar a max_normal_hours
            for line in res:
                if line.get('code') == 'WORK100':
                    original_hours = line.get('number_of_hours', 0)
                    if original_hours > 0:
                        # Limitar las horas normales al máximo permitido
                        line['number_of_hours'] = max_normal_hours
                        _logger.info(
                            "Ajustando horas normales: %.2f -> %.2f (exceso: %.2f)",
                            original_hours, max_normal_hours, excess_hours
                        )
            
            # Buscar el tipo de entrada de trabajo para HE25
            he25_type = self.env['hr.work.entry.type'].search([
                ('code', '=', 'HE25')
            ], limit=1)
            
            if not he25_type:
                # Crear el tipo si no existe
                he25_type = self.env['hr.work.entry.type'].create({
                    'name': 'Horas Extra 25%',
                    'code': 'HE25',
                    'is_leave': False,
                })
            
            # Verificar si ya existe una línea HE25 para no duplicar
            existing_he25 = False
            for line in res:
                if line.get('code') == 'HE25':
                    # Sumar las horas excedentes a la línea existente
                    line['number_of_hours'] = line.get('number_of_hours', 0) + excess_hours
                    existing_he25 = True
                    _logger.info(
                        "Actualizando línea HE25 existente: +%.2f horas (total: %.2f)",
                        excess_hours, line['number_of_hours']
                    )
                    break
            
            # Si no existe línea HE25, crear una nueva
            if not existing_he25:
                res.append({
                    'sequence': he25_type.sequence or 10,
                    'work_entry_type_id': he25_type.id,
                    'number_of_days': 0,
                    'number_of_hours': excess_hours,
                    'code': 'HE25',
                })
                _logger.info(
                    "Agregadas %.2f horas extra (HE25) para empleado %s",
                    excess_hours, self.employee_id.name
                )

        return res

