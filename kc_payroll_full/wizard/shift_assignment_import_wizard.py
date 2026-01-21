# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import io
import logging
from datetime import datetime, timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    _logger.warning("La librería 'openpyxl' no está instalada. Para importar Excel, instale con: pip install openpyxl")


class ShiftAssignmentImportWizard(models.TransientModel):
    _name = 'shift.assignment.import.wizard'
    _description = 'Wizard para importar asignaciones de turnos desde Excel'

    file = fields.Binary(
        string='Archivo Excel',
        required=True,
        help='Archivo Excel con columnas: Empleado, Turno (y opcionalmente Fecha)'
    )
    filename = fields.Char(
        string='Nombre del archivo'
    )
    date = fields.Date(
        string='Fecha',
        required=False,
        default=fields.Date.today,
        help='Fecha para las asignaciones. Solo se usa si el Excel no tiene columna de fecha.'
    )
    has_date_column = fields.Boolean(
        string='El Excel tiene columna de Fecha',
        default=False,
        help='Marcar si el Excel incluye una columna con las fechas individuales'
    )

    def action_import(self):
        """Importar datos desde Excel y crear una rotación de turnos"""
        self.ensure_one()
        
        if not OPENPYXL_AVAILABLE:
            raise ValidationError(_('La librería openpyxl no está instalada. Instale con: pip install openpyxl'))
        
        if not self.file:
            raise ValidationError(_('Debe subir un archivo Excel.'))
        
        if not self.has_date_column and not self.date:
            raise ValidationError(_('Debe proporcionar una fecha si el Excel no incluye columna de fecha.'))
        
        # Decodificar el archivo
        file_data = base64.b64decode(self.file)
        file_buffer = io.BytesIO(file_data)
        
        # Leer el Excel
        try:
            workbook = openpyxl.load_workbook(file_buffer, data_only=True)
            worksheet = workbook.active
        except Exception as e:
            raise ValidationError(_('Error al leer el archivo Excel: %s') % str(e))
        
        # Diccionario para almacenar datos: {empleado_id: [(fecha, turno), ...]}
        employee_assignments = defaultdict(list)
        error_count = 0
        errors = []
        employee_model = self.env['hr.employee']
        
        # Procesar cada fila (empezando desde la fila 2 para saltar encabezados)
        for row_idx, row in enumerate(worksheet.iter_rows(min_row=2, values_only=True), start=2):
            try:
                # Saltar filas vacías
                if not row or all(cell is None or str(cell).strip() == '' for cell in row if cell):
                    continue
                
                # Obtener valores de las columnas
                employee_name_or_id = row[0] if len(row) > 0 else None
                shift_str = row[1] if len(row) > 1 else None
                date_val = row[2] if len(row) > 2 and self.has_date_column else None
                
                # Validar campos requeridos
                if not employee_name_or_id:
                    errors.append(_('Fila %d: Falta el nombre o ID del empleado') % row_idx)
                    error_count += 1
                    continue
                
                if not shift_str:
                    errors.append(_('Fila %d: Falta el turno') % row_idx)
                    error_count += 1
                    continue
                
                # Normalizar turno
                shift_str_lower = str(shift_str).strip().lower()
                if shift_str_lower in ['dia', 'día', 'day', 'd']:
                    shift_period = 'dia'
                elif shift_str_lower in ['noche', 'night', 'n', 'nocturna']:
                    shift_period = 'noche'
                else:
                    errors.append(_('Fila %d: Turno inválido "%s". Debe ser "dia" o "noche"') % (row_idx, shift_str))
                    error_count += 1
                    continue
                
                # Determinar fecha
                if date_val:
                    # Si hay fecha en el Excel, convertirla
                    if isinstance(date_val, str):
                        try:
                            date_val = datetime.strptime(date_val.strip(), '%Y-%m-%d').date()
                        except:
                            try:
                                date_val = datetime.strptime(date_val.strip(), '%d/%m/%Y').date()
                            except:
                                errors.append(_('Fila %d: Formato de fecha inválido "%s"') % (row_idx, date_val))
                                error_count += 1
                                continue
                    elif hasattr(date_val, 'date'):
                        date_val = date_val.date()
                    elif isinstance(date_val, datetime):
                        date_val = date_val.date()
                else:
                    # Usar la fecha del wizard
                    date_val = self.date
                
                # Buscar empleado
                employee = None
                
                # Intentar por ID biométrico (barcode)
                if isinstance(employee_name_or_id, (int, float)):
                    employee = employee_model.search([
                        ('barcode', '=', str(int(employee_name_or_id)))
                    ], limit=1)
                
                # Si no se encuentra, buscar por nombre
                if not employee:
                    employee = employee_model.search([
                        ('name', '=ilike', str(employee_name_or_id).strip())
                    ], limit=1)
                
                if not employee:
                    errors.append(_('Fila %d: No se encontró el empleado "%s"') % (row_idx, employee_name_or_id))
                    error_count += 1
                    continue
                
                # Agregar a la lista de asignaciones del empleado
                employee_assignments[employee.id].append((date_val, shift_period))
                
            except Exception as e:
                errors.append(_('Fila %d: Error inesperado - %s') % (row_idx, str(e)))
                error_count += 1
                _logger.error(f"Error en fila {row_idx}: {str(e)}")
        
        if not employee_assignments:
            raise ValidationError(_('No se encontraron datos válidos en el archivo Excel.') + 
                                ('\n\n' + '\n'.join(errors[:10]) if errors else ''))
        
        # Crear una nueva rotación
        rotation_name = _('Rotación Importada desde Excel - %s') % fields.Date.today()
        rotation = self.env['hr.shift.rotation'].create({
            'name': rotation_name,
            'state': 'draft',
            'notes': _('Rotación creada desde importación de Excel. Archivo: %s') % (self.filename or 'N/A')
        })
        
        # Agregar empleados a la rotación
        employee_ids = list(employee_assignments.keys())
        rotation.write({'employee_ids': [(6, 0, employee_ids)]})
        
        # Para cada empleado, crear líneas de rotación agrupando períodos consecutivos del mismo turno
        rotation_line_model = self.env['hr.shift.rotation.line']
        sequence = 10
        
        for employee_id, assignments in employee_assignments.items():
            # Ordenar asignaciones por fecha
            assignments.sort(key=lambda x: x[0])
            
            # Agrupar períodos consecutivos del mismo turno
            current_period = None
            
            for date_val, shift_period in assignments:
                if current_period is None:
                    # Iniciar nuevo período
                    current_period = {
                        'shift_period': shift_period,
                        'date_from': date_val,
                        'date_to': date_val,
                    }
                elif current_period['shift_period'] == shift_period:
                    # Mismo turno, extender período
                    current_period['date_to'] = date_val
                else:
                    # Cambio de turno, guardar período anterior y crear nuevo
                    rotation_line_model.create({
                        'rotation_id': rotation.id,
                        'sequence': sequence,
                        'shift_period': current_period['shift_period'],
                        'date_from': current_period['date_from'],
                        'date_to': current_period['date_to'],
                        'reason': _('Importado desde Excel')
                    })
                    sequence += 10
                    current_period = {
                        'shift_period': shift_period,
                        'date_from': date_val,
                        'date_to': date_val,
                    }
            
            # Guardar último período
            if current_period:
                rotation_line_model.create({
                    'rotation_id': rotation.id,
                    'sequence': sequence,
                    'shift_period': current_period['shift_period'],
                    'date_from': current_period['date_from'],
                    'date_to': current_period['date_to'],
                    'reason': _('Importado desde Excel')
                })
                sequence += 10
        
        # Mensaje de resultado
        total_employees = len(employee_assignments)
        total_periods = len(rotation.rotation_line_ids)
        message = _('Rotación creada exitosamente:\n')
        message += _('- %d empleado(s) agregado(s)\n') % total_employees
        message += _('- %d período(s) de rotación creado(s)') % total_periods
        
        if error_count > 0:
            message += '\n\n' + _('Advertencias:\n') + '\n'.join(errors[:5])
            if len(errors) > 5:
                message += '\n' + _('... y %d errores más') % (len(errors) - 5)
        
        _logger.info(f"Rotación creada: {rotation.id}, {total_employees} empleados, {total_periods} períodos")
        
        # Abrir el formulario de la rotación creada
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rotación de Turnos - Revisar'),
            'res_model': 'hr.shift.rotation',
            'res_id': rotation.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }
