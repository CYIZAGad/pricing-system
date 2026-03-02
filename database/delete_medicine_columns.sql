-- SQL Query to Delete Unused Columns from Medicines Table
-- Run this on each tenant database
-- 
-- WARNING: This will permanently delete data in these columns!
-- Make sure to backup your data before running this!

-- Step 1: Drop the old unique constraint (if it includes unit_type)
ALTER TABLE medicines 
DROP CONSTRAINT IF EXISTS unique_medicine_per_list;

-- Step 2: Drop indexes on columns that will be removed
DROP INDEX IF EXISTS idx_medicines_code;

-- Step 3: Delete the columns
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

-- Step 5: Verify the changes
-- Run this to see the new table structure:
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'medicines' 
ORDER BY ordinal_position;
