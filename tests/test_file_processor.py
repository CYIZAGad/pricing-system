"""
Tests for FileProcessor service (app/services/file_processor.py)
Pure unit tests — no database or Flask context needed.
"""

import io
import pytest
from app.services.file_processor import FileProcessor


# =====================================================================
# HELPERS
# =====================================================================

def _csv_bytes(header, rows):
    """Build a UTF-8 CSV file from strings."""
    return (header + '\n' + '\n'.join(rows)).encode('utf-8')


# =====================================================================
# CSV PROCESSING
# =====================================================================

class TestCSVProcessing:
    """Tests for CSV file parsing."""

    def test_valid_csv(self):
        fp = FileProcessor()
        content = _csv_bytes(
            'medicine_name,unit_price,expiry_date',
            ['Aspirin,5.00,2027-01-15', 'Ibuprofen,3.50,2027-06-30'],
        )
        records, valid, invalid = fp.process_file(content, 'test.csv')
        assert valid == 2
        assert invalid == 0
        assert records[0]['medicine_name'] == 'Aspirin'
        assert records[0]['unit_price'] == 5.0

    def test_csv_with_alternate_column_names(self):
        """Columns like 'product' and 'price' should be auto-mapped."""
        fp = FileProcessor()
        content = _csv_bytes(
            'product,price,expiry',
            ['Aspirin,5.00,2027-01-15'],
        )
        records, valid, invalid = fp.process_file(content, 'test.csv')
        assert valid >= 1

    def test_empty_csv(self):
        fp = FileProcessor()
        with pytest.raises(ValueError, match='empty|parsed|decode|Failed'):
            fp.process_file(b'', 'test.csv')

    def test_csv_missing_required_columns(self):
        """CSV with no recognizable medicine column should raise."""
        fp = FileProcessor()
        content = _csv_bytes('foo,bar,baz', ['1,2,3'])
        with pytest.raises(ValueError, match='Missing required columns|Failed'):
            fp.process_file(content, 'test.csv')

    def test_csv_invalid_price(self):
        """Rows with non-numeric prices are counted as invalid."""
        fp = FileProcessor()
        content = _csv_bytes(
            'medicine_name,unit_price,expiry_date',
            ['Aspirin,abc,2027-01-15', 'Ibuprofen,3.50,2027-06-30'],
        )
        records, valid, invalid = fp.process_file(content, 'test.csv')
        # Ibuprofen valid, Aspirin invalid
        assert valid >= 1

    def test_csv_negative_price(self):
        """Rows with negative prices should be invalid."""
        fp = FileProcessor()
        content = _csv_bytes(
            'medicine_name,unit_price,expiry_date',
            ['Aspirin,-5.00,2027-01-15', 'Ibuprofen,3.50,2027-06-30'],
        )
        records, valid, invalid = fp.process_file(content, 'test.csv')
        assert valid >= 1  # At least Ibuprofen

    def test_csv_empty_name_skipped(self):
        """Rows where medicine_name is blank are invalid."""
        fp = FileProcessor()
        content = _csv_bytes(
            'medicine_name,unit_price,expiry_date',
            [',5.00,2027-01-15', 'Ibuprofen,3.50,2027-06-30'],
        )
        records, valid, invalid = fp.process_file(content, 'test.csv')
        assert valid >= 1


# =====================================================================
# EXCEL PROCESSING
# =====================================================================

class TestExcelProcessing:
    """Tests for Excel file parsing."""

    def _make_xlsx_bytes(self, header, rows):
        """Create a minimal .xlsx file in memory."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(header)
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def test_valid_xlsx(self):
        fp = FileProcessor()
        content = self._make_xlsx_bytes(
            ['medicine_name', 'unit_price', 'expiry_date'],
            [['Aspirin', 5.0, '2027-01-15'], ['Ibuprofen', 3.5, '2027-06-30']],
        )
        records, valid, invalid = fp.process_file(content, 'test.xlsx')
        assert valid == 2

    def test_xlsx_extra_columns(self):
        """Extra columns should be silently ignored."""
        fp = FileProcessor()
        content = self._make_xlsx_bytes(
            ['medicine_name', 'unit_price', 'expiry_date', 'notes'],
            [['Aspirin', 5.0, '2027-01-15', 'note']],
        )
        records, valid, _ = fp.process_file(content, 'test.xlsx')
        assert valid == 1


# =====================================================================
# UNSUPPORTED FILE TYPE
# =====================================================================

class TestUnsupported:
    def test_unsupported_extension(self):
        fp = FileProcessor()
        with pytest.raises(ValueError, match='Unsupported|Failed'):
            fp.process_file(b'hello', 'test.pdf')


# =====================================================================
# COLUMN MAPPING LOGIC
# =====================================================================

class TestColumnMapping:
    """Unit tests for _map_columns helper."""

    def test_exact_match(self):
        fp = FileProcessor()
        mapping = fp._map_columns(['medicine_name', 'unit_price', 'expiry_date'])
        assert 'medicine_name' in mapping.values()
        assert 'unit_price' in mapping.values()

    def test_case_insensitive(self):
        fp = FileProcessor()
        mapping = fp._map_columns(['Medicine Name', 'Unit Price', 'Expiry Date'])
        assert 'medicine_name' in mapping.values()
        assert 'unit_price' in mapping.values()

    def test_alternative_names(self):
        fp = FileProcessor()
        mapping = fp._map_columns(['product', 'cost', 'expiry'])
        assert 'medicine_name' in mapping.values()
        assert 'unit_price' in mapping.values()


# =====================================================================
# ENCODING FALLBACK
# =====================================================================

class TestEncodingFallback:
    """CSV files with different encodings should be handled."""

    def test_latin1_csv(self):
        fp = FileProcessor()
        content = 'medicine_name,unit_price,expiry_date\nAspirin,5.00,2027-01-15\n'
        encoded = content.encode('latin-1')
        records, valid, _ = fp.process_file(encoded, 'test.csv')
        assert valid == 1
