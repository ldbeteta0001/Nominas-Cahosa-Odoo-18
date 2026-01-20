# Documentación Detallada: `hr_attendance_extension.py`

## 📋 Propósito General

Este módulo extiende el modelo `hr.attendance` de Odoo para calcular automáticamente las horas extra (HE) de los empleados según diferentes escenarios y reglas de negocio complejas. Maneja casos especiales como turnos nocturnos, sábados sin horario, domingos, y diferentes tasas de horas extra (25%, 50%, 75%).

---

## 🏗️ Estructura del Módulo

### 1. Campos Principales

#### 1.1 Campos de Horas Extra
- **`hours_25`**: Horas extra al 25% (calculado automáticamente)
- **`hours_50`**: Horas extra al 50% (calculado automáticamente)
- **`hours_75`**: Horas extra al 75% (calculado automáticamente)
- **`sunday_hours`**: Horas trabajadas en domingo (se pagan al doble)

#### 1.2 Campos de Horarios Programados
- **`check_in_schedule`**: Hora de entrada según el horario del empleado (almacenado manualmente o calculado)
- **`check_out_schedule`**: Hora de salida según el horario del empleado (almacenado manualmente o calculado)
- **`check_in_difference`**: Diferencia en horas entre entrada real y programada (negativo = temprano, positivo = tardío)
- **`check_out_difference`**: Diferencia en horas entre salida real y programada (positivo = tardío)

#### 1.3 Campos de Configuración
- **`count_early_check_in_overtime`**: Boolean para contar entrada temprana como horas extra
- **`early_check_in_overtime_rate`**: Tasa a aplicar (25%, 50%, 75%) para entrada temprana

#### 1.4 Campos Auxiliares (Computed)
- **`is_sunday`**: Indica si el check-in es domingo
- **`is_saturday`**: Indica si el check-in es sábado
- **`is_night_shift`**: Indica si el empleado tiene turno nocturno

---

## 🔄 Métodos Principales

### 2.1 Métodos de Cálculo Automático

#### `_compute_is_sunday()` (líneas 96-102)
- **Propósito**: Determina si el check-in es domingo
- **Lógica**: Compara `weekday()` con 6 (domingo = 6 en Python)

#### `_compute_is_saturday()` (líneas 104-110)
- **Propósito**: Determina si el check-in es sábado
- **Lógica**: Compara `weekday()` con 5 (sábado = 5 en Python)

#### `_compute_is_night_shift()` (líneas 112-118)
- **Propósito**: Determina si el empleado tiene turno nocturno
- **Lógica**: Lee el campo `nocturna` del calendario del empleado

#### `_compute_schedule_differences()` (líneas 120-135)
- **Propósito**: Calcula diferencias entre horarios reales y programados
- **Lógica**: 
  - `check_in_difference = check_in - check_in_schedule` (en horas)
  - `check_out_difference = check_out - check_out_schedule` (en horas)

---

### 2.2 Métodos de Acción Manual

#### `action_update_schedule_times()` (líneas 137-157)
- **Propósito**: Actualiza manualmente `check_in_schedule` y `check_out_schedule`
- **Flujo**:
  1. Valida que exista empleado y check-in
  2. Llama a `_get_expected_schedule()` para obtener horario esperado
  3. Guarda los valores en `check_in_schedule` y `check_out_schedule`
- **Uso**: Botón en la UI para recalcular horarios programados

#### `action_recalculate_overtime_hours()` (líneas 159-210)
- **Propósito**: Recalcula todas las horas extra y horarios programados
- **Flujo**:
  1. Actualiza horarios programados (`action_update_schedule_times()`)
  2. Calcula diferencias (`_compute_schedule_differences()`)
  3. Calcula horas extra (`_compute_overtime_hours()`)
  4. Invalida campos para forzar recálculo
  5. Muestra notificación con resultados
- **Uso**: Botón en la UI para recalcular todo

---

### 2.3 Método Core: `_get_expected_schedule()` (líneas 212-673)

**Este es el método más complejo e importante del módulo.**

#### Propósito
Determina el horario esperado (entrada y salida programadas) para una asistencia, considerando:
- Turnos nocturnos que cruzan medianoche
- Sábados sin horario configurado
- Agrupación por `shift_group` para turnos nocturnos
- Búsqueda en días anteriores/siguientes cuando no hay horario para el día actual

#### Flujo Detallado

**Paso 1: Validación Inicial (líneas 214-223)**
- Valida que exista empleado y check-in
- Obtiene el calendario del empleado
- Convierte check-in a zona horaria local

**Paso 2: Búsqueda de Horario para el Día Actual (líneas 235-242)**
- Busca líneas de horario (`attendance_ids`) para el `weekday` del check-in
- Guarda `original_weekday` para casos especiales

