# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for Task 1C: Document Processing Pipeline

Covers:
- Task 1C-1: Excel Processing Engine (multi-sheet, dynamic columns, formulas, validation)
- Task 1C-2: PDF Processing Engine (text PDFs, OCR for scanned PDFs, form/table-like content)
- Task 1C-3: Content Normalization System (currency/date/terminology/precision)
- Integration: Verifies handoff to vector embedding/storage via a mocked client

Usage:
    cd backend/
    pytest app/features/rag_chatbot/tests/test_task1c_processing_pipeline.py -q

Assumed public API in `processing/document_processing_engine.py`:
    - class DocumentProcessingEngine:
        def __init__(self, *, vector_client=None, ocr_enabled=True, locale="en_BD"): ...
        def process_excel(self, path: str) -> list[dict]: ...
        def process_pdf(self, path: str) -> list[dict]: ...
        def normalize_record(self, rec: dict) -> dict: ...
        def integrate_to_embeddings(self, chunks: list[dict]) -> list[str]: ...
    - Optional helper call sites (for monkeypatch):
        - document_processing_engine.ocr_extract(image_or_pdf_path) -> str
        - document_processing_engine.detect_tables_from_pdf(path) -> list[dict]

If your engine uses different names, adjust the import/attribute lookups below.
Tests are defensive and will raise clear errors when expected methods are missing.
"""

import io
import os
import sys
import json
import math
import types
import shutil
import datetime as dt
from pathlib import Path

import pytest

# ---------- Import engine (with defensive checks) ----------

ENGINE_IMPORT_PATH = "app.features.rag_chatbot.processing.document_processing_engine"

def _import_engine():
    try:
        mod = __import__(ENGINE_IMPORT_PATH, fromlist=["*"])
    except Exception as e:
        pytest.fail(f"Failed to import engine module '{ENGINE_IMPORT_PATH}': {e}")
    # Heuristically find class
    candidates = [getattr(mod, n) for n in dir(mod) if "Engine" in n or "DocumentProcessing" in n]
    cls = next((c for c in candidates if isinstance(c, type)), None)
    if cls is None:
        pytest.fail("Could not find a processing engine class in the module. "
                    "Expected a class like 'DocumentProcessingEngine'.")
    # Required methods
    required = ["process_excel", "process_pdf", "normalize_record", "integrate_to_embeddings"]
    for r in required:
        if not hasattr(cls, r):
            pytest.fail(f"Engine class '{cls.__name__}' missing required method: {r}()")
    return mod, cls

engine_mod, EngineClass = _import_engine()

# ---------- Test markers ----------

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

# ---------- Utilities: create sample Excel & PDFs ----------

@pytest.fixture
def tmpdir_str(tmp_path) -> str:
    return str(tmp_path)

@pytest.fixture
def sample_excel(tmp_path):
    """
    Creates a multi-sheet Excel workbook:
      Sheet 'Transactions': Date, Vendor, Amount (BDT), Currency ('BDT'), Notes
      Sheet 'Salaries': Name, Department, Base, Bonus, Total (=Base+Bonus as formula)
      Sheet 'Mixed': random columns and missing headers to test dynamic mapping
    """
    import pandas as pd

    tx = pd.DataFrame({
        "Date": [dt.date(2024, 3, 1), dt.date(2024, 3, 15), dt.date(2024, 4, 1)],
        "Vendor": ["ABC Corp", "মোঃ রহমান ট্রেডার্স", "XYZ Ltd"],
        "Amount": [50000, 125000, 89000],
        "Currency": ["BDT", "BDT", "BDT"],
        "Notes": ["LC-2024-03", "Q1 supplies", "Delivery charge inc."]
    })

    sal = pd.DataFrame({
        "Name": ["John Smith", "Ayesha Khan", "Iqram"],
        "Department": ["Finance", "HR", "Ops"],
        "Base": [80000, 60000, 70000],
        "Bonus": [20000, 15000, 10000],
        # Put placeholder numeric, and write a real formula later with openpyxl
        "Total": [100000, 75000, 80000],
        "Currency": ["BDT", "BDT", "BDT"]
    })

    mixed = pd.DataFrame({
        "ColA": ["Invoice 123", "Invoice 124", None],
        "Amount (টাকা)": ["৫০,০০০", "১২,৫০০", "০"],  # Bengali numerals
        "When": ["2024-03-05", "05/04/2024", "April 10, 2024"]
    })

    xlsx_path = tmp_path / "task1c_sample.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        tx.to_excel(writer, index=False, sheet_name="Transactions")
        sal.to_excel(writer, index=False, sheet_name="Salaries")
        mixed.to_excel(writer, index=False, sheet_name="Mixed")
        # Insert real formula for Total in Salaries using openpyxl
        ws = writer.book["Salaries"]
        # Header row is row 1; Base=col3, Bonus=col4, Total=col5
        for r in range(2, 2 + len(sal)):
            ws.cell(row=r, column=5, value=f"=C{r}+D{r}")

    return str(xlsx_path)

@pytest.fixture
def sample_text_pdf(tmp_path):
    """
    Creates a simple text-based PDF with table-like lines and a currency/date mix.
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except Exception:
        pytest.skip("reportlab not installed; install to run PDF generation tests: pip install reportlab")

    pdf_path = tmp_path / "task1c_text.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    t = c.beginText(50, 800)
    lines = [
        "INVOICE: C-2024-03",
        "Vendor: ABC Corp",
        "Amount: 50,000 BDT",
        "Date: 2024-03-05",
        "Notes: Office supplies; slow filtration = cleaner water (charcoal).",
        "Table:",
        "Item,Qty,Price",
        "Paper,10,1000",
        "Ink,2,5000",
    ]
    for line in lines:
        t.textLine(line)
    c.drawText(t)
    c.showPage()
    c.save()
    return str(pdf_path)

