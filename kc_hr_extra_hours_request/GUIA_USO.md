# 📖 Guía de Uso - Módulo KC Gestión de Horas Extra

## 🎯 Resumen Ejecutivo

Este módulo gestiona automáticamente las solicitudes de horas extra detectadas desde los registros de asistencia, con un flujo de aprobación por jefe inmediato y reportes completos para RRHH.

---

## ⚙️ Configuración Inicial

### 1. Configurar Empleados

**Ruta:** `Recursos Humanos > Empleados`

Para cada empleado:
- ✅ **Asignar Jefe Inmediato** (`Jefe`): Obligatorio para que funcione la aprobación
- ✅ **Asignar Sucursal** (`Sucursal`): Opcional, para reportes por sucursal
- ✅ **Tolerancia de Horas Extra** (minutos): Por defecto 15 minutos
  - Si las horas extra son menores a la tolerancia, NO se crea solicitud automática

### 2. Configurar Calendario Laboral

**Ruta:** `Recursos Humanos > Configuración > Calendarios Laborales`

- ✅ Asegurar que cada empleado tenga un calendario laboral asignado en su contrato activo
- ✅ El sistema usa el calendario del contrato activo para detectar el horario esperado

### 3. Motivos de Horas Extra

**Ruta:** `Recursos Humanos > Horas Extra > Motivos`

El módulo incluye motivos predefinidos:
- Detección Automática
- Proyecto Urgente
- Cumplimiento de Fecha Límite
- Emergencia
- Capacitación
- Reunión Importante
- Otros

✅ Puedes agregar más motivos si es necesario

---

## 🔄 Funcionamiento Automático

### ¿Cómo Funciona la Detección Automática?

1. **Empleado registra asistencia** (Check-in y Check-out)
2. **Sistema calcula** si hay horas fuera del horario laboral:
   - Entrada antes del horario esperado
   - Salida después del horario esperado
   - O ambas
3. **Sistema verifica tolerancia**: Si las horas extra son menores a la tolerancia configurada, NO crea solicitud
4. **Sistema crea solicitud automática** con:
   - Estado: "Por Aprobar"
   - Motivo: "Detección Automática"
   - Tipo: Entrada Anticipada / Salida Tardía / Ambas
   - Horas calculadas automáticamente
5. **Jefe recibe notificación** (actividad de correo) para revisar la solicitud

### Ejemplo Práctico

**Escenario:**
- Empleado con horario: 8:00 AM - 5:00 PM
- Tolerancia: 15 minutos
- Registro real: Entrada 7:30 AM, Salida 6:00 PM

**Resultado:**
- ✅ Se detecta: 0.5 horas de entrada anticipada + 1 hora de salida tardía = 1.5 horas extra
- ✅ Como es mayor a 15 minutos, se crea solicitud automática
- ✅ Tipo: "Entrada Anticipada y Salida Tardía"
- ✅ Estado: "Por Aprobar"
- ✅ Jefe recibe notificación

---

## 👤 Uso por Rol

### 👷 Para Empleados

#### Ver Mis Solicitudes

**Ruta:** `Recursos Humanos > Horas Extra > Solicitudes`

O desde el portal: `Mi Portal > Mis Horas Extra`

**Qué puedes ver:**
- ✅ Todas tus solicitudes (automáticas y manuales)
- ✅ Estado actual (Borrador, Por Aprobar, Aprobada, Rechazada)
- ✅ Detalles: fecha, horas, motivo, justificación
- ✅ Historial de aprobación/rechazo

#### Crear Solicitud Manual

1. **Ruta:** `Recursos Humanos > Horas Extra > Solicitudes > Crear`
2. **Completar campos:**
   - Empleado: Se pre-selecciona tu usuario
   - Fecha: Seleccionar fecha
   - Hora de Entrada: Fecha y hora
   - Hora de Salida: Fecha y hora
   - Tipo: Entrada Anticipada / Salida Tardía / Ambas
   - Motivo: Seleccionar de la lista
   - Justificación: **Obligatorio** - Descripción detallada
3. **Guardar** → Estado inicial: "Borrador"
4. **Enviar** (botón "Enviar") → Cambia a "Por Aprobar"
5. **Notificar al jefe** automáticamente

#### Desde el Formulario de Empleado

**Ruta:** `Recursos Humanos > Empleados > [Tu Empleado]`

En el formulario verás:
- **Botón "Horas Extra"**: Muestra contador de solicitudes
- **Click en el botón**: Abre todas tus solicitudes

---

### 👔 Para Jefes

#### Revisar Solicitudes Pendientes

**Ruta:** `Recursos Humanos > Horas Extra > Solicitudes`

**Filtros útiles:**
- 🔍 "Por Aprobar" - Ver solo pendientes
- 🔍 "Este Mes" - Ver solicitudes del mes actual
- 🔍 Agrupar por "Empleado" - Ver solicitudes por subordinado

**También puedes ver:**
- 📧 **Notificaciones**: Actividades pendientes en tu bandeja
- 📧 **Correos**: Notificaciones de nuevas solicitudes

#### Aprobar Solicitud

