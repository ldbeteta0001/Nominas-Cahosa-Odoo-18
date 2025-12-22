-- Script SQL para agregar las columnas de deducciones fijas
-- Este script se puede ejecutar manualmente si el hook no se ejecuta automáticamente

-- Verificar y agregar columnas si no existen
DO $$
BEGIN
    -- Bono Educativo
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'apply_education'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN apply_education BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'amount_fixed_education'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN amount_fixed_education NUMERIC;
    END IF;
    
    -- Colegiatura
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'apply_colegiatura'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN apply_colegiatura BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'amount_fixed_colegiatura'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN amount_fixed_colegiatura NUMERIC;
    END IF;
    
    -- Pensión
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'apply_pension'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN apply_pension BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'hr_contract' AND column_name = 'amount_fixed_pension'
    ) THEN
        ALTER TABLE hr_contract ADD COLUMN amount_fixed_pension NUMERIC;
    END IF;
END $$;

