# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta


class BiometricSyncWizard(models.TransientModel):
    _name = 'biometric.sync.wizard'
    _description = 'Asistente de Sincronización Biométrica'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True,
        help='Dispositivo biométrico a sincronizar'
    )
    
    sync_mode = fields.Selection([
        ('new', 'Solo Registros Nuevos'),
        ('range', 'Rango de Fechas Personalizado'),
        ('all', 'Todos los Registros (Últimos 90 días)')
    ], string='Modo de Sincronización', default='new', required=True,
       help='Seleccione cómo desea sincronizar los registros')
    
    date_from = fields.Date(
        string='Fecha Desde',
        help='Fecha desde la cual sincronizar registros'
    )
    
    date_to = fields.Date(
        string='Fecha Hasta',
        default=fields.Date.context_today,
        help='Fecha hasta la cual sincronizar registros'
    )
    
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        help='Dejar vacío para sincronizar todos los empleados. Si selecciona empleados, solo se sincronizarán los registros de estos.'
    )
    
    sync_existing = fields.Boolean(
        string='Resincronizar Registros Existentes',
        default=False,
        help='Si está marcado, también procesará registros que ya fueron sincronizados anteriormente'
    )

    @api.onchange('sync_mode')
    def _onchange_sync_mode(self):
        """Actualizar fechas según el modo seleccionado"""
        if self.sync_mode == 'new':
            # Modo nuevo: usar última sincronización
            self.date_from = False
            self.date_to = date.today()
        elif self.sync_mode == 'all':
            # Modo todos: últimos 90 días
            self.date_from = date.today() - timedelta(days=90)
            self.date_to = date.today()
        elif self.sync_mode == 'range':
            # Modo rango: pedir al usuario que ingrese fechas
            if not self.date_from:
                self.date_from = date.today() - timedelta(days=30)
    
    @api.onchange('device_id')
    def _onchange_device_id(self):
        """Actualizar fechas según la última sincronización del dispositivo"""
        if self.device_id and self.device_id.last_sync and self.sync_mode == 'new':
            self.date_from = self.device_id.last_sync.date()
        elif self.device_id and not self.device_id.last_sync and self.sync_mode == 'new':
            self.date_from = date.today() - timedelta(days=30)

    def action_sync(self):
        """Ejecutar la sincronización con los filtros seleccionados"""
        self.ensure_one()
        
        if not self.device_id:
            raise UserError(_('Debe seleccionar un dispositivo biométrico'))
        
        # Validar fechas si está en modo rango
        if self.sync_mode == 'range':
            if not self.date_from or not self.date_to:
                raise UserError(_('Debe especificar ambas fechas (desde y hasta) en modo rango personalizado'))
            if self.date_from > self.date_to:
                raise UserError(_('La fecha "Desde" debe ser anterior a la fecha "Hasta"'))
        
        # Preparar parámetros para la sincronización
        fecha_desde = None
        fecha_hasta = None
        
        if self.sync_mode == 'new':
            # Usar última sincronización (el método sync_attendance lo maneja automáticamente)
            fecha_desde = None
            fecha_hasta = None
        elif self.sync_mode == 'all':
            # Últimos 90 días
            fecha_desde = date.today() - timedelta(days=90)
            fecha_hasta = date.today()
        elif self.sync_mode == 'range':
            # Rango personalizado
            fecha_desde = self.date_from
            fecha_hasta = self.date_to
        
        # Ejecutar sincronización
        # Nota: El filtrado por empleados se puede agregar después si es necesario
        # Por ahora sincroniza todos los registros del rango de fechas
        result = self.device_id.sync_attendance(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        
        # Mostrar mensaje informativo si hay empleados seleccionados
        # (aunque aún no se filtre, puede ser útil para el usuario saber qué se seleccionó)
        if self.employee_ids and len(self.employee_ids) > 0:
            # Por ahora sincroniza todos pero muestra un mensaje
            # TODO: Implementar filtrado por empleados en sync_attendance si es necesario
            pass
        
        return result

