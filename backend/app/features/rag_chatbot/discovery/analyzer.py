# backend/app/features/rag_chatbot/discovery/analyzer.py
"""
Document Analysis Engine for RAG System

This module provides deep analysis capabilities for Excel and PDF documents.
It's designed specifically for your textile company's business documents,
with focus on extracting structured data and business patterns.

Key Features:
1. Excel Structure Analysis - Column types, data patterns, business context
2. PDF Content Classification - Text extraction, pattern recognition, LC detection
3. Business Pattern Recognition - Transaction logs, employee data, inventory
4. Data Quality Assessment - Completeness, consistency, reliability scoring
5. Relationship Detection - Cross-sheet links, data dependencies

Usage:
    excel_analyzer = ExcelStructureAnalyzer()
    excel_result = await excel_analyzer.analyze_excel_file(file_content, filename)
    
    pdf_classifier = PDFClassifier()
    pdf_result = await pdf_classifier.analyze_pdf_document(file_content, filename)
"""

import asyncio
import io
import logging
import re
import statistics
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union, Tuple
from collections import Counter, defaultdict

import pandas as pd
import numpy as np
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import PyPDF2
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams

from ..models.schemas import (
    ExcelAnalysisResult,
    PDFAnalysisResult,
    ColumnInfo,
    DocumentCategory,
    FileType
)


# =============================================================================
# EXCEL STRUCTURE ANALYZER
# =============================================================================

