# -*- coding: utf-8 -*-
{
    'name': 'Kenocia - Gestión de Horas Extra',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Gestión completa de solicitudes de horas extra con aprobación automática',
    'description': """
        Módulo para la gestión de solicitudes de horas extra:
        - Detección automática de horas extra desde asistencia
        - Flujo de aprobación por jefe inmediato
        - Reportes pivot y gráfico
        - Control de acceso por roles
        - Integración con hr.attendance y hr.employee
    """,
    'author': 'Super2Caminos',
    'website': 'https://www.super2caminos.com',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
        'hr_contract',
        'mail',
        'portal',
        'website',
        'web',
    ],
    'data': [
        'security/hr_extra_hours_security.xml',
        'data/hr_extra_hours_data.xml',
        'views/hr_extra_hours_request_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
        'report/hr_extra_hours_reports.xml',
        'wizard/hr_extra_hours_approval_wizard.xml',
        'wizard/hr_extra_hours_report_wizard.xml',
        'views/hr_extra_hours_menu.xml',
        'views/portal_templates.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}
