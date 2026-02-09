# NEC Contract Ingestion Engine

Complete structured extraction pipeline for NEC contract documents.

## Overview

This module provides a comprehensive contract ingestion system that extracts:
- **Tables** (Schedule of Drawings, Series tables) using Camelot, pdfplumber, and OCR
- **Structured clauses** (Part 1 sections 1-9, Part 2 contractor data)
- **Contract data fields** (Employer, Project Manager, Payment terms, etc.)
- **Fully structured JSON** matching the NEC contract model

## Architecture

### Core Modules

1. **`contract_ingestion_engine.py`**
   - Main orchestrator
   - Coordinates table extraction, text extraction, clause parsing
   - Builds final structured JSON contract model

2. **`table_extractor.py`**
   - Hybrid table extraction (Camelot → pdfplumber → OCR)
   - Handles vector-based PDFs, image-based PDFs, and scanned documents
   - Parses Schedule of Drawings tables

3. **`clause_parser.py`**
   - Detects clause structure (main sections, subclauses)
   - Extracts Part 1 sections (1-9)
   - Extracts Part 2 contractor data
   - Parses Works Description, Payment terms, Time sections

4. **`nec_contract_model.py`**
   - Dataclasses for structured contract representation
   - Part 1, Part 2, Drawings, Risks, Insurance models
   - JSON serialization support

5. **`utils_pdf.py`**
   - PDF page type detection (vector/image/mixed)
   - Text extraction utilities
   - Table detection helpers

6. **`utils_cleaning.py`**
   - OCR noise removal
   - Header/footer removal
   - Hyphenated line break fixing
   - Unicode normalization

## Usage

### Basic Usage

```python
from app.services.extraction.extractors import ContractIngestionEngine

engine = ContractIngestionEngine()
result = engine.ingest_contract("contract.pdf")

# Result is a fully structured dictionary matching NEC contract model
print(result["contract"]["part_1"]["1_general"]["1.2_works_description"])
```

### API Endpoint

The ingestion engine is available via the FastAPI endpoint:

```
POST /api/ingest_contract
```

Upload a PDF file and receive fully structured JSON response.

## Output Format

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

Install with:
```bash
pip install camelot-py[cv] pdfplumber pytesseract pdf2image pandas Pillow
```

## Testing

Run tests with:
```bash
pytest app/services/extraction/extractors/tests/test_ingestion_engine.py -vv
```

## Notes

- Camelot requires `ghostscript` and `tesseract` system dependencies
- OCR fallback is slower but handles scanned documents
- Table extraction accuracy depends on PDF quality
- Clause parsing uses regex patterns optimized for NEC contract format



