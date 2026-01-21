# KC - Gestión de Horas Extra

## Descripción

Módulo completo para la gestión de solicitudes de horas extra en Odoo 18, que incluye:

- **Detección automática** de horas extra desde registros de asistencia
- **Flujo de aprobación** por jefe inmediato
- **Reportes pivot y gráfico** para análisis
- **Control de acceso** por roles (empleado, jefe, RRHH)
- **Integración completa** con hr.attendance y hr.employee

## Características Principales

### 🔧 Detección Automática
- Detecta automáticamente cuando un empleado entra antes o sale después del horario laboral
- Crea solicitudes automáticas con estado "Por Aprobar"
- Configurable tolerancia en minutos
- Evita duplicados verificando si ya existe una solicitud para la asistencia

### 📋 Gestión de Solicitudes
- **Estados**: Borrador, Por Aprobar, Aprobada, Rechazada
- **Campos principales**:
  - Empleado, fecha, horas de entrada/salida
  - Tipo: Entrada Anticipada, Salida Tardía, Ambas
  - Duración calculada automáticamente
  - Horas pagables (modificables por el jefe)
  - Motivo y justificación
  - Jefe inmediato para aprobación

### 👥 Control de Acceso
- **Empleados**: Solo ven sus propias solicitudes
- **Jefes**: Ven solicitudes de sus subordinados y pueden aprobar/rechazar
- **RRHH**: Acceso completo a todas las solicitudes

### 📊 Reportes y Análisis
- **Vista Pivot**: Agrupación por empleado, motivo, sucursal, tipo
- **Gráficos**: Barras, líneas, pastel
- **Exportación Excel**: Reportes personalizables con filtros
- **Análisis temporal**: Evolución por mes/año

### 🔄 Flujo de Trabajo
1. **Detección**: Sistema detecta horas extra automáticamente
2. **Notificación**: Jefe recibe actividad para revisar
3. **Aprobación**: Jefe aprueba/rechaza con justificación
4. **Seguimiento**: Empleado puede consultar estado
5. **Reportes**: RRHH genera análisis y reportes

## Instalación

1. Copiar el módulo a la carpeta de addons
2. Actualizar lista de módulos
3. Instalar "KC - Gestión de Horas Extra"

## Configuración

### 1. Configurar Empleados
- Asignar jefe inmediato (`parent_id`)
- Establecer tolerancia de horas extra (opcional)

### 2. Configurar Motivos
- El módulo incluye motivos predefinidos
- Se pueden agregar nuevos motivos desde el menú

### 3. Configurar Calendarios Laborales
- Asegurar que los empleados tengan calendarios laborales asignados
- Los calendarios se obtienen del contrato activo

## Uso

### Para Empleados
1. Acceder a "Recursos Humanos > Horas Extra > Solicitudes"
2. Las solicitudes automáticas aparecen con estado "Por Aprobar"
3. Se pueden crear solicitudes manuales si es necesario
4. Consultar estado de solicitudes en el portal

### Para Jefes
1. Recibir notificaciones de solicitudes pendientes
2. Revisar y aprobar/rechazar desde la lista de solicitudes
3. Modificar horas pagables si es necesario
4. Agregar comentarios en la decisión

### Para RRHH
1. Acceso completo a todas las solicitudes
2. Generar reportes desde "Recursos Humanos > Horas Extra > Reportes"
3. Exportar datos a Excel con filtros personalizados
4. Analizar tendencias con vistas pivot y gráficos

## Estructura del Módulo

```
kc_hr_extra_hours_request/
├── models/
│   ├── hr_extra_hours_request.py    # Modelo principal
│   ├── hr_employee.py               # Extensión de empleados
│   └── hr_attendance.py             # Extensión de asistencia
├── views/
│   ├── hr_extra_hours_request_views.xml
│   ├── hr_employee_views.xml
│   ├── hr_attendance_views.xml
│   └── hr_extra_hours_menu.xml
├── wizard/
│   ├── hr_extra_hours_approval_wizard.py
│   ├── hr_extra_hours_report_wizard.py
│   └── *.xml
├── security/
│   ├── ir.model.access.csv
│   └── hr_extra_hours_security.xml
├── data/
│   └── hr_extra_hours_data.xml
├── report/
│   └── hr_extra_hours_reports.xml
└── __manifest__.py
```

## Dependencias

- `base`
- `hr`
- `hr_attendance`
- `hr_contract`
- `mail`
- `portal`
- `web`

## Notas Técnicas

- Compatible con Odoo 18
- Usa nomenclatura actualizada (`list` en lugar de `tree`)
- Incluye validaciones de datos y restricciones
- Optimizado para rendimiento con índices apropiados
- Incluye logging para debugging

## Soporte

Para soporte técnico o consultas sobre el módulo, contactar al equipo de desarrollo de Super2Caminos.
