# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    biometric_user_id = fields.Integer(
        string='ID Biométrico',
        help='ID del empleado en el dispositivo biométrico',
        tracking=True
    )
    
    biometric_device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo Biométrico',
        help='Dispositivo biométrico asignado al empleado',
        tracking=True
    )
    
    biometric_sync_active = fields.Boolean(
        string='Sincronización Biométrica Activa',
        default=True,
        help='Indica si este empleado debe sincronizarse desde el dispositivo biométrico',
        tracking=True
    )

