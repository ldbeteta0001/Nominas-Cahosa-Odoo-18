# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BiometricSyncServerDataWizard(models.TransientModel):
    _name = 'biometric.sync.server.data.wizard'
    _description = 'Wizard para Sincronizar Datos del Servidor'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo Biométrico',
        required=True,
        domain=[('connection_type', '=', 'server')],
        help='Seleccione el dispositivo servidor desde el cual sincronizar'
    )
    
    sync_type = fields.Selection([
        ('employees', 'Empleados'),
        ('departments', 'Departamentos'),
        ('areas', 'Áreas'),
        ('all', 'Todos (Empleados, Departamentos y Áreas)')
    ], string='Tipo de Sincronización', required=True, default='employees')
    
    def action_sync(self):
        """Ejecutar la sincronización según el tipo seleccionado"""
        self.ensure_one()
        
        if self.device_id.connection_type != 'server':
            raise UserError(_('El dispositivo seleccionado debe ser de tipo "Conexión al Servidor Biométrico"'))
        
        try:
            if self.sync_type == 'employees' or self.sync_type == 'all':
                result = self.device_id.sync_server_employees()
            if self.sync_type == 'departments' or self.sync_type == 'all':
                result = self.device_id.sync_server_departments()
            if self.sync_type == 'areas' or self.sync_type == 'all':
                result = self.device_id.sync_server_areas()
            
            # Abrir la vista correspondiente después de sincronizar
            if self.sync_type == 'employees':
                return self.device_id.action_view_server_employees()
            elif self.sync_type == 'departments':
                return self.device_id.action_view_server_departments()
            elif self.sync_type == 'areas':
                return self.device_id.action_view_server_areas()
            else:
                # Si sincronizó todos, abrir vista de empleados por defecto
                return self.device_id.action_view_server_employees()
        except Exception as e:
            _logger.error("Error en sincronización: %s", str(e))
            raise UserError(_('Error al sincronizar: %s') % str(e))


class BiometricSyncServerDataWizard(models.TransientModel):
    _name = 'biometric.sync.server.data.wizard'
    _description = 'Wizard para Sincronizar Datos del Servidor'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo Biométrico',
        required=True,
        domain=[('connection_type', '=', 'server')],
        help='Seleccione el dispositivo servidor desde el cual sincronizar'
    )
    
    sync_type = fields.Selection([
        ('employees', 'Empleados'),
        ('departments', 'Departamentos'),
        ('areas', 'Áreas'),
        ('all', 'Todos (Empleados, Departamentos y Áreas)')
    ], string='Tipo de Sincronización', required=True, default='employees')
    
    def action_sync(self):
        """Ejecutar la sincronización según el tipo seleccionado"""
        self.ensure_one()
        
        if self.device_id.connection_type != 'server':
            raise UserError(_('El dispositivo seleccionado debe ser de tipo "Conexión al Servidor Biométrico"'))
        
        try:
            if self.sync_type == 'employees' or self.sync_type == 'all':
                self.device_id.sync_server_employees()
            if self.sync_type == 'departments' or self.sync_type == 'all':
                self.device_id.sync_server_departments()
            if self.sync_type == 'areas' or self.sync_type == 'all':
                self.device_id.sync_server_areas()
            
            # Abrir la vista correspondiente después de sincronizar
            if self.sync_type == 'employees':
                return self.device_id.action_view_server_employees()
            elif self.sync_type == 'departments':
                return self.device_id.action_view_server_departments()
            elif self.sync_type == 'areas':
                return self.device_id.action_view_server_areas()
            else:
                # Si sincronizó todos, abrir vista de empleados por defecto
                return self.device_id.action_view_server_employees()
        except Exception as e:
            _logger.error("Error en sincronización: %s", str(e))
            raise UserError(_('Error al sincronizar: %s') % str(e))


