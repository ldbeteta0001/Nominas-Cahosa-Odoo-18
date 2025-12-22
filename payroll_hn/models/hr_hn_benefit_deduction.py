from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

class HrHnBenefitDeduction(models.Model):
    _name = 'hr.hn.benefit.deduction'
    _description = 'Beneficios y deducciones HN'
    _rec_name = "rule_id"

    category = fields.Selection(string="Categoría", selection=[('DED','Deducción'),('ALW','Beneficio')], required=True)
    rule_id = fields.Many2one(string="Regla", comodel_name="hr.salary.rule", required=True)
    state = fields.Selection(string="Estado", selection=[('draft','Borrador'),('pause','Pausa'),('progress','Progreso'),('done','Finalizado')], default='draft')
    periodicity = fields.Selection(string="Periodicidad", selection=[('finite','Finito'),('infinite','Infinito')], required=True)
    fee_amount = fields.Float(string="Cuota mensual")
    fee_amount_apply = fields.Float(string="Monto cuota aplicar", compute="_compute_fee_amount_apply", store=True)
    schedule_pay = fields.Selection(string="Pago programado", related="contract_id.schedule_pay")
    apply_in = fields.Selection([('first', 'Primera quincena'),('second', 'Segunda quincena'),('both', 'Ambas quincenas')], string="Aplicar en", default="both")
    currency_id = fields.Many2one(string='Currency', comodel_name='res.currency', default=lambda self:self.env.user.company_id.currency_id.id, required=True)
    contract_id = fields.Many2one(string="Contrato", comodel_name="hr.contract")
    description = fields.Char(string="Descripción")
    
    # Campos de la periodicidad finita
    start_date = fields.Date(string="Fecha de inicio")
    fee_numbers = fields.Integer(string="Número de cuotas", help="Cantidad de cuotas totales que se deducirán. (cuotas segun la periodicidad de pago)")
    fee_numbers_remaining = fields.Integer(string="Número de cuotas restantes", compute="_compute_fee_numbers_remaining")
    fee_numbers_apply = fields.Integer(string="Número de cuotas aplicadas", default=0, store=True)
    total_fee_residual = fields.Float(string="Total cuotas residual", compute="_compute_total_fee_residual")

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_pause(self):
        self.write({'state': 'pause'})
    
    def action_progress(self):
        self.write({'state': 'progress'})

    def action_done(self):
        self.write({'state': 'done'})
    
    @api.depends('fee_numbers','fee_numbers_apply')
    def _compute_fee_numbers_remaining(self):
        for record in self:
            record.fee_numbers_remaining = record.fee_numbers - record.fee_numbers_apply

    @api.depends('fee_amount_apply','fee_numbers','fee_numbers_apply')
    def _compute_total_fee_residual(self):
        for record in self:
            record.total_fee_residual = (record.fee_numbers * record.fee_amount_apply) - (record.fee_numbers_apply * record.fee_amount_apply)

    @api.depends('schedule_pay','fee_amount','apply_in')
    def _compute_fee_amount_apply(self):
        # fee_amount = monto mensual
        # fee_amount_apply = monto por cuota según schedule_pay (se calcula dividiendo el mensual)
        frequency_divider = {
            'annually': 12,  # Anual: dividir mensual entre 12
            'semi-annually': 6,  # Semestral: dividir mensual entre 6
            'quarterly': 4,  # Trimestral: dividir mensual entre 4
            'bi-monthly': 2,  # Bimestral: dividir mensual entre 2
            'monthly': 1,  # Mensual: sin conversión
            'bi-weekly': 0.5,  # Quincenal: dividir mensual entre 0.5 (multiplicar por 2)
            'weekly': 4.33,  # Semanal: dividir mensual entre 4.33
        }
        
        for rec in self:
            # Para quincenal, ajustar según apply_in
            if rec.schedule_pay == 'bi-weekly':
                if rec.apply_in == 'both':
                    # Si se aplica en ambas quincenas, el monto por cuota es la mitad del mensual
                    rec.fee_amount_apply = rec.fee_amount / 2
                else:
                    # Si solo se aplica en una quincena, el monto por cuota es igual al mensual
                    rec.fee_amount_apply = rec.fee_amount
            else:
                # Calcular el monto por cuota dividiendo el mensual
                divider = frequency_divider.get(rec.schedule_pay, 1)
                rec.fee_amount_apply = rec.fee_amount / divider
    
    def get_fee_amount(self):
        return self.fee_amount_apply