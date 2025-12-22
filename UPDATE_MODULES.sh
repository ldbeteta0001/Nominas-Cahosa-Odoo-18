#!/bin/bash
# Script para actualizar todos los módulos modificados
# Módulos modificados en esta sesión:
# - l10n_hn_hr_contract: Eliminados campos is_perifoneo e is_animador
# - l10n_hn_hr_holidays: Eliminados campos relacionados is_perifoneo e is_animador
# - kc_payroll_full: Agregado wizard para importar IDs biométricos
# - l10n_hn_hr_recruitment: Eliminados campos firstname, firstname2, lastname, lastname2 y dependencias
# - l10n_hn_hr_payroll: Eliminada dependencia de hr_hn_employee_lastnames
# - kc_biometric_connect: Ajustada vista de empleado para mostrar etiquetas correctamente
# NOTA: Los módulos hr_employee_firstname y hr_hn_employee_lastnames han sido eliminados completamente

sudo -u odoo /usr/bin/odoo -c /etc/odoo/odoo.conf -d main -u l10n_hn_hr_contract,l10n_hn_hr_holidays,kc_payroll_full,l10n_hn_hr_recruitment,l10n_hn_hr_payroll,kc_biometric_connect --stop-after-init

