# -*- coding: utf-8 -*-

from odoo import fields, models


class ResourceCalendar(models.Model):
    """Extender resource.calendar para agregar campos de nómina semanal y turno nocturno"""
    _inherit = 'resource.calendar'

    es_nomina_semanal = fields.Boolean(
        string='Nómina Semanal',
        default=False,
        help='Marcar si este horario aplica para nómina semanal. '
             'En horarios semanales de día, solo se pagan 44 horas como normales, '
             'las horas adicionales se cuentan como horas extra.'
    )
    nocturna = fields.Boolean(
        string='Turno Nocturno',
        default=False,
        help='Marcar si este es un turno nocturno. '
             'Los turnos nocturnos tienen lógica especial para horas que cruzan medianoche.'
    )


class ResourceCalendarAttendance(models.Model):
    """Extender resource.calendar.attendance para agregar campo shift_group"""
    _inherit = 'resource.calendar.attendance'

    shift_group = fields.Char(
        string='Grupo de Turno',
        help='Identificador para agrupar líneas de horario relacionadas '
             '(por ejemplo, para turnos nocturnos que cruzan medianoche). '
             'Las líneas con el mismo shift_group pertenecen al mismo turno.'
    )

