# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from datetime import datetime
from odoo.exceptions import ValidationError, UserError
from odoo.addons.base.models.ir_mail_server import MailDeliveryException
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"


    # Datos de la familia
    family_ids = fields.One2many(string="Families", comodel_name='hr.family', inverse_name='employee_id')

    children = fields.Integer(compute='_compute_children', string='Number of Children',
                              help=_('The number of children you register on the Family page is counted here.'))

    # asignación organizativa
    hr_employee_company = fields.Char(string='Empresa',
                                      compute='_compute_department_company', readonly=True, store=True)
    hr_employee_sucursal = fields.Char(string='Sucursal',
                                       compute='_compute_department_sucursal', readonly=True, store=True)
    spouse_complete_name = fields.Char(string="Spouse Complete Name", groups="hr.group_hr_user", tracking=True,
                                       compute='_compute_spouse_name', readonly=True, store=True,
                                       help=_('Debe llenar los datos familiares.'))
    spouse_birthdate = fields.Date(string="Spouse Birthdate", groups="hr.group_hr_user", tracking=True,
                                   compute='_compute_spouse_birthdate', readonly=True, store=True,
                                   help=_('Debe llenar los datos familiares.'))

    hr_employee_blood_type_id = fields.Many2one('hr.blood.type', string='Tipo de sangre', )
    weight = fields.Float(string='Peso', help='Peso en libras')
    height = fields.Float(string='Altura', help='Altura en metro y centímetros')
    rtn = fields.Char(string="Registro Tributario Nacional")

    registration_number = fields.Char(required=False)

    @api.model
    def create(self, vals):
        sequence_code = 'hr.employee.registration_number'
        sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)
        # si existe la secuencia  o está activa sw optiene el consecutivo
        if sequence and sequence.active:
            vals['registration_number'] = sequence.next_by_code(sequence_code)
        res = super(HrEmployee, self).create(vals)
        return res

    @api.depends('family_ids')
    def _compute_children(self):
        for rec in self:
            rec.children = 0
            if rec.id:
                family = rec.family_ids.filtered(lambda f: f.kindred == 'son')
                if family:
                    rec.children = len(family.ids)

    @api.depends('marital', 'family_ids')
    def _compute_spouse_name(self):
        for rec in self:
            if rec.marital == 'married':
                sister_family = rec.family_ids.filtered(lambda f: f.kindred == 'wife')
                if sister_family:
                    rec.spouse_complete_name = sister_family.name

    @api.depends('marital', 'family_ids')
    def _compute_spouse_birthdate(self):
        for rec in self:
            if rec.marital == 'married':
                sister_family = rec.family_ids.filtered(lambda f: f.kindred == 'wife')
                if sister_family:
                    rec.spouse_birthdate = sister_family.date_of_birth

    @api.depends('department_id')
    def _compute_department_company(self):
        level = 0
        for record in self:
            if record.department_id:
                if record.department_id.level == level:
                    record.hr_employee_company = record.department_id.name
                else:
                    record.hr_employee_company = self.find_top_department(record.department_id, level)
            else:
                record.hr_employee_company = ''

    @api.depends('department_id')
    def _compute_department_sucursal(self):
        level = 1
        for record in self:
            if record.department_id:
                if record.department_id.level == level:
                    record.hr_employee_sucursal = record.department_id.name
                else:
                    record.hr_employee_sucursal = self.find_top_department(record.department_id, level)
            else:
                record.hr_employee_sucursal = ''

    def find_top_department(self, department, level):
        if department.level == level:
            return department.name
        elif department.parent_id:
            return self.find_top_department(department.parent_id, level)
        else:
            return False

    @api.model
    def get_employees_of_months(self, sections=None):
        result = {}
        current_month = datetime.now().month
        res = self.search([('birthday', '!=', False)], order='birthday asc')
        list_empl = []
        if res:
            for r in res:
                if r.birthday.month == current_month:
                    list_empl.append({
                        'id': r.id,
                        'name': r.display_name,
                        'date_birthday': r.birthday,
                        'department': r.department_id.display_name,
                    })
        result['employees'] = list_empl
        result['month'] = datetime.now().strftime('%B').upper()
        return result

    _sql_constraints = [
        ('unique_identification_id', 'UNIQUE(identification_id, company_id)',
         'No se permiten números de identificación duplicados')
    ]

    # Para enviar correo electrónico
    def send_notification_email(self, subject, body, email_to):
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': email_to,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        try:
            mail.send()
        except MailDeliveryException as e:
            raise UserError('No se puede conectar al servidor SMTP')
        except Exception as ex:
            raise UserError(ex)

    @api.model
    def send_birthday_email(self):
        """Envía emails de cumpleaños a empleados que cumplen años hoy"""
        current_month = datetime.now().month
        current_day = datetime.now().day
        
        # Buscar empleados que cumplen años hoy
        employees = self.search([
            ('birthday', '!=', False), 
            ('work_email', '!=', False),
            ('active', '=', True)
        ])
        
        if not employees:
            return
            
        for employee in employees:
            if employee.birthday.month == current_month and employee.birthday.day == current_day:
                try:
                    subject = "Feliz cumpleaños"
                    body = f"Apreciable {employee.name}, Muchas felicidades en su día de cumpleaños. Que tenga un hermoso día"
                    email_to = employee.work_email
                    employee.send_notification_email(subject, body, email_to)
                except Exception as e:
                    # Log del error pero no interrumpir el proceso
                    _logger.warning(f"Error enviando email de cumpleaños a {employee.name}: {str(e)}")

