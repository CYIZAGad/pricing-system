# Pharmacy Pricing System

A multi-tenant SaaS web application for distributing medicine price lists from pharmaceutical depots (wholesalers) to pharmacies across Rwanda.

## System Overview

This system eliminates the manual process of collecting prices from multiple depots by providing a centralized platform where:
- **Depots** upload their price lists using multiple methods (file upload, manual entry)
- **Depots** can retrieve prices using file upload, OCR scanning, or manual entry

- **OCR Technology** enables scanning of printed or handwritten medicine lists from images/PDFs

## Architecture

### Multi-Tenant Database-per-Tenant Architecture

- **Central Database**: Contains tenant registry, users, authentication, and audit logs
- **Tenant Databases**: Each depot has its own isolated database with:
  - `price_lists` - Price list metadata
  - `medicines` - Medicine catalog with prices
  - `upload_history` - Upload tracking

### Technology Stack

**Backend:**
- Python 3.10+
- Flask (app factory pattern)
- SQLAlchemy
- PostgreSQL 14+
- JWT authentication
- bcrypt password hashing
- EasyOCR for text extraction from images
- ReportLab for PDF generation
- pdf2image with Poppler for PDF processing

**Frontend:**
- HTML5, CSS3, Vanilla JavaScript (ES6+)
- Modern responsive dashboard UI with gradient designs
- Real-time OCR processing feedback

## Prerequisites

1. **PostgreSQL 14+** installed and running
2. **Python 3.10+** installed
3. **Poppler** (for PDF processing):
   - **Windows**: Download from [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/) and add to PATH
   - **Linux**: `sudo apt-get install poppler-utils`
   - **macOS**: `brew install poppler`
4. **Central Database** - A PostgreSQL database dump/file that contains:
   - `tenants` table
   - `users` table
   - `audit_logs` table
   - Authentication data

## Installation

### 1. Clone/Download the Project

```bash
cd "pricing project"
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Note**: The system requires additional dependencies for OCR and PDF processing:
- `easyocr` - OCR text extraction
- `reportlab` - PDF generation
- `pdf2image` - PDF to image conversion
- `Pillow` - Image processing

### 3. Install Poppler (Required for PDF Processing)

#### Windows:
1. Download Poppler from [http://blog.alivate.com.au/poppler-windows/](http://blog.alivate.com.au/poppler-windows/)
2. Extract to `C:\poppler`
3. Add `C:\poppler\Library\bin` to your system PATH
4. Restart your terminal/IDE

#### Linux:
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

#### macOS:
```bash
brew install poppler
```

### 4. Create and Import Central Database

**IMPORTANT**: The central database must be created and imported before running the application.

#### Option A: Create Database from Schema (Recommended)

1. **Create the database**:
   ```bash
   psql -U postgres -c "CREATE DATABASE pricing_central;"
   ```

2. **Import the schema**:
   ```bash
   psql -U postgres -d pricing_central < database/central_database_schema.sql
   ```

3. **Create an admin user**:
   ```bash
   python database/create_admin_user.py admin@pricing.local your_password_here
   ```

#### Option B: Use Existing Database Dump

If you have an existing database dump file:

```bash
# Using psql
psql -U postgres -d pricing_central < your_database_dump.sql

# Or using pg_restore
pg_restore -U postgres -d pricing_central your_database_dump.dump
```

**Note**: The application will NOT create these tables automatically. They must exist in the database.

**Required Tables:**
- `tenants` - Depot/tenant registry
- `users` - User accounts
- `audit_logs` - System audit trail

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```env
# Secret Keys
SECRET_KEY=your-secret-key-here-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-here

# Central Database (pre-existing, imported)
CENTRAL_DB_HOST=localhost
CENTRAL_DB_PORT=5432
CENTRAL_DB_NAME=pricing_central
CENTRAL_DB_USER=postgres
CENTRAL_DB_PASSWORD=your-password

# PostgreSQL Admin (for creating tenant databases)
PG_ADMIN_USER=postgres
PG_ADMIN_PASSWORD=your-password
PG_ADMIN_HOST=localhost

# File Upload
UPLOAD_FOLDER=uploads
```

### 6. Create Upload Directory

```bash
mkdir uploads
```

### 7. Initialize Central Database Connection

The application will automatically connect to the central database on startup. Ensure:
- PostgreSQL is running
- Central database exists and is imported
- Database credentials in `.env` are correct

## Running the Application

### Development Mode

```bash
python run.py
```

The application will start on `http://localhost:5000`

### Production Mode

For production, use a WSGI server like Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## User Roles

### System Administrator
- Create and manage depot tenants with full business details
- View all tenant information in a comprehensive table
- Trigger automatic tenant database creation
- Manage users (create, update, delete)
- Delete depot users (automatically cleans up tenant and database)
- View audit logs
- Monitor system health
- Update admin profile and password

### Depot Manager / Depot Staff
- **Adjust Prices** (formerly "Upload Prices"):
  - Upload price lists via CSV/Excel files
  - Manual entry with editable table (add/remove rows)
- **Get Prices** (formerly "Download Prices"):
  - Upload file with medicine names to get prices
  - **OCR Scanning**: Upload images/PDFs (printed or handwritten) to extract medicine names
  - Manual entry: Paste or type medicine names
  - Download results as CSV, Excel, or PDF
  - View scanned names alongside matched medicine names
- **Manage Products**: View and search medicine catalog
- View statistics and upload history
- Default landing page: Get Prices (after login)

### Pharmacy User
- Browse available depots
- Search medicines across depots
- Download price lists (CSV)
- Read-only access

## Key Features

### OCR (Optical Character Recognition)
- **Location**: Available only in "Get Prices" section
- **Supported Formats**: PNG, JPG, JPEG, PDF, BMP, TIFF, WEBP
- **Capabilities**:
  - Extracts text from printed documents
  - Extracts text from handwritten documents
  - Processes multi-page PDFs
  - Cleans and normalizes extracted text
- **Fuzzy Matching**: 
  - 70% similarity threshold for medicine name matching
  - Prioritizes matches based on first 3-4 letters
  - Ignores numbers and special characters
  - Handles variations in medicine names
- **Results Display**: Shows both scanned names and matched database names

### Price Adjustment (Upload)
- **File Upload**: CSV/Excel files with medicine names and prices
- **Manual Entry**: Editable table interface
  - Add/remove rows dynamically
  - Real-time validation
  - Bulk upload capability

### Price Retrieval (Get Prices)
- **File Upload**: Upload CSV/Excel with medicine names
- **OCR Scanning**: Scan images/PDFs to extract medicine names
- **Manual Entry**: Paste or type medicine names (one per line or comma-separated)
- **Download Options**:
  - CSV format
  - Excel format (.xlsx)
  - PDF format (prices formatted without decimals)
- **Results Table**: Displays scanned name, matched medicine name, and price

### Fuzzy Matching Algorithm
- Normalizes medicine names (removes numbers, punctuation, extra spaces)
- Compares character-level similarity
- Compares token-level similarity
- Prioritizes matches with same first 3-4 letters
- 70% similarity threshold for automatic matching
- Handles abbreviations and variations

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout
- `POST /api/v1/auth/register` - Register new user (admin only)

### Admin
- `POST /api/v1/admin/tenant` - Create new tenant (auto-creates database)
- `GET /api/v1/admin/tenants` - List all tenants
- `GET /api/v1/admin/users` - List all users with tenant details
- `PUT /api/v1/admin/tenant/<id>` - Update tenant
- `DELETE /api/v1/admin/tenant/<id>` - Delete tenant and database
- `PUT /api/v1/admin/user/<id>` - Update user
- `DELETE /api/v1/admin/user/<id>` - Delete user (and tenant if depot user)
- `GET /api/v1/admin/profile` - Get admin profile
- `PUT /api/v1/admin/profile` - Update admin profile
- `PUT /api/v1/admin/profile/password` - Change admin password
- `GET /api/v1/admin/system-health` - System health check

