# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
from io import BytesIO
from datetime import date, datetime, time, timedelta

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False
    _logger.warning("La librería 'xlsxwriter' no está instalada. Para exportar a Excel, instale con: pip install xlsxwriter")


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    biometric_device_id = fields.Many2one(
        'biometric.device',
        string='Dispositivo Biométrico',
        readonly=True,
        help='Dispositivo biométrico desde el cual se registró esta asistencia'
    )
    
    biometric_punch_time = fields.Datetime(
        string='Hora del Registro Biométrico',
        readonly=True,
        help='Fecha y hora exacta del registro en el dispositivo biométrico'
    )
    
    is_biometric = fields.Boolean(
        string='Registro Biométrico',
        default=False,
        help='Indica si este registro proviene de un dispositivo biométrico',
        readonly=True
    )
    
    def action_export_attendance(self):
        """Exportar registros de asistencia seleccionados a Excel"""
        if not XLSXWRITER_AVAILABLE:
            raise UserError(_('La librería xlsxwriter no está instalada. Instale con: pip install xlsxwriter'))
        
        # Obtener registros seleccionados o usar el dominio del contexto
        attendances = self
        if not attendances:
            # Si no hay registros seleccionados, usar el contexto para buscar
            # Intentar obtener el dominio del contexto de la vista
            domain = self.env.context.get('active_domain', [])
            if domain:
                attendances = self.env['hr.attendance'].search(domain, order='check_in desc')
            else:
                # Si no hay dominio, buscar todos los del último mes
                fecha_desde = date.today() - timedelta(days=30)
                fecha_desde_dt = datetime.combine(fecha_desde, time.min)
                fecha_hasta_dt = datetime.combine(date.today(), time.max)
                attendances = self.env['hr.attendance'].search([
                    ('check_in', '>=', fecha_desde_dt),
                    ('check_in', '<=', fecha_hasta_dt),
                ], order='check_in desc', limit=10000)
        
        if not attendances:
            raise UserError(_('No se encontraron registros de asistencia para exportar.'))
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Asistencias')
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#366092',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        text_format = workbook.add_format({
            'border': 1
        })
        
        center_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Encabezados
        headers = [
            'Empleado',
            'Código Empleado',
            'Departamento',
            'Fecha Entrada',
            'Hora Entrada',
            'Fecha Salida',
            'Hora Salida',
            'Horas Trabajadas',
            'Dispositivo Biométrico',
            'Hora Registro Biométrico'
        ]
        
        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Ancho de columnas
        worksheet.set_column(0, 0, 30)  # Empleado
        worksheet.set_column(1, 1, 15)  # Código Empleado
        worksheet.set_column(2, 2, 25)  # Departamento
        worksheet.set_column(3, 3, 18)  # Fecha Entrada
        worksheet.set_column(4, 4, 12)  # Hora Entrada
        worksheet.set_column(5, 5, 18)  # Fecha Salida
        worksheet.set_column(6, 6, 12)  # Hora Salida
        worksheet.set_column(7, 7, 18)  # Horas Trabajadas
        worksheet.set_column(8, 8, 25)  # Dispositivo Biométrico
        worksheet.set_column(9, 9, 20)  # Hora Registro Biométrico
        
        # Escribir datos
        row = 1
        for att in attendances:
            # Empleado
            worksheet.write(row, 0, att.employee_id.name or '', text_format)
            
            # Código de empleado
            worksheet.write(row, 1, att.employee_id.barcode or att.employee_id.employee_number or '', text_format)
            
            # Departamento
            worksheet.write(row, 2, att.employee_id.department_id.name if att.employee_id.department_id else '', text_format)
            
            # Fecha y hora de entrada
            if att.check_in:
                worksheet.write(row, 3, att.check_in.strftime('%d/%m/%Y'), text_format)
                worksheet.write(row, 4, att.check_in.strftime('%H:%M:%S'), text_format)
            else:
                worksheet.write(row, 3, '', text_format)
                worksheet.write(row, 4, '', text_format)
            
            # Fecha y hora de salida
            if att.check_out:
                worksheet.write(row, 5, att.check_out.strftime('%d/%m/%Y'), text_format)
                worksheet.write(row, 6, att.check_out.strftime('%H:%M:%S'), text_format)
            else:
                worksheet.write(row, 5, '', text_format)
                worksheet.write(row, 6, '', text_format)
            
            # Horas trabajadas
            if att.check_in and att.check_out:
                horas_trabajadas = att.check_out - att.check_in
                horas = horas_trabajadas.total_seconds() / 3600
                worksheet.write(row, 7, f"{horas:.2f}", center_format)
            else:
                worksheet.write(row, 7, att.worked_hours or '', center_format if att.worked_hours else text_format)
            
            # Dispositivo biométrico
            worksheet.write(row, 8, att.biometric_device_id.name if att.biometric_device_id else '', text_format)
            
            # Hora del registro biométrico
            if att.biometric_punch_time:
                worksheet.write(row, 9, att.biometric_punch_time.strftime('%d/%m/%Y %H:%M:%S'), text_format)
            else:
                worksheet.write(row, 9, '', text_format)
            
            row += 1
        
        # Congelar primera fila
        worksheet.freeze_panes(1, 0)
        
        # Cerrar workbook
        workbook.close()
        output.seek(0)
        
        # Nombre del archivo
        fecha_hoy = date.today().strftime('%Y%m%d')
        filename = f'asistencias_{fecha_hoy}.xlsx'
        
        # Crear attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id if len(self) == 1 else False,
        })
        
        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