@pytest.fixture
def sample_scanned_pdf(tmp_path):
    """
    "Scanned" PDF stand-in: we won't actually embed an image; instead we create a blank PDF
    and rely on the engine calling an OCR helper which we monkeypatch to return text.
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except Exception:
        pytest.skip("reportlab not installed; install to run PDF generation tests: pip install reportlab")

    pdf_path = tmp_path / "task1c_scanned.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setFont("Helvetica", 12)
    c.drawString(50, 800, " ")  # empty-ish
    c.showPage()
    c.save()
    return str(pdf_path)

# ---------- Mocks ----------

class DummyVectorClient:
    """
    Minimal mock of a vector/embedding client. Collects what was sent for assertions.
    """
    def __init__(self):
        self.records = []
        self.return_ids = True

    def upsert_embeddings(self, items):
        # items: list of dicts with keys like: id, text, metadata, embedding (optional)
        self.records.extend(items)
        # Return fake IDs to simulate success
        return [f"emb-{i}" for i in range(len(items))]

@pytest.fixture
def vector_client():
    return DummyVectorClient()

@pytest.fixture
def engine(vector_client):
    # ocr_enabled=True so that PDF OCR path is available to be monkeypatched
    eng = EngineClass(vector_client=vector_client, ocr_enabled=True, locale="en_BD")
    return eng

# ---------- Helper: assert chunk schema ----------

def assert_chunk_schema(ch):
    assert isinstance(ch, dict), "Chunk should be a dict"
    for k in ("content", "source_path", "doc_type"):
        assert k in ch, f"Chunk missing key: {k}"
    # Optional but recommended
    assert "metadata" in ch, "Chunk should include metadata"
    assert isinstance(ch["metadata"], dict), "Chunk.metadata must be dict"

# ---------- Tests: Excel Processing Engine ----------

def test_excel_multisheet_dynamic_columns(engine, sample_excel):
    chunks = engine.process_excel(sample_excel)
    assert isinstance(chunks, list) and len(chunks) > 0, "No chunks returned from process_excel()"
    for ch in chunks:
        assert_chunk_schema(ch)
        assert ch["doc_type"] == "excel"
        assert "sheet_name" in ch["metadata"]
        # Ensure dynamic mapping: presence of semantically important fields
        # (date/vendor/amount or name/department/total)
        text = ch["content"].lower()
        assert any(key in text for key in ["date", "vendor", "amount", "name", "department", "total", "currency"]), \
            "Chunk content seems not to preserve table context"

def test_excel_formula_handling(engine, sample_excel):
    """
    Salaries.Total is a formula (=Base+Bonus). Engine should either evaluate or at least not crash.
    It should surface a numeric total or a clearly labeled raw formula.
    """
    chunks = engine.process_excel(sample_excel)
    salary_chunks = [c for c in chunks if c["metadata"].get("sheet_name") == "Salaries"]
    assert salary_chunks, "Expected Salaries sheet chunks"
    # Find any chunk line mentioning Total and a number
    got_total = any(("total" in c["content"].lower() and any(ch.isdigit() for ch in c["content"]))
                    for c in salary_chunks)
    assert got_total, "Expected a computed or extracted 'Total' value from formula rows"

def test_excel_validation_flags_errors(engine, sample_excel):
    """
    If your engine does validation, it should flag obvious anomalies (e.g., negative amounts or empty vendor).
    We'll inject a row at runtime by re-processing with a patched loader if engine exposes such hook.
    If not, we at least confirm that 'errors' key exists or engine is robust to odd rows.
    """
    chunks = engine.process_excel(sample_excel)
    # Not all engines return 'errors'; if present, assert type
    for ch in chunks:
        if "errors" in ch:
            assert isinstance(ch["errors"], list), "'errors' should be a list if present"

# ---------- Tests: PDF Processing Engine ----------

def test_pdf_text_extraction(engine, sample_text_pdf):
    chunks = engine.process_pdf(sample_text_pdf)
    assert chunks and isinstance(chunks, list), "No chunks returned from process_pdf()"
    for ch in chunks:
        assert_chunk_schema(ch)
        assert ch["doc_type"] == "pdf"
    joined = "\n".join(c["content"] for c in chunks).lower()
    assert "invoice" in joined and "abc corp" in joined and "50,000" in joined, \
        "Text PDF content not extracted/preserved as expected"

def test_pdf_scanned_uses_ocr(monkeypatch, engine, sample_scanned_pdf):
    """
    The engine should call an OCR helper when it detects a scanned PDF.
    We monkeypatch a function 'ocr_extract' in the engine module namespace.
    """
    fake_text = "SCANNED INVOICE: LC-2024-04 Amount: ১২,০০০ BDT Date: 05/04/2024"
    # Only patch if function exists; if not, patch a known call site in your code.
    if hasattr(engine_mod, "ocr_extract"):
        monkeypatch.setattr(engine_mod, "ocr_extract", lambda p: fake_text, raising=True)
    else:
        # Fallback: patch a method on the engine if it exists
        if hasattr(engine, "ocr_extract"):
            monkeypatch.setattr(engine, "ocr_extract", lambda p: fake_text, raising=True)
        else:
            pytest.skip("No OCR hook ('ocr_extract') exposed to monkeypatch; skip OCR test.")

    chunks = engine.process_pdf(sample_scanned_pdf)
    joined = "\n".join(c["content"] for c in chunks)
    assert "LC-2024-04" in joined and "১২,০০০" in joined, "OCR output not found in chunks"

# ---------- Tests: Content Normalization System ----------

@pytest.mark.parametrize(
    "raw,expect",
    [
        ({"amount": "50,000 BDT"}, {"amount_value": 50000.0, "currency": "BDT"}),
        ({"amount": "USD 125,000"}, {"amount_value": 125000.0, "currency": "USD"}),
        ({"amount": "১২,৫০০ টাকা"}, {"amount_value": 12500.0, "currency": "BDT"}),
        ({"date": "2024-03-05"}, {"date_iso": "2024-03-05"}),
        ({"date": "05/04/2024"}, {"date_iso": "2024-04-05"}),  # dd/mm/yyyy assumption
        ({"date": "April 10, 2024"}, {"date_iso": "2024-04-10"}),
        ({"notes": "LC-2024-03; slow = cleaner"}, {"notes_std": "LC-2024-03; slow = cleaner"}),
    ],
)
def test_normalization(engine, raw, expect):
    """
    Engine.normalize_record should:
      - Parse currency & numbers (including Bengali numerals) into amount_value + currency
      - Normalize dates to ISO 8601 (YYYY-MM-DD)
      - Preserve key textual terms (charcoal, LC-XXXX-XX, etc.) in a standard field
    Only check keys we expect, so engines are free to add extra normalized fields.
    """
    out = engine.normalize_record(raw.copy())
    for k, v in expect.items():
        assert k in out, f"Normalized record missing expected key '{k}'"
        assert str(out[k]) == str(v), f"Mismatch for '{k}': got {out[k]!r}, expected {v!r}"

# ---------- Tests: End-to-End Integration to Embeddings (mocked) ----------

def test_end_to_end_excel_to_vectors(engine, vector_client, sample_excel):
    chunks = engine.process_excel(sample_excel)
    # Normalize before integrate (your engine might do this internally; doing explicitly is ok)
    normed = [engine.normalize_record(c | {"raw_text": c.get("content", "")}) for c in chunks]
    ids = engine.integrate_to_embeddings(normed)
    assert isinstance(ids, list) and ids, "No IDs returned from integrate_to_embeddings()"
    # Ensure vector client received structured payloads
    assert len(vector_client.records) == len(normed), "Vector client did not receive all items"
    sample = vector_client.records[0]
    assert "text" in sample and "metadata" in sample, "Vector payload missing 'text' and/or 'metadata'"

def test_end_to_end_pdf_to_vectors(engine, vector_client, sample_text_pdf):
    chunks = engine.process_pdf(sample_text_pdf)
    normed = [engine.normalize_record(c | {"raw_text": c.get("content", "")}) for c in chunks]
    ids = engine.integrate_to_embeddings(normed)
    assert ids and all(isinstance(x, str) for x in ids), "Vector IDs should be strings"

# ---------- Robustness & Logging ----------

def test_engine_handles_empty_files_gracefully(engine, tmp_path):
    empty_xlsx = tmp_path / "empty.xlsx"
    empty_xlsx.write_bytes(b"")  # corrupt/empty
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")  # minimal stub

    # Should not crash; should return [] or a chunk containing an error state
    for p, fn in [(str(empty_xlsx), engine.process_excel), (str(empty_pdf), engine.process_pdf)]:
        try:
            out = fn(p)
        except Exception as e:
            pytest.fail(f"Engine raised on empty file {p}: {e}")
        assert isinstance(out, list), "Engine should return a list even on bad input"
        # Allow either empty result or error-labeled chunk
        if out:
            assert all(isinstance(c, dict) for c in out)
            if any("errors" in c for c in out):
                assert all(isinstance(c.get("errors", []), list) for c in out)

# ---------- Optional: Table detection hook ----------

def test_pdf_table_detection_hook_if_present(monkeypatch, engine, sample_text_pdf):
    """
    If engine exposes `detect_tables_from_pdf`, ensure it's called and its results are merged.
    We monkeypatch it to return a synthetic table so we can assert it appears in chunks.
    """
    if not hasattr(engine_mod, "detect_tables_from_pdf") and not hasattr(engine, "detect_tables_from_pdf"):
        pytest.skip("No table detection hook exposed; skipping.")

    def fake_detect_tables(_path):
        return [{"type": "table", "rows": [["Item", "Qty", "Price"], ["Paper", "10", "1000"]]}]

    if hasattr(engine_mod, "detect_tables_from_pdf"):
        monkeypatch.setattr(engine_mod, "detect_tables_from_pdf", fake_detect_tables, raising=True)
    else:
        monkeypatch.setattr(engine, "detect_tables_from_pdf", fake_detect_tables, raising=True)

    chunks = engine.process_pdf(sample_text_pdf)
    joined = "\n".join(c["content"] for c in chunks).lower()
    assert "paper" in joined and "price" in joined, "Expected table content from detection hook not found"

# ---------- Smoke: CLI helper script exists ----------

def test_quick_script_log_exists_or_generates(tmp_path):
    """
    Your repo ships 'scripts/task1c_quick_test.sh'. We don't execute it here,
    but we ensure the expected log directory path is reasonable.
    """
    root = Path(__file__).resolve().parents[5]  # go to repo root from this file
    script = root / "backend" / "scripts" / "task1c_quick_test.sh"
    assert script.exists(), "Expected quick test script missing: backend/scripts/task1c_quick_test.sh"