### Depot - Price Adjustment (Upload)
- `POST /api/v1/depot/upload` - Upload CSV/Excel price list file
- `POST /api/v1/depot/upload-manual` - Upload prices via manual entry

### Depot - Price Retrieval (Get Prices)
- `POST /api/v1/depot/download-prices` - Get prices from file (CSV/Excel)
- `POST /api/v1/depot/download-prices-ocr` - Get prices via OCR scanning
- `POST /api/v1/depot/download-prices-manual` - Get prices via manual entry
- `POST /api/v1/depot/download-prices-csv` - Download results as CSV
- `POST /api/v1/depot/download-prices-excel` - Download results as Excel
- `POST /api/v1/depot/download-prices-pdf` - Download results as PDF

### Depot - Management
- `GET /api/v1/depot/medicines` - List medicines (with search)
- `PUT /api/v1/depot/medicine/<id>` - Update medicine
- `DELETE /api/v1/depot/medicine/<id>` - Delete medicine
- `GET /api/v1/depot/price-lists` - Get depot price lists
- `GET /api/v1/depot/statistics` - Get depot statistics

### Pharmacy
- `GET /api/v1/pharmacy/depots` - List all depots
- `GET /api/v1/pharmacy/depot/<id>/prices` - Get depot price list
- `GET /api/v1/pharmacy/download/<id>` - Download price list as CSV

## Tenant Database Creation

When an admin creates a new tenant:

1. **Automatic Database Creation**: The system automatically:
   - Generates a unique database name: `tenant_<sanitized_business_name>` (with suffix if needed)
   - Creates a new PostgreSQL database
   - Creates all required tables:
     - `price_lists`
     - `medicines`
     - `upload_history`
   - Creates indexes and constraints
   - Stores the database name in `tenants.database_name`

2. **Database Isolation**: Each tenant's data is completely isolated in its own database

3. **Rollback on Failure**: If creation fails, the system attempts to clean up the database

4. **User Account Creation**: Automatically creates a depot user account with the provided email and password

## File Upload Format

### Supported Formats
- CSV (.csv)
- Excel (.xlsx, .xls)

### Required Columns
- **Medicine Name** (required)
- **Unit Price** (required, must be > 0)

### Optional Columns
- Medicine Code
- Manufacturer
- Batch Number
- Expiry Date
- Quantity Available
- Minimum Order

### Column Mapping
The system automatically maps columns using case-insensitive matching:
- Medicine Name: "medicine", "product", "drug name", "item", "medicine name"
- Price: "price", "unit price", "cost", "rate", "unit_price"

## OCR Processing

### How It Works
1. User uploads an image or PDF file
2. System extracts text using EasyOCR
3. Text is cleaned and normalized (removes extra spaces, normalizes case)
4. Medicine names are extracted (one per line or from table structure)
5. Each extracted name is matched against the depot's database using fuzzy matching
6. Results show:
   - Scanned name (what OCR extracted)
   - Matched medicine name (from database)
   - Unit price
   - Match score (if available)

### Fuzzy Matching Details
- **Normalization**: Removes numbers, punctuation, extra spaces
- **Similarity Calculation**: Uses SequenceMatcher for character and token comparison
- **Prefix Matching**: Prioritizes matches where first 3-4 letters match
- **Threshold**: 70% similarity required for automatic matching
- **No Match**: Items below threshold are marked as "No match found"

## Security Features

- **JWT Authentication**: Token-based authentication with 24-hour expiry
- **Password Hashing**: bcrypt with cost factor 12
- **Role-Based Access Control**: Strict RBAC enforcement
- **Tenant Isolation**: Database-level isolation
- **Audit Logging**: All API requests logged to `audit_logs`
- **Input Validation**: SQL injection and XSS protection
- **File Upload Validation**: Type, size, and content validation
- **OCR File Validation**: Image/PDF type and size validation

## Project Structure

