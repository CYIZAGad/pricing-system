-- Migration Script: Simplify medicines table to only contain name and price
-- Run this script on each tenant database to update existing tables
-- 
-- WARNING: This will remove columns: medicine_code, unit_type, manufacturer, 
--          batch_number, expiry_date, quantity_available, minimum_order
-- 
-- Make sure to backup your data before running this migration!

-- Step 1: Drop the old unique constraint
ALTER TABLE medicines 
DROP CONSTRAINT IF EXISTS unique_medicine_per_list;

-- Step 2: Drop indexes on columns that will be removed
DROP INDEX IF EXISTS idx_medicines_code;

-- Step 3: Drop columns that are no longer needed
ALTER TABLE medicines 
DROP COLUMN IF EXISTS medicine_code,
DROP COLUMN IF EXISTS unit_type,
DROP COLUMN IF EXISTS manufacturer,
DROP COLUMN IF EXISTS batch_number,
DROP COLUMN IF EXISTS expiry_date,
DROP COLUMN IF EXISTS quantity_available,
DROP COLUMN IF EXISTS minimum_order;

-- Step 4: Create new unique constraint (only on price_list_id and medicine_name)
ALTER TABLE medicines 
ADD CONSTRAINT unique_medicine_per_list 
UNIQUE(price_list_id, medicine_name);

-- Step 5: Verify the table structure
-- SELECT column_name, data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'medicines' 
-- ORDER BY ordinal_position;
