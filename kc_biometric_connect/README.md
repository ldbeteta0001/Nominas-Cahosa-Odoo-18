# KC - Conexión Biométrica ZKTeco

Módulo de Odoo para conectar dispositivos biométricos ZKTeco y sincronizar automáticamente los registros de asistencia con el módulo `hr_attendance`.

## Características

- ✅ Configuración de múltiples dispositivos biométricos ZKTeco
- ✅ Sincronización automática de registros de asistencia
- ✅ Importación de datos de check-in y check-out
- ✅ Integración completa con `hr.attendance`
- ✅ Sincronización programada mediante cron
- ✅ Asociación de empleados con IDs biométricos
- ✅ Historial completo de registros biométricos

## Requisitos

### Dependencias de Python

El módulo requiere la librería `zk` (pyzk) para conectarse a los dispositivos ZKTeco:

```bash
pip install pyzk
```

### Dependencias de Odoo

- `base`
- `hr`
- `hr_attendance`

## Instalación

1. Copiar el módulo a la carpeta de addons de Odoo
2. Actualizar la lista de módulos en Odoo
3. Instalar "KC - Conexión Biométrica ZKTeco"

## Configuración

### 1. Configurar Dispositivo Biométrico

1. Ir a **Recursos Humanos > Biométrico > Dispositivos**
2. Crear un nuevo dispositivo:
   - **Nombre**: Nombre descriptivo del dispositivo
   - **Dirección IP**: IP del dispositivo biométrico
   - **Puerto**: Puerto de comunicación (por defecto 4370)
   - **Contraseña**: Contraseña del dispositivo (si aplica)
   - **Activo**: Marcar si el dispositivo está activo
   - **Sincronización Automática**: Activar para sincronización automática

3. Hacer clic en **"Probar Conexión"** para verificar la conectividad

### 2. Configurar Empleados

1. Ir a **Recursos Humanos > Empleados**
2. Editar cada empleado y configurar:
   - **ID Biométrico**: ID del empleado en el dispositivo biométrico
   - **Dispositivo Biométrico**: Seleccionar el dispositivo asignado
   - **Sincronización Biométrica Activa**: Activar para sincronizar este empleado

### 3. Sincronización Manual

1. Ir a **Recursos Humanos > Biométrico > Dispositivos**
2. Seleccionar el dispositivo
3. Hacer clic en **"Sincronizar Asistencia"**

### 4. Sincronización Automática

El módulo incluye un cron que se ejecuta cada 30 minutos para sincronizar automáticamente todos los dispositivos activos con sincronización automática habilitada.

## Funcionamiento

### Proceso de Sincronización

1. El módulo se conecta al dispositivo biométrico usando la IP y puerto configurados
2. Obtiene todos los registros de asistencia del dispositivo
3. Agrupa los registros por empleado y fecha
4. Para cada día:
   - **Entrada**: Toma el primer registro del día (mínimo)
   - **Salida**: Toma el último registro del día (máximo)
5. Crea registros en `biometric.attendance` para historial
6. Crea o actualiza registros en `hr.attendance` con la información biométrica

### Registros Biométricos

Los registros se almacenan en dos modelos:

- **biometric.attendance**: Historial completo de todos los registros del dispositivo
- **hr.attendance**: Registros de asistencia procesados (entrada/salida por día)

## Estructura del Módulo

```
kc_biometric_connect/
├── models/
│   ├── biometric_device.py      # Modelo de dispositivo biométrico
│   ├── biometric_attendance.py  # Modelo de registros biométricos
│   ├── hr_employee.py            # Extensión de empleados
│   └── hr_attendance.py          # Extensión de asistencia
├── views/
│   ├── biometric_device_views.xml
│   ├── biometric_sync_views.xml
│   └── biometric_menu.xml
├── security/
│   ├── ir.model.access.csv
│   └── biometric_security.xml
├── data/
│   └── biometric_cron.xml
└── __manifest__.py
```

## Solución de Problemas

### Error: "La librería zk no está instalada"

Instalar la librería:
```bash
pip install pyzk
```

### Error de Conexión

- Verificar que la IP y puerto sean correctos
- Verificar que el dispositivo esté encendido y en la misma red
- Verificar que no haya firewall bloqueando la conexión

### Empleados no se sincronizan

- Verificar que el empleado tenga configurado el **ID Biométrico** correcto
- Verificar que el empleado tenga **Sincronización Biométrica Activa** habilitada
- Verificar que el empleado esté asignado al dispositivo correcto

## Autor

Kenosis Company

## Licencia

LGPL-3

