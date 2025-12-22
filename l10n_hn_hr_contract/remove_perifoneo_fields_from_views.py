#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para eliminar referencias a campos is_perifoneo e is_animador de las vistas almacenadas.
Ejecutar desde el directorio raíz de Odoo o configurar las variables de entorno apropiadas.

Uso:
    python3 remove_perifoneo_fields_from_views.py -d nombre_base_datos
"""

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError
import re
import sys

try:
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
except ImportError:
    print("Error: No se puede importar Odoo. Asegúrate de ejecutar este script desde el entorno de Odoo.")
    sys.exit(1)


def clean_view_arch(arch_xml):
    """
    Limpia las referencias a is_perifoneo e is_animador de la arquitectura XML de una vista.
    """
    try:
        # Intentar parsear el XML
        root = ET.fromstring(arch_xml)
    except ParseError:
        # Si no es XML válido, intentar limpiar con regex
        cleaned = re.sub(r'<field[^>]*name=["\']is_perifoneo["\'][^>]*/?>', '', arch_xml)
        cleaned = re.sub(r'<field[^>]*name=["\']is_animador["\'][^>]*/?>', '', cleaned)
        cleaned = re.sub(r'invisible=["\']is_perifoneo\s+or\s+is_animador["\']', '', cleaned)
        cleaned = re.sub(r'invisible=["\']is_animador\s+or\s+is_perifoneo["\']', '', cleaned)
        cleaned = re.sub(r'invisible=["\']is_perifoneo[^"\']*["\']', '', cleaned)
        cleaned = re.sub(r'invisible=["\']is_animador[^"\']*["\']', '', cleaned)
        return cleaned
    
    # Si es XML válido, eliminar los elementos field con estos nombres
    for field in root.findall(".//field[@name='is_perifoneo']"):
        parent = field.getparent()
        if parent is not None:
            parent.remove(field)
    
    for field in root.findall(".//field[@name='is_animador']"):
        parent = field.getparent()
        if parent is not None:
            parent.remove(field)
    
    # Eliminar atributos invisible que usen estos campos
    for elem in root.iter():
        invisible_attr = elem.get('invisible')
        if invisible_attr:
            if 'is_perifoneo' in invisible_attr or 'is_animador' in invisible_attr:
                elem.attrib.pop('invisible', None)
    
    return ET.tostring(root, encoding='unicode')


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 remove_perifoneo_fields_from_views.py -d nombre_base_datos")
        sys.exit(1)
    
    # Configurar Odoo
    dbname = None
    for i, arg in enumerate(sys.argv):
        if arg == '-d' and i + 1 < len(sys.argv):
            dbname = sys.argv[i + 1]
    
    if not dbname:
        print("Error: Debe especificar el nombre de la base de datos con -d")
        sys.exit(1)
    
    # Inicializar Odoo
    config['db_name'] = dbname
    odoo.tools.config.parse_config(['--database', dbname])
    
    # Crear entorno
    registry = odoo.registry(dbname)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # Buscar todas las vistas que contengan referencias a estos campos
        View = env['ir.ui.view']
        views_with_fields = View.search([
            '|',
            ('arch_db', 'ilike', 'is_perifoneo'),
            ('arch_db', 'ilike', 'is_animador')
        ])
        
        print(f"Encontradas {len(views_with_fields)} vistas con referencias a is_perifoneo o is_animador")
        
        for view in views_with_fields:
            try:
                original_arch = view.arch_db or ''
                if 'is_perifoneo' in original_arch or 'is_animador' in original_arch:
                    cleaned_arch = clean_view_arch(original_arch)
                    if cleaned_arch != original_arch:
                        view.write({'arch_db': cleaned_arch})
                        print(f"  ✓ Limpiada vista: {view.name} (ID: {view.id})")
            except Exception as e:
                print(f"  ✗ Error al limpiar vista {view.name} (ID: {view.id}): {e}")
        
        cr.commit()
        print("\n✓ Proceso completado. Vistas actualizadas.")


if __name__ == '__main__':
    main()

