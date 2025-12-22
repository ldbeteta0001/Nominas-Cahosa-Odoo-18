# -*- coding: utf-8 -*-
{
    'name': 'KC - Conexión Biométrica ZKTeco',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Conexión e integración con dispositivos biométricos ZKTeco para sincronización de asistencia',
    'description': """
        Módulo para conectar dispositivos biométricos ZKTeco con Odoo:
        - Configuración de múltiples dispositivos biométricos
        - Conexión directa al dispositivo (puerto 4370) o conexión a servidor (puerto 8082)
        - Sincronización automática de registros de asistencia
        - Importación de datos de check-in y check-out
        - Integración con hr.attendance
        - Sincronización programada mediante cron
    """,
    'author': 'Kenosis Company',
    'website': 'https://www.kenosiscompany.com',
    'depends': [
        'base',
        'hr',
        'hr_attendance',
    ],
    'external_dependencies': {
        'python': ['zk', 'requests'],
    },
    'data': [
        'security/biometric_security.xml',
        'security/ir.model.access.csv',
        'views/biometric_device_views.xml',
        'views/biometric_sync_views.xml',
        'views/biometric_server_data_views.xml',
        'views/biometric_sync_server_data_wizard_views.xml',
        'views/biometric_menu.xml',
        'wizard/biometric_sync_wizard_views.xml',
        # 'data/biometric_cron.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}

