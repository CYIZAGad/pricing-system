"""
File Processing Service
Handles CSV/Excel file parsing and validation
"""

import pandas as pd
import csv
import io
import logging
from typing import List, Dict, Tuple
import math

logger = logging.getLogger(__name__)


class FileProcessor:
    """Processes uploaded price list files"""
    
    # Column mapping rules (case-insensitive) - expanded with many variations
    COLUMN_MAPPINGS = {
        'medicine_name': [
            'medicine', 'product', 'drug name', 'item', 'medicine name', 'name',
            'drug', 'medicament', 'medication', 'product name', 'item name',
            'drugs', 'medicines', 'products', 'items', 'nom', 'medicament',
            'medicina', 'medicamento', 'produit', 'produkt', 'nombre',
            # Common misspellings we see in uploaded spreadsheets
            'medecine name', 'medecine_name', 'medicene name', 'medicene_name'
        ],
        'medicine_code': ['code', 'medicine code', 'product code', 'item code', 'sku'],
        'unit_price': [
            'price', 'unit price', 'cost', 'rate', 'selling price',
            'prix', 'precio', 'preis', 'costo', 'prijs', 'price per unit',
            'unit cost', 'selling rate', 'amount', 'value', 'prix unitaire'
            ,
            # Common misspellings
            'unity price', 'unity_price'
        ],
        'unit_type': ['unit', 'type', 'packaging', 'form', 'unit type', 'package'],
        'manufacturer': ['manufacturer', 'maker', 'brand', 'company'],
        'batch_number': ['batch', 'batch number', 'lot', 'lot number'],
        'expiry_date': ['expiry', 'expiry date', 'exp date', 'expiration'],
        'quantity_available': ['quantity', 'qty', 'stock', 'available', 'quantity available'],
        'minimum_order': ['minimum order', 'min order', 'moq', 'minimum']
    }
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def process_file(self, file_content, filename: str) -> Tuple[List[Dict], int, int]:
        """
        Process uploaded file
        Returns: (valid_records, valid_count, invalid_count)
        """
        self.errors = []
        self.warnings = []
        
        try:
            # Detect file type
            if filename.endswith('.csv'):
                df = self._read_csv(file_content)
            elif filename.endswith(('.xlsx', '.xls')):
                df = self._read_excel(file_content)
            else:
                raise ValueError(f"Unsupported file type: {filename}")
            
            if df is None or df.empty:
                raise ValueError("File is empty or could not be parsed")
            
            # Map columns
            column_map = self._map_columns(df.columns.tolist())
            
            # Smart detection if columns not found by name matching
            # Find medicine_name column (first text column if not found)
            if 'medicine_name' not in column_map.values():
                medicine_col = self._detect_medicine_column(df, column_map)
                if medicine_col:
                    column_map[medicine_col] = 'medicine_name'
            
            # Find unit_price column (first numeric column if not found)
            if 'unit_price' not in column_map.values():
                price_col = self._detect_price_column(df, column_map)
                if price_col:
                    column_map[price_col] = 'unit_price'
            
            # Find expiry_date column (if not found by name matching)
            if 'expiry_date' not in column_map.values():
                expiry_col = self._detect_expiry_column(df, column_map)
                if expiry_col:
                    column_map[expiry_col] = 'expiry_date'
            
            # Validate required columns (name, price, and expiry_date required)
            required = ['medicine_name', 'unit_price', 'expiry_date']
            missing = [col for col in required if col not in column_map.values()]
            if missing:
                raise ValueError(f"Missing required columns: {missing}. Found columns: {list(df.columns)}")
            
            # Process rows
            valid_records = []
            valid_count = 0
            invalid_count = 0
            
            for idx, row in df.iterrows():
                try:
                    record = self._parse_row(row, column_map, idx + 2)  # +2 for header and 0-index
                    if record:
                        valid_records.append(record)
                        valid_count += 1
                    else:
                        invalid_count += 1
                except Exception as e:
                    invalid_count += 1
                    self.errors.append(f"Row {idx + 2}: {str(e)}")
            
            return valid_records, valid_count, invalid_count
            
        except Exception as e:
            logger.error(f"File processing error: {e}")
            raise ValueError(f"Failed to process file: {str(e)}")
    
    def _read_csv(self, file_content) -> pd.DataFrame:
        """Read CSV file"""
        try:
            # Handle both bytes and string
            if isinstance(file_content, bytes):
                # Try different encodings
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                    try:
                        df = pd.read_csv(io.StringIO(file_content.decode(encoding)))
                        return df
                    except:
                        continue
                raise ValueError("Could not decode CSV file")
            else:
                # Already a string
                df = pd.read_csv(io.StringIO(file_content))
                return df
        except Exception as e:
            logger.error(f"CSV read error: {e}")
            raise
    
    def _read_excel(self, file_content) -> pd.DataFrame:
        """Read Excel file"""
        try:
            return self._read_excel_with_header_detection(file_content)
        except Exception as e:
            logger.error(f"Excel read error: {e}")
            raise

    def _read_excel_with_header_detection(self, file_content) -> pd.DataFrame:
        """
        Read Excel file, but tolerate common real-world formatting issues:
        - Blank rows before the header
        - Header starting in later columns (e.g. column C/D) leaving NaN headers in A/B
        - Slight header misspellings
        - Data can start in any column, not just column A
        """
        # Load raw sheet without assuming the first row is header
        raw = pd.read_excel(
            io.BytesIO(file_content),
            header=None,
            engine="openpyxl"
        )

        if raw is None or raw.empty:
            return raw

        # Find best header row by scanning all rows in the sheet
        # (users may place headers far down in the file)
        max_scan_rows = len(raw)
        medicine_hints = ['med', 'drug', 'product', 'item', 'name', 'nom', 'medecine', 'medicene']
        price_hints = ['price', 'prix', 'cost', 'rate', 'amount', 'value', 'unity']
        expiry_hints = ['expiry', 'exp', 'expiration', 'exp date', 'expiry date', 'valid until', 'validity']

        def _cell_to_str(v) -> str:
            if v is None:
                return ''
            try:
                if isinstance(v, float) and math.isnan(v):
                    return ''
            except Exception:
                pass
            return str(v).strip()

        best_idx = None
        best_score = -1.0
        for i in range(max_scan_rows):
            row_vals = [_cell_to_str(v) for v in raw.iloc[i].tolist()]
            lower_vals = [v.lower() for v in row_vals if v]
            non_empty = len(lower_vals)
            if non_empty < 2:
                continue

            has_med = any(any(h in v for h in medicine_hints) for v in lower_vals)
            has_price = any(any(h in v for h in price_hints) for v in lower_vals)
            has_expiry = any(any(h in v for h in expiry_hints) for v in lower_vals)

            # Prefer rows that look like headers (medicine + price + expiry hints)
            score = non_empty
            if has_med:
                score += 5
            if has_price:
                score += 5
            if has_expiry:
                score += 5
            if has_med and has_price:
                score += 10
            if has_med and has_price and has_expiry:
                score += 15

            if score > best_score:
                best_score = score
                best_idx = i

        # Fallback: if we couldn't find a good header row, assume first non-empty row
        if best_idx is None:
            for i in range(max_scan_rows):
                row_vals = [_cell_to_str(v) for v in raw.iloc[i].tolist()]
                if any(v for v in row_vals):
                    best_idx = i
                    break
            if best_idx is None:
                return raw

        header_row = [_cell_to_str(v) for v in raw.iloc[best_idx].tolist()]

        # Find the first non-empty header column index (data might start in column C, D, etc.)
        first_data_col_idx = None
        for idx, h in enumerate(header_row):
            if h and h.strip():
                first_data_col_idx = idx
                break
        
        # If we found where data starts, only keep columns from that point forward
        # This handles cases where headers/data start in column C, D, etc. instead of A
        if first_data_col_idx is not None and first_data_col_idx > 0:
            # Keep only columns from first_data_col_idx onwards
            raw = raw.iloc[:, first_data_col_idx:]
            header_row = header_row[first_data_col_idx:]

        # Build dataframe below header row
        df = raw.iloc[best_idx + 1:].copy()
        df.columns = header_row

        # Drop columns with empty headers (these are usually blank columns before the real data)
        cols_to_keep = []
        new_cols = []
        for idx, col in enumerate(df.columns.tolist()):
            col_str = _cell_to_str(col)
            if col_str:  # Only keep columns with non-empty headers
                cols_to_keep.append(idx)
                new_cols.append(col_str)
        
        if cols_to_keep:
            df = df.iloc[:, cols_to_keep]
            df.columns = new_cols
        else:
            # Fallback: if all headers are empty, use positional names
            df.columns = [f"Column_{i+1}" for i in range(len(df.columns))]

        # Drop completely empty columns (all NaN values)
        df = df.dropna(axis=1, how='all')

        # Drop completely empty rows
        df = df.dropna(axis=0, how='all')
        df = df.reset_index(drop=True)

        # If after all this there is still no data, treat file as empty
        if df.empty:
            raise ValueError("File is empty or does not contain any data rows")

        return df
    
    def _map_columns(self, headers: List[str]) -> Dict[str, str]:
        """Map file columns to expected fields - flexible matching"""
        column_map = {}
        # Excel often yields NaN/None headers when the header starts in later columns.
        # Normalize everything to safe strings.
        header_lower = []
        for h in headers:
            if h is None:
                header_lower.append('')
                continue
            try:
                if isinstance(h, float) and math.isnan(h):
                    header_lower.append('')
                    continue
            except Exception:
                pass
            header_lower.append(str(h).lower().strip())
        
        # First, try exact matches
        for field, variations in self.COLUMN_MAPPINGS.items():
            for header in header_lower:
                if header in [v.lower() for v in variations]:
                    # Find original header index
                    idx = header_lower.index(header)
                    column_map[headers[idx]] = field
                    break
        
        # If medicine_name not found, try partial matching
        if 'medicine_name' not in column_map.values():
            for idx, header in enumerate(header_lower):
                # Check if header contains common medicine-related keywords
                medicine_keywords = ['med', 'drug', 'product', 'item', 'name', 'nom']
                if any(keyword in header for keyword in medicine_keywords):
                    if headers[idx] not in column_map:
                        column_map[headers[idx]] = 'medicine_name'
                        break
        
        # If unit_price not found, try partial matching
        if 'unit_price' not in column_map.values():
            for idx, header in enumerate(header_lower):
                # Check if header contains common price-related keywords
                price_keywords = ['price', 'prix', 'cost', 'rate', 'amount', 'value', 'unity']
                if any(keyword in header for keyword in price_keywords):
                    if headers[idx] not in column_map:
                        column_map[headers[idx]] = 'unit_price'
                        break
        
        # If expiry_date not found, try partial matching
        if 'expiry_date' not in column_map.values():
            for idx, header in enumerate(header_lower):
                # Check if header contains common expiry-related keywords
                expiry_keywords = ['expiry', 'exp', 'expiration', 'valid', 'validity']
                if any(keyword in header for keyword in expiry_keywords):
                    if headers[idx] not in column_map:
                        column_map[headers[idx]] = 'expiry_date'
                        break
        
        return column_map
    
    def _parse_row(self, row: pd.Series, column_map: Dict[str, str], row_num: int) -> Dict:
        """Parse a single row into a medicine record"""
        record = {}
        
        # Find column for each field
        reverse_map = {v: k for k, v in column_map.items()}
        
        # Required fields: name, price, and expiry_date
        medicine_name = self._get_value(row, reverse_map.get('medicine_name'))
        unit_price = self._get_value(row, reverse_map.get('unit_price'))
        expiry_date = self._get_value(row, reverse_map.get('expiry_date'))
        
        if not medicine_name or pd.isna(medicine_name):
            raise ValueError("Medicine name is required")
        
        if unit_price is None or pd.isna(unit_price):
            raise ValueError("Unit price is required")
        
        if expiry_date is None or pd.isna(expiry_date):
            raise ValueError("Expiry date is required")
        
        try:
            unit_price = float(unit_price)
            if unit_price <= 0:
                raise ValueError("Unit price must be greater than 0")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid unit price: {unit_price}")
        
        # Parse expiry date
        try:
            if isinstance(expiry_date, str):
                parsed_date = pd.to_datetime(expiry_date, errors='coerce')
            else:
                parsed_date = pd.to_datetime(expiry_date, errors='coerce')
            
            if pd.isna(parsed_date):
                raise ValueError(f"Invalid expiry date format: {expiry_date}")
            
            record['expiry_date'] = parsed_date.date().isoformat()
        except Exception as e:
            raise ValueError(f"Invalid expiry date: {expiry_date}. Error: {str(e)}")
        
        record['medicine_name'] = str(medicine_name).strip()
        record['unit_price'] = float(unit_price)
        
        if 'quantity_available' in reverse_map:
            qty = self._get_value(row, reverse_map['quantity_available'])
            if qty is not None and not pd.isna(qty):
                try:
                    qty_int = int(float(qty))
                    if qty_int >= 0:
                        record['quantity_available'] = qty_int
                except:
                    pass
        
        if 'minimum_order' in reverse_map:
            min_order = self._get_value(row, reverse_map['minimum_order'])
            if min_order is not None and not pd.isna(min_order):
                try:
                    min_int = int(float(min_order))
                    if min_int >= 0:
                        record['minimum_order'] = min_int
                except:
                    pass
        
        return record
    
    def _get_value(self, row: pd.Series, column_name: str):
        """Get value from row by column name"""
        if not column_name:
            return None
        try:
            return row[column_name]
        except KeyError:
            return None
    
    def _detect_medicine_column(self, df: pd.DataFrame, existing_map: Dict[str, str]) -> str:
        """Detect which column is likely the medicine name by analyzing data"""
        # Get columns not already mapped
        available_cols = [col for col in df.columns if col not in existing_map]
        
        if not available_cols:
            return None
        
        # Analyze each column to find the one with most text/non-numeric data
        best_col = None
        best_score = -1
        
        for col in available_cols:
            try:
                # Sample first 10 non-null values
                sample = df[col].dropna().head(10)
                if len(sample) == 0:
                    continue
                
                # Count how many are non-numeric (likely text)
                text_count = 0
                for val in sample:
                    val_str = str(val).strip()
                    if val_str:
                        # Try to convert to number
                        try:
                            float(val_str)
                            # If successful, it's numeric - skip
                        except (ValueError, TypeError):
                            # Not numeric - likely text
                            text_count += 1
                
                score = text_count / len(sample) if len(sample) > 0 else 0
                
                # Prefer first column if scores are similar
                if score > best_score or (score == best_score and best_col is None):
                    best_score = score
                    best_col = col
            except:
                continue
        
        # If we found a good candidate (mostly text), return it
        # Otherwise, just return the first available column
        if best_score > 0.5:
            return best_col
        elif available_cols:
            # Fallback: use first column
            return available_cols[0]
        
        return None
    
    def _detect_expiry_column(self, df: pd.DataFrame, existing_map: Dict[str, str]) -> str:
        """Detect which column is likely the expiry date by analyzing data"""
        # Get columns not already mapped
        available_cols = [col for col in df.columns if col not in existing_map]
        
        if not available_cols:
            return None
        
        # Analyze each column to find the one with date-like data
        best_col = None
        best_score = -1
        
        for col in available_cols:
            try:
                # Sample first 10 non-null values
                sample = df[col].dropna().head(10)
                if len(sample) == 0:
                    continue
                
                # Count how many look like dates
                date_count = 0
                for val in sample:
                    val_str = str(val).strip()
                    if val_str:
                        # Try to parse as date
                        try:
                            pd.to_datetime(val_str, errors='raise')
                            date_count += 1
                        except (ValueError, TypeError):
                            # Not a date
                            pass
                
                score = date_count / len(sample) if len(sample) > 0 else 0
                
                if score > best_score:
                    best_score = score
                    best_col = col
            except:
                continue
        
        # If we found a good candidate (mostly dates), return it
        if best_score > 0.3:
            return best_col
        
        return None
    
    def _detect_price_column(self, df: pd.DataFrame, existing_map: Dict[str, str]) -> str:
        """Detect which column is likely the price by analyzing data"""
        # Get columns not already mapped
        available_cols = [col for col in df.columns if col not in existing_map]
        
        if not available_cols:
            return None
        
        # Analyze each column to find the one with most numeric data
        best_col = None
        best_score = -1
        
        for col in available_cols:
            try:
                # Sample first 10 non-null values
                sample = df[col].dropna().head(10)
                if len(sample) == 0:
                    continue
                
                # Count how many are numeric
                numeric_count = 0
                for val in sample:
                    val_str = str(val).strip()
                    if val_str:
                        # Try to convert to number
                        try:
                            num_val = float(val_str)
                            # If it's a positive number, it's likely a price
                            if num_val > 0:
                                numeric_count += 1
                        except (ValueError, TypeError):
                            # Not numeric
                            pass
                
                score = numeric_count / len(sample) if len(sample) > 0 else 0
                
                if score > best_score:
                    best_score = score
                    best_col = col
            except:
                continue
        
        # If we found a good candidate (mostly numeric), return it
        if best_score > 0.3:  # Lower threshold for price detection
            return best_col
        elif len(available_cols) > 1:
            # Fallback: use second column (assuming first is name)
            return available_cols[1] if len(available_cols) > 1 else available_cols[0]
        elif available_cols:
            return available_cols[0]
        
        return None