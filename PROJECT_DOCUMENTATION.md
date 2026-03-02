# Pharmacy Pricing System - Complete Project Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [File-by-File Documentation](#file-by-file-documentation)
5. [Data Flow](#data-flow)
6. [Key Features Explained](#key-features-explained)

---

## Project Overview

The **Pharmacy Pricing System** is a multi-tenant SaaS web application designed for distributing medicine price lists from pharmaceutical depots (wholesalers) to pharmacies across Rwanda. The system uses a **database-per-tenant** architecture where each depot has its own isolated PostgreSQL database.

### Core Functionality
- **Depots** upload their price lists (CSV, Excel, or via OCR from images/PDFs)
- **Pharmacies** can access current pricing from multiple suppliers
- **Admin** manages depots, users, and system configuration
- Complete data isolation between tenants
- OCR support for handwritten and typed documents

---

## Architecture

### Multi-Tenant Database Architecture

```
┌─────────────────────────────────────┐
│     Central Database (PostgreSQL)   │
│  - tenants (depot registry)         │
│  - users (all system users)         │
│  - audit_logs (system activity)     │
│  - user_sessions (session tokens)   │
└─────────────────────────────────────┘
              │
              ├─── Tenant 1 Database
              │    - price_lists
              │    - medicines
              │    - upload_history
              │
              ├─── Tenant 2 Database
              │    - price_lists
              │    - medicines
              │    - upload_history
              │
              └─── Tenant N Database
                   - price_lists
                   - medicines
                   - upload_history
```

### Technology Stack
- **Backend**: Python 3.10+, Flask, SQLAlchemy, PostgreSQL
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+)
- **OCR**: EasyOCR (for image/PDF text extraction)
- **Authentication**: JWT tokens + Flask sessions
- **File Processing**: pandas, openpyxl, pdf2image

---

## Project Structure

```
pricing project/
├── app/                          # Main application package
│   ├── __init__.py              # Flask app factory
│   ├── routes.py                # Frontend route handlers
│   ├── errors.py                # Error handlers
│   │
│   ├── blueprints/              # API endpoint modules
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── admin.py            # Admin management endpoints
│   │   └── depot.py            # Depot operations endpoints
│   │
│   ├── database/                # Database connection managers
│   │   ├── __init__.py
│   │   ├── central_db.py        # Central database connection
│   │   └── tenant_db.py         # Tenant database router
│   │
│   ├── services/                # Business logic services
│   │   ├── file_processor.py   # CSV/Excel file parsing
│   │   ├── ocr_processor.py    # OCR text extraction
│   │   └── tenant_creator.py   # Tenant database creation
│   │
│   ├── utils/                   # Utility functions
│   │   └── auth.py             # JWT & password utilities
│   │
│   ├── middleware/              # Request/response middleware
│   │   └── audit.py            # Audit logging middleware
│   │
│   └── models/                  # Data models (reference)
│       ├── user.py
│       ├── tenant.py
│       └── audit_log.py
│
├── templates/                    # HTML templates
│   ├── landing.html             # Login/landing page
│   ├── admin.html               # Admin dashboard
│   └── depot.html               # Depot dashboard
│
├── static/                       # Static assets
│   ├── css/
│   │   └── style.css            # Main stylesheet
│   └── js/
│       ├── auth.js              # Authentication utilities
│       ├── admin.js             # Admin dashboard logic
│       └── depot.js             # Depot dashboard logic
│
├── database/                     # Database schema files
│   ├── central_database_schema.sql
│   ├── create_sessions_table.sql
│   └── migrate_*.sql            # Migration scripts
│
├── config.py                     # Configuration settings
├── run.py                        # Application entry point
├── requirements.txt              # Python dependencies
├── README.md                     # Quick start guide
└── PROJECT_DOCUMENTATION.md      # This file
```

---

## File-by-File Documentation

### Root Level Files

#### `run.py`
**Purpose**: Application entry point - starts the Flask development server

**Code Explanation**:
```python
from app import create_app
from config import Config

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)

# Create Flask app instance using factory pattern
app = create_app(Config)

# Run development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
```

**Key Points**:
- Uses Flask's application factory pattern (`create_app`)
- Runs on port 5000, accessible from all network interfaces
- Debug mode enabled for development

---

#### `config.py`
**Purpose**: Centralized configuration management using environment variables

**Code Explanation**:
```python
class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or SECRET_KEY
    
    # Database connections
    CENTRAL_DB_HOST = os.environ.get('CENTRAL_DB_HOST') or 'localhost'
    CENTRAL_DB_NAME = os.environ.get('CENTRAL_DB_NAME') or 'pricing_central'
    
    # File upload limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    @staticmethod
    def get_central_db_uri():
        """Builds PostgreSQL connection string"""
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
```

**Key Points**:
- Loads from `.env` and `db.env` files
- Provides defaults for development
- Centralizes all configuration in one place
- Includes helper methods for database URIs

---

#### `requirements.txt`
**Purpose**: Python package dependencies

**Key Dependencies**:
- `Flask==3.0.0` - Web framework
- `SQLAlchemy==2.0.23` - ORM for database
- `psycopg2-binary==2.9.9` - PostgreSQL adapter
- `pandas==2.1.3` - Data processing (CSV/Excel)
- `easyocr==1.7.0` - OCR engine
- `reportlab==4.0.7` - PDF generation
- `openpyxl==3.1.2` - Excel file handling
- `pdf2image==1.16.3` - PDF to image conversion

---

### Application Package (`app/`)

#### `app/__init__.py`
**Purpose**: Flask application factory - creates and configures the Flask app

**Code Explanation**:
```python
def create_app(config_class=Config):
    """Application factory pattern"""
    # Create Flask instance with custom template/static folders
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(config_class)
    
    # Configure session management
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # Enable CORS for frontend API calls
    CORS(app, supports_credentials=True)
    
    # Register routes and blueprints
    from app.routes import index, admin, depot
    app.add_url_rule('/', 'index', index)
    app.add_url_rule('/admin.html', 'admin', admin)
    app.add_url_rule('/depot.html', 'depot', depot)
    
    # Register API blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/v1/admin')
    app.register_blueprint(depot_bp, url_prefix='/api/v1/depot')
    
    # Register middleware
    app.before_request(audit_middleware)
    app.after_request(log_request)
    
    return app
```

**Key Points**:
- Uses factory pattern for testability and flexibility
- Configures CORS for cross-origin requests
- Sets up session management
- Registers all routes and blueprints
- Attaches middleware for audit logging

---

#### `app/routes.py`
**Purpose**: Frontend route handlers - serves HTML pages

**Code Explanation**:
```python
def index():
    """Serve landing/login page"""
    return render_template('landing.html')

def admin():
    """Serve admin dashboard"""
    return render_template('admin.html')

def depot():
    """Serve depot dashboard"""
    return render_template('depot.html')
```

**Key Points**:
- Simple route handlers that render HTML templates
- No authentication check here (handled in frontend JavaScript)

---

#### `app/errors.py`
**Purpose**: Global error handlers for the application

**Code Explanation**:
```python
def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
```

**Key Points**:
- Centralized error handling
- Returns JSON responses for API errors
- Logs errors for debugging

---

### Blueprints (`app/blueprints/`)

#### `app/blueprints/auth.py`
**Purpose**: Authentication endpoints (login, logout, registration)

**Key Endpoints**:

1. **POST `/api/v1/auth/login`**
   - Validates email/password
   - Creates JWT token and Flask session
   - Returns user info and token

```python
@auth_bp.route('/login', methods=['POST'])
def login():
    email = data.get('email')
    password = data.get('password')
    
    # Query user from database
    user = session.execute(text("SELECT * FROM users WHERE email = :email"), {'email': email})
    
    # Verify password
    if not verify_password(password, user.password_hash):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate JWT token
    token = generate_token({
        'user_id': str(user.id),
        'email': user.email,
        'role': user.role,
        'tenant_id': str(user.tenant_id) if user.tenant_id else None
    })
    
    # Create Flask session
    flask_session['user_id'] = user.id
    flask_session['role'] = user.role
    flask_session['tenant_id'] = user.tenant_id
    flask_session['session_token'] = session_token
    
    return jsonify({'token': token, 'user': {...}})
```

2. **POST `/api/v1/auth/logout`**
   - Invalidates session
   - Clears session data

3. **POST `/api/v1/auth/register`**
   - Creates new user account (admin only)
   - Hashes password with bcrypt

**Key Points**:
- Uses both JWT tokens and Flask sessions
- Passwords hashed with bcrypt (cost factor 12)
- Session tokens stored in database for validation

---

#### `app/blueprints/admin.py`
**Purpose**: Admin management endpoints

**Key Endpoints**:

1. **POST `/api/v1/admin/tenant`** - Create new depot
   - Creates tenant record in central database
   - Automatically creates tenant database
   - Creates depot user account
   - Returns tenant and user info

```python
@admin_bp.route('/tenant', methods=['POST'])
@require_auth
@require_role('admin')
def create_tenant():
    # Extract form data
    business_name = data.get('business_name')
    email = data.get('email')
    password = data.get('password')
    
    # Create tenant database
    creator = TenantDatabaseCreator()
    success, database_name, error = creator.create_tenant_database(business_name)
    
    # Insert tenant into central database
    session.execute(text("""
        INSERT INTO tenants (id, business_name, email, database_name, ...)
        VALUES (:id, :business_name, :email, :database_name, ...)
    """), {...})
    
    # Create depot user account
    password_hash = hash_password(password)
    session.execute(text("""
        INSERT INTO users (id, email, password_hash, role, tenant_id, ...)
        VALUES (:id, :email, :password_hash, 'depot', :tenant_id, ...)
    """), {...})
    
    session.commit()
    return jsonify({'message': 'Depot created successfully', ...})
```

2. **GET `/api/v1/admin/users`** - List all users
   - Returns all users with tenant details
   - Used by admin dashboard to display depot users table

3. **PUT `/api/v1/admin/user/<id>`** - Update user
   - Updates user information
   - Validates role changes

4. **DELETE `/api/v1/admin/user/<id>`** - Delete user
   - Removes user from system
   - Prevents self-deletion

5. **GET `/api/v1/admin/profile`** - Get admin profile
6. **PUT `/api/v1/admin/profile`** - Update admin profile
7. **PUT `/api/v1/admin/profile/password`** - Change password

**Key Points**:
- All endpoints require admin role
- Tenant database creation is automatic
- Full CRUD operations for users and tenants

---

#### `app/blueprints/depot.py`
**Purpose**: Depot operations endpoints (largest file, ~1800 lines)

**Key Endpoints**:

1. **POST `/api/v1/depot/upload`** - Upload CSV/Excel file
   - Validates file type and size
   - Processes file with FileProcessor
   - Saves medicines to tenant database
   - Creates price_list record

```python
@depot_bp.route('/upload', methods=['POST'])
@require_auth
@require_role('depot')
def upload_price_list():
    file = request.files['file']
    file_content = file.read()
    
    # Process file
    processor = FileProcessor()
    valid_records, valid_count, invalid_count = processor.process_file(file_content, filename)
    
    # Save to tenant database
    tenant_session = TenantDBManager.get_session(tenant_db_name)
    
    # Create price list
    price_list_id = uuid.uuid4()
    tenant_session.execute(text("""
        INSERT INTO price_lists (id, tenant_id, file_name, total_items, ...)
        VALUES (:id, :tenant_id, :file_name, :total_items, ...)
    """), {...})
    
    # Insert medicines
    for record in valid_records:
        tenant_session.execute(text("""
            INSERT INTO medicines (price_list_id, medicine_name, unit_price, ...)
            VALUES (:price_list_id, :medicine_name, :unit_price, ...)
        """), {...})
    
    tenant_session.commit()
```

2. **POST `/api/v1/depot/upload-ocr`** - OCR scan for upload
   - Accepts image/PDF file
   - Uses OCRProcessor to extract text
   - Structures data into medicine name/price pairs
   - Returns preview data for user editing

3. **POST `/api/v1/depot/upload-ocr-confirm`** - Confirm OCR upload
   - Saves edited OCR data to database
   - Same logic as regular upload

4. **POST `/api/v1/depot/upload-manual`** - Manual entry upload
   - Accepts JSON array of medicine records
   - Validates and saves to database

5. **GET `/api/v1/depot/upload-ocr-progress`** - OCR progress
   - Returns current OCR processing progress
   - Uses Flask session to track progress

6. **POST `/api/v1/depot/download-prices`** - Get prices from file
   - Accepts CSV/Excel with medicine names
   - Matches names with database
   - Returns matched medicines with prices

7. **POST `/api/v1/depot/download-prices-ocr`** - OCR for price lookup
   - Scans image/PDF for medicine names
   - Looks up prices in database
   - Returns matched medicines

8. **POST `/api/v1/depot/download-prices-manual`** - Manual price lookup
   - Accepts array of medicine names
   - Flexible matching (ignores numbers)
   - Returns matched medicines

9. **POST `/api/v1/depot/download-prices-excel`** - Download Excel
   - Generates Excel file with prices
   - Uses openpyxl library

10. **POST `/api/v1/depot/download-prices-pdf`** - Download PDF
    - Generates PDF file with prices
    - Uses reportlab library
    - Formats prices without decimals

11. **GET `/api/v1/depot/medicines`** - List medicines
12. **PUT `/api/v1/depot/medicine/<id>`** - Update medicine
13. **DELETE `/api/v1/depot/medicine/<id>`** - Delete medicine
14. **GET `/api/v1/depot/price-lists`** - List price lists
15. **GET `/api/v1/depot/statistics`** - Get statistics

**Key Points**:
- All endpoints require depot role and authentication
- Uses tenant database isolation
- Supports multiple upload methods (file, OCR, manual)
- Flexible medicine name matching for price lookup
- Progress tracking for long-running OCR operations

---

### Database (`app/database/`)

#### `app/database/central_db.py`
**Purpose**: Central database connection manager (singleton pattern)

**Code Explanation**:
```python
class CentralDB:
    _engine = None
    _session_factory = None
    
    @classmethod
    def initialize(cls):
        """Initialize database connection"""
        if cls._engine is None:
            db_uri = Config.get_central_db_uri()
            cls._engine = create_engine(db_uri, pool_pre_ping=True)
            cls._session_factory = sessionmaker(bind=cls._engine)
    
    @classmethod
    def get_session(cls):
        """Get database session"""
        if cls._engine is None:
            cls.initialize()
        return cls._session_factory()
    
    @classmethod
    def test_connection(cls):
        """Test database connection"""
        try:
            session = cls.get_session()
            session.execute(text("SELECT 1"))
            session.close()
            return True
        except:
            return False
```

**Key Points**:
- Singleton pattern ensures single connection pool
- Lazy initialization (connects on first use)
- Connection pooling for performance
- Test method for health checks

---

#### `app/database/tenant_db.py`
**Purpose**: Tenant database router - manages connections to tenant databases

**Code Explanation**:
```python
class TenantDBManager:
    _engines = {}  # Cache of database engines
    _session_factories = {}
    
    @classmethod
    def get_session(cls, tenant_db_name):
        """Get session for specific tenant database"""
        if tenant_db_name not in cls._engines:
            # Create new engine for this tenant
            db_uri = Config.get_tenant_db_uri(tenant_db_name)
            cls._engines[tenant_db_name] = create_engine(db_uri, pool_pre_ping=True)
            cls._session_factories[tenant_db_name] = sessionmaker(
                bind=cls._engines[tenant_db_name]
            )
        
        return cls._session_factories[tenant_db_name]()
```

**Key Points**:
- Caches database engines per tenant
- Creates connections on-demand
- Each tenant has isolated database connection
- Used by depot endpoints to access tenant data

---

### Services (`app/services/`)

#### `app/services/file_processor.py`
**Purpose**: Processes CSV and Excel files to extract medicine data

**Code Explanation**:
```python
class FileProcessor:
    def process_file(self, file_content, filename):
        """Main processing method"""
        # Read file based on extension
        if filename.endswith('.csv'):
            df = self._read_csv(file_content)
        elif filename.endswith(('.xlsx', '.xls')):
            df = self._read_excel(file_content)
        
        # Detect columns
        medicine_col = self._detect_medicine_column(df)
        price_col = self._detect_price_column(df)
        
        # Process rows
        valid_records = []
        for index, row in df.iterrows():
            medicine_name = str(row[medicine_col]).strip()
            unit_price = self._parse_price(row[price_col])
            
            if medicine_name and unit_price > 0:
                valid_records.append({
                    'medicine_name': medicine_name,
                    'unit_price': unit_price
                })
        
        return valid_records, len(valid_records), len(df) - len(valid_records)
    
    def _detect_medicine_column(self, df):
        """Intelligently find medicine name column"""
        # Try exact matches first
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['medicine', 'name', 'product']):
                return col
        
        # Try content-based detection
        for col in df.columns:
            if self._looks_like_medicine_name(df[col]):
                return col
        
        return df.columns[0]  # Default to first column
```

**Key Points**:
- Supports CSV and Excel formats
- Intelligent column detection (name-based and content-based)
- Validates and cleans data
- Returns valid records and error count

---

#### `app/services/ocr_processor.py`
**Purpose**: OCR processing for images and PDFs (759 lines - most complex service)

**Code Explanation**:
```python
class OCRProcessor:
    _ocr_processor_instance = None
    
    @classmethod
    def get_ocr_processor(cls):
        """Singleton pattern for EasyOCR reader"""
        if cls._ocr_processor_instance is None:
            cls._ocr_processor_instance = OCRProcessor()
        return cls._ocr_processor_instance
    
    def __init__(self):
        """Initialize EasyOCR reader"""
        # Patch SSL for model downloads
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # Initialize EasyOCR (lazy loading)
        self.reader = None
    
    def process_file(self, file_content, filename, progress_callback=None):
        """Main processing method"""
        # Determine file type
        if filename.lower().endswith('.pdf'):
            return self._process_pdf(file_content, progress_callback)
        else:
            return self._process_image(file_content, progress_callback)
    
    def _process_image(self, file_content, progress_callback):
        """Process image file"""
        # Load image
        image = Image.open(io.BytesIO(file_content))
        
        # Resize if too large
        image = self._resize_image_if_needed(image)
        
        # Preprocess for better OCR
        processed_image = self._preprocess_image(image)
        
        # Run OCR
        self._update_progress(30, "Running OCR...")
        results = self.reader.readtext(np.array(image), ...)
        
        # Extract text
        text = ' '.join([item[1] for item in results])
        
        # Structure data (detect table format)
        structured_data = self._structure_ocr_data(results)
        
        return {
            'text': text,
            'structured_data': structured_data,
            'pages': 1
        }
    
    def _structure_ocr_data(self, ocr_results):
        """Convert OCR results to structured medicine/price pairs"""
        # Group text by y-coordinate (rows)
        lines = self._group_by_lines(ocr_results)
        
        # Detect column boundaries
        columns = self._detect_columns(lines)
        
        # Parse table structure
        return self._parse_table_structure(lines, columns)
```

**Key Features**:
- **Singleton Pattern**: Reuses EasyOCR reader for performance
- **Image Preprocessing**: Grayscale, denoising, contrast enhancement
- **Image Resizing**: Scales down large images for faster processing
- **Table Detection**: Detects two-column layout (medicine name | price)
- **Progress Tracking**: Reports progress via callback
- **PDF Support**: Converts PDF pages to images
- **Flexible Parsing**: Handles various table formats

**Key Methods**:
- `_preprocess_image()` - Image enhancement for better OCR
- `_resize_image_if_needed()` - Performance optimization
- `_group_by_lines()` - Groups OCR results by row
- `_detect_columns()` - Finds column boundaries
- `_parse_table_structure()` - Extracts medicine/price pairs
- `parse_line()` - Parses single line of text

---

#### `app/services/tenant_creator.py`
**Purpose**: Creates tenant databases automatically

**Code Explanation**:
```python
class TenantDatabaseCreator:
    def create_tenant_database(self, business_name):
        """Create new tenant database"""
        # Sanitize database name
        db_name = self._sanitize_db_name(business_name)
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(...)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Create database
        cursor.execute(f'CREATE DATABASE "{db_name}"')
        
        # Connect to new database
        tenant_conn = psycopg2.connect(..., database=db_name)
        tenant_cursor = tenant_conn.cursor()
        
        # Create tables
        self._create_price_lists_table(tenant_cursor)
        self._create_medicines_table(tenant_cursor)
        self._create_upload_history_table(tenant_cursor)
        self._create_download_logs_table(tenant_cursor)
        
        # Create indexes
        self._create_indexes(tenant_cursor)
        
        tenant_conn.commit()
        return True, db_name, None
```

**Key Points**:
- Sanitizes business name for database name
- Creates all required tables
- Sets up indexes and constraints
- Handles errors and rollback

---

### Utilities (`app/utils/`)

#### `app/utils/auth.py`
**Purpose**: Authentication utilities (JWT, password hashing, decorators)

**Code Explanation**:
```python
def hash_password(password):
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))

def verify_password(password, password_hash):
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def generate_token(payload):
    """Generate JWT token"""
    payload['exp'] = datetime.utcnow() + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')

def verify_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Try JWT token first
        token = get_token_from_request()
        if token:
            payload = verify_token(token)
            if payload:
                request.current_user = payload
                return f(*args, **kwargs)
        
        # Fallback to Flask session
        session_token = flask_session.get('session_token')
        if session_token:
            # Verify session in database
            if session_valid:
                request.current_user = {...}
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function

def require_role(*allowed_roles):
    """Decorator to require specific role"""
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated_function(*args, **kwargs):
            user_role = request.current_user.get('role')
            if user_role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

**Key Points**:
- Bcrypt with 12 rounds for password hashing
- JWT tokens with 24-hour expiry
- Dual authentication (JWT + Flask sessions)
- Role-based access control decorators

---

### Middleware (`app/middleware/`)

#### `app/middleware/audit.py`
**Purpose**: Audit logging middleware - logs all API requests

**Code Explanation**:
```python
def audit_middleware():
    """Called before each request"""
    # Skip static files and health checks
    if request.path.startswith('/static') or request.path == '/health':
        return
    
    # Extract user info from token
    token = get_token_from_request()
    if token:
        payload = verify_token(token)
        if payload:
            request.audit_user_id = payload.get('user_id')
            request.audit_tenant_id = payload.get('tenant_id')

def log_request(response):
    """Called after each request"""
    # Log to audit_logs table
    session = CentralDB.get_session()
    session.execute(text("""
        INSERT INTO audit_logs (user_id, tenant_id, action, resource_type, ...)
        VALUES (:user_id, :tenant_id, :action, :resource_type, ...)
    """), {
        'user_id': request.audit_user_id,
        'tenant_id': request.audit_tenant_id,
        'action': request.method,
        'resource_type': request.path,
        ...
    })
    session.commit()
```

**Key Points**:
- Logs all API requests to database
- Captures user, tenant, action, IP address
- Used for security auditing and debugging

---

### Frontend Files

#### `templates/landing.html`
**Purpose**: Login/landing page

**Key Features**:
- Login form with email/password
- Role selection (admin/depot)
- Error message display
- Redirects to appropriate dashboard after login

---

#### `templates/admin.html`
**Purpose**: Admin dashboard

**Key Sections**:
1. **Create Depot Form**
   - Business name, registration number, contact person
   - Email, phone, address
   - Password for depot user account
   - Creates tenant and user automatically

2. **Depot Users Table**
   - Displays all depot users with full details
   - Shows business name, registration, contact, email, phone, address
   - Edit and delete actions
   - Refresh button

3. **Admin Profile**
   - Update profile information
   - Change password

---

#### `templates/depot.html`
**Purpose**: Depot dashboard

**Key Sections**:
1. **Upload Prices**
   - **File Upload Tab**: CSV/Excel upload
   - **OCR Tab**: Image/PDF scan with preview/edit
   - **Manual Entry Tab**: Editable table for manual input

2. **Manage Products**
   - List all medicines
   - Search functionality
   - Edit/delete medicines

3. **Download Prices**
   - **File Upload Tab**: Upload file with medicine names
   - **OCR Tab**: Scan image/PDF for medicine names
   - **Manual Entry Tab**: Paste/type medicine names
   - Results table with download options (CSV, Excel, PDF)

---

#### `static/js/auth.js`
**Purpose**: Authentication utilities for frontend

**Key Functions**:
```javascript
function getToken() {
    return localStorage.getItem('auth_token');
}

function setToken(token) {
    localStorage.setItem('auth_token', token);
}

function removeToken() {
    localStorage.removeItem('auth_token');
}

async function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.replace('/');
        return false;
    }
    
    // Verify token with backend
    const response = await fetch('/api/v1/auth/verify', {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) {
        removeToken();
        window.location.replace('/');
        return false;
    }
    
    return true;
}

