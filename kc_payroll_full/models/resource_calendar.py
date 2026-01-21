# -*- coding: utf-8 -*-
from odoo import fields, models


class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    nocturna = fields.Boolean(
        string='Turno Nocturno',
        help="Marcar si el horario abarca medianoche"
    )

    es_turno_24_horas = fields.Boolean(
        string='Turno de 24 Horas',
        help="Marcar si el horario es de 24 horas. Día: 06:00-18:00, Noche: 19:00-06:00"
    )

    es_nomina_semanal = fields.Boolean(
        string='Nómina Semanal',
        help='Indica que este calendario se utiliza para nóminas semanales'
    )


class ResourceCalendarAttendance(models.Model):
    _inherit = 'resource.calendar.attendance'

    shift_group = fields.Char(
        string='Grupo de Turno',
        help='Identificador para agrupar líneas de horario relacionadas (ej. "Día", "Noche")'
    )
