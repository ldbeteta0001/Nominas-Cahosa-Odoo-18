# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import io
import xlsxwriter


class HrExtraHoursReportWizard(models.TransientModel):
    _name = 'hr.extra.hours.report.wizard'
    _description = 'Asistente de Reportes de Horas Extra'

    date_from = fields.Date(
        string='Fecha Desde',
        required=True,
        default=fields.Date.context_today
    )
    
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True,
        default=fields.Date.context_today
    )
    
    employee_ids = fields.Many2many(
        'hr.employee',
        string='Empleados',
        help='Dejar vacío para incluir todos los empleados'
    )
    
    department_ids = fields.Many2many(
        'hr.department',
        string='Departamentos',
        help='Dejar vacío para incluir todos los departamentos'
    )
    
    state = fields.Selection([
        ('all', 'Todos'),
        ('approved', 'Solo Aprobadas'),
        ('rejected', 'Solo Rechazadas'),
        ('to_approve', 'Solo Pendientes')
    ], string='Estado', default='approved', required=True)
    
    report_type = fields.Selection([
        ('summary', 'Resumen'),
        ('detail', 'Detallado'),
        ('by_employee', 'Por Empleado'),
        ('by_reason', 'Por Motivo')
    ], string='Tipo de Reporte', default='summary', required=True)
    
    file_name = fields.Char(
        string='Nombre del Archivo',
        compute='_compute_file_name',
        store=True
    )
    
    file_data = fields.Binary(
        string='Archivo',
        readonly=True
    )

    @api.depends('date_from', 'date_to', 'report_type')
    def _compute_file_name(self):
        for record in self:
            if record.date_from and record.date_to and record.report_type:
                record.file_name = 'horas_extra_%s_%s_%s.xlsx' % (
                    record.report_type,
                    record.date_from.strftime('%Y%m%d'),
                    record.date_to.strftime('%Y%m%d')
                )
            else:
                record.file_name = 'horas_extra.xlsx'

    def action_generate_report(self):
        """Generar el reporte"""
        self.ensure_one()
        
        # Validar fechas
        if self.date_from > self.date_to:
            raise UserError(_('La fecha desde debe ser anterior a la fecha hasta.'))
        
        # Obtener datos
        domain = self._get_domain()
        requests = self.env['hr.extra.hours.request'].search(domain)
        
        if not requests:
            raise UserError(_('No se encontraron datos para el período seleccionado.'))
        
        # Generar archivo Excel
        file_data = self._generate_excel(requests)
        
        # Guardar archivo
        self.write({
            'file_data': base64.b64encode(file_data)
        })
        
        return {
            'name': _('Descargar Reporte'),
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=hr.extra.hours.report.wizard&id={self.id}&field=file_data&filename_field=file_name&download=true',
            'target': 'new'
        }

    def _get_domain(self):
        """Obtener dominio de búsqueda"""
        domain = [
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to)
        ]
        
        if self.state != 'all':
            domain.append(('state', '=', self.state))
        
        if self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        if self.department_ids:
            domain.append(('department_id', 'in', self.department_ids.ids))
        
        return domain

    def _generate_excel(self, requests):
        """Generar archivo Excel"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Formato para encabezados
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#366092',
            'font_color': 'white',
            'border': 1
        })
        
        # Formato para datos
        data_format = workbook.add_format({
            'border': 1
        })
        
        # Formato para números
        number_format = workbook.add_format({
            'num_format': '0.00',
            'border': 1
        })
        
        if self.report_type == 'summary':
            self._generate_summary_sheet(workbook, requests, header_format, data_format, number_format)
        elif self.report_type == 'detail':
            self._generate_detail_sheet(workbook, requests, header_format, data_format, number_format)
        elif self.report_type == 'by_employee':
            self._generate_by_employee_sheet(workbook, requests, header_format, data_format, number_format)
        elif self.report_type == 'by_reason':
            self._generate_by_reason_sheet(workbook, requests, header_format, data_format, number_format)
        
        workbook.close()
        return output.getvalue()

    def _generate_summary_sheet(self, workbook, requests, header_format, data_format, number_format):
        """Generar hoja de resumen"""
        worksheet = workbook.add_worksheet('Resumen')
        
        # Encabezados
        headers = [
            'Total Solicitudes',
            'Horas Totales',
            'Horas Pagables',
            'Aprobadas',
            'Rechazadas',
            'Pendientes'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        total_requests = len(requests)
        total_hours = sum(requests.mapped('duration_hours'))
        total_payable = sum(requests.mapped('payable_hours'))
        approved = len(requests.filtered(lambda r: r.state == 'approved'))
        rejected = len(requests.filtered(lambda r: r.state == 'rejected'))
        pending = len(requests.filtered(lambda r: r.state == 'to_approve'))
        
        data = [total_requests, total_hours, total_payable, approved, rejected, pending]
        
        for col, value in enumerate(data):
            if col in [1, 2]:  # Horas
                worksheet.write(1, col, value, number_format)
            else:
                worksheet.write(1, col, value, data_format)

    def _generate_detail_sheet(self, workbook, requests, header_format, data_format, number_format):
        """Generar hoja detallada"""
        worksheet = workbook.add_worksheet('Detalle')
        
        # Encabezados
        headers = [
            'Referencia',
            'Empleado',
            'Fecha',
            'Entrada',
            'Salida',
            'Tipo',
            'Duración (h)',
            'Horas Pagables',
            'Motivo',
            'Estado',
            'Jefe',
            'Aprobado por',
            'Fecha Aprobación'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        row = 1
        for request in requests:
            data = [
                request.name,
                request.employee_id.name,
                request.date.strftime('%Y-%m-%d'),
                request.check_in.strftime('%H:%M') if request.check_in else '',
                request.check_out.strftime('%H:%M') if request.check_out else '',
                dict(request._fields['type'].selection)[request.type],
                request.duration_hours,
                request.payable_hours,
                request.reason_id.name,
                dict(request._fields['state'].selection)[request.state],
                request.manager_id.name,
                request.approved_by.name if request.approved_by else '',
                request.approved_date.strftime('%Y-%m-%d %H:%M') if request.approved_date else ''
            ]
            
            for col, value in enumerate(data):
                if col in [6, 7]:  # Horas
                    worksheet.write(row, col, value, number_format)
                else:
                    worksheet.write(row, col, value, data_format)
            
            row += 1

    def _generate_by_employee_sheet(self, workbook, requests, header_format, data_format, number_format):
        """Generar hoja por empleado"""
        worksheet = workbook.add_worksheet('Por Empleado')
        
        # Agrupar por empleado
        employee_data = {}
        for request in requests:
            employee = request.employee_id
            if employee not in employee_data:
                employee_data[employee] = {
                    'requests': 0,
                    'total_hours': 0,
                    'payable_hours': 0,
                    'approved': 0,
                    'rejected': 0,
                    'pending': 0
                }
            
            employee_data[employee]['requests'] += 1
            employee_data[employee]['total_hours'] += request.duration_hours
            employee_data[employee]['payable_hours'] += request.payable_hours
            
            if request.state == 'approved':
                employee_data[employee]['approved'] += 1
            elif request.state == 'rejected':
                employee_data[employee]['rejected'] += 1
            elif request.state == 'to_approve':
                employee_data[employee]['pending'] += 1
        
        # Encabezados
        headers = [
            'Empleado',
            'Solicitudes',
            'Horas Totales',
            'Horas Pagables',
            'Aprobadas',
            'Rechazadas',
            'Pendientes'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        row = 1
        for employee, data in employee_data.items():
            values = [
                employee.name,
                data['requests'],
                data['total_hours'],
                data['payable_hours'],
                data['approved'],
                data['rejected'],
                data['pending']
            ]
            
            for col, value in enumerate(values):
                if col in [2, 3]:  # Horas
                    worksheet.write(row, col, value, number_format)
                else:
                    worksheet.write(row, col, value, data_format)
            
            row += 1

    def _generate_by_reason_sheet(self, workbook, requests, header_format, data_format, number_format):
        """Generar hoja por motivo"""
        worksheet = workbook.add_worksheet('Por Motivo')
        
        # Agrupar por motivo
        reason_data = {}
        for request in requests:
            reason = request.reason_id
            if reason not in reason_data:
                reason_data[reason] = {
                    'requests': 0,
                    'total_hours': 0,
                    'payable_hours': 0
                }
            
            reason_data[reason]['requests'] += 1
            reason_data[reason]['total_hours'] += request.duration_hours
            reason_data[reason]['payable_hours'] += request.payable_hours
        
        # Encabezados
        headers = ['Motivo', 'Solicitudes', 'Horas Totales', 'Horas Pagables']
        
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Datos
        row = 1
        for reason, data in reason_data.items():
            values = [
                reason.name if reason else 'Sin Motivo',
                data['requests'],
                data['total_hours'],
                data['payable_hours']
            ]
            
            for col, value in enumerate(values):
                if col in [2, 3]:  # Horas
                    worksheet.write(row, col, value, number_format)
                else:
                    worksheet.write(row, col, value, data_format)
            
            row += 1