**Opción 1: Desde la Lista**
1. Buscar la solicitud
2. Abrir la solicitud
3. Click en botón **"Aprobar"**
4. Sistema automáticamente:
   - ✅ Cambia estado a "Aprobada"
   - ✅ Registra tu usuario como aprobador
   - ✅ Guarda fecha y hora de aprobación
   - ✅ Notifica al empleado

**Opción 2: Modificar Horas Pagables**
1. Abrir la solicitud
2. **Revisar "Horas Pagables"**:
   - Por defecto = Horas calculadas
   - Puedes modificarlas si es necesario (ej: redondear, ajustar)
3. Click en **"Aprobar"**
4. Las horas pagables modificadas se guardan

**Qué puedes modificar antes de aprobar:**
- ✅ Horas Pagables (solo en estado "Por Aprobar")
- ❌ NO puedes modificar: fecha, horas de entrada/salida, empleado

#### Rechazar Solicitud

**Método 1: Botón Rechazar**
1. Abrir la solicitud
2. Click en **"Rechazar"**
3. Se abre wizard para ingresar:
   - **Motivo de Rechazo** (obligatorio)
   - Comentarios adicionales (opcional)
4. Click en **"Confirmar"**
5. Sistema:
   - ✅ Cambia estado a "Rechazada"
   - ✅ Guarda motivo de rechazo
   - ✅ Notifica al empleado

**Método 2: Wizard de Aprobación**
1. Abrir solicitud
2. En el wizard de aprobación, seleccionar acción "Rechazar"
3. Completar motivo
4. Confirmar

#### Ver Solicitudes de Tus Subordinados

**Filtros recomendados:**
- 🔍 Agrupar por "Empleado" para ver todos tus subordinados
- 🔍 Filtro por "Estado" para ver aprobadas/rechazadas/pendientes
- 🔍 Filtro "Este Mes" para ver actividad reciente

---

### 👔👔 Para RRHH / Administradores

#### Acceso Completo

**Ruta:** `Recursos Humanos > Horas Extra`

**Permisos:**
- ✅ Ver TODAS las solicitudes de todos los empleados
- ✅ Aprobar/Rechazar cualquier solicitud
- ✅ Configurar motivos de horas extra
- ✅ Generar reportes completos
- ✅ Exportar datos a Excel

#### Generar Reportes

**Ruta:** `Recursos Humanos > Horas Extra > Reportes`

**Tipos de Reportes Disponibles:**

1. **📊 Análisis (Vista Pivot)**
   - Agrupar por: Empleado, Motivo, Sucursal, Tipo, Estado
   - Medir: Duración (horas), Horas Pagables
   - **Uso:** Análisis detallado y personalizado

2. **📈 Gráficos**
   - Gráfico de barras por empleado
   - Gráfico de pastel por motivo
   - Gráfico de líneas (evolución temporal)
   - **Uso:** Visualización rápida de tendencias

3. **📋 Reporte por Empleado**
   - Agrupa todas las solicitudes por empleado
   - **Uso:** Ver resumen por persona

4. **📋 Reporte por Motivo**
   - Agrupa por motivo de horas extra
   - **Uso:** Analizar razones más comunes

5. **📋 Reporte por Sucursal**
   - Agrupa por sucursal/ubicación
   - **Uso:** Comparar entre oficinas

6. **📥 Exportar a Excel**
   - Wizard completo con filtros:
     - ✅ Rango de fechas
     - ✅ Empleados específicos
     - ✅ Departamentos
     - ✅ Sucursales
     - ✅ Estado (Aprobadas, Rechazadas, etc.)
     - ✅ Tipo de reporte (Resumen, Detallado, Por Empleado, Por Motivo, Por Sucursal)
   - **Uso:** Análisis fuera de Odoo, compartir con otras áreas

#### Configurar Motivos

**Ruta:** `Recursos Humanos > Horas Extra > Motivos`

- ✅ Crear nuevos motivos
- ✅ Editar motivos existentes
- ✅ Desactivar motivos (campo "Activo")
- ✅ Ordenar por secuencia

---

## 📋 Estados de las Solicitudes

| Estado | Descripción | Quién puede cambiar | Acciones disponibles |
|--------|-------------|---------------------|----------------------|
| **Borrador** | Solicitud creada pero no enviada | Empleado | Editar, Enviar, Eliminar |
| **Por Aprobar** | Enviada, esperando aprobación del jefe | Jefe / RRHH | Aprobar, Rechazar, Ver |
| **Aprobada** | Aprobada por el jefe | RRHH | Ver, Resetear a Borrador |
| **Rechazada** | Rechazada por el jefe | RRHH | Ver, Resetear a Borrador |

---

## 🔍 Casos de Uso Comunes

### Caso 1: Horas Extra Automáticas

**Escenario:** Empleado trabajó hasta tarde

1. ✅ Empleado registra asistencia (Check-in y Check-out)
2. ✅ Sistema detecta salida fuera de horario
3. ✅ Sistema crea solicitud automática "Por Aprobar"
4. ✅ Jefe recibe notificación
5. ✅ Jefe revisa y aprueba
6. ✅ Empleado ve su solicitud aprobada