async function apiRequest(url, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(`/api/v1${url}`, {
        ...options,
        headers
    });
    
    if (response.status === 401) {
        removeToken();
        window.location.replace('/');
        throw new Error('Session expired');
    }
    
    return response.json();
}
```

**Key Points**:
- Token stored in localStorage
- Automatic token validation
- Handles session expiration
- Centralized API request function

---

#### `static/js/admin.js`
**Purpose**: Admin dashboard functionality

**Key Functions**:
- `loadDepotUsers()` - Loads and displays depot users table
- `setupCreateTenantForm()` - Handles depot creation form
- `editDepotUser()` - Opens edit modal
- `deleteDepotUser()` - Deletes depot user
- `loadAdminProfile()` - Loads admin profile data
- `setupAdminProfileForm()` - Handles profile update
- `setupAdminPasswordForm()` - Handles password change

---

#### `static/js/depot.js`
**Purpose**: Depot dashboard functionality (largest JS file, ~1350 lines)

**Key Functions**:

1. **Upload Functions**:
   - `setupUploadForm()` - CSV/Excel upload
   - `setupOCRUploadForm()` - OCR upload with progress
   - `submitManualUpload()` - Manual entry upload
   - `displayOCRPreview()` - Shows OCR results for editing

2. **Download Functions**:
   - `handleDownloadPrices()` - File-based price lookup
   - `setupDownloadPricesOCRForm()` - OCR-based price lookup
   - `getManualPrices()` - Manual entry price lookup
   - `downloadPricesCSV()` - Download as CSV
   - `downloadPricesExcel()` - Download as Excel
   - `downloadPricesPDF()` - Download as PDF

3. **Product Management**:
   - `loadProducts()` - Load medicine list
   - `searchProducts()` - Search medicines
   - `editMedicine()` - Edit medicine
   - `deleteMedicine()` - Delete medicine

4. **Utility Functions**:
   - `showOCRProgress()` - Display OCR progress bar
   - `switchUploadTab()` - Switch between upload tabs
   - `switchDownloadTab()` - Switch between download tabs

**Key Points**:
- Handles all three upload methods
- Progress tracking for OCR operations
- Flexible medicine name matching
- Multiple download formats

---

#### `static/css/style.css`
**Purpose**: Main stylesheet for the application

**Key Features**:
- Modern, responsive design
- Dashboard layout with sidebar
- Form styling
- Table styling
- Alert/notification styling
- Color scheme with CSS variables

---

## Data Flow

### Upload Price List Flow

```
1. User selects file (CSV/Excel) or image/PDF
   ↓