class BiometricServerEmployee(models.TransientModel):
    _name = 'biometric.server.employee'
    _description = 'Empleado del Servidor Biométrico'
    _order = 'emp_code'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True
    )
    
    biometric_id = fields.Integer(
        string='ID Biométrico',
        required=True,
        help='ID del empleado en el servidor BioTime'
    )
    
    emp_code = fields.Char(
        string='Código de Empleado',
        help='Código del empleado en BioTime'
    )
    
    first_name = fields.Char(
        string='Nombre'
    )
    
    last_name = fields.Char(
        string='Apellido'
    )
    
    full_name = fields.Char(
        string='Nombre Completo',
        compute='_compute_full_name',
        store=True
    )
    
    department_id = fields.Integer(
        string='ID Departamento'
    )
    
    department_name = fields.Char(
        string='Departamento'
    )
    
    area_ids = fields.Char(
        string='Áreas',
        help='IDs de áreas separados por coma'
    )
    
    hire_date = fields.Date(
        string='Fecha de Contratación'
    )
    
    gender = fields.Char(
        string='Género'
    )
    
    birthday = fields.Date(
        string='Fecha de Nacimiento'
    )
    
    card_no = fields.Char(
        string='Número de Tarjeta'
    )
    
    device_password = fields.Char(
        string='Contraseña del Dispositivo'
    )
    
    verify_mode = fields.Integer(
        string='Modo de Verificación'
    )
    
    app_status = fields.Char(
        string='Estado de Aplicación'
    )
    
    # Relación con empleado de Odoo
    odoo_employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado en Odoo',
        compute='_compute_odoo_employee',
        store=True,
        search='_search_odoo_employee'
    )
    
    exists_in_odoo = fields.Boolean(
        string='Existe en Odoo',
        compute='_compute_odoo_employee',
        store=True
    )
    
    @api.depends('biometric_id')
    def _compute_odoo_employee(self):
        for record in self:
            employee = self.env['hr.employee'].search([
                ('biometric_user_id', '=', str(record.biometric_id))
            ], limit=1)
            record.odoo_employee_id = employee.id if employee else False
            record.exists_in_odoo = bool(employee)
    
    def _search_odoo_employee(self, operator, value):
        """Búsqueda personalizada para odoo_employee_id basada en biometric_id"""
        # Para filtros que buscan si existe o no existe empleado
        all_employees = self.env['hr.employee'].search([('biometric_user_id', '!=', False)])
        biometric_ids_with_employee = []
        for emp in all_employees:
            try:
                if emp.biometric_user_id:
                    biometric_ids_with_employee.append(int(emp.biometric_user_id))
            except (ValueError, TypeError):
                continue
        
        if operator == '=' and not value:
            # Buscar registros que SÍ tengan empleado en Odoo (odoo_employee_id != False)
            return [('biometric_id', 'in', biometric_ids_with_employee)]
        elif operator == '!=' and not value:
            # Buscar registros que NO tengan empleado en Odoo (odoo_employee_id = False)
            return [('biometric_id', 'not in', biometric_ids_with_employee)]
        elif operator == '=' and value:
            # Buscar por ID específico de empleado
            employee = self.env['hr.employee'].browse(value)
            if employee and employee.biometric_user_id:
                try:
                    return [('biometric_id', '=', int(employee.biometric_user_id))]
                except (ValueError, TypeError):
                    return []
        return []
    
    @api.depends('first_name', 'last_name')
    def _compute_full_name(self):
        for record in self:
            record.full_name = f"{record.first_name or ''} {record.last_name or ''}".strip()
    
    def action_create_in_odoo(self):
        """Crear empleado en Odoo desde el servidor biométrico"""
        self.ensure_one()
        
        if self.odoo_employee_id:
            raise UserError(_('Este empleado ya existe en Odoo: %s') % self.odoo_employee_id.name)
        
        # Crear empleado en Odoo
        employee_vals = {
            'name': self.full_name,
            'biometric_user_id': str(self.biometric_id),
            'biometric_device_id': self.device_id.id,
            'biometric_sync_active': True,
        }
        
        employee = self.env['hr.employee'].create(employee_vals)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleado Creado'),
                'message': _('El empleado %s ha sido creado en Odoo.') % self.full_name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def action_create_multiple_in_odoo(self, employee_ids):
        """Crear múltiples empleados en Odoo"""
        employees = self.browse(employee_ids)
        created = 0
        skipped = 0
        
        for emp in employees:
            if emp.odoo_employee_id:
                skipped += 1
                continue
            
            try:
                employee_vals = {
                    'name': emp.full_name,
                    'biometric_user_id': str(emp.biometric_id),
                    'biometric_device_id': emp.device_id.id,
                    'biometric_sync_active': True,
                }
                self.env['hr.employee'].create(employee_vals)
                created += 1
            except Exception as e:
                _logger.error("Error al crear empleado %s: %s", emp.full_name, str(e))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Empleados Creados'),
                'message': _('Se crearon %d empleados en Odoo. %d ya existían.') % (created, skipped),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_update_in_biotime(self):
        """Actualizar empleado en BioTime"""
        self.ensure_one()
        return {
            'name': _('Actualizar Empleado en BioTime'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.update.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_device_id': self.device_id.id,
                'default_employee_id': self.biometric_id,
                'default_first_name': self.first_name,
                'default_last_name': self.last_name,
                'default_emp_code': self.emp_code,
            }
        }
    
    def action_delete_in_biotime(self):
        """Eliminar empleado en BioTime"""
        self.ensure_one()
        return {
            'name': _('Eliminar Empleado en BioTime'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.delete.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_device_id': self.device_id.id,
                'default_employee_id': self.biometric_id,
                'default_employee_name': self.full_name,
            }
        }
    
    def action_open_sync_wizard(self):
        """Abrir wizard para sincronizar datos del servidor"""
        sync_type = self.env.context.get('default_sync_type', 'employees')
        return {
            'name': _('Sincronizar Datos del Servidor'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.sync.server.data.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_type': sync_type,
            }
        }


class BiometricServerDepartment(models.TransientModel):
    _name = 'biometric.server.department'
    _description = 'Departamento del Servidor Biométrico'
    _order = 'dept_code'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True
    )
    
    def action_open_sync_wizard(self):
        """Abrir wizard para sincronizar datos del servidor"""
        return {
            'name': _('Sincronizar Datos del Servidor'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.sync.server.data.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_type': 'departments',
            }
        }
    
    biometric_id = fields.Integer(
        string='ID Biométrico',
        required=True
    )
    
    dept_code = fields.Char(
        string='Código'
    )
    
    dept_name = fields.Char(
        string='Nombre'
    )
    
    parent_dept = fields.Integer(
        string='ID Departamento Padre'
    )
    
    parent_dept_name = fields.Char(
        string='Departamento Padre'
    )


class BiometricServerArea(models.TransientModel):
    _name = 'biometric.server.area'
    _description = 'Área del Servidor Biométrico'
    _order = 'area_code'

    device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo',
        required=True
    )
    
    def action_open_sync_wizard(self):
        """Abrir wizard para sincronizar datos del servidor"""
        return {
            'name': _('Sincronizar Datos del Servidor'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.sync.server.data.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_type': 'areas',
            }
        }
    
    biometric_id = fields.Integer(
        string='ID Biométrico',
        required=True
    )
    
    area_code = fields.Char(
        string='Código'
    )
    
    area_name = fields.Char(
        string='Nombre'
    )
    
    parent_area_id = fields.Integer(
        string='ID Área Padre'
    )
    
    parent_area_name = fields.Char(
        string='Área Padre'
    )