### Caso 2: Solicitud Manual Preventiva

**Escenario:** Empleado sabe que trabajará horas extra mañana

1. ✅ Empleado crea solicitud manual en estado "Borrador"
2. ✅ Completa todos los campos
3. ✅ Guarda (estado Borrador)
4. ✅ Al día siguiente, cuando trabaje las horas:
   - Opción A: Enviar solicitud manualmente
   - Opción B: Si registra asistencia, el sistema puede crear solicitud automática también
5. ✅ Jefe aprueba la solicitud

### Caso 3: Ajuste de Horas Pagables

**Escenario:** Jefe quiere ajustar las horas pagables

1. ✅ Sistema detecta 2.3 horas extra automáticamente
2. ✅ Jefe abre la solicitud
3. ✅ Jefe modifica "Horas Pagables" a 2.5 horas (redondeo)
4. ✅ Jefe aprueba
5. ✅ Se guardan 2.5 horas pagables (no 2.3)

### Caso 4: Rechazo con Justificación

**Escenario:** Jefe rechaza solicitud por falta de autorización previa

1. ✅ Solicitud en estado "Por Aprobar"
2. ✅ Jefe abre la solicitud
3. ✅ Click en "Rechazar"
4. ✅ Ingresa motivo: "Falta autorización previa del supervisor"
5. ✅ Confirma rechazo
6. ✅ Empleado recibe notificación con motivo de rechazo

### Caso 5: Reporte Mensual para Nómina

**Escenario:** RRHH necesita reporte mensual de horas extra aprobadas

1. ✅ RRHH va a `Reportes > Exportar a Excel`
2. ✅ Configura:
   - Fecha desde: Primer día del mes
   - Fecha hasta: Último día del mes
   - Estado: Solo Aprobadas
   - Tipo: Detallado
3. ✅ Click en "Generar Reporte"
4. ✅ Descarga archivo Excel
5. ✅ Comparte con nómina

---

## ⚠️ Puntos Importantes

### ✅ Funciona Bien Cuando:
- ✅ Empleados tienen jefe asignado (`parent_id`)
- ✅ Empleados tienen calendario laboral en su contrato activo
- ✅ Los registros de asistencia tienen check-in Y check-out
- ✅ La tolerancia está configurada apropiadamente

### ❌ No Funciona Si:
- ❌ Empleado no tiene jefe asignado → No puede enviar para aprobación
- ❌ Empleado no tiene calendario laboral → No puede detectar horas extra automáticamente
- ❌ Registro de asistencia incompleto → No detecta horas extra hasta que haya check-out
- ❌ Horas extra menores a la tolerancia → No crea solicitud (esto es por diseño)

### 🔧 Soluciones a Problemas Comunes

**Problema:** No se crean solicitudes automáticas
- ✅ Verificar que el empleado tenga calendario laboral
- ✅ Verificar que el registro tenga check-in y check-out
- ✅ Verificar la tolerancia configurada
- ✅ Verificar que el horario en el calendario sea correcto

**Problema:** No puedo aprobar/rechazar
- ✅ Verificar que tengas el grupo "Gestor de Horas Extra"
- ✅ Verificar que la solicitud esté en estado "Por Aprobar"

**Problema:** No veo notificaciones
- ✅ Verificar bandeja de actividades (icono campana)
- ✅ Verificar configuración de correo electrónico
- ✅ Verificar que el jefe tenga usuario asociado al empleado

---

## 📍 Ubicación de Menús

### Menú Principal
`Recursos Humanos > Horas Extra`

### Submenús
- **Solicitudes**: Lista completa de solicitudes
- **Motivos**: Gestión de motivos (solo RRHH)
- **Reportes**: 
  - Análisis (Pivot)
  - Gráficos
  - Por Empleado
  - Por Motivo
  - Por Sucursal
  - Exportar a Excel

### Desde Empleados
`Recursos Humanos > Empleados > [Empleado] > Botón "Horas Extra"`

### Desde Asistencia
`Recursos Humanos > Asistencia > [Registro] > Botón "Ver Solicitud de Horas Extra"` (solo si tiene solicitud)

### Portal
`Mi Portal > Mis Horas Extra` (para empleados)

---

## 🎓 Resumen Rápido

### Para Empleados:
1. Las solicitudes se crean automáticamente al registrar asistencia fuera de horario
2. Puedes crear solicitudes manuales si es necesario
3. Consulta el estado de tus solicitudes en cualquier momento
4. Recibirás notificaciones cuando tu jefe apruebe o rechace

### Para Jefes:
1. Recibirás notificaciones cuando haya solicitudes pendientes
2. Revisa y aprueba/rechaza desde la lista de solicitudes
3. Puedes ajustar las horas pagables antes de aprobar
4. Debes justificar los rechazos

### Para RRHH:
1. Acceso completo a todas las solicitudes
2. Genera reportes pivot, gráficos y exportaciones Excel
3. Configura motivos de horas extra
4. Analiza tendencias y patrones

---

**¿Necesitas ayuda?** Revisa los logs del sistema o contacta al administrador de Odoo.

