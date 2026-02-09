"""
Contract Analysis Router for NEC Engineering Analysis System.

Analyzes contract documents (PDF/DOCX) and extracts engineering features
from each line/clause using the FeatureExtractor.
"""

import re
import os
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Body
from fastapi.responses import JSONResponse, Response

from app.services.parsing.parsers.pdf_parser import DocumentParser
from app.services.extraction.core.feature_extractor import FeatureExtractor
from app.services.extraction.core.ontology import EngineeringOntology
from app.services.extraction.core.contract_classifier import ContractClassifier
from app.services.extraction.core.scope_extractor import ScopeExtractor
from app.services.extraction.extractors.contract_ingestion_engine import ContractIngestionEngine
from app.contract_parser.nec_parser import NECParser
from app.p6_engine.frozen_requirements import build_frozen_requirements

router = APIRouter(
    prefix="/api",
    tags=["analysis"],
    responses={404: {"description": "Not found"}},
)


def _get_latest_analysis_json_path():
    """Return path to the latest analysis_*.json in outputs/analysis_reports, or None."""
    analysis_dir = Path(__file__).parent.parent / "outputs" / "analysis_reports"
    if not analysis_dir.exists():
        return None
    json_files = list(analysis_dir.glob("analysis_*.json"))
    if not json_files:
        return None
    return max(json_files, key=lambda p: p.stat().st_mtime)