class ExcelStructureAnalyzer:
    """
    Advanced Excel file structure analyzer for business documents.
    
    This class performs comprehensive analysis of Excel files to understand:
    - Sheet structure and relationships
    - Column data types and business meanings
    - Data quality and consistency
    - Business patterns (transactions, payroll, inventory)
    - Cross-sheet relationships and dependencies
    
    Designed specifically for your textile company's finance, HR, and
    operational Excel files.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Business type patterns for your textile company
        self.business_patterns = {
            'currency': [
                r'amount', r'price', r'cost', r'value', r'total', r'sum',
                r'bdt', r'usd', r'eur', r'taka', r'dollar', r'balance'
            ],
            'date': [
                r'date', r'time', r'created', r'modified', r'updated',
                r'start', r'end', r'due', r'expiry', r'delivery'
            ],
            'id': [
                r'id', r'code', r'number', r'ref', r'reference',
                r'employee_id', r'product_id', r'vendor_id', r'lc_id'
            ],
            'name': [
                r'name', r'title', r'description', r'label',
                r'employee', r'product', r'vendor', r'customer'
            ],
            'quantity': [
                r'qty', r'quantity', r'count', r'units', r'pieces',
                r'meters', r'yards', r'kg', r'tons'
            ],
            'percentage': [
                r'percent', r'rate', r'ratio', r'%', r'commission'
            ]
        }
        
        # Textile industry specific patterns
        self.textile_patterns = {
            'transaction_log': {
                'required_columns': ['date', 'amount', 'description'],
                'optional_columns': ['vendor', 'category', 'reference'],
                'indicators': ['payment', 'receipt', 'transaction']
            },
            'employee_roster': {
                'required_columns': ['name', 'id', 'department'],
                'optional_columns': ['salary', 'designation', 'join_date'],
                'indicators': ['employee', 'staff', 'worker']
            },
            'inventory_list': {
                'required_columns': ['product', 'quantity', 'unit_cost'],
                'optional_columns': ['supplier', 'category', 'location'],
                'indicators': ['stock', 'inventory', 'product', 'item']
            },
            'lc_register': {
                'required_columns': ['lc_number', 'date', 'amount'],
                'optional_columns': ['beneficiary', 'bank', 'expiry'],
                'indicators': ['lc', 'letter', 'credit', 'export']
            },
            'financial_summary': {
                'required_columns': ['category', 'amount'],
                'optional_columns': ['period', 'budget', 'variance'],
                'indicators': ['summary', 'total', 'balance']
            }
        }
        
        # Data type detection patterns
        self.data_type_patterns = {
            'integer': r'^\d+$',
            'float': r'^\d*\.?\d+$',
            'currency': r'^\$?[\d,]+\.?\d*$|^[\d,]+\.?\d*\s?(BDT|USD|EUR|Taka)$',
            'date': r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}[/-]\d{1,2}[/-]\d{1,2}$',
            'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'phone': r'^(\+88)?[0-9\-\s\(\)]{10,15}$',
            'percentage': r'^\d+\.?\d*%$'
        }
    
    async def analyze_excel_file(self, file_content: bytes, filename: str) -> ExcelAnalysisResult:
        """
        Perform comprehensive analysis of an Excel file.
        
        Args:
            file_content: Raw Excel file bytes
            filename: Original filename for context
        
        Returns:
            Complete Excel analysis results
        """
        try:
            self.logger.info(f"Starting Excel analysis for: {filename}")
            
            # Load workbook with multiple methods for robustness
            workbook_data = await self._load_excel_workbook(file_content)
            
            if not workbook_data:
                raise ValueError("Failed to load Excel workbook")
            
            # Analyze workbook structure
            structure_analysis = await self._analyze_workbook_structure(workbook_data)
            
            # Analyze primary sheet in detail
            primary_sheet_analysis = await self._analyze_primary_sheet(
                workbook_data, structure_analysis['primary_sheet']
            )
            
            # Detect business patterns
            pattern_analysis = await self._detect_business_patterns(
                primary_sheet_analysis, filename
            )
            
            # Calculate data quality metrics
            quality_metrics = await self._calculate_data_quality(primary_sheet_analysis)
            
            # Compile complete results
            analysis_result = ExcelAnalysisResult(
                sheet_names=structure_analysis['sheet_names'],
                analyzed_sheet=structure_analysis['primary_sheet'],
                total_rows=primary_sheet_analysis['total_rows'],
                total_columns=primary_sheet_analysis['total_columns'],
                columns=primary_sheet_analysis['columns'],
                has_dates=primary_sheet_analysis['has_dates'],
                has_amounts=primary_sheet_analysis['has_amounts'],
                has_ids=primary_sheet_analysis['has_ids'],
                completeness_score=quality_metrics['completeness_score'],
                consistency_score=quality_metrics['consistency_score'],
                detected_patterns=pattern_analysis['detected_patterns']
            )
            
            self.logger.info(f"Excel analysis completed for: {filename}")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"Excel analysis failed for {filename}: {str(e)}")
            # Return minimal analysis result on failure
            return ExcelAnalysisResult(
                sheet_names=[],
                analyzed_sheet="unknown",
                total_rows=0,
                total_columns=0,
                columns=[],
                has_dates=False,
                has_amounts=False,
                has_ids=False,
                completeness_score=0.0,
                consistency_score=0.0,
                detected_patterns=[]
            )
    
    async def _load_excel_workbook(self, file_content: bytes) -> Optional[Dict]:
        """
        Load Excel workbook using multiple methods for maximum compatibility.
        
        Args:
            file_content: Raw Excel file bytes
        
        Returns:
            Workbook data dictionary or None if failed
        """
        file_stream = io.BytesIO(file_content)
        
        # Method 1: Try openpyxl for .xlsx files
        try:
            workbook = load_workbook(file_stream, read_only=True, data_only=True)
            return {
                'type': 'openpyxl',
                'workbook': workbook,
                'sheet_names': workbook.sheetnames
            }
        except Exception as e:
            self.logger.warning(f"openpyxl failed: {str(e)}")
        
        # Method 2: Try pandas for broader compatibility
        try:
            file_stream.seek(0)
            excel_file = pd.ExcelFile(file_stream)
            return {
                'type': 'pandas',
                'excel_file': excel_file,
                'sheet_names': excel_file.sheet_names
            }
        except Exception as e:
            self.logger.warning(f"pandas failed: {str(e)}")
        
        return None
    
    async def _analyze_workbook_structure(self, workbook_data: Dict) -> Dict:
        """
        Analyze the overall structure of the Excel workbook.
        
        Args:
            workbook_data: Loaded workbook data
        
        Returns:
            Structure analysis results
        """
        sheet_names = workbook_data['sheet_names']
        
        # Determine primary sheet (usually first non-empty sheet)
        primary_sheet = sheet_names[0] if sheet_names else "Sheet1"
        
        # Look for sheets with business-relevant names
        business_sheets = []
        for sheet_name in sheet_names:
            sheet_lower = sheet_name.lower()
            if any(keyword in sheet_lower for keyword in [
                'transaction', 'payment', 'finance', 'employee', 
                'inventory', 'lc', 'summary', 'data'
            ]):
                business_sheets.append(sheet_name)
        
        if business_sheets:
            primary_sheet = business_sheets[0]
        
        return {
            'sheet_names': sheet_names,
            'primary_sheet': primary_sheet,
            'total_sheets': len(sheet_names),
            'business_sheets': business_sheets
        }
    
    async def _analyze_primary_sheet(self, workbook_data: Dict, sheet_name: str) -> Dict:
        """
        Perform detailed analysis of the primary sheet.
        
        Args:
            workbook_data: Loaded workbook data
            sheet_name: Name of sheet to analyze
        
        Returns:
            Detailed sheet analysis
        """
        if workbook_data['type'] == 'openpyxl':
            return await self._analyze_openpyxl_sheet(workbook_data['workbook'], sheet_name)
        elif workbook_data['type'] == 'pandas':
            return await self._analyze_pandas_sheet(workbook_data['excel_file'], sheet_name)
        else:
            raise ValueError("Unknown workbook type")
    
    async def _analyze_openpyxl_sheet(self, workbook, sheet_name: str) -> Dict:
        """Analyze sheet using openpyxl."""
        try:
            worksheet = workbook[sheet_name]
            
            # Get sheet dimensions
            max_row = worksheet.max_row
            max_col = worksheet.max_column
            
            # Extract headers (assuming first row contains headers)
            headers = []
            for col in range(1, max_col + 1):
                cell_value = worksheet.cell(row=1, column=col).value
                headers.append(str(cell_value) if cell_value else f"Column_{col}")
            
            # Analyze each column
            columns = []
            has_dates = False
            has_amounts = False
            has_ids = False
            
            for col_idx, header in enumerate(headers, 1):
                # Sample column data (first 100 rows)
                sample_data = []
                for row in range(2, min(max_row + 1, 102)):
                    cell_value = worksheet.cell(row=row, column=col_idx).value
                    if cell_value is not None:
                        sample_data.append(str(cell_value))
                
                # Analyze column
                column_analysis = await self._analyze_column_data(header, sample_data)
                columns.append(column_analysis)
                
                # Update sheet-level flags
                if column_analysis.business_type == 'date':
                    has_dates = True
                elif column_analysis.business_type == 'currency':
                    has_amounts = True
                elif column_analysis.business_type == 'id':
                    has_ids = True
            
            return {
                'total_rows': max_row - 1,  # Exclude header row
                'total_columns': max_col,
                'columns': columns,
                'has_dates': has_dates,
                'has_amounts': has_amounts,
                'has_ids': has_ids
            }
            
        except Exception as e:
            self.logger.error(f"openpyxl sheet analysis failed: {str(e)}")
            return self._create_empty_analysis()
    
    async def _analyze_pandas_sheet(self, excel_file, sheet_name: str) -> Dict:
        """Analyze sheet using pandas."""
        try:
            # Read the sheet
            df = excel_file.parse(sheet_name, nrows=1000)  # Limit rows for performance
            
            # Clean column names
            df.columns = df.columns.astype(str)
            
            # Analyze each column
            columns = []
            has_dates = False
            has_amounts = False
            has_ids = False
            
            for col_name in df.columns:
                # Get sample data (non-null values)
                sample_data = df[col_name].dropna().head(100).astype(str).tolist()
                
                # Analyze column
                column_analysis = await self._analyze_column_data(col_name, sample_data)
                columns.append(column_analysis)
                
                # Update sheet-level flags
                if column_analysis.business_type == 'date':
                    has_dates = True
                elif column_analysis.business_type == 'currency':
                    has_amounts = True
                elif column_analysis.business_type == 'id':
                    has_ids = True
            
            return {
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'columns': columns,
                'has_dates': has_dates,
                'has_amounts': has_amounts,
                'has_ids': has_ids
            }
            
        except Exception as e:
            self.logger.error(f"pandas sheet analysis failed: {str(e)}")
            return self._create_empty_analysis()
    
    async def _analyze_column_data(self, column_name: str, sample_data: List[str]) -> ColumnInfo:
        """
        Analyze individual column data to determine types and patterns.
        
        Args:
            column_name: Name of the column
            sample_data: Sample values from the column
        
        Returns:
            Complete column analysis
        """
        if not sample_data:
            return ColumnInfo(
                name=column_name,
                data_type="unknown",
                business_type=None,
                sample_values=[],
                null_count=0,
                unique_count=0
            )
        
        # Detect data type
        data_type = await self._detect_data_type(sample_data)
        
        # Detect business type
        business_type = await self._detect_business_type(column_name, sample_data, data_type)
        
        # Calculate statistics
        unique_count = len(set(sample_data))
        sample_values = sample_data[:5]  # First 5 samples
        
        return ColumnInfo(
            name=column_name,
            data_type=data_type,
            business_type=business_type,
            sample_values=sample_values,
            null_count=0,  # Would need full data to calculate
            unique_count=unique_count
        )
    
    async def _detect_data_type(self, sample_data: List[str]) -> str:
        """
        Detect the primary data type of a column.
        
        Args:
            sample_data: Sample values from column
        
        Returns:
            Detected data type
        """
        if not sample_data:
            return "unknown"
        
        # Count matches for each pattern
        type_scores = defaultdict(int)
        
        for value in sample_data[:50]:  # Check first 50 values
            value_clean = str(value).strip()
            
            # Check each pattern
            for data_type, pattern in self.data_type_patterns.items():
                if re.match(pattern, value_clean, re.IGNORECASE):
                    type_scores[data_type] += 1
        
        # Special handling for dates using pandas
        try:
            pd.to_datetime(sample_data[:10], infer_datetime_format=True, errors='raise')
            type_scores['date'] += 10  # Boost date score if pandas recognizes it
        except:
            pass
        
        # Special handling for numbers
        numeric_count = 0
        for value in sample_data[:20]:
            try:
                float(value)
                numeric_count += 1
            except:
                pass
        
        if numeric_count > len(sample_data) * 0.8:
            # Check if integers or floats
            has_decimal = any('.' in str(v) for v in sample_data[:10])
            type_scores['float' if has_decimal else 'integer'] += numeric_count
        
        # Return highest scoring type
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        else:
            return "string"
    
    async def _detect_business_type(self, column_name: str, sample_data: List[str], 
                                  data_type: str) -> Optional[str]:
        """
        Detect the business meaning of a column.
        
        Args:
            column_name: Name of the column
            sample_data: Sample values
            data_type: Detected data type
        
        Returns:
            Business type or None
        """
        column_lower = column_name.lower()
        
        # Check business patterns
        for business_type, patterns in self.business_patterns.items():
            for pattern in patterns:
                if re.search(pattern, column_lower):
                    return business_type
        
        # Data type based inference
        if data_type in ['date']:
            return 'date'
        elif data_type in ['currency', 'float'] and any(
            term in column_lower for term in ['amount', 'price', 'cost', 'total', 'balance']
        ):
            return 'currency'
        elif data_type in ['integer', 'string'] and any(
            term in column_lower for term in ['id', 'code', 'number', 'ref']
        ):
            return 'id'
        elif data_type == 'percentage':
            return 'percentage'
        
        # Sample value analysis for additional context
        if sample_data:
            sample_text = ' '.join(sample_data[:5]).lower()
            
            # Look for business indicators in sample values
            if any(indicator in sample_text for indicator in ['vendor', 'supplier', 'customer']):
                return 'vendor_name'
            elif any(indicator in sample_text for indicator in ['employee', 'staff', 'worker']):
                return 'employee_name'
            elif any(indicator in sample_text for indicator in ['product', 'item', 'material']):
                return 'product_name'
        
        return None
    
    async def _detect_business_patterns(self, sheet_analysis: Dict, filename: str) -> Dict:
        """
        Detect high-level business patterns in the sheet.
        
        Args:
            sheet_analysis: Detailed sheet analysis
            filename: Original filename for context
        
        Returns:
            Pattern detection results
        """
        detected_patterns = []
        columns = sheet_analysis['columns']
        
        # Extract column names and business types
        column_names = [col.name.lower() for col in columns]
        business_types = [col.business_type for col in columns if col.business_type]
        
        # Check each textile business pattern
        for pattern_name, pattern_config in self.textile_patterns.items():
            score = 0
            
            # Required columns check
            required_matches = 0
            for required_col in pattern_config['required_columns']:
                if any(required_col in col_name for col_name in column_names):
                    required_matches += 1
            
            required_score = required_matches / len(pattern_config['required_columns'])
            
            # Optional columns bonus
            optional_matches = 0
            for optional_col in pattern_config['optional_columns']:
                if any(optional_col in col_name for col_name in column_names):
                    optional_matches += 1
            
            optional_score = optional_matches / len(pattern_config['optional_columns']) if pattern_config['optional_columns'] else 0
            
            # Filename indicators
            filename_score = 0
            filename_lower = filename.lower()
            for indicator in pattern_config['indicators']:
                if indicator in filename_lower:
                    filename_score += 0.2
            
            # Business type indicators
            business_type_score = 0
            if 'currency' in business_types and pattern_name in ['transaction_log', 'financial_summary']:
                business_type_score += 0.3
            if 'date' in business_types:
                business_type_score += 0.2
            if 'id' in business_types:
                business_type_score += 0.1
            
            # Calculate total score
            total_score = (required_score * 0.5) + (optional_score * 0.2) + filename_score + business_type_score
            
            # If score is high enough, consider pattern detected
            if total_score > 0.4:  # Threshold for pattern detection
                detected_patterns.append(pattern_name)
                self.logger.info(f"Detected business pattern: {pattern_name} (score: {total_score:.2f})")
        
        return {
            'detected_patterns': detected_patterns,
            'pattern_confidence': len(detected_patterns) / len(self.textile_patterns)
        }
    
    async def _calculate_data_quality(self, sheet_analysis: Dict) -> Dict:
        """
        Calculate data quality metrics for the sheet.
        
        Args:
            sheet_analysis: Detailed sheet analysis
        
        Returns:
            Data quality metrics
        """
        columns = sheet_analysis['columns']
        
        if not columns:
            return {
                'completeness_score': 0.0,
                'consistency_score': 0.0
            }
        
        # Completeness: Average of non-null ratios across columns
        # Since we don't have null counts in our simplified analysis, estimate based on sample size
        completeness_scores = []
        for col in columns:
            if col.sample_values:
                # Estimate completeness based on whether we got sample values
                estimated_completeness = min(1.0, len(col.sample_values) / 5)  # Our sample size is 5
                completeness_scores.append(estimated_completeness)
        
        completeness_score = statistics.mean(completeness_scores) if completeness_scores else 0.0
        
        # Consistency: Based on successful data type detection
        consistency_scores = []
        for col in columns:
            if col.data_type != "unknown":
                # High consistency if we could determine data type
                consistency_scores.append(0.9)
            else:
                consistency_scores.append(0.3)
        
        consistency_score = statistics.mean(consistency_scores) if consistency_scores else 0.0
        
        return {
            'completeness_score': completeness_score,
            'consistency_score': consistency_score
        }
    
    def _create_empty_analysis(self) -> Dict:
        """Create empty analysis result for error cases."""
        return {
            'total_rows': 0,
            'total_columns': 0,
            'columns': [],
            'has_dates': False,
            'has_amounts': False,
            'has_ids': False
        }


# =============================================================================
# PDF CLASSIFIER AND ANALYZER
# =============================================================================

class PDFClassifier:
    """
    Advanced PDF document classifier for business documents.
    
    This class provides comprehensive PDF analysis including:
    - Text extraction with multiple methods
    - Document type classification
    - Letter of Credit specific detection
    - Content quality assessment
    - Business pattern recognition
    
    Optimized for your textile company's document types:
    LC documents, invoices, financial reports, contracts.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # LC (Letter of Credit) specific keywords and patterns
        self.lc_keywords = {
            'primary': [
                'letter of credit', 'documentary credit', 'l/c', 'lc number',
                'issuing bank', 'beneficiary', 'applicant', 'advising bank'
            ],
            'secondary': [
                'credit number', 'credit amount', 'expiry date', 'latest shipment',
                'documents required', 'presentation period', 'confirmation',
                'amendment', 'discrepancy', 'negotiation'
            ],
            'shipping': [
                'bill of lading', 'commercial invoice', 'packing list',
                'certificate of origin', 'inspection certificate'
            ]
        }
        
        # Invoice detection patterns
        self.invoice_keywords = {
            'primary': [
                'invoice', 'bill', 'receipt', 'statement',
                'invoice number', 'bill number'
            ],
            'financial': [
                'total amount', 'subtotal', 'tax', 'discount',
                'due date', 'payment terms', 'net amount'
            ],
            'parties': [
                'bill to', 'ship to', 'vendor', 'supplier',
                'customer', 'buyer', 'seller'
            ]
        }
        
        # Financial report patterns
        self.report_keywords = {
            'financial': [
                'balance sheet', 'income statement', 'cash flow',
                'profit and loss', 'financial statement', 'trial balance'
            ],
            'periods': [
                'quarterly', 'monthly', 'annual', 'year ended',
                'period ending', 'as of', 'for the period'
            ],
            'metrics': [
                'revenue', 'expenses', 'assets', 'liabilities',
                'equity', 'net income', 'gross profit'
            ]
        }
        
        # Text quality indicators
        self.quality_indicators = {
            'good': [
                r'\b\w+\b',  # Regular words
                r'\d+',      # Numbers
                r'[.!?]'     # Proper punctuation
            ],
            'poor': [
                r'[^\w\s.,!?-]',  # Unusual characters
                r'\b\w{15,}\b',   # Extremely long words (likely OCR errors)
                r'\d{10,}'        # Very long number sequences
            ]
        }
        
        # Document structure patterns
        self.structure_patterns = {
            'table_indicators': [
                r'\|\s*\w+\s*\|',  # Table borders
                r'\w+\s+\w+\s+\w+\s+\w+',  # Multiple columns
                r'total\s+amount',  # Table footers
                r'\d+\.\d{2}\s+\d+\.\d{2}'  # Currency columns
            ],
            'form_indicators': [
                r'[_]{5,}',  # Underlines for filling
                r'\[\s*\]',  # Checkboxes
                r'signature:?\s*[_]{3,}',  # Signature lines
                r'date:?\s*[_]{3,}'  # Date fields
            ]
        }
    
    async def analyze_pdf_document(self, file_content: bytes, filename: str) -> PDFAnalysisResult:
        """
        Perform comprehensive analysis of a PDF document.
        
        Args:
            file_content: Raw PDF file bytes
            filename: Original filename for context
        
        Returns:
            Complete PDF analysis results
        """
        try:
            self.logger.info(f"Starting PDF analysis for: {filename}")
            
            # Extract text using multiple methods
            text_extraction = await self._extract_pdf_text(file_content)
            
            # Analyze document structure
            structure_analysis = await self._analyze_pdf_structure(text_extraction['text'])
            
            # Classify document type
            classification = await self._classify_document_type(
                text_extraction['text'], filename
            )
            
            # Analyze text quality
            quality_metrics = await self._analyze_text_quality(text_extraction['text'])
            
            # Detect LC specific patterns
            lc_analysis = await self._analyze_lc_document(
                text_extraction['text'], filename
            )
            
            # Compile results
            analysis_result = PDFAnalysisResult(
                page_count=text_extraction['page_count'],
                text_extractable=text_extraction['direct_extraction'],
                ocr_required=text_extraction['ocr_required'],
                classification_confidence=classification['confidence'],
                detected_keywords=classification['keywords'],
                has_tables=structure_analysis['has_tables'],
                has_forms=structure_analysis['has_forms'],
                language_detected=text_extraction['language'],
                text_quality_score=quality_metrics['quality_score'],
                character_count=len(text_extraction['text']),
                is_letter_of_credit=lc_analysis['is_lc'],
                lc_confidence=lc_analysis['confidence']
            )
            
            self.logger.info(f"PDF analysis completed for: {filename}")
            return analysis_result
            
        except Exception as e:
            self.logger.error(f"PDF analysis failed for {filename}: {str(e)}")
            # Return minimal analysis on failure
            return PDFAnalysisResult(
                page_count=0,
                text_extractable=False,
                ocr_required=True,
                classification_confidence=0.0,
                detected_keywords=[],
                has_tables=False,
                has_forms=False,
                language_detected="unknown",
                text_quality_score=0.0,
                character_count=0,
                is_letter_of_credit=False,
                lc_confidence=0.0
            )
    
    async def _extract_pdf_text(self, file_content: bytes) -> Dict[str, Any]:
        """
        Extract text from PDF using multiple methods for maximum reliability.
        
        Args:
            file_content: Raw PDF file bytes
        
        Returns:
            Text extraction results with metadata
        """
        file_stream = io.BytesIO(file_content)
        extracted_text = ""
        page_count = 0
        direct_extraction = False
        ocr_required = False
        language = "english"
        
        # Method 1: Try PyPDF2 for simple text extraction
        try:
            file_stream.seek(0)
            pdf_reader = PyPDF2.PdfReader(file_stream)
            page_count = len(pdf_reader.pages)
            
            text_parts = []
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text.strip():
                    text_parts.append(page_text)
            
            if text_parts:
                extracted_text = '\n'.join(text_parts)
                direct_extraction = True
                self.logger.info("PyPDF2 extraction successful")
        
        except Exception as e:
            self.logger.warning(f"PyPDF2 extraction failed: {str(e)}")
        
        # Method 2: Try pdfplumber for better structure preservation
        if not extracted_text or len(extracted_text) < 100:
            try:
                file_stream.seek(0)
                with pdfplumber.open(file_stream) as pdf:
                    page_count = len(pdf.pages)
                    text_parts = []
                    
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                    
                    if text_parts:
                        extracted_text = '\n'.join(text_parts)
                        direct_extraction = True
                        self.logger.info("pdfplumber extraction successful")
            
            except Exception as e:
                self.logger.warning(f"pdfplumber extraction failed: {str(e)}")
        
        # Method 3: Try pdfminer for complex layouts
        if not extracted_text or len(extracted_text) < 50:
            try:
                file_stream.seek(0)
                output_string = io.StringIO()
                resource_manager = PDFResourceManager()
                codec = 'utf-8'
                laparams = LAParams()
                
                device = TextConverter(resource_manager, output_string, codec=codec, laparams=laparams)
                interpreter = PDFPageInterpreter(resource_manager, device)
                
                pages = PDFPage.get_pages(file_stream, check_extractable=True)
                page_count = 0
                
                for page in pages:
                    interpreter.process_page(page)
                    page_count += 1
                
                device.close()
                extracted_text = output_string.getvalue()
                output_string.close()
                
                if extracted_text.strip():
                    direct_extraction = True
                    self.logger.info("pdfminer extraction successful")
            
            except Exception as e:
                self.logger.warning(f"pdfminer extraction failed: {str(e)}")
        
        # If all text extraction methods failed, mark for OCR
        if not extracted_text or len(extracted_text.strip()) < 20:
            ocr_required = True
            extracted_text = ""
            self.logger.warning("All text extraction methods failed - OCR would be required")
        
        # Basic language detection (simplified)
        if extracted_text:
            # Look for Bengali/Bangla characters
            bengali_chars = re.findall(r'[\u0980-\u09FF]', extracted_text)
            if bengali_chars and len(bengali_chars) > 10:
                language = "bengali"
            # Look for Arabic/Urdu characters
            elif re.findall(r'[\u0600-\u06FF]', extracted_text):
                language = "arabic"
            else:
                language = "english"
        
        return {
            'text': extracted_text,
            'page_count': page_count,
            'direct_extraction': direct_extraction,
            'ocr_required': ocr_required,
            'language': language,
            'character_count': len(extracted_text)
        }
    
    async def _analyze_pdf_structure(self, text: str) -> Dict[str, Any]:
        """
        Analyze the structural elements of the PDF document.
        
        Args:
            text: Extracted text content
        
        Returns:
            Structure analysis results
        """
        has_tables = False
        has_forms = False
        
        if not text:
            return {
                'has_tables': has_tables,
                'has_forms': has_forms
            }
        
        text_lower = text.lower()
        
        # Detect table-like structures
        for pattern in self.structure_patterns['table_indicators']:
            if re.search(pattern, text, re.IGNORECASE):
                has_tables = True
                break
        
        # Additional table detection heuristics
        if not has_tables:
            lines = text.split('\n')
            aligned_data_count = 0
            
            for line in lines:
                # Look for lines with multiple numeric values (potential table rows)
                numbers = re.findall(r'\d+\.?\d*', line)
                if len(numbers) >= 3:
                    aligned_data_count += 1
            
            # If many lines have multiple numbers, likely a table
            if aligned_data_count > 5:
                has_tables = True
        
        # Detect form-like structures
        for pattern in self.structure_patterns['form_indicators']:
            if re.search(pattern, text, re.IGNORECASE):
                has_forms = True
                break
        
        return {
            'has_tables': has_tables,
            'has_forms': has_forms
        }
    
    async def _classify_document_type(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Classify the document type based on content and filename.
        
        Args:
            text: Extracted text content
            filename: Original filename
        
        Returns:
            Classification results with confidence and keywords
        """
        if not text:
            return {
                'confidence': 0.0,
                'keywords': [],
                'primary_type': 'unknown'
            }
        
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        # Score each document type
        type_scores = {
            'lc': 0.0,
            'invoice': 0.0,
            'report': 0.0,
            'contract': 0.0,
            'unknown': 0.0
        }
        
        detected_keywords = []
        
        # LC Document scoring
        lc_score = 0.0
        for keyword in self.lc_keywords['primary']:
            if keyword in text_lower:
                lc_score += 0.3
                detected_keywords.append(keyword)
        
        for keyword in self.lc_keywords['secondary']:
            if keyword in text_lower:
                lc_score += 0.1
                detected_keywords.append(keyword)
        
        # Filename boost for LC
        if any(term in filename_lower for term in ['lc', 'letter', 'credit']):
            lc_score += 0.2
        
        type_scores['lc'] = min(1.0, lc_score)
        
        # Invoice scoring
        invoice_score = 0.0
        for keyword in self.invoice_keywords['primary']:
            if keyword in text_lower:
                invoice_score += 0.3
                detected_keywords.append(keyword)
        
        for keyword in self.invoice_keywords['financial']:
            if keyword in text_lower:
                invoice_score += 0.1
                detected_keywords.append(keyword)
        
        # Filename boost for invoice
        if any(term in filename_lower for term in ['invoice', 'bill', 'receipt']):
            invoice_score += 0.2
        
        type_scores['invoice'] = min(1.0, invoice_score)
        
        # Report scoring
        report_score = 0.0
        for keyword in self.report_keywords['financial']:
            if keyword in text_lower:
                report_score += 0.3
                detected_keywords.append(keyword)
        
        for keyword in self.report_keywords['periods']:
            if keyword in text_lower:
                report_score += 0.1
                detected_keywords.append(keyword)
        
        # Filename boost for reports
        if any(term in filename_lower for term in ['report', 'statement', 'summary']):
            report_score += 0.2
        
        type_scores['report'] = min(1.0, report_score)
        
        # Contract scoring (basic)
        contract_keywords = ['agreement', 'contract', 'terms and conditions', 'party', 'whereas']
        contract_score = 0.0
        for keyword in contract_keywords:
            if keyword in text_lower:
                contract_score += 0.2
                detected_keywords.append(keyword)
        
        type_scores['contract'] = min(1.0, contract_score)
        
        # Determine primary type and confidence
        primary_type = max(type_scores.items(), key=lambda x: x[1])[0]
        confidence = type_scores[primary_type]
        
        # If no strong classification, mark as unknown
        if confidence < 0.3:
            primary_type = 'unknown'
            confidence = 0.0
        
        return {
            'confidence': confidence,
            'keywords': list(set(detected_keywords)),
            'primary_type': primary_type,
            'all_scores': type_scores
        }
    
    async def _analyze_text_quality(self, text: str) -> Dict[str, Any]:
        """
        Analyze the quality of extracted text.
        
        Args:
            text: Extracted text content
        
        Returns:
            Text quality metrics
        """
        if not text:
            return {
                'quality_score': 0.0,
                'readability': 'poor',
                'issues': ['no_text_extracted']
            }
        
        quality_score = 1.0
        issues = []
        
        # Check text length
        if len(text) < 50:
            quality_score -= 0.3
            issues.append('very_short_text')
        
        # Check for good indicators
        good_patterns_found = 0
        for pattern in self.quality_indicators['good']:
            matches = len(re.findall(pattern, text))
            if matches > 5:
                good_patterns_found += 1
        
        if good_patterns_found < 2:
            quality_score -= 0.2
            issues.append('poor_text_structure')
        
        # Check for poor indicators (OCR errors)
        for pattern in self.quality_indicators['poor']:
            matches = len(re.findall(pattern, text))
            if matches > len(text) * 0.05:  # More than 5% of content
                quality_score -= 0.3
                issues.append('ocr_artifacts')
                break
        
        # Check character distribution
        alpha_ratio = len(re.findall(r'[a-zA-Z]', text)) / len(text) if text else 0
        if alpha_ratio < 0.5:
            quality_score -= 0.2
            issues.append('low_alphabetic_content')
        
        # Check for proper sentence structure
        sentences = re.split(r'[.!?]+', text)
        valid_sentences = [s for s in sentences if len(s.strip()) > 10 and ' ' in s.strip()]
        
        if len(valid_sentences) < len(sentences) * 0.5:
            quality_score -= 0.2
            issues.append('fragmented_sentences')
        
        # Ensure quality score doesn't go below 0
        quality_score = max(0.0, quality_score)
        
        # Determine readability
        if quality_score >= 0.8:
            readability = 'excellent'
        elif quality_score >= 0.6:
            readability = 'good'
        elif quality_score >= 0.4:
            readability = 'fair'
        else:
            readability = 'poor'
        
        return {
            'quality_score': quality_score,
            'readability': readability,
            'issues': issues
        }
    
    async def _analyze_lc_document(self, text: str, filename: str) -> Dict[str, Any]:
        """
        Specialized analysis for Letter of Credit documents.
        
        Args:
            text: Extracted text content
            filename: Original filename
        
        Returns:
            LC-specific analysis results
        """
        if not text:
            return {
                'is_lc': False,
                'confidence': 0.0,
                'lc_elements': []
            }
        
        text_lower = text.lower()
        filename_lower = filename.lower()
        
        lc_confidence = 0.0
        detected_elements = []
        
        # Primary LC indicators (high weight)
        primary_matches = 0
        primary_terms = ['letter of credit', 'documentary credit', 'issuing bank', 'beneficiary', 'applicant']
        for keyword in primary_terms:
            if keyword in text_lower:
                primary_matches += 1
                detected_elements.append(keyword)
        
        # Scale primary matches more generously
        if primary_matches >= 3:
            lc_confidence += 0.7
        elif primary_matches >= 2:
            lc_confidence += 0.5
        elif primary_matches >= 1:
            lc_confidence += 0.3
        
        # Secondary LC indicators
        secondary_matches = 0
        for keyword in self.lc_keywords['secondary']:
            if keyword in text_lower:
                secondary_matches += 1
                detected_elements.append(keyword)
        
        lc_confidence += min(0.3, secondary_matches * 0.05)
        
        # Shipping document indicators
        shipping_matches = 0
        for keyword in self.lc_keywords['shipping']:
            if keyword in text_lower:
                shipping_matches += 1
                detected_elements.append(keyword)
        
        lc_confidence += min(0.2, shipping_matches * 0.05)
        
        # Filename indicators (improved scoring)
        filename_indicators = ['lc', 'letter of credit', 'documentary credit', 'export', 'amendment']
        filename_score = 0.0
        for indicator in filename_indicators:
            if indicator in filename_lower:
                if indicator == 'lc':
                    filename_score += 0.4
                elif indicator == 'letter of credit':
                    filename_score += 0.5
                elif indicator == 'amendment':
                    filename_score += 0.3
                else:
                    filename_score += 0.2
        
        lc_confidence += min(0.6, filename_score)  # Cap filename contribution
        
        # Look for LC number patterns
        lc_number_patterns = [
            r'lc\s*(?:no|number)?\s*:?\s*[a-zA-Z0-9-/]+',
            r'credit\s*(?:no|number)\s*:?\s*[a-zA-Z0-9-/]+',
            r'documentary\s*credit\s*(?:no|number)\s*:?\s*[a-zA-Z0-9-/]+'
        ]
        
        for pattern in lc_number_patterns:
            if re.search(pattern, text_lower):
                lc_confidence += 0.1
                detected_elements.append('lc_number_found')
                break
        
        # Look for banking terminology
        banking_terms = ['issuing bank', 'advising bank', 'confirming bank', 'beneficiary', 'applicant']
        banking_matches = sum(1 for term in banking_terms if term in text_lower)
        
        if banking_matches >= 3:
            lc_confidence += 0.2
            detected_elements.extend(['banking_terminology'])
        
        # Look for amount and currency patterns
        currency_patterns = [
            r'(?:usd|eur|gbp|bdt)\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*(?:usd|eur|gbp|bdt|dollars?|euros?|pounds?|taka)'
        ]
        
        for pattern in currency_patterns:
            if re.search(pattern, text_lower):
                lc_confidence += 0.05
                detected_elements.append('currency_found')
                break
        
        # Cap confidence at 1.0
        lc_confidence = min(1.0, lc_confidence)
        
        # Consider it an LC document if confidence > 0.5 (lowered threshold)
        is_lc = lc_confidence > 0.5
        
        return {
            'is_lc': is_lc,
            'confidence': lc_confidence,
            'lc_elements': list(set(detected_elements))
        }


# =============================================================================
# UTILITY FUNCTIONS AND HELPERS
# =============================================================================

def create_analyzer_from_config(config: Dict[str, Any]) -> Tuple[ExcelStructureAnalyzer, PDFClassifier]:
    """
    Factory function to create analyzers from configuration.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Tuple of (ExcelStructureAnalyzer, PDFClassifier)
    """
    excel_analyzer = ExcelStructureAnalyzer()
    pdf_classifier = PDFClassifier()
    
    return excel_analyzer, pdf_classifier


async def analyze_document_batch(documents: List[Dict], 
                                excel_analyzer: ExcelStructureAnalyzer,
                                pdf_classifier: PDFClassifier) -> List[Dict]:
    """
    Analyze a batch of documents efficiently.
    
    Args:
        documents: List of document metadata with file content
        excel_analyzer: Excel analyzer instance
        pdf_classifier: PDF classifier instance
    
    Returns:
        List of analysis results
    """
    results = []
    
    for doc in documents:
        try:
            file_type = doc.get('file_type')
            file_content = doc.get('file_content')
            filename = doc.get('filename', 'unknown')
            
            if file_type == FileType.EXCEL:
                result = await excel_analyzer.analyze_excel_file(file_content, filename)
            elif file_type == FileType.PDF:
                result = await pdf_classifier.analyze_pdf_document(file_content, filename)
            else:
                result = None
            
            results.append({
                'document_id': doc.get('id'),
                'filename': filename,
                'file_type': file_type,
                'analysis_result': result,
                'status': 'success' if result else 'unsupported'
            })
            
        except Exception as e:
            results.append({
                'document_id': doc.get('id'),
                'filename': doc.get('filename', 'unknown'),
                'file_type': doc.get('file_type'),
                'analysis_result': None,
                'status': 'failed',
                'error': str(e)
            })
    
    return results


def validate_analysis_results(analysis_result: Union[ExcelAnalysisResult, PDFAnalysisResult]) -> Dict[str, Any]:
    """
    Validate analysis results for quality and completeness.
    
    Args:
        analysis_result: Analysis result to validate
    
    Returns:
        Validation report
    """
    validation_report = {
        'is_valid': True,
        'warnings': [],
        'errors': [],
        'quality_score': 1.0
    }
    
    if isinstance(analysis_result, ExcelAnalysisResult):
        # Excel validation
        if analysis_result.total_rows == 0:
            validation_report['warnings'].append('No data rows found')
            validation_report['quality_score'] -= 0.2
        
        if not analysis_result.columns:
            validation_report['errors'].append('No columns analyzed')
            validation_report['is_valid'] = False
        
        if analysis_result.completeness_score < 0.5:
            validation_report['warnings'].append('Low data completeness')
            validation_report['quality_score'] -= 0.3
        
        if not analysis_result.detected_patterns:
            validation_report['warnings'].append('No business patterns detected')
            validation_report['quality_score'] -= 0.1
    
    elif isinstance(analysis_result, PDFAnalysisResult):
        # PDF validation
        if analysis_result.character_count == 0:
            validation_report['errors'].append('No text extracted')
            validation_report['is_valid'] = False
        
        if analysis_result.text_quality_score < 0.5:
            validation_report['warnings'].append('Poor text quality - may need OCR')
            validation_report['quality_score'] -= 0.3
        
        if analysis_result.classification_confidence < 0.3:
            validation_report['warnings'].append('Low classification confidence')
            validation_report['quality_score'] -= 0.2
        
        if analysis_result.page_count == 0:
            validation_report['warnings'].append('Page count unknown')
            validation_report['quality_score'] -= 0.1
    
    validation_report['quality_score'] = max(0.0, validation_report['quality_score'])
    
    return validation_report


# =============================================================================
# TESTING AND VALIDATION UTILITIES
# =============================================================================

async def test_excel_analyzer(test_file_path: str = None) -> Dict[str, Any]:
    """
    Test the Excel analyzer with a sample file.
    
    Args:
        test_file_path: Path to test Excel file (optional)
    
    Returns:
        Test results
    """
    analyzer = ExcelStructureAnalyzer()
    
    if test_file_path and os.path.exists(test_file_path):
        # Test with real file
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        filename = os.path.basename(test_file_path)
        result = await analyzer.analyze_excel_file(file_content, filename)
        
        return {
            'test_type': 'real_file',
            'filename': filename,
            'result': result,
            'validation': validate_analysis_results(result)
        }
    else:
        # Create mock Excel data for testing
        import pandas as pd
        from io import BytesIO
        
        # Create sample data
        sample_data = pd.DataFrame({
            'Date': pd.date_range('2024-01-01', periods=100),
            'Amount': np.random.uniform(1000, 50000, 100),
            'Description': ['Payment to vendor', 'Receipt from customer'] * 50,
            'Vendor_ID': ['V' + str(i).zfill(3) for i in range(1, 101)],
            'Category': np.random.choice(['Raw Materials', 'Finished Goods', 'Services'], 100)
        })
        
        # Save to bytes
        buffer = BytesIO()
        sample_data.to_excel(buffer, index=False, sheet_name='Transactions')
        file_content = buffer.getvalue()
        
        result = await analyzer.analyze_excel_file(file_content, 'test_transactions.xlsx')
        
        return {
            'test_type': 'mock_data',
            'filename': 'test_transactions.xlsx',
            'result': result,
            'validation': validate_analysis_results(result)
        }


async def test_pdf_classifier(test_file_path: str = None) -> Dict[str, Any]:
    """
    Test the PDF classifier with a sample file.
    
    Args:
        test_file_path: Path to test PDF file (optional)
    
    Returns:
        Test results
    """
    classifier = PDFClassifier()
    
    if test_file_path and os.path.exists(test_file_path):
        # Test with real file
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        filename = os.path.basename(test_file_path)
        result = await classifier.analyze_pdf_document(file_content, filename)
        
        return {
            'test_type': 'real_file',
            'filename': filename,
            'result': result,
            'validation': validate_analysis_results(result)
        }
    else:
        # For PDF, we can't easily create mock content, so return test structure
        return {
            'test_type': 'mock_structure',
            'message': 'PDF classifier ready - provide real PDF file for testing',
            'classifier_ready': True,
            'supported_types': ['LC documents', 'Invoices', 'Financial reports', 'Contracts']
        }


# =============================================================================
# MAIN ENTRY POINT FOR TESTING
# =============================================================================

async def main():
    """Main entry point for testing the analyzers."""
    print("="*60)
    print("DOCUMENT ANALYZER TESTING")
    print("="*60)
    
    # Test Excel Analyzer
    print("\n1. Testing Excel Structure Analyzer...")
    excel_test = await test_excel_analyzer()
    print(f"Excel Test Result: {excel_test['test_type']}")
    if 'result' in excel_test:
        result = excel_test['result']
        print(f"  Sheets: {result.sheet_names}")
        print(f"  Dimensions: {result.total_rows} rows × {result.total_columns} columns")
        print(f"  Patterns: {result.detected_patterns}")
        print(f"  Quality: {result.completeness_score:.1%} complete")
    
    # Test PDF Classifier
    print("\n2. Testing PDF Classifier...")
    pdf_test = await test_pdf_classifier()
    print(f"PDF Test Result: {pdf_test['test_type']}")
    if 'result' in pdf_test:
        result = pdf_test['result']
        print(f"  Pages: {result.page_count}")
        print(f"  Text Quality: {result.text_quality_score:.1%}")
        print(f"  Classification: {result.classification_confidence:.1%}")
        print(f"  LC Document: {result.is_letter_of_credit}")
    
    print(f"\n✅ Analyzer testing completed!")
    print("Ready for integration with Task 1A Document Discovery System")


if __name__ == "__main__":
    import os
    import asyncio
    asyncio.run(main())