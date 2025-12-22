# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, UserError
from odoo.addons.portal.controllers.portal import CustomerPortal
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class ExtraHoursPortalController(CustomerPortal):
    """Controlador para gestionar las horas extra desde el portal"""

    def _prepare_home_portal_values(self, counters):
        """Agrega contador de horas extra al home del portal"""
        values = super()._prepare_home_portal_values(counters)
        if 'extra_hours_count' in counters:
            employee = self._get_current_employee()
            if employee:
                count = request.env['hr.extra.hours.request'].search_count([
                    ('employee_id', '=', employee.id)
                ])
                values['extra_hours_count'] = count
        return values

    def _get_current_employee(self):
        """Obtiene el empleado actual del usuario portal"""
        user = request.env.user
        
        # Verificar que el usuario tenga permisos de portal o sea empleado
        if not (user.has_group('base.group_portal') or user.has_group('hr.group_hr_user')):
            return False
        
        # Obtener empleado asociado al usuario
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id),
            ('active', '=', True)
        ], limit=1)
        
        return employee

    @http.route(['/my/extra-hours', '/my/extra-hours/page/<int:page>'], 
                type='http', auth='user', website=True)
    def portal_my_extra_hours(self, page=1, **kw):
        """Lista de solicitudes de horas extra del empleado"""
        employee = self._get_current_employee()
        
        if not employee:
            return request.render('kc_hr_extra_hours_request.portal_no_employee', {})
        
        # Parámetros de paginación
        items_per_page = 20
        page = max(1, int(page))
        offset = (page - 1) * items_per_page
        
        # Obtener solicitudes del empleado
        domain = [
            ('employee_id', '=', employee.id),
            ('company_id', '=', employee.company_id.id)
        ]
        
        total_items = request.env['hr.extra.hours.request'].search_count(domain)
        total_pages = (total_items - 1) // items_per_page + 1 if total_items > 0 else 1
        
        # Obtener solicitudes con paginación
        requests = request.env['hr.extra.hours.request'].search(
            domain,
            offset=offset,
            limit=items_per_page,
            order='date desc, id desc'
        )
        
        # Obtener motivos para el formulario
        reasons = request.env['hr.extra.hours.reason'].search([
            ('active', '=', True)
        ])
        
        values = {
            'requests': requests,
            'employee': employee,
            'reasons': reasons,
            'page': page,
            'total_pages': total_pages,
            'total_items': total_items,
            'page_name': 'extra_hours',
        }
        
        return request.render('kc_hr_extra_hours_request.portal_my_extra_hours', values)

    @http.route(['/my/extra-hours/<int:request_id>'], 
                type='http', auth='user', website=True)
    def portal_extra_hours_detail(self, request_id, **kw):
        """Detalle de una solicitud de horas extra"""
        employee = self._get_current_employee()
        
        if not employee:
            return request.render('kc_hr_extra_hours_request.portal_no_employee', {})
        
        # Obtener la solicitud
        extra_hours_request = request.env['hr.extra.hours.request'].browse(request_id)
        
        # Verificar que la solicitud pertenezca al empleado
        if not extra_hours_request.exists() or extra_hours_request.employee_id.id != employee.id:
            return request.redirect('/my/extra-hours')
        
        values = {
            'extra_hours_request': extra_hours_request,
            'employee': employee,
            'page_name': 'extra_hours_detail',
        }
        
        return request.render('kc_hr_extra_hours_request.portal_extra_hours_detail', values)

    @http.route(['/my/extra-hours/new'], 
                type='http', auth='user', website=True, methods=['GET'])
    def portal_extra_hours_new(self, **kw):
        """Formulario para crear nueva solicitud de horas extra"""
        employee = self._get_current_employee()
        
        if not employee:
            return request.render('kc_hr_extra_hours_request.portal_no_employee', {})
        
        # Obtener motivos activos
        reasons = request.env['hr.extra.hours.reason'].search([
            ('active', '=', True)
        ])
        
        # Obtener fecha actual
        today = fields.Date.context_today(employee) if employee else date.today()
        
        values = {
            'employee': employee,
            'reasons': reasons,
            'today': today,
            'page_name': 'extra_hours_new',
        }
        
        return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', values)

    @http.route(['/my/extra-hours/create'], 
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_extra_hours_create(self, **kw):
        """Crear nueva solicitud de horas extra desde el portal"""
        employee = self._get_current_employee()
        
        if not employee:
            return request.redirect('/my/extra-hours')
        
        try:
            # Validar datos requeridos
            if not kw.get('date'):
                return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                    'employee': employee,
                    'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                    'error': 'La fecha es obligatoria',
                    'page_name': 'extra_hours_new',
                })
            
            if not kw.get('check_in'):
                return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                    'employee': employee,
                    'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                    'error': 'La hora de entrada es obligatoria',
                    'page_name': 'extra_hours_new',
                })
            
            if not kw.get('check_out'):
                return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                    'employee': employee,
                    'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                    'error': 'La hora de salida es obligatoria',
                    'page_name': 'extra_hours_new',
                })
            
            if not kw.get('reason_id'):
                return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                    'employee': employee,
                    'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                    'error': 'El motivo es obligatorio',
                    'page_name': 'extra_hours_new',
                })
            
            if not kw.get('justification'):
                return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                    'employee': employee,
                    'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                    'error': 'La justificación es obligatoria',
                    'page_name': 'extra_hours_new',
                })
            
            # Crear la solicitud
            # Convertir formato datetime-local (YYYY-MM-DDTHH:mm) a formato Odoo (YYYY-MM-DD HH:MM:SS)
            check_in_str = kw['check_in'].replace('T', ' ')
            if len(check_in_str.split(':')) == 2:  # Si no tiene segundos, agregarlos
                check_in_str += ':00'
            check_in = fields.Datetime.from_string(check_in_str)
            
            check_out_str = kw['check_out'].replace('T', ' ')
            if len(check_out_str.split(':')) == 2:  # Si no tiene segundos, agregarlos
                check_out_str += ':00'
            check_out = fields.Datetime.from_string(check_out_str)
            
            # Determinar el tipo
            # Esto es una simplificación, deberías calcularlo basándote en el horario laboral
            request_type = kw.get('type', 'late')
            
            values = {
                'employee_id': employee.id,
                'date': kw['date'],
                'check_in': check_in,
                'check_out': check_out,
                'type': request_type,
                'reason_id': int(kw['reason_id']),
                'justification': kw['justification'],
                'state': 'draft',
            }
            
            extra_hours_request = request.env['hr.extra.hours.request'].sudo().create(values)
            
            # Si se envía directamente, cambiar a "por aprobar"
            if kw.get('submit') == 'submit':
                extra_hours_request.action_submit()
            
            return request.redirect(f'/my/extra-hours/{extra_hours_request.id}?success=1')
            
        except Exception as e:
            _logger.error(f"Error creando solicitud de horas extra: {e}")
            return request.render('kc_hr_extra_hours_request.portal_extra_hours_new', {
                'employee': employee,
                'reasons': request.env['hr.extra.hours.reason'].search([('active', '=', True)]),
                'error': f'Error al crear la solicitud: {str(e)}',
                'page_name': 'extra_hours_new',
            })

