# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrExtraHoursApprovalWizard(models.TransientModel):
    _name = 'hr.extra.hours.approval.wizard'
    _description = 'Asistente de Aprobación de Horas Extra'

    request_id = fields.Many2one(
        'hr.extra.hours.request',
        string='Solicitud',
        required=True
    )
    
    action = fields.Selection([
        ('approve', 'Aprobar'),
        ('reject', 'Rechazar')
    ], string='Acción', required=True, default='approve')
    
    payable_hours = fields.Float(
        string='Horas Pagables',
        help='Modificar las horas que serán pagadas'
    )
    
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        help='Especificar el motivo del rechazo'
    )
    
    comment = fields.Text(
        string='Comentarios Adicionales',
        help='Comentarios adicionales sobre la decisión'
    )

    @api.model
    def default_get(self, fields_list):
        res = super(HrExtraHoursApprovalWizard, self).default_get(fields_list)
        
        if 'request_id' in self.env.context:
            request_id = self.env.context['request_id']
            request = self.env['hr.extra.hours.request'].browse(request_id)
            res['payable_hours'] = request.payable_hours
        
        return res

    def action_confirm(self):
        """Confirmar la acción de aprobación o rechazo"""
        self.ensure_one()
        
        if not self.env.user.has_group('hr_extra_hours_request.group_hr_extra_hours_manager'):
            raise UserError(_('No tiene permisos para aprobar o rechazar solicitudes de horas extra.'))
        
        if self.action == 'approve':
            self._approve_request()
        elif self.action == 'reject':
            self._reject_request()
        
        return {'type': 'ir.actions.act_window_close'}

    def _approve_request(self):
        """Aprobar la solicitud"""
        self.request_id.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
            'payable_hours': self.payable_hours,
        })
        
        # Crear mensaje de seguimiento
        message = _('Solicitud aprobada por %s') % self.env.user.name
        if self.comment:
            message += _('\nComentarios: %s') % self.comment
        
        self.request_id.message_post(body=message)

    def _reject_request(self):
        """Rechazar la solicitud"""
        if not self.rejection_reason:
            raise UserError(_('Debe especificar el motivo del rechazo.'))
        
        self.request_id.write({
            'state': 'rejected',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
            'rejection_reason': self.rejection_reason,
        })
        
        # Crear mensaje de seguimiento
        message = _('Solicitud rechazada por %s\nMotivo: %s') % (
            self.env.user.name,
            self.rejection_reason
        )
        if self.comment:
            message += _('\nComentarios adicionales: %s') % self.comment
        
        self.request_id.message_post(body=message)


class HrExtraHoursRejectionWizard(models.TransientModel):
    _name = 'hr.extra.hours.rejection.wizard'
    _description = 'Asistente de Rechazo de Horas Extra'

    request_id = fields.Many2one(
        'hr.extra.hours.request',
        string='Solicitud',
        required=True
    )
    
    rejection_reason = fields.Text(
        string='Motivo de Rechazo',
        required=True,
        help='Especificar el motivo del rechazo'
    )
    
    comment = fields.Text(
        string='Comentarios Adicionales',
        help='Comentarios adicionales sobre el rechazo'
    )

    def action_reject(self):
        """Confirmar el rechazo"""
        self.ensure_one()
        
        if not self.env.user.has_group('hr_extra_hours_request.group_hr_extra_hours_manager'):
            raise UserError(_('No tiene permisos para rechazar solicitudes de horas extra.'))
        
        self.request_id.write({
            'state': 'rejected',
            'approved_by': self.env.user.id,
            'approved_date': fields.Datetime.now(),
            'rejection_reason': self.rejection_reason,
        })
        
        # Crear mensaje de seguimiento
        message = _('Solicitud rechazada por %s\nMotivo: %s') % (
            self.env.user.name,
            self.rejection_reason
        )
        if self.comment:
            message += _('\nComentarios adicionales: %s') % self.comment
        
        self.request_id.message_post(body=message)
        
        return {'type': 'ir.actions.act_window_close'}
