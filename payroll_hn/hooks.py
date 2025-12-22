# -*- coding: utf-8 -*-

def post_init_hook(cr, registry):
    """
    Hook que se ejecuta después de instalar/actualizar el módulo.
    Agrega las columnas necesarias para los campos stored si no existen.
    """
    def column_exists(cr, table_name, column_name):
        """Verifica si una columna existe en una tabla"""
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name=%s AND column_name=%s
        """, (table_name, column_name))
        return cr.fetchone() is not None
    
    # Agregar columnas si no existen
    columns_to_add = [
        ('amount_rap', 'NUMERIC'),
        ('value_rap', 'NUMERIC'),
        ('amount_ihss', 'NUMERIC'),
        ('value_ihss', 'NUMERIC'),
        ('amount_isr', 'NUMERIC'),
        ('value_isr', 'NUMERIC'),
        ('rap_calculation_type', 'VARCHAR'),
        ('ihss_calculation_type', 'VARCHAR'),
        ('isr_calculation_type', 'VARCHAR'),
        # Campos de deducciones fijas
        ('apply_education', 'BOOLEAN'),
        ('amount_fixed_education', 'NUMERIC'),
        ('apply_colegiatura', 'BOOLEAN'),
        ('amount_fixed_colegiatura', 'NUMERIC'),
        ('apply_pension', 'BOOLEAN'),
        ('amount_fixed_pension', 'NUMERIC'),
    ]
    
    for column_name, column_type in columns_to_add:
        if not column_exists(cr, 'hr_contract', column_name):
            try:
                # Para BOOLEAN, usar el tipo correcto de PostgreSQL
                if column_type == 'BOOLEAN':
                    sql_type = 'BOOLEAN DEFAULT FALSE'
                    cr.execute("ALTER TABLE hr_contract ADD COLUMN %s %s" % (column_name, sql_type))
                elif column_type == 'NUMERIC':
                    sql_type = 'NUMERIC'
                    cr.execute("ALTER TABLE hr_contract ADD COLUMN %s %s" % (column_name, sql_type))
                elif column_type == 'VARCHAR':
                    sql_type = 'VARCHAR'
                    cr.execute("ALTER TABLE hr_contract ADD COLUMN %s %s" % (column_name, sql_type))
                else:
                    sql_type = column_type
                    cr.execute("ALTER TABLE hr_contract ADD COLUMN %s %s" % (column_name, sql_type))
            except Exception as e:
                # Si la columna ya existe o hay otro error, continuar
                # Log del error para debugging
                import logging
                _logger = logging.getLogger(__name__)
                _logger.warning("Error al agregar columna %s: %s" % (column_name, str(e)))
                pass

