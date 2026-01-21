# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Nota: El cálculo de horas extra (HE25, HE50, HE75) se ha movido a otro módulo
# Este archivo se mantiene solo para compatibilidad con extensiones existentes

class HRAttendance(models.Model):
    _inherit = 'hr.attendance'
    
    # Este archivo está vacío intencionalmente
    # Las extensiones de asistencia están en hr_attendance_extension.py
