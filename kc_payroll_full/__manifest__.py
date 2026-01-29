# -*- coding: utf-8 -*-
{
    'name': 'KC - Nómina Completa',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'Módulo completo de nómina con gestión de horarios y horas extra',
    'description': """
        Módulo de nómina completo que incluye:
        - Gestión de horarios de trabajo
        - Cálculo de horas extra (HE25, HE50, HE75)
        - Historial de cambios de horarios
        - Nómina semanal con límite de 44 horas normales
        - Turnos nocturnos
    """,
    'author': 'Kenosis Company',
    'website': 'https://www.kenosiscompany.com',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'hr_payroll',
        'hr_attendance',
        'resource',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/resource_calendar_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_employee_shift_views.xml',
        'views/hr_employee_schedule_history_views.xml',
        'views/hr_employee_shift_history_views.xml',
        'views/hr_employee_shift_assignment_views.xml',
        'wizard/hr_shift_assignment_import_views.xml',
        'views/hr_shift_rotation_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_attendance_views.xml',
        'views/overtime_config_views.xml',
        'wizard/change_schedule_wizard_views.xml',
        'wizard/hr_attendance_import_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}