**Paso 3: Casos Especiales (líneas 244-274)**

**3.1 Domingo Nocturno (líneas 244-248)**
- Si es domingo y turno nocturno → retorna `None` (todas las horas son horas de domingo)

**3.2 Sábado Sin Horario Nocturno (líneas 250-274)**
- Si es sábado sin horario y turno nocturno → usa horario estándar:
  - Entrada: 18:00 del sábado
  - Salida: 06:00 del domingo

**Paso 4: Búsqueda de Horario Alternativo (líneas 276-325)**
- Si no hay horario para el día actual:
  - **Turnos nocturnos**: Busca primero hacia atrás (día anterior), luego hacia adelante
  - **Turnos diurnos**: Busca el más cercano (adelante o atrás)

**Paso 5: Procesamiento de Turnos Nocturnos (líneas 327-559)**

**5.1 Agrupación por `shift_group` (líneas 330-338)**
- Agrupa las líneas de horario por `shift_group` (campo que identifica grupos de turnos relacionados)

**5.2 Búsqueda de Líneas de Tarde/Noche (líneas 348-412)**
- Busca línea de tarde/noche (18:00-24:00) del día actual
- Si no encuentra, busca en el día anterior
- Prioriza líneas que empiecen entre 16:00-20:00
- Si es sábado y encuentra línea temprana (< 12:00), busca en día anterior

**5.3 Búsqueda de Línea de Madrugada (líneas 414-500)**
- Busca línea de madrugada (00:00-08:00) del día siguiente
- Busca primero en el día siguiente del check-in original
- Si no encuentra con mismo `shift_group`, busca sin restricción de grupo
- Si no encuentra, busca hasta 3 días adelante
- La línea de madrugada debe tener el mismo `shift_group` que la línea de tarde

**5.4 Fallback (líneas 502-559)**
- Si no encuentra grupo completo, usa el primer grupo disponible
- Busca línea de mañana en días siguientes

**Paso 6: Procesamiento de Turnos Diurnos (líneas 560-564)**
- Simplemente usa la primera y última línea de horario del día

**Paso 7: Construcción de Fechas Programadas (líneas 575-673)**

**7.1 Fecha de Entrada Programada (líneas 579-604)**
- Si `first_attendance` viene del día anterior → usa fecha del día anterior
- Si viene del mismo día → usa fecha del check-in
- Combina fecha con hora de `first_attendance.hour_from`
- Convierte a UTC

**7.2 Fecha de Salida Programada (líneas 606-668)**
- Si `last_attendance` viene del día siguiente → calcula días adelante
- Si `hour_to >= 24.0` → es medianoche del día siguiente
- Si `hour_to < hour_from` → cruza medianoche
- Combina fecha con hora de `last_attendance.hour_to`
- Convierte a UTC

**Retorno**: Diccionario con `check_in` y `check_out` en UTC

---

### 2.4 Método Core: `_compute_overtime_hours()` (líneas 678-1057)

**Este método calcula las horas extra según diferentes escenarios.**

#### Flujo Principal

**Paso 1: Inicialización (líneas 680-691)**
- Inicializa todas las horas extra en 0.0
- Valida que existan check-in, check-out y empleado

**Paso 2: Caso Especial - Domingo (líneas 701-709)**
- Si es domingo → todas las horas son `sunday_hours`
- No se calculan HE25, HE50, HE75
- Se pagan al doble

**Paso 3: Caso Especial - Sábado Sin Horario (líneas 711-780)**

**3.1 Validación de Horario Completo (líneas 720-741)**
- Si es turno nocturno y tiene horario de sábado:
  - Verifica que exista segunda línea del domingo (00:00-08:00)
  - Verifica que tenga el mismo `shift_group`
  - Si no tiene segunda línea válida → trata como sábado sin horario

**3.2 Cálculo para Sábado Sin Horario Nocturno (líneas 743-775)**
- Calcula horas desde medianoche (00:00) hasta 06:00 como **HE75**
- Las horas de 18:00 a 00:00 son **normales** (no extra)
- Ejemplo: Sábado 18:00 → Domingo 06:00:
  - 18:00-00:00 = 6 horas normales
  - 00:00-06:00 = 6 horas HE75

**3.3 Cálculo para Sábado Sin Horario Diurno (líneas 776-779)**
- Todo es **HE25**

**Paso 4: Cálculo para Turnos Nocturnos (líneas 787-1002)**

**4.1 Obtención de Horario (líneas 790-795)**
- Llama a `_get_expected_schedule()` para obtener horario programado
- Si no hay horario → no calcula horas extra

**4.2 Agrupación por `shift_group` (líneas 839-861)**
- Agrupa líneas de horario por `shift_group`
- Busca líneas del día siguiente con mismo `shift_group`
- Identifica grupo que cruza medianoche

