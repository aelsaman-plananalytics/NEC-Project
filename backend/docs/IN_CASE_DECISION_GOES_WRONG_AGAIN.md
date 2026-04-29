# In case decision goes wrong again

This note is a “where to look” guide for the most common **extraction / evidence** environment issues that can cause unexpected validation outputs.

It also contains a compact overview of the contract extraction modules so you know where relevant behaviour lives.

---

# NEC Contract Extractors (reference)

Table extraction, clause parsing, and contract data models for NEC documents.

## Overview

This module provides:
- **Tables** (Schedule of Drawings, Series tables) using Camelot, pdfplumber, and OCR
- **Structured clauses** (Part 1 sections 1-9, Part 2 contractor data)
- **Contract data fields** (Employer, Project Manager, Payment terms, etc.)
- **Data models** for NEC contract structure (Part 1, Part 2, Drawings, etc.)

The former **Contract Ingestion Engine** and **POST /api/ingest_contract** endpoint were removed; contract analysis uses the main **analyze_contract** pipeline (contract_parser + extraction core) instead.

## Architecture

### Core Modules

1. **`table_extractor.py`**
   - Hybrid table extraction (Camelot → pdfplumber → OCR)
   - Handles vector-based PDFs, image-based PDFs, and scanned documents
   - Parses Schedule of Drawings tables

2. **`clause_parser.py`**
   - Detects clause structure (main sections, subclauses)
   - Extracts Part 1 sections (1-9)
   - Extracts Part 2 contractor data
   - Parses Works Description, Payment terms, Time sections

3. **`nec_contract_model.py`**
   - Dataclasses for structured contract representation
   - Part 1, Part 2, Drawings, Risks, Insurance models
   - JSON serialization support

4. **`utils_pdf.py`**
   - PDF page type detection (vector/image/mixed)
   - Text extraction utilities
   - Table detection helpers

5. **`utils_cleaning.py`**
   - OCR noise removal
   - Header/footer removal
   - Hyphenated line break fixing
   - Unicode normalization

## Usage

Use **TableExtractor**, **ClauseParser**, and the **nec_contract_model** types from this package as needed. Contract analysis is performed by the main app via **POST /api/v1/analyze_contract** (see contract_parser and extraction core).

## Output Format (nec_contract_model)

The output matches the exact NEC contract model structure:

```json
{
  "metadata": {
    "file_name": "...",
    "pages": 0,
    "extraction_time": "...",
    "tables_detected": 0
  },
  "contract": {
    "part_1": {
      "1_general": {
        "1.1_conditions_of_contract": "...",
        "1.2_works_description": "...",
        "1.3_employer": { "name": "...", "address": "..." },
        ...
      },
      "10_schedule_of_drawings": [
        {
          "size": "A1",
          "number": "000041/ELW/100/01",
          "revision": "A",
          "title": "...",
          "scale": "1:500",
          "status": "Complete"
        }
      ]
    },
    "part_2": {
      "contractor_data": { ... },
      "schedule_of_cost_components": { ... }
    }
  }
}
```

## Dependencies

Required packages:
- `camelot-py[cv]` - Table extraction from vector PDFs
- `pdfplumber` - Text and table extraction fallback
- `pytesseract` - OCR for image-based PDFs
- `pdf2image` - PDF to image conversion for OCR
- `pandas` - Table data handling
- `Pillow` - Image processing

System dependencies (most common missing pieces):
- **Tesseract OCR** must be installed and available on PATH
- **Ghostscript** is required by Camelot on many systems

Install with:
```bash
pip install camelot-py[cv] pdfplumber pytesseract pdf2image pandas Pillow
```

## Notes

- Camelot requires `ghostscript` and `tesseract` system dependencies
- OCR fallback is slower but handles scanned documents
- Table extraction accuracy depends on PDF quality
- Clause parsing uses regex patterns optimized for NEC contract format

## Troubleshooting

### OCR / table extraction fails (no tables, empty output)

Checks:
- Confirm Tesseract is installed and callable:

```bash
tesseract --version
```

- For Camelot, confirm Ghostscript is installed.
- If PDFs are scanned/images, OCR will be used and may be slow; ensure `pdf2image` can find a PDF renderer (Poppler on Windows setups).