def _run_contract_analysis_from_path(file_path: str, filename: str, content: bytes) -> Dict[str, Any]:
    """
    Run contract analysis from a file path. Used by the analyze_contract endpoint and by the full-review orchestrator.
    Returns the analysis dict; does not persist to disk.
    """
    # Extract clean text using PDF parser
    print(f"[ANALYZE_CONTRACT] Extracting clean text from PDF...")
    from app.services.parsing.parsers.pdf_parser import DocumentParser

    clean_text = DocumentParser.extract_clean_text(file_path)
    print(f"[ANALYZE_CONTRACT] Extracted {len(clean_text)} characters of clean text")

    # EXTRACTION — Section-Based Unified Extractor
    print(f"[ANALYZE_CONTRACT] Running UnifiedExtractor (section-based method)...")
    from app.contract_parser.unified_extractor import UnifiedExtractor
    extractor = UnifiedExtractor(debug=False, enable_ai=bool(os.getenv("AZURE_OPENAI_ENDPOINT", "") and os.getenv("AZURE_OPENAI_API_KEY", "")))
    results_final = extractor.extract(clean_text)
    print(f"[ANALYZE_CONTRACT] UnifiedExtractor completed extraction")

    # Extract scope, constraints, milestones (unchanged)
    print(f"[ANALYZE_CONTRACT] Extracting scope, constraints, milestones using HybridAIExtractor...")
    enable_ai = os.getenv("AZURE_OPENAI_ENDPOINT", "") and os.getenv("AZURE_OPENAI_API_KEY", "")

    scope_items = []
    constraints = []
    programme_requirements = []
    milestones = []
    programme_critical_info = {}

    if enable_ai:
        from app.contract_parser.hybrid_ai_extractor import HybridAIExtractor
        hybrid_extractor = HybridAIExtractor(debug=False, enable_ai=True, pdf_path=file_path)

        # Extract scope, constraints, programme requirements, milestones
        ai_struct = hybrid_extractor.extract_scope_constraints_milestones(clean_text)
        scope_items = ai_struct.get("scope_items", [])
        constraints = ai_struct.get("constraints", [])
        programme_requirements = ai_struct.get("programme_requirements", [])
        milestones = ai_struct.get("milestones", [])
        print(f"[ANALYZE_CONTRACT] Extracted {len(scope_items)} scope items, {len(constraints)} constraints, {len(programme_requirements)} programme requirements, {len(milestones)} milestones")

        # Extract programme-compliance specification (PROGRAMME-CRITICAL)
        programme_critical_info = hybrid_extractor.extract_programme_critical_info(clean_text)
        programme_compliance_model = programme_critical_info.get("programme_compliance_model", {})
        print(f"[ANALYZE_CONTRACT] Extracted programme-compliance specification (programme_compliance_model):")
        print(f"  - {len(programme_compliance_model.get('required_activities', []))} required activities")
        print(f"  - {len(programme_compliance_model.get('sequencing_and_timing_constraints', []))} sequencing/timing constraints")
        print(f"  - {len(programme_compliance_model.get('external_dependencies', []))} external dependencies")
        print(f"  - {len(programme_compliance_model.get('programme_governance_and_acceptance_rules', []))} programme governance/acceptance rules")
        print(f"  - {len(programme_compliance_model.get('completion_and_takeover_gates', []))} completion/takeover gates")
        print(f"  - {len(programme_compliance_model.get('risk_and_early_warning_requirements', []))} risk/early warning requirements")
    else:
        print(f"[ANALYZE_CONTRACT] WARNING: Azure OpenAI not configured. Skipping semantic extraction.")

    # Set default metadata
    nec_metadata = {
        "total_pages": 0,
        "toc_detected": False,
        "missing_sections": []
    }

    # Parse access_dates (may be list, string, "not specified", or "confidential")
    access_dates_value = results_final.get("access_dates", [])
    access_dates_list = []
    if access_dates_value:
        if isinstance(access_dates_value, list):
            access_dates_list = access_dates_value
        elif isinstance(access_dates_value, str):
            if access_dates_value in ["not specified", "confidential"]:
                access_dates_list = access_dates_value
            else:
                access_dates_list = [d.strip() for d in access_dates_value.split(",") if d.strip()]
    else:
        access_dates_list = "not specified"

    date_pattern = r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b'
    # Extract dates from milestones
    starting_date = results_final.get("starting_date", "")
    access_dates = results_final.get("access_dates", [])
    completion_date = results_final.get("completion_date", "")

    if milestones:
        for milestone in milestones:
            if isinstance(milestone, str):
                if re.search(r'starting\s+date', milestone, re.IGNORECASE):
                    match = re.search(date_pattern, milestone, re.IGNORECASE)
                    if match:
                        day = re.search(r'\d{1,2}', match.group(0)).group()
                        month = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', match.group(0), re.IGNORECASE).group().capitalize()
                        year = re.search(r'\d{4}', match.group(0)).group()
                        milestone_date = f"{day} {month} {year}"
                        starting_date = milestone_date
                        break
        if not access_dates or (isinstance(access_dates, list) and len(access_dates) == 0):
            found_access_dates = []
            for milestone in milestones:
                if isinstance(milestone, str):
                    if re.search(r'access\s+date', milestone, re.IGNORECASE):
                        matches = re.finditer(date_pattern, milestone, re.IGNORECASE)
                        for match in matches:
                            day = re.search(r'\d{1,2}', match.group(0)).group()
                            month = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', match.group(0), re.IGNORECASE).group().capitalize()
                            year = re.search(r'\d{4}', match.group(0)).group()
                            milestone_date = f"{day} {month} {year}"
                            found_access_dates.append(milestone_date)
            if found_access_dates:
                access_dates = found_access_dates
        if not completion_date or not re.search(date_pattern, completion_date, re.IGNORECASE):
            for milestone in milestones:
                if isinstance(milestone, str):
                    match = re.search(date_pattern, milestone, re.IGNORECASE)
                    if match:
                        day = re.search(r'\d{1,2}', match.group(0)).group()
                        month = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)', match.group(0), re.IGNORECASE).group().capitalize()
                        year = re.search(r'\d{4}', match.group(0)).group()
                        milestone_date = f"{day} {month} {year}"
                        completion_date = milestone_date
                        break

    # Extract delay damages amount
    delay_damages = results_final.get("delay_damages", "")
    delay_damages_amount = results_final.get("delay_damages_amount", "")
    if not delay_damages_amount and delay_damages and delay_damages != "specified but redacted":
        amount_match = re.search(r'([£$€]?\s*\d[\d,\.]*)\s*(per|a)\s*(day|week|month)', delay_damages, re.IGNORECASE)
        if amount_match:
            delay_damages_amount = amount_match.group(0).strip()

    def format_clause_field(value):
        if value == "confidential":
            return "confidential"
        if isinstance(value, str) and not value.strip():
            return "not specified"
        if value is None:
            return "not specified"
        return value

    clause_summary = {
        "starting_date": format_clause_field(results_final.get("starting_date", "")),
        "possession_dates": access_dates_list if (isinstance(access_dates_list, list) and access_dates_list) else (access_dates_list if isinstance(access_dates_list, str) and access_dates_list in ["not specified", "confidential"] else "not specified"),
        "completion_date": format_clause_field(completion_date),
        "programme_requirements": {
            "submit_first_programme_within": format_clause_field(results_final.get("first_programme_submission", "")),
            "revised_programme_interval": format_clause_field(results_final.get("revised_programme_interval", "")),
            "period_for_reply": format_clause_field(results_final.get("period_for_reply", ""))
        },
        "delay_damages": format_clause_field(delay_damages),
        "delay_damages_amount": format_clause_field(delay_damages_amount),
        "defects": {
            "defects_date": format_clause_field(results_final.get("defects_date", "")),
            "defect_correction_period": format_clause_field(results_final.get("defect_correction_period", ""))
        },
        "payment_terms": {
            "assessment_interval": format_clause_field(results_final.get("assessment_interval", "")),
            "payment_period": format_clause_field(results_final.get("payment_period", "")),
            "retention_percentage": format_clause_field(results_final.get("retention_percentage", "")),
            "retention_period": format_clause_field(results_final.get("retention_period", "")),
            "interest_rate": format_clause_field(results_final.get("interest_rate", "")),
            "currency": format_clause_field(results_final.get("currency", ""))
        },
        "weather_data": {
            "recording_location": results_final.get("weather_location", "") if results_final.get("weather_location") not in ["", None] else "not specified",
            "measurement_data": results_final.get("weather_measurement_type", []) if isinstance(results_final.get("weather_measurement_type"), list) and results_final.get("weather_measurement_type") else ("not specified" if results_final.get("weather_measurement_type") != "confidential" else "confidential"),
            "historical_records_source": results_final.get("weather_historical_source", "") if results_final.get("weather_historical_source") not in ["", None] else "not specified"
        },
        "key_dates": results_final.get("key_dates", []) if isinstance(results_final.get("key_dates"), list) else [],
        "contractor_information": {
            "fee_percentage": results_final.get("fee_percentage", "") if results_final.get("fee_percentage") not in ["", None] else "not specified",
            "working_areas": results_final.get("working_areas", "") if results_final.get("working_areas") not in ["", None] else "not specified",
            "key_persons": results_final.get("key_persons", []) if isinstance(results_final.get("key_persons"), list) and results_final.get("key_persons") else (results_final.get("key_persons", "") if results_final.get("key_persons") in ["confidential", "not specified"] else "not specified")
        },
        "financial_terms": {
            "client_set_total": results_final.get("client_set_total", "") if results_final.get("client_set_total") not in ["", None] else "not specified",
            "contractor_share": results_final.get("contractor_share", "") if results_final.get("contractor_share") not in ["", None] else "not specified"
        },
        "contract_completeness": {
            "document_type": "completed" if results_final.get("starting_date") else "partial",
            "is_template": False
        }
    }

    project_name = Path(filename).stem if filename else "Unknown Project"

    items_with_features = 0
    for item in scope_items:
        if isinstance(item, dict):
            if item.get("features", {}).get("discipline") or item.get("features", {}).get("actions") or item.get("features", {}).get("assets"):
                items_with_features += 1
        elif isinstance(item, str):
            if item.strip():
                items_with_features += 1

    extraction_confidence = items_with_features / len(scope_items) if scope_items else 0.0

    response_data = {
        "project": project_name,
        "scope_items": scope_items,
        "constraints": constraints,
        "programme_requirements": programme_requirements,
        "milestones": milestones,
        "programme_compliance_model": programme_critical_info.get("programme_compliance_model", {
            "required_activities": [],
            "sequencing_and_timing_constraints": [],
            "external_dependencies": [],
            "programme_governance_and_acceptance_rules": [],
            "completion_and_takeover_gates": [],
            "risk_and_early_warning_requirements": []
        }),
        "contract_dates": {
            "starting_date": starting_date,
            "access_dates": access_dates,
            "completion_date": completion_date,
            "programme_submission_rules": clause_summary.get("programme_requirements", {}).get("submit_first_programme_within", ""),
            "programme_revision_rules": clause_summary.get("programme_requirements", {}).get("revised_programme_interval", "")
        },
        "programme_requirements_detailed": clause_summary.get("programme_requirements", {}),
        "key_dates": clause_summary.get("key_dates", []),
        "delay_damages": clause_summary.get("delay_damages", ""),
        "delay_damages_amount": clause_summary.get("delay_damages_amount", ""),
        "defects": clause_summary.get("defects", {}),
        "payment_terms": clause_summary.get("payment_terms", {}),
        "weather_data": clause_summary.get("weather_data", {}),
        "contractor_information": clause_summary.get("contractor_information", {}),
        "financial_terms": clause_summary.get("financial_terms", {}),
        "contract_completeness": clause_summary.get("contract_completeness", {}),
        "metadata": {
            "filename": filename,
            "total_scope_items": len(scope_items),
            "extraction_confidence": round(extraction_confidence, 3),
            "analysis_timestamp": datetime.now().isoformat(),
            "file_size_bytes": len(content),
            "total_pages": nec_metadata.get("total_pages", 0),
            "toc_detected": nec_metadata.get("toc_detected", False),
            "missing_sections": nec_metadata.get("missing_sections", []),
            "document_type": clause_summary.get("contract_completeness", {}).get("document_type", "unknown"),
            "is_template": clause_summary.get("contract_completeness", {}).get("is_template", False),
            "extraction_method": "option_a_phrase_ai_only"
        }
    }
    # Deduplicated obligation entities (single list); frozen_requirements = same list.
    try:
        frozen = build_frozen_requirements(response_data)
        response_data["obligation_entities"] = frozen.get("obligation_entities", {})
        response_data["frozen_requirements"] = frozen.get("frozen_requirements", [])
        response_data["frozen_requirements_version"] = frozen.get("frozen_requirements_version", 5)
        response_data["frozen_requirements_total_count"] = frozen.get("total_count", 0)
        response_data["obligation_entity_validation_error"] = frozen.get("obligation_entity_validation_error")
    except Exception as e:
        response_data["obligation_entities"] = {"obligations": [], "validation_error": str(e)}
        response_data["frozen_requirements"] = []
        response_data["frozen_requirements_version"] = 4
        response_data["frozen_requirements_total_count"] = 0
        response_data["frozen_requirements_error"] = str(e)
        response_data["obligation_entity_validation_error"] = str(e)
    return response_data