**4.3 Identificación de Líneas del Turno (líneas 888-934)**
- **Primera línea**: Tarde/noche del día actual (ej: 18:00-24:00)
- **Segunda línea**: Madrugada del día siguiente (ej: 00:00-06:00) → esta es HE75

**4.4 Cálculo de HE75 (líneas 936-997)**
- Calcula horas trabajadas en el rango de la segunda línea (normalmente 00:00-06:00)
- Si `check_out` está dentro del rango → calcula horas HE75
- **Restar `check_in_difference`** si es positivo (llegada tardía reduce HE75)
- Si no encuentra segunda línea y es sábado → fallback: calcula desde medianoche hasta 06:00

**4.5 Resultado para Turnos Nocturnos (líneas 999-1002)**
- `hours_25 = 0.0`
- `hours_50 = 0.0`
- `hours_75 = [horas calculadas]`

**Paso 5: Cálculo para Turnos Diurnos (líneas 1003-1054)**

**5.1 Cálculo por Rangos (líneas 1006-1042)**
- Si hay `check_out_difference > 0` (salida tardía):
  - Llama a `_calculate_overtime_hours_by_ranges()` para distribuir horas según hora de salida
  - Resta `check_in_difference` si es positivo (llegada tardía):
    - Resta primero de HE25
    - Luego de HE50
    - Finalmente de HE75

**5.2 Entrada Temprana (líneas 1044-1054)**
- Si `check_in_difference < 0` (entrada temprana) y `count_early_check_in_overtime = True`:
  - Agrega horas según `early_check_in_overtime_rate` (25%, 50%, 75%)

---

### 2.5 Método Auxiliar: `_calculate_overtime_hours_by_ranges()` (líneas 1059-1106)

**Propósito**: Distribuye horas extra según la hora de salida y rangos configurados.

#### Flujo
1. Obtiene configuración de rangos (`config.overtime.hours`)
2. Obtiene hora de salida (`check_out_local.hour`)
3. Compara con rangos configurados:
   - Si está en rango HE25 → todo como HE25
   - Si está en rango HE50 → todo como HE50
   - Si está en rango HE75 → todo como HE75
   - Por defecto → HE25

---

## 🎯 Reglas de Negocio Implementadas

### 1. Horas de Domingo
- **Regla**: Todas las horas trabajadas en domingo se pagan al doble
- **Implementación**: Se asignan a `sunday_hours`, no a HE25/HE50/HE75

### 2. Turnos Nocturnos
- **Regla**: Horas de 00:00 a 06:00 del día siguiente son HE75%
- **Implementación**: Busca segunda línea del turno (00:00-06:00) y calcula horas en ese rango

### 3. Sábado Sin Horario Nocturno
- **Regla**: 
  - 18:00-00:00 = horas normales
  - 00:00-06:00 = HE75%
- **Implementación**: Usa horario estándar (18:00 entrada, 06:00 salida) y calcula HE75 desde medianoche

### 4. Llegada Tardía
- **Regla**: Si el empleado llega tarde, se resta de las horas extra
- **Implementación**: Resta `check_in_difference` de HE75 (turnos nocturnos) o de HE25/HE50/HE75 (turnos diurnos)

### 5. Salida Tardía
- **Regla**: Horas trabajadas después del horario programado son horas extra
- **Implementación**: Usa `check_out_difference` y distribuye según hora de salida (rangos configurados)

### 6. Entrada Temprana
- **Regla**: Opcionalmente, las horas de entrada temprana pueden contar como horas extra
- **Implementación**: Si `count_early_check_in_overtime = True`, agrega horas según tasa configurada

---

## 🔍 Áreas de Mejora Identificadas

### 1. **Complejidad del Método `_get_expected_schedule()`**
- **Problema**: Método muy largo (461 líneas) con lógica compleja anidada
- **Impacto**: Difícil de mantener, depurar y testear
- **Mejora Sugerida**: 
  - Dividir en métodos más pequeños:
    - `_find_evening_line()`
    - `_find_morning_line()`
    - `_build_schedule_dates()`
    - `_handle_saturday_without_schedule()`

### 2. **Duplicación de Lógica de Búsqueda de Horario**
- **Problema**: La lógica de búsqueda de horario se repite en `_get_expected_schedule()` y `_compute_overtime_hours()`
- **Impacto**: Mantenimiento duplicado, posibles inconsistencias
- **Mejora Sugerida**: 
  - Extraer a método común `_find_attendance_lines()`

### 3. **Manejo de Zonas Horarias**
- **Problema**: Se usa `self.env.user.tz` que puede no estar configurado
- **Impacto**: Cálculos incorrectos si no hay zona horaria
- **Mejora Sugerida**: 
  - Usar zona horaria del empleado o calendario como fallback
  - Validar que exista zona horaria antes de calcular

