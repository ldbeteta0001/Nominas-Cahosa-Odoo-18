# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ConfigOvertimeHours(models.Model):
    """Configuración de rangos de horas extra"""
    _name = 'config.overtime.hours'
    _description = 'Configuración de Rangos de Horas Extra'
    _order = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        help='Nombre descriptivo de esta configuración'
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('active', 'Activo'),
    ], string='Estado', default='draft', required=True, tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company
    )
    active = fields.Boolean(string='Activo', default=True)

    # Rangos de horas extra
    hour_25_from = fields.Float(
        string='HE 25% Desde',
        required=True,
        help='Hora de inicio del rango de horas extra al 25% (formato: 18.5 = 18:30)'
    )
    hour_25_to = fields.Float(
        string='HE 25% Hasta',
        required=True,
        help='Hora de fin del rango de horas extra al 25% (formato: 20.5 = 20:30)'
    )
    hour_50_from = fields.Float(
        string='HE 50% Desde',
        required=True,
        help='Hora de inicio del rango de horas extra al 50% (formato: 20.5 = 20:30)'
    )
    hour_50_to = fields.Float(
        string='HE 50% Hasta',
        required=True,
        help='Hora de fin del rango de horas extra al 50% (formato: 22.5 = 22:30)'
    )
    hour_75_from = fields.Float(
        string='HE 75% Desde',
        required=True,
        help='Hora de inicio del rango de horas extra al 75% (formato: 22.5 = 22:30)'
    )
    hour_75_to = fields.Float(
        string='HE 75% Hasta',
        required=True,
        help='Hora de fin del rango de horas extra al 75% (formato: 6.0 = 06:00 del día siguiente)'
    )

    @api.constrains('hour_25_from', 'hour_25_to', 'hour_50_from', 'hour_50_to', 
                    'hour_75_from', 'hour_75_to')
    def _check_hour_ranges(self):
        """Validar que los rangos sean lógicos"""
        for record in self:
            if record.hour_25_from >= record.hour_25_to:
                raise ValidationError(_('El rango HE 25% es inválido: Desde debe ser menor que Hasta'))
            if record.hour_50_from >= record.hour_50_to:
                raise ValidationError(_('El rango HE 50% es inválido: Desde debe ser menor que Hasta'))
            if record.hour_75_from >= record.hour_75_to and record.hour_75_to >= record.hour_75_from:
                # Permitir rangos que cruzan medianoche (ej: 22.5 a 6.0)
                if not (record.hour_75_from > 12 and record.hour_75_to < 12):
                    raise ValidationError(_('El rango HE 75% es inválido'))

    def action_activate(self):
        """Activar esta configuración y desactivar las demás"""
        self.ensure_one()
        # Desactivar otras configuraciones activas
        self.env['config.overtime.hours'].search([
            ('state', '=', 'active'),
            ('id', '!=', self.id)
        ]).write({'state': 'draft'})
        self.write({'state': 'active'})

    def action_draft(self):
        """Pasar a borrador"""
        self.write({'state': 'draft'})