```
pricing project/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── blueprints/               # API blueprints
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── admin.py             # Admin endpoints
│   │   └── depot.py             # Depot endpoints (upload, download, OCR, manual)
│   ├── database/                # Database managers
│   │   ├── central_db.py       # Central DB connection
│   │   └── tenant_db.py         # Tenant DB router
│   ├── models/                  # SQLAlchemy models (reference)
│   ├── services/                # Business logic
│   │   ├── tenant_creator.py   # Tenant DB creation
│   │   ├── file_processor.py   # File parsing (CSV/Excel)
│   │   └── ocr_processor.py    # OCR text extraction
│   ├── middleware/              # Middleware
│   │   └── audit.py            # Audit logging
│   ├── utils/                   # Utilities
│   │   └── auth.py             # JWT & password hashing
│   ├── errors.py               # Error handlers
│   └── routes.py               # Frontend routes
├── templates/                   # HTML templates
│   ├── landing.html            # Login page
│   ├── admin.html              # Admin dashboard
│   └── depot.html              # Depot dashboard
├── static/                      # Static files
│   ├── css/
│   │   └── style.css           # Main stylesheet
│   └── js/
│       ├── auth.js             # Authentication utilities
│       ├── admin.js             # Admin dashboard
│       └── depot.js             # Depot dashboard
├── config.py                    # Configuration
├── run.py                       # Application entry point
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Troubleshooting

### Database Connection Issues

1. **Check PostgreSQL is running**:
   ```bash
   psql -U postgres -c "SELECT version();"
   ```

2. **Verify central database exists**:
   ```bash
   psql -U postgres -l | grep pricing_central
   ```

3. **Check environment variables** in `.env` file

### Tenant Database Creation Fails

1. Ensure PostgreSQL admin user has `CREATEDB` privilege
2. Check database name doesn't already exist (system auto-generates unique names)
3. Review application logs for specific error messages
4. Verify `PG_ADMIN_USER` and `PG_ADMIN_PASSWORD` are correct

### OCR/PDF Processing Issues

1. **Poppler not found**:
   - Windows: Ensure Poppler is installed and `C:\poppler\Library\bin` is in PATH
   - Linux: Install with `sudo apt-get install poppler-utils`
   - macOS: Install with `brew install poppler`

2. **OCR fails to extract text**:
   - Ensure image is clear and readable
   - Check file size (max 16MB)
   - Verify image format is supported

3. **PDF processing fails**:
   - Verify Poppler is installed correctly
   - Check PDF is not password-protected
   - Ensure PDF is not corrupted

### File Upload Issues

1. Check file format (CSV or Excel)
2. Verify required columns are present
3. Check file size (max 16MB)
4. Review processing errors in response

### Fuzzy Matching Not Working

1. Ensure medicine names in database are properly formatted
2. Check OCR extracted text quality
3. Verify similarity threshold (70%) is appropriate
4. Review match scores in response

## Development Notes

- The central database tables are **NOT** created by this application
- Tenant databases are **automatically created** when a new tenant is added
- Database names are auto-generated with unique suffixes if conflicts occur
- All tenant databases use the same PostgreSQL server but are completely isolated
- JWT tokens are stored in browser localStorage
- File uploads are processed synchronously (consider async processing for large files in production)
- OCR processing may take time for large images/PDFs
- First OCR run downloads EasyOCR models (one-time, ~500MB)

## Production Considerations

1. **Use environment variables** for all secrets
2. **Set up proper logging** (ELK stack recommended)
3. **Implement rate limiting** (Flask-Limiter)
4. **Use a production WSGI server** (Gunicorn, uWSGI)
5. **Set up database backups** for both central and tenant databases
6. **Configure HTTPS/TLS**
7. **Implement file storage** (AWS S3, MinIO) instead of local storage
8. **Add monitoring** (Prometheus, Grafana)
9. **Consider async file processing** for large uploads and OCR
10. **Implement caching** (Redis) for frequently accessed data
11. **Optimize OCR processing** (GPU acceleration, model caching)
12. **Set up Poppler** on production server
13. **Monitor OCR model downloads** (first-time setup)

## License

This is a proprietary system built for pharmaceutical distribution in Rwanda.

## Support

For issues or questions, please contact the development team.
