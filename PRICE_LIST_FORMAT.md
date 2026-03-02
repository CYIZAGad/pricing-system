# Price List Upload Format Guide

## Supported File Formats

- **CSV** (.csv)
- **Excel** (.xlsx, .xls)

## Required Columns

Your file **MUST** have these columns (column names are case-insensitive):

1. **Medicine Name** (Required)
   - Acceptable column names: `medicine`, `product`, `drug name`, `item`, `medicine name`, `name`
   - Example: "Paracetamol 500mg"

2. **Unit Price** (Required)
   - Acceptable column names: `price`, `unit price`, `cost`, `rate`, `selling price`
   - Must be a number greater than 0
   - Example: 25.50

## CSV Example

```csv
Medicine Name,Unit Price
Paracetamol 500mg,25.50
Ibuprofen 200mg,30.00
Amoxicillin 250mg,45.75
```

## Excel Example

| Medicine Name | Unit Price |
|--------------|------------|
| Paracetamol 500mg | 25.50 |
| Ibuprofen 200mg | 30.00 |
| Amoxicillin 250mg | 45.75 |

## Column Name Flexibility

The system is **flexible with column names**. It will recognize variations:

- **Medicine Name**: "Medicine", "Product", "Drug Name", "Item", "Medicine Name", "Name"
- **Unit Price**: "Price", "Unit Price", "Cost", "Rate", "Selling Price"

## File Requirements

- **Maximum file size**: 16MB
- **Encoding**: UTF-8 (preferred), but system will try to auto-detect
- **First row**: Must contain column headers
- **Data rows**: Start from row 2

## Validation Rules

1. **Medicine Name**: Cannot be empty
2. **Unit Price**: Must be a number > 0

## Common Errors

### ❌ Missing Required Columns
**Error**: "Missing required columns: ['medicine_name', 'unit_price']"
**Solution**: Make sure your file has columns for Medicine Name and Unit Price

### ❌ Invalid Price
**Error**: "Invalid unit price: abc"
**Solution**: Unit Price must be a number (e.g., 25.50, not "abc")

### ❌ Empty Medicine Name
**Error**: "Row 5: Medicine name is required"
**Solution**: Every row must have a medicine name

### ❌ Price <= 0
**Error**: "Unit price must be greater than 0"
**Solution**: Prices must be positive numbers

## Sample Files

### Minimal CSV (Only Required Columns)
```csv
Medicine Name,Unit Price
Paracetamol,25.50
Ibuprofen,30.00
```

## Tips

1. **Use consistent column names** across all your uploads
2. **Check for empty rows** - they will be skipped
3. **Ensure prices are numbers**, not text
4. **Save CSV files as UTF-8** to avoid encoding issues

## Testing Your File

Before uploading, verify:
- ✅ File has headers in the first row
- ✅ At least 2 columns: Medicine Name, Unit Price
- ✅ All prices are numbers > 0
- ✅ No empty medicine names
- ✅ File size < 16MB