def classify_line(text: str) -> str:
    """
    Classify a line of contract text into one of: scope, technical, drawing_ref, admin, ignore.
    
    Classification rules:
    - If text contains construction actions → "scope"
    - If text contains construction items (drainage, kerbs, pavement, etc.) → "scope"
    - If text contains drawing numbers (ELW/###/###) → "drawing_ref"
    - If text contains organisation details, legal terms, insurances, H&S, quality, preliminaries → "admin"
    - If the line begins with a number but contains no construction verbs → "admin"
    - If the line is a table of contents → "ignore"
    
    Args:
        text: Line of text to classify
        
    Returns:
        Classification string: "scope", "technical", "drawing_ref", "admin", or "ignore"
    """
    text_lower = text.lower()
    
    # Check for table of contents indicators
    toc_indicators = [
        "content", "table of contents", "contents page", "index",
        "page", "status", "july", "size", "number", "rev", "title", "scale"
    ]
    if any(indicator in text_lower for indicator in toc_indicators) and len(text) < 200:
        # Check if it looks like a TOC entry (short line with page numbers or status)
        if re.search(r'\b(page|status|july|size|number|rev|title|scale)\b', text_lower):
            return "ignore"
    
    # Check for drawing references (ELW/###/### pattern)
    drawing_pattern = r'\b(?:ELW|elw|drawing|drg|drw|sht|sheet)\s*[\/\-]?\s*\d+[\/\-]\d+'
    if re.search(drawing_pattern, text_lower):
        return "drawing_ref"
    
    # Check for construction actions (scope indicators)
    construction_actions = [
        "construct", "demolish", "install", "excavate", "reconstruct", 
        "resurface", "divert", "erect", "refurbish", "build", "create",
        "remove", "replace", "upgrade", "modify", "extend", "repair",
        "lay", "place", "form", "cast", "pour", "compact", "backfill"
    ]
    has_construction_action = any(action in text_lower for action in construction_actions)
    
    # Check for construction items/assets (scope indicators)
    construction_items = [
        "drainage", "kerb", "pavement", "retaining wall", "earthworks",
        "carriageway", "footway", "bridge", "culvert", "manhole",
        "pipe", "ditch", "fence", "guardrail", "lighting", "signage",
        "junction", "crossing", "access", "road", "highway", "pavement"
    ]
    has_construction_item = any(item in text_lower for item in construction_items)
    
    # If has construction action or item, classify as scope
    if has_construction_action or has_construction_item:
        return "scope"
    
    # Check for admin/legal terms
    admin_indicators = [
        "employer", "contractor", "project manager", "supervisor",
        "insurance", "liability", "indemnity", "bond", "guarantee",
        "payment", "currency", "interest", "retention", "assessment",
        "adjudicator", "dispute", "arbitration", "law of", "language",
        "health and safety", "quality", "preliminaries", "pre-construction",
        "cdm", "risk register", "method statement", "subcontractor",
        "organisation", "address", "represented by", "fee percentage"
    ]
    has_admin_indicator = any(indicator in text_lower for indicator in admin_indicators)
    
    # Check if line begins with number but no construction verbs (likely admin)
    numbered_start = re.match(r'^\d+(\.\d+)*(\.|\))\s+', text)
    if numbered_start and not has_construction_action:
        return "admin"
    
    # If has admin indicators, classify as admin
    if has_admin_indicator:
        return "admin"
    
    # Default to scope if substantial text (might be scope we didn't catch)
    if len(text) > 20:
        return "scope"
    
    # Very short lines or unclear → ignore
    return "ignore"