2. Frontend sends file to backend endpoint
   ↓
3. Backend validates file type and size
   ↓
4. FileProcessor or OCRProcessor processes file
   ↓
5. Extracts medicine names and prices
   ↓
6. Backend gets tenant database name from central DB
   ↓
7. Connects to tenant database
   ↓
8. Creates price_list record
   ↓
9. Inserts medicines into tenant database
   ↓
10. Returns success response with statistics
    ↓
11. Frontend displays success message
```

### Download Prices Flow

```
1. User provides medicine names (file/OCR/manual)
   ↓
2. Frontend sends names to backend
   ↓
3. Backend gets tenant database name
   ↓
4. Queries tenant database for matching medicines
   ↓
5. Flexible matching (ignores numbers, case-insensitive)
   ↓
6. Returns matched medicines with prices
   ↓
7. Frontend displays results in table
   ↓
8. User can download as CSV/Excel/PDF
```

### Authentication Flow

```
1. User enters email/password
   ↓
2. Frontend sends to /api/v1/auth/login
   ↓
3. Backend verifies credentials
   ↓
4. Generates JWT token
   ↓
5. Creates Flask session
   ↓
6. Returns token and user info
   ↓
7. Frontend stores token in localStorage
   ↓
8. Subsequent requests include token in Authorization header
   ↓