### 4. **Validación de Datos**
- **Problema**: Algunas validaciones son básicas o faltan
- **Impacto**: Posibles errores en tiempo de ejecución
- **Mejora Sugerida**: 
  - Validar que `check_out > check_in`
  - Validar que `check_in_schedule` y `check_out_schedule` existan antes de calcular diferencias
  - Validar rangos de horas (0-23)

### 5. **Performance**
- **Problema**: Múltiples búsquedas en `calendar.attendance_ids` con filtros
- **Impacto**: Consultas repetidas a la base de datos
- **Mejora Sugerida**: 
  - Cachear resultados de búsquedas
  - Usar `read_group` para agrupar por `shift_group` en una sola consulta

### 6. **Logging Excesivo**
- **Problema**: Muchos logs en producción pueden afectar performance
- **Impacto**: Logs muy verbosos, difícil encontrar información relevante
- **Mejora Sugerida**: 
  - Usar niveles de log apropiados (DEBUG, INFO, WARNING)
  - Agregar flag de configuración para activar/desactivar logs detallados

### 7. **Manejo de Casos Edge**
- **Problema**: Algunos casos edge no están cubiertos:
  - Turnos que cruzan múltiples días (más de 24 horas)
  - Horarios con múltiples `shift_group` en el mismo día
  - Empleados sin calendario asignado
- **Mejora Sugerida**: 
  - Agregar validaciones y mensajes de error claros
  - Documentar casos no soportados

### 8. **Cálculo de HE75 para Turnos Nocturnos**
- **Problema**: La lógica de cálculo de HE75 es compleja y tiene múltiples fallbacks
- **Impacto**: Puede haber inconsistencias en casos especiales
- **Mejora Sugerida**: 
  - Simplificar lógica: siempre buscar segunda línea, si no existe usar rango estándar (00:00-06:00)
  - Documentar claramente qué rango se usa para HE75

### 9. **Dependencia de `check_in_schedule` y `check_out_schedule`**
- **Problema**: Estos campos no se calculan automáticamente, deben actualizarse manualmente
- **Impacto**: Si no se actualizan, los cálculos de horas extra pueden ser incorrectos
- **Mejora Sugerida**: 
  - Hacer que `_compute_overtime_hours()` llame automáticamente a `_get_expected_schedule()` si no existen
  - O hacer que `check_in_schedule` y `check_out_schedule` sean computed fields

### 10. **Testing**
- **Problema**: No hay tests unitarios visibles
- **Impacto**: Difícil validar cambios y regresiones
- **Mejora Sugerida**: 
  - Agregar tests para cada escenario:
    - Domingo nocturno
    - Sábado sin horario nocturno
    - Turno nocturno con segunda línea
    - Turno diurno con salida tardía
    - Entrada temprana

---

## 📊 Flujo de Datos

```
check_in, check_out
    ↓
_compute_is_sunday/is_saturday/is_night_shift
    ↓
_get_expected_schedule() → check_in_schedule, check_out_schedule
    ↓
_compute_schedule_differences() → check_in_difference, check_out_difference
    ↓
_compute_overtime_hours() → hours_25, hours_50, hours_75, sunday_hours
    ↓
hr_payslip.py → Integración en nómina
```

---

## 🔧 Dependencias

- **Odoo Core**: `hr.attendance`, `resource.calendar`, `resource.calendar.attendance`
- **Modelos Personalizados**: `config.overtime.hours` (para rangos de horas extra)
- **Librerías Python**: `pytz` (manejo de zonas horarias), `datetime`, `logging`

---

## 📝 Notas Importantes

1. **`shift_group`**: Campo clave para agrupar turnos nocturnos que cruzan medianoche. Debe estar configurado correctamente en el calendario.

2. **Zona Horaria**: El sistema usa la zona horaria del usuario (`self.env.user.tz`). Asegurarse de que esté configurada.

3. **Horarios Programados**: `check_in_schedule` y `check_out_schedule` deben actualizarse manualmente o mediante `action_update_schedule_times()` antes de calcular horas extra.

4. **Sábado Sin Horario**: Si un sábado no tiene horario configurado y es turno nocturno, se usa horario estándar (18:00-06:00).

5. **Domingo Nocturno**: Si es domingo y turno nocturno, todas las horas son horas de domingo (no se calculan HE25/50/75).

---

## 🎓 Conclusión

Este módulo implementa una lógica compleja de cálculo de horas extra que maneja múltiples escenarios de negocio. La funcionalidad principal está implementada, pero hay oportunidades de mejora en términos de:
- **Mantenibilidad**: Dividir métodos largos
- **Performance**: Optimizar consultas a BD
- **Robustez**: Mejorar validaciones y manejo de errores
- **Testing**: Agregar tests unitarios
- **Documentación**: Mejorar comentarios en código complejo