def split_works_description(text: str) -> List[str]:
    """
    Extract and split Works Description section into individual work items.
    
    Detects the "1.2 Works description" heading and splits its content
    into individual bullet-like items.
    
    Args:
        text: Full contract text
        
    Returns:
        List of individual work item strings
    """
    work_items = []
    
    # Pattern to find Works Description section
    works_desc_pattern = r'1\.2\s+[Ww]orks\s+[Dd]escription[:\s]*(.*?)(?=\d+\.\d+|$)'
    match = re.search(works_desc_pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        works_desc_content = match.group(1)
        
        # Split by common delimiters (commas, semicolons, "and", bullet points)
        # Look for construction-related phrases
        # Split on: comma, semicolon, "and", "including", bullet points
        split_pattern = r'[,;]\s+|(?:\s+and\s+)|(?:\s+including\s+)|(?:\s*[-•*]\s+)'
        items = re.split(split_pattern, works_desc_content)
        
        for item in items:
            item = item.strip()
            # Filter out very short items and non-construction text
            if len(item) > 15 and any(word in item.lower() for word in [
                "demolition", "construction", "works", "installation", 
                "improvement", "upgrade", "diversion", "coordination"
            ]):
                work_items.append(item)
    
    return work_items


def split_into_lines(text: str) -> List[Dict[str, Any]]:
    """
    Split contract text into individual lines/clauses using heuristics.
    
    Heuristics:
    - Newline separation
    - Bullet points (-, •, *)
    - Numbered items (1., 1.1, 2.3.4, etc.)
    - Section headings (numbered or lettered)
    - Special handling for very long lines (> 2000 chars)
    
    Args:
        text: Full contract text
        
    Returns:
        List of line dictionaries with line_no and text
    """
    lines = []
    line_no = 1
    
    # Split by newlines first
    raw_lines = text.split('\n')
    
    for raw_line in raw_lines:
        # Strip whitespace
        cleaned = raw_line.strip()
        
        # Skip empty lines
        if not cleaned:
            continue
        
        # Handle very long lines (> 2000 chars) - break into logical segments
        if len(cleaned) > 2000:
            # Try to split on sentence boundaries or common delimiters
            segments = re.split(r'[.;]\s+|,\s+(?=[A-Z])', cleaned)
            for segment in segments:
                segment = segment.strip()
                if len(segment) > 10:
                    lines.append({
                        "line_no": line_no,
                        "text": segment
                    })
                    line_no += 1
            continue
        
        # Check for numbered items (1., 1.1, 2.3.4, etc.)
        numbered_pattern = r'^\d+(\.\d+)*(\.|\))\s+'
        # Check for bullet points (-, •, *)
        bullet_pattern = r'^[-•*]\s+'
        # Check for lettered items (a., b., i., etc.)
        lettered_pattern = r'^[a-z](\.|\))\s+'
        
        # Check if line matches any pattern or is substantial text
        is_numbered = bool(re.match(numbered_pattern, cleaned, re.IGNORECASE))
        is_bullet = bool(re.match(bullet_pattern, cleaned))
        is_lettered = bool(re.match(lettered_pattern, cleaned, re.IGNORECASE))
        is_substantial = len(cleaned) > 10  # At least 10 characters
        
        # Include if it matches a pattern or is substantial text
        if is_numbered or is_bullet or is_lettered or is_substantial:
            lines.append({
                "line_no": line_no,
                "text": cleaned
            })
            line_no += 1
    
    return lines


@router.post("/analyze_contract")
async def analyze_contract(file: UploadFile = File(...)) -> JSONResponse:
    """
    Extract compact, structured scope items from contract document (PDF only).
    
    Process:
    1. Extract structured data from PDF (text blocks and tables)
    2. Extract scope items from:
       - Works Description section (Part 1, page ~6)
       - Drawing schedule table (pages 13-16)
       - Bullet lists with physical work verbs
    3. Apply fine-grained segmentation (split compound clauses)
    4. Strict scope classification (only physical deliverables)
    5. Extract features using ontology (offline, Tier 1 only)
    6. Return compact JSON (< 2MB) without contract_text
    
    Args:
        file: Uploaded file (PDF or DOCX)
        
    Returns:
        JSONResponse: {
            "project": str,
            "scope_items": [
                {
                    "id": "SC-0001",
                    "text": "...",
                    "features": {
                        "discipline": str,
                        "actions": list[str],
                        "assets": list[str],
                        "materials": list[str],
                        "chainages": list[str],
                        "drawings": list[str]
                    },
                    "source": "works_description" | "drawing_schedule" | "bullet_list"
                },
                ...
            ],
            "metadata": {
                "filename": str,
                "analysis_timestamp": str,
                "file_size_bytes": int,
                "total_pages": int,
                "scope_items_count": int
            }
        }
    """
    print(f"[ANALYZE_CONTRACT] Received file: {file.filename}, content_type: {file.content_type}")
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf', '.docx']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Only PDF and DOCX are supported."
        )
    
    # Save uploaded file temporarily
    temp_file_path = None
    try:
        # Read file content
        content = await file.read()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            temp_file_path = tmp_file.name

        response_data = _run_contract_analysis_from_path(temp_file_path, file.filename, content)
        
        # Save to JSON file
        try:
            # Save to analysis_reports folder
            analysis_dir = Path(__file__).parent.parent / "outputs" / "analysis_reports"
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Clean filename (remove extension and special chars)
            safe_filename = re.sub(r'[^\w\-_\.]', '_', Path(file.filename).stem) if file.filename else "contract"
            json_filename = f"analysis_{safe_filename}_{timestamp}.json"
            json_filepath = analysis_dir / json_filename
            
            # Save JSON file (compact format)
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(response_data, f, indent=2, ensure_ascii=False)
            
            # Check file size (must be < 1MB per requirements)
            file_size_mb = os.path.getsize(json_filepath) / (1024 * 1024)
            print(f"[ANALYZE_CONTRACT] Results saved to: {json_filepath}")
            print(f"[ANALYZE_CONTRACT] Output file size: {file_size_mb:.2f} MB")
            if file_size_mb > 1.0:
                print(f"[ANALYZE_CONTRACT] WARNING: Output exceeds 1MB limit! Current: {file_size_mb:.2f} MB")
            
            # Add file path and size to response metadata
            response_data["metadata"]["output_file"] = str(json_filepath)
            response_data["metadata"]["output_filename"] = json_filename
            response_data["metadata"]["output_size_mb"] = round(file_size_mb, 2)
            
        except Exception as save_error:
            print(f"[ANALYZE_CONTRACT] Warning: Failed to save JSON file: {str(save_error)}")
            # Continue even if file save fails
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error processing file: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass  # Ignore cleanup errors


