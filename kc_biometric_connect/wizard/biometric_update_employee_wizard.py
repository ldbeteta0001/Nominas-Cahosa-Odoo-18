# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BiometricUpdateEmployeeWizard(models.TransientModel):
    _name = 'biometric.update.employee.wizard'
    _description = 'Wizard para Actualizar Empleado en BioTime'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True
    )
    
    employee_id = fields.Integer(
        string='ID Empleado',
        required=True
    )
    
    emp_code = fields.Char(
        string='Código de Empleado'
    )
    
    first_name = fields.Char(
        string='Nombre',
        required=True
    )
    
    last_name = fields.Char(
        string='Apellido',
        required=True
    )
    
    department = fields.Integer(
        string='ID Departamento'
    )
    
    area = fields.Char(
        string='IDs de Áreas',
        help='IDs de áreas separados por coma, ej: [1,2]'
    )
    
    def action_update(self):
        """Actualizar empleado en BioTime"""
        self.ensure_one()
        
        if self.device_id.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        try:
            auth_token = self.device_id._server_authenticate()
            
            # Preparar datos para actualizar
            update_data = {
                'first_name': self.first_name,
                'last_name': self.last_name,
            }
            
            if self.emp_code:
                update_data['emp_code'] = self.emp_code
            
            if self.department:
                update_data['department'] = self.department
            
            if self.area:
                # Convertir string a lista de enteros
                try:
                    area_list = eval(self.area) if self.area.startswith('[') else [int(a.strip()) for a in self.area.split(',')]
                    update_data['area'] = area_list
                except:
                    pass
            
            # Actualizar en BioTime
            result = self.device_id._server_update_employee(self.employee_id, update_data, auth_token)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Empleado Actualizado'),
                    'message': _('El empleado ha sido actualizado exitosamente en BioTime.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al actualizar empleado: %s", str(e))
            raise UserError(_('Error al actualizar empleado: %s') % str(e))


class BiometricDeleteEmployeeWizard(models.TransientModel):
    _name = 'biometric.delete.employee.wizard'
    _description = 'Wizard para Eliminar Empleado en BioTime'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True
    )
    
    employee_id = fields.Integer(
        string='ID Empleado',
        required=True
    )
    
    employee_name = fields.Char(
        string='Nombre del Empleado',
        readonly=True
    )
    
    def action_delete(self):
        """Eliminar empleado en BioTime"""
        self.ensure_one()
        
        if self.device_id.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        try:
            auth_token = self.device_id._server_authenticate()
            
            # Eliminar en BioTime
            self.device_id._server_delete_employee(self.employee_id, auth_token)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Empleado Eliminado'),
                    'message': _('El empleado ha sido eliminado exitosamente de BioTime.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al eliminar empleado: %s", str(e))
            raise UserError(_('Error al eliminar empleado: %s') % str(e))