9. Backend validates token on each request
```

---

## Key Features Explained

### 1. Multi-Tenant Architecture
- Each depot has isolated database
- Complete data separation
- Scalable architecture
- Tenant databases created automatically

### 2. OCR Processing
- Supports images (PNG, JPG, PDF)
- Handles handwritten text
- Table structure detection
- Progress tracking
- Image preprocessing for accuracy

### 3. Flexible Medicine Matching
- Exact matching first
- Falls back to number-ignored matching
- Case-insensitive
- Partial matching support

### 4. Multiple Upload Methods
- File upload (CSV/Excel)
- OCR scan (Image/PDF)
- Manual entry (table)

### 5. Multiple Download Formats
- CSV
- Excel (formatted)
- PDF (formatted, no decimals)

### 6. Security Features
- JWT authentication
- Bcrypt password hashing
- Role-based access control
- Session management
- Audit logging

---

## Database Schema

### Central Database Tables

**tenants**
- id (UUID)
- business_name
- registration_number
- contact_person
- email
- phone
- address
- database_name
- status
- created_at, updated_at

**users**
- id (UUID)
- email (unique)
- password_hash
- full_name
- phone
- role (admin/depot)
- tenant_id (FK to tenants)
- is_active
- email_verified
- last_login
- created_at, updated_at

**audit_logs**
- id (UUID)
- user_id (FK)
- tenant_id (FK)
- action
- resource_type
- resource_id
- details (JSONB)
- ip_address
- user_agent
- created_at

**user_sessions**
- session_token
- user_id (FK)
- expires_at
- created_at

### Tenant Database Tables

**price_lists**
- id (UUID)
- tenant_id (UUID)
- version
- status
- file_name
- total_items
- valid_items
- invalid_items
- activated_at
- created_at

**medicines**
- id (UUID)
- price_list_id (FK)
- medicine_name
- unit_price
- is_active
- created_at
- last_updated
- UNIQUE(price_list_id, medicine_name)

**upload_history**
- id (UUID)
- price_list_id (FK)
- uploaded_by (UUID)
- upload_method
- file_size
- processing_time
- created_at

---

## Environment Variables

Required in `.env` or `db.env`:

```env
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
CENTRAL_DB_HOST=localhost
CENTRAL_DB_PORT=5432
CENTRAL_DB_NAME=pricing_central
CENTRAL_DB_USER=postgres
CENTRAL_DB_PASSWORD=your-password
PG_ADMIN_USER=postgres
PG_ADMIN_PASSWORD=your-password
PG_ADMIN_HOST=localhost
UPLOAD_FOLDER=uploads
```

---

## Dependencies Explained

- **Flask**: Web framework
- **SQLAlchemy**: ORM for database operations
- **psycopg2-binary**: PostgreSQL database adapter
- **pandas**: Data processing for CSV/Excel files
- **openpyxl**: Excel file reading/writing
- **easyocr**: OCR engine for text extraction
- **pdf2image**: Converts PDF pages to images
- **reportlab**: PDF generation
- **Pillow**: Image processing
- **opencv-python**: Image preprocessing
- **PyJWT**: JWT token generation/validation
- **bcrypt**: Password hashing
- **python-dotenv**: Environment variable loading

---

## Common Patterns Used

1. **Application Factory Pattern**: `create_app()` function
2. **Singleton Pattern**: OCRProcessor, database connections
3. **Decorator Pattern**: `@require_auth`, `@require_role`
4. **Repository Pattern**: Database managers (CentralDB, TenantDBManager)
5. **Service Pattern**: FileProcessor, OCRProcessor, TenantDatabaseCreator

---

## Error Handling

- Global error handlers in `app/errors.py`
- Try-catch blocks in all endpoints
- Detailed error messages returned to frontend
- Logging for debugging
- Graceful degradation

---

## Performance Optimizations

1. **Database Connection Pooling**: SQLAlchemy connection pools
2. **OCR Singleton**: Reuses EasyOCR reader instance
3. **Image Resizing**: Scales down large images before OCR
4. **Lazy Loading**: Database connections created on-demand
5. **Caching**: Tenant database engines cached

---

## Security Considerations

1. **Password Hashing**: Bcrypt with 12 rounds
2. **JWT Tokens**: Signed and time-limited
3. **SQL Injection Prevention**: Parameterized queries
4. **XSS Prevention**: Input sanitization
5. **CSRF Protection**: SameSite cookies
6. **File Upload Validation**: Type and size checks
7. **Role-Based Access**: Strict permission checks

---

## Future Enhancements

Potential improvements:
- Async file processing for large uploads
- Redis caching for frequently accessed data
- WebSocket for real-time progress updates
- Advanced OCR with machine learning
- Bulk operations API
- Export/import functionality
- API rate limiting
- Email notifications
- Dashboard analytics

---

## Conclusion

This documentation provides a comprehensive overview of the Pharmacy Pricing System. Each file serves a specific purpose in the multi-tenant architecture, with clear separation of concerns between frontend, backend, database, and services.

For questions or clarifications, refer to the code comments or contact the development team.