@router.get("/latest_contract_analysis")
async def get_latest_contract_analysis() -> JSONResponse:
    """
    Return the most recent contract analysis JSON from the server (last saved by analyze_contract).
    Use when Compare shows 0 required activities but the contract has them—pipeline may have an older copy.
    """
    latest_path = _get_latest_analysis_json_path()
    if not latest_path or not latest_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No contract analysis found on server. Run contract analysis first.",
        )
    with open(latest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(status_code=status.HTTP_200_OK, content=data)


@router.post("/generate_report")
async def generate_report(
    json_file: UploadFile = File(..., description="JSON file output from /api/analyze_contract")
) -> Response:
    """
    Generate a professional PDF report from contract analysis JSON.
    
    Accepts ONLY JSON file output from /api/analyze_contract endpoint.
    Does NOT accept PDF or DOCX files.
    
    Process:
    1. Validate JSON file (must be application/json)
    2. Load and validate JSON structure
    3. Pass to ReportGenerator to generate professional PDF
    4. Return PDF file as response
    
    Args:
        json_file: JSON file from /api/analyze_contract (required, application/json only)
        
    Returns:
        Response: PDF file with Content-Type: application/pdf
    """
    print(f"[GENERATE_REPORT] Received file: {json_file.filename}")
    
    # Validate content type
    if json_file.content_type and json_file.content_type not in ["application/json", "text/json"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {json_file.content_type}. Only application/json is accepted."
        )
    
    # Validate file extension
    if json_file.filename:
        file_ext = Path(json_file.filename).suffix.lower()
        if file_ext not in ['.json']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type: {file_ext}. Only .json files are accepted."
            )
    
    try:
        # Load JSON from file
        print(f"[GENERATE_REPORT] Loading JSON from file: {json_file.filename}")
        contents = await json_file.read()
        
        try:
            analysis_json = json.loads(contents.decode('utf-8'))
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file encoding. File must be UTF-8 encoded JSON."
            )
        
        # Validate JSON structure
        if not isinstance(analysis_json, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format: expected a dictionary/object"
            )
        
        # Validate required fields with graceful defaults
        if "project" not in analysis_json:
            analysis_json["project"] = "Unknown Project"
        if "extracted_clauses" not in analysis_json:
            analysis_json["extracted_clauses"] = {}
        if "contract_completeness" not in analysis_json:
            analysis_json["contract_completeness"] = {
                "document_type": "unknown",
                "filled_percentage": 0.0,
                "blank_percentage": 0.0,
                "mandatory_missing": 0,
                "total_mandatory": 0
            }
        if "metadata" not in analysis_json:
            analysis_json["metadata"] = {}
        
        # Generate PDF report from JSON data
        print(f"[GENERATE_REPORT] Generating PDF report...")
        from app.reporting.report_generator import ReportGenerator
        
        try:
            generator = ReportGenerator()
            report_bytes = generator.generate_pdf(analysis_json)
            
            # Check if it's PDF or DOCX (based on file extension if path returned, or try to detect)
            is_docx = False
            if isinstance(report_bytes, str):
                # Path returned - check extension
                is_docx = report_bytes.endswith('.docx')
                with open(report_bytes, 'rb') as f:
                    report_bytes = f.read()
            else:
                # Check if it's a DOCX (ZIP-based format)
                # PDFs start with %PDF, DOCX starts with PK (ZIP signature)
                if report_bytes[:4] == b'PK\x03\x04' and report_bytes[:4] != b'%PDF':
                    is_docx = True
            
            print(f"[GENERATE_REPORT] Report generated ({len(report_bytes)} bytes, format: {'DOCX' if is_docx else 'PDF'})")
            
            # Return report as response
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if is_docx else "application/pdf"
            filename = "contract_analysis_report.docx" if is_docx else "contract_analysis_report.pdf"
            
            return Response(
                content=report_bytes,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                }
            )
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[GENERATE_REPORT] Error generating PDF: {str(e)}")
            print(f"Traceback: {error_trace}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating PDF report: {str(e)}"
            )
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON format: {str(e)}"
        )
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[GENERATE_REPORT] Error generating report: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )


