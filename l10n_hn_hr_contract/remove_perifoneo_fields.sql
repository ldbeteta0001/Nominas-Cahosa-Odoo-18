-- Script para eliminar referencias a campos is_perifoneo e is_animador de las vistas almacenadas
-- Ejecutar este script en la base de datos DESPUÉS de actualizar el código y ANTES de iniciar Odoo

-- Opción 1: Eliminar completamente las vistas que contengan estos campos (más seguro)
-- Esto hará que Odoo las recree cuando actualice el módulo
DELETE FROM ir_ui_view 
WHERE (arch_db::text LIKE '%is_perifoneo%' OR arch_db::text LIKE '%is_animador%')
AND model IN ('hr.contract', 'hr.employee');

-- Opción 2 (alternativa si la opción 1 no funciona): 
-- Desactivar las vistas problemáticas para que Odoo las recree
-- UPDATE ir_ui_view 
-- SET active = false
-- WHERE (arch_db::text LIKE '%is_perifoneo%' OR arch_db::text LIKE '%is_animador%')
-- AND model IN ('hr.contract', 'hr.employee');

