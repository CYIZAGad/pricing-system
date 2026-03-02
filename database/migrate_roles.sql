-- Migration Script: Update user roles to only 'admin' and 'depot'
-- Run this script on the central database (pricing_central) to update existing users
-- 
-- WARNING: This will:
-- 1. Change all 'depot_manager' and 'depot_staff' roles to 'depot'
-- 2. Delete all users with 'pharmacy' role
-- 3. Update the role constraint to only allow 'admin' and 'depot'
-- 
-- Make sure to backup your data before running this migration!

-- Step 1: Update depot_manager and depot_staff to 'depot'
UPDATE users 
SET role = 'depot', updated_at = CURRENT_TIMESTAMP
WHERE role IN ('depot_manager', 'depot_staff');

-- Step 2: Delete all pharmacy users
DELETE FROM users WHERE role = 'pharmacy';

-- Step 3: Drop the old constraint
ALTER TABLE users 
DROP CONSTRAINT IF EXISTS users_role_check;

-- Step 4: Add new constraint (only admin and depot allowed)
ALTER TABLE users 
ADD CONSTRAINT users_role_check 
CHECK (role IN ('admin', 'depot'));

-- Step 5: Verify the changes
-- Run this to see updated roles:
-- SELECT role, COUNT(*) as count 
-- FROM users 
-- GROUP BY role;
