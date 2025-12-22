-- Script SQL para crear las columnas faltantes en hr_contract
-- Ejecutar como: sudo -u postgres psql -d main -f fix_columns.sql

-- Bono Educativo
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS apply_education BOOLEAN DEFAULT FALSE;
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS amount_fixed_education NUMERIC;

-- Colegiatura
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS apply_colegiatura BOOLEAN DEFAULT FALSE;
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS amount_fixed_colegiatura NUMERIC;

-- Pensión
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS apply_pension BOOLEAN DEFAULT FALSE;
ALTER TABLE hr_contract ADD COLUMN IF NOT EXISTS amount_fixed_pension NUMERIC;

-- Verificar que se crearon correctamente
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'hr_contract' 
AND column_name IN ('apply_education', 'amount_fixed_education', 'apply_colegiatura', 'amount_fixed_colegiatura', 'apply_pension', 'amount_fixed_pension')
ORDER BY column_name;