@router.post("/ingest_contract")
async def ingest_contract_structured(file: UploadFile = File(...)) -> JSONResponse:
    """
    Ingest contract document (PDF) and extract fully structured NEC contract data.
    
    This endpoint uses the Contract Ingestion Engine to extract:
    - Tables (Schedule of Drawings, Series tables)
    - Structured clauses (Part 1, Part 2)
    - Contract data fields
    - Complete structured JSON model
    
    Args:
        file: Uploaded PDF file
        
    Returns:
        JSONResponse: Fully structured contract data matching NEC contract model
    """
    print(f"[INGEST_CONTRACT] Received file: {file.filename}, content_type: {file.content_type}")
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Only PDF is supported for structured ingestion."
        )
    
    temp_file_path = None
    try:
        # Read file content
        content = await file.read()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            temp_file_path = tmp_file.name
        
        print(f"[INGEST_CONTRACT] Processing file: {temp_file_path}")
        
        # Initialize ingestion engine
        engine = ContractIngestionEngine()
        
        # Ingest contract
        structured_data = engine.ingest_contract(temp_file_path)
        
        # Save to JSON file
        try:
            # Save to contracts folder
            contracts_dir = Path(__file__).parent.parent / "outputs" / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = re.sub(r'[^\w\-_\.]', '_', Path(file.filename).stem) if file.filename else "contract"
            json_filename = f"structured_{safe_filename}_{timestamp}.json"
            json_filepath = contracts_dir / json_filename
            
            # Save JSON file
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            
            print(f"[INGEST_CONTRACT] Structured data saved to: {json_filepath}")
            
            # Add file path to metadata
            structured_data["metadata"]["output_file"] = str(json_filepath)
            structured_data["metadata"]["output_filename"] = json_filename
            
        except Exception as save_error:
            print(f"[INGEST_CONTRACT] Warning: Failed to save JSON file: {str(save_error)}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=structured_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[INGEST_CONTRACT] Error processing file: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass  # Ignore cleanup errors

@router.post("/extract_pdf_structured")
async def extract_pdf_structured(file: UploadFile = File(...)) -> JSONResponse:
    """
    Extract structured data from PDF (text blocks and tables).
    
    Returns JSON with pages containing:
    - text_blocks: List of text block strings
    - tables: List of tables, each with rows
    
    Args:
        file: Uploaded PDF file
        
    Returns:
        JSONResponse: {
            "pages": [
                {
                    "page_no": int,
                    "text_blocks": List[str],
                    "tables": [
                        {
                            "rows": List[List[str]]
                        }
                    ]
                }
            ],
            "metadata": {
                "filename": str,
                "extraction_timestamp": str,
                "total_pages": int,
                "total_tables": int,
                "total_text_blocks": int
            }
        }
    """
    print(f"[EXTRACT_PDF_STRUCTURED] Received file: {file.filename}")
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file_ext}. Only PDF is supported for structured extraction."
        )
    
    temp_file_path = None
    try:
        # Read file content
        content = await file.read()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            temp_file_path = tmp_file.name
        
        print(f"[EXTRACT_PDF_STRUCTURED] Processing file: {temp_file_path}")
        
        # Extract structured data
        structured_data = DocumentParser.extract_structured(temp_file_path)
        
        # Save to JSON file
        try:
            # Save to contracts folder
            contracts_dir = Path(__file__).parent.parent / "outputs" / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = re.sub(r'[^\w\-_\.]', '_', Path(file.filename).stem) if file.filename else "pdf"
            json_filename = f"structured_pdf_{safe_filename}_{timestamp}.json"
            json_filepath = contracts_dir / json_filename
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=2, ensure_ascii=False)
            
            print(f"[EXTRACT_PDF_STRUCTURED] Structured data saved to: {json_filepath}")
            
            # Add metadata
            structured_data["metadata"] = {
                "filename": file.filename,
                "extraction_timestamp": datetime.now().isoformat(),
                "output_file": str(json_filepath),
                "output_filename": json_filename,
                "total_pages": len(structured_data.get("pages", [])),
                "total_tables": sum(len(page.get("tables", [])) for page in structured_data.get("pages", [])),
                "total_text_blocks": sum(len(page.get("text_blocks", [])) for page in structured_data.get("pages", []))
            }
            
        except Exception as save_error:
            print(f"[EXTRACT_PDF_STRUCTURED] Warning: Failed to save JSON file: {str(save_error)}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=structured_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[EXTRACT_PDF_STRUCTURED] Error processing file: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass


@router.post("/parse_nec_contract")
async def parse_nec_contract(file: UploadFile = File(...)) -> JSONResponse:
    """
    Parse NEC contract PDF and extract programme-critical information.
    
    Uses TOC detection and fuzzy matching to locate and extract:
    - Scope items
    - Constraints
    - Milestones
    - Contract dates
    
    Works in both MOCK and REAL mode (respects AI_MODE environment variable).
    
    Returns clean, reduced JSON with only programme-critical information.
    """
    print(f"[PARSE_NEC_CONTRACT] Received file: {file.filename}, content_type: {file.content_type}")
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext != '.pdf':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are supported. Received: {file_ext}"
        )
    
    temp_file_path = None
    try:
        # Read file content
        content = await file.read()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(content)
            temp_file_path = tmp_file.name
        
        print(f"[PARSE_NEC_CONTRACT] Processing file: {temp_file_path}")
        
        # Initialize NEC parser
        nec_parser = NECParser()
        
        # Parse contract
        result = nec_parser.parse_contract(temp_file_path)
        
        # Check AI_MODE
        ai_mode = os.getenv("AI_MODE", "mock").lower().strip()
        print(f"[PARSE_NEC_CONTRACT] AI_MODE: {ai_mode}")
        
        # Save to JSON file
        try:
            # Save to contracts folder
            contracts_dir = Path(__file__).parent.parent / "outputs" / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = re.sub(r'[^\w\-_\.]', '_', Path(file.filename).stem) if file.filename else "contract"
            json_filename = f"nec_parse_{safe_filename}_{timestamp}.json"
            json_filepath = contracts_dir / json_filename
            
            with open(json_filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            file_size_mb = os.path.getsize(json_filepath) / (1024 * 1024)
            print(f"[PARSE_NEC_CONTRACT] Results saved to: {json_filepath}")
            print(f"[PARSE_NEC_CONTRACT] Output file size: {file_size_mb:.2f} MB")
            
            if file_size_mb > 1.0:
                print(f"[PARSE_NEC_CONTRACT] WARNING: Output exceeds 1MB limit! Current: {file_size_mb:.2f} MB")
            
            result["metadata"]["output_file"] = str(json_filepath)
            result["metadata"]["output_filename"] = json_filename
            result["metadata"]["output_size_mb"] = round(file_size_mb, 2)
            
        except Exception as save_error:
            print(f"[PARSE_NEC_CONTRACT] Warning: Failed to save JSON file: {str(save_error)}")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[PARSE_NEC_CONTRACT] Error: {str(e)}")
        print(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error parsing contract: {str(e)}"
        )
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

