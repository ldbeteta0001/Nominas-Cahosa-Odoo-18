# -*- coding: utf-8 -*-
{
    'name': 'KC - Nómina Completa',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Módulo completo de nómina con gestión de turnos y rotaciones',
    'description': """
        Módulo completo de nómina con:
        - Gestión de rotación de turnos día/noche
        - Historial de turnos por empleado
        - Programación de rotaciones
        - Importación de asistencias
        - Reportes de asistencia
    """,
    'author': 'Super2Caminos',
    'website': 'https://www.super2caminos.com',
    'depends': [
        'base',
        'hr',
        'hr_contract',
        'hr_payroll',
        'hr_attendance',
        'kc_hr_extra_hours_request',
    ],
    'data': [
        'security/ir.model.access.csv',
        'wizard/shift_assignment_import_wizard_views.xml',
        'wizard/hr_attendance_import_views.xml',
        'views/resource_calendar_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_employee_schedule_history_views.xml',
        'views/hr_shift_rotation_views.xml',
        'views/hr_employee_shift_history_views.xml',
        'views/hr_employee_shift_assignment_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
