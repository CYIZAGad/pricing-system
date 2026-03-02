-- Migration Script: Add expiry_date column to medicines table
-- Run this script on each tenant database to add expiry_date column
-- 
-- IMPORTANT: This migration adds a REQUIRED field (expiry_date)
-- Existing records will need to be updated with valid expiry dates
-- 
-- Step 1: Add the expiry_date column (nullable first to allow migration)
ALTER TABLE medicines 
ADD COLUMN IF NOT EXISTS expiry_date DATE;

-- Step 2: Create index on expiry_date for faster queries
CREATE INDEX IF NOT EXISTS idx_medicines_expiry_date 
ON medicines(expiry_date);

-- Step 3: Set a default expiry date for existing records (1 year from now)
-- This ensures existing data remains valid
-- You can update these dates later with actual expiry dates
UPDATE medicines 
SET expiry_date = CURRENT_DATE + INTERVAL '1 year'
WHERE expiry_date IS NULL;

-- Step 4: Make the column NOT NULL (required field)
-- This will fail if there are still NULL values, so make sure step 3 completed successfully
ALTER TABLE medicines 
ALTER COLUMN expiry_date SET NOT NULL;

-- Step 5: Verify the table structure
-- Run this to see the updated table structure:
-- SELECT column_name, data_type, is_nullable 
-- FROM information_schema.columns 
-- WHERE table_name = 'medicines' 
-- ORDER BY ordinal_position;
