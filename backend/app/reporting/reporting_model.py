"""
Reporting Model for NEC Contract Analysis System.

Converts engineering JSON output into narrative report text using Azure OpenAI.
Also provides PDF generation via ReportGenerator.
"""

import os
import json
from typing import Dict, Any, Optional, Union

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AzureOpenAI = None

from app.config import settings
from app.reporting.report_generator import ReportGenerator


class ReportingModel:
    """
    Converts engineering JSON output into narrative report text.
    
    Uses Azure OpenAI to generate professional narrative reports from
    structured contract analysis data. Does NOT re-analyze contracts or
    hallucinate missing information - only summarizes what exists in the JSON.
    """
    
    def __init__(self):
        """Initialize the reporting model with Azure OpenAI client."""
        self.model_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")
        
        # Initialize Azure OpenAI client if available
        self.azure_client = None
        if OPENAI_AVAILABLE:
            azure_endpoint = settings.AZURE_OPENAI_ENDPOINT
            azure_key = settings.AZURE_OPENAI_API_KEY
            
            if azure_endpoint and azure_key:
                try:
                    self.azure_client = AzureOpenAI(
                        api_key=azure_key,
                        api_version=settings.AZURE_OPENAI_API_VERSION,
                        azure_endpoint=azure_endpoint
                    )
                    print(f"[ReportingModel] Azure OpenAI initialized with model: {self.model_name}")
                except Exception as e:
                    print(f"[ReportingModel] Warning: Failed to initialize Azure OpenAI: {e}")
                    self.azure_client = None
            else:
                print("[ReportingModel] Azure OpenAI credentials not configured")
        else:
            print("[ReportingModel] OpenAI library not available")
    
    def generate_report(self, data: Dict[str, Any]) -> str:
        """
        Convert engineering JSON into narrative text.
        
        Must NOT hallucinate clauses not present.
        Must NOT re-analyze the contract.
        Only summarize what exists in JSON.
        
        Args:
            data: Engineering JSON output from /api/analyze_contract
            
        Returns:
            str: Professional narrative report text
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
        
        # Extract key information from JSON
        project_name = data.get("project", "Unknown Project")
        metadata = data.get("metadata", {})
        extracted_clauses = data.get("extracted_clauses", {})
        contract_completeness = data.get("contract_completeness", {})
        scope_items = data.get("scope_items", [])
        constraints = data.get("constraints", [])
        milestones = data.get("milestones", [])
        
        # If Azure OpenAI is available, use it for narrative generation
        if self.azure_client:
            return self._generate_with_llm(data, project_name, metadata, extracted_clauses, 
                                         contract_completeness, scope_items, constraints, milestones)
        else:
            # Fallback to template-based generation
            return self._generate_template_report(project_name, metadata, extracted_clauses,
                                                contract_completeness, scope_items, constraints, milestones)
    
    def _generate_with_llm(
        self,
        data: Dict[str, Any],
        project_name: str,
        metadata: Dict[str, Any],
        extracted_clauses: Dict[str, Any],
        contract_completeness: Dict[str, Any],
        scope_items: list,
        constraints: list,
        milestones: list
    ) -> str:
        """Generate report using Azure OpenAI LLM."""
        try:
            # Prepare prompt with strict instructions
            system_prompt = """You are a professional contract analysis report writer for NEC engineering contracts.

CRITICAL RULES:
1. ONLY summarize information that is explicitly present in the provided JSON data
2. DO NOT invent, assume, or hallucinate any clause values, dates, or information
3. DO NOT re-analyze the contract - only report what the analysis found
4. If a clause is missing or blank, state that clearly - do not make up values
5. Write in a professional, clear, and structured narrative style
6. Focus on facts and what was actually extracted from the contract

Generate a comprehensive narrative report covering:
- Project overview and metadata
- Contract completeness assessment
- Programme-critical clauses status (filled/blank/missing)
- Scope summary
- Constraints and milestones
- Risks and recommendations based on what is actually present

Be factual, professional, and accurate. Do not add information that is not in the JSON."""

            user_prompt = f"""Generate a professional narrative report for the following NEC contract analysis:

Project: {project_name}
Analysis Date: {metadata.get('analysis_timestamp', 'Unknown')}
Document: {metadata.get('filename', 'Unknown')}

Contract Completeness:
- Document Type: {contract_completeness.get('document_type', 'unknown')}
- Filled Clauses: {contract_completeness.get('filled_percentage', 0.0):.1f}%
- Blank Clauses: {contract_completeness.get('blank_percentage', 0.0):.1f}%
- Missing Clauses: {contract_completeness.get('mandatory_missing', 0)} / {contract_completeness.get('total_mandatory', 0)}

Extracted Clauses:
{json.dumps(extracted_clauses, indent=2)}

Scope Items: {len(scope_items)} items identified
Constraints: {len(constraints)} constraints identified
Milestones: {len(milestones)} milestones identified

Full JSON Data:
{json.dumps(data, indent=2)}

Generate a comprehensive narrative report. Remember: ONLY report what is in the data above. Do not invent or assume any values."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.azure_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.3,  # Lower temperature for more factual output
                max_tokens=4000
            )
            
            report_text = response.choices[0].message.content.strip()
            print(f"[ReportingModel] Generated report using LLM ({len(report_text)} characters)")
            return report_text
            
        except Exception as e:
            print(f"[ReportingModel] LLM generation failed: {e}, falling back to template")
            return self._generate_template_report(
                project_name, metadata, extracted_clauses,
                contract_completeness, scope_items, constraints, milestones
            )
    
    def _generate_template_report(
        self,
        project_name: str,
        metadata: Dict[str, Any],
        extracted_clauses: Dict[str, Any],
        contract_completeness: Dict[str, Any],
        scope_items: list,
        constraints: list,
        milestones: list
    ) -> str:
        """Generate report using template-based approach (fallback)."""
        lines = []
        
        # Title
        lines.append("=" * 80)
        lines.append(f"NEC CONTRACT ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Project Overview
        lines.append("PROJECT OVERVIEW")
        lines.append("-" * 80)
        lines.append(f"Project Name: {project_name}")
        lines.append(f"Source Document: {metadata.get('filename', 'Unknown')}")
        lines.append(f"Analysis Date: {metadata.get('analysis_timestamp', 'Unknown')}")
        lines.append(f"Total Pages: {metadata.get('total_pages', 0)}")
        lines.append("")
        
        # Contract Completeness
        lines.append("CONTRACT COMPLETENESS ASSESSMENT")
        lines.append("-" * 80)
        doc_type = contract_completeness.get("document_type", "unknown")
        filled_pct = contract_completeness.get("filled_percentage", 0.0)
        blank_pct = contract_completeness.get("blank_percentage", 0.0)
        missing_count = contract_completeness.get("mandatory_missing", 0)
        total_mandatory = contract_completeness.get("total_mandatory", 0)
        
        lines.append(f"Document Classification: {doc_type.upper()}")
        lines.append(f"Completeness Score: {filled_pct:.1f}%")
        lines.append(f"Filled Clauses: {contract_completeness.get('mandatory_filled', 0)} / {total_mandatory}")
        lines.append(f"Blank Clauses: {contract_completeness.get('mandatory_blank', 0)} / {total_mandatory}")
        lines.append(f"Missing Clauses: {missing_count} / {total_mandatory}")
        lines.append("")
        
        if doc_type == "template":
            lines.append("This contract has been classified as a TEMPLATE or INCOMPLETE contract.")
            lines.append("Many programme-critical clauses are missing or blank, indicating this")
            lines.append("document may not be ready for active project use.")
        elif doc_type == "partial":
            lines.append("This contract has been classified as PARTIALLY COMPLETE.")
            lines.append("Some programme-critical clauses are filled, but others remain blank or missing.")
        elif doc_type == "complete":
            lines.append("This contract has been classified as COMPLETE.")
            lines.append("Most programme-critical clauses have been filled with actual values.")
        lines.append("")
        
        # Programme-Critical Clauses
        lines.append("PROGRAMME-CRITICAL CLAUSES STATUS")
        lines.append("-" * 80)
        
        filled_clauses = []
        blank_clauses = []
        missing_clauses = []
        
        for clause_num, clause_data in sorted(extracted_clauses.items()):
            status = clause_data.get("status", "unknown")
            title = clause_data.get("title", "Unknown")
            value = clause_data.get("value", "")
            
            if status == "filled":
                filled_clauses.append(f"  {clause_num} - {title}: {value[:100] if value else 'N/A'}")
            elif status == "blank":
                blank_clauses.append(f"  {clause_num} - {title}")
            else:
                missing_clauses.append(f"  {clause_num} - {title}")
        
        if filled_clauses:
            lines.append("FILLED CLAUSES:")
            lines.extend(filled_clauses)
            lines.append("")
        
        if blank_clauses:
            lines.append("BLANK CLAUSES (present but empty):")
            lines.extend(blank_clauses)
            lines.append("")
        
        if missing_clauses:
            lines.append("MISSING CLAUSES (not found in contract):")
            lines.extend(missing_clauses)
            lines.append("")
        
        # Scope Summary
        lines.append("SCOPE SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Scope Items Identified: {len(scope_items)}")
        lines.append(f"Constraints Identified: {len(constraints)}")
        lines.append(f"Milestones Identified: {len(milestones)}")
        lines.append("")
        
        # Risks and Recommendations
        lines.append("RISKS AND RECOMMENDATIONS")
        lines.append("-" * 80)
        
        if missing_count > 0:
            lines.append(f"RISK: {missing_count} programme-critical clause(s) are missing from the contract.")
            lines.append("This may indicate an incomplete contract or extraction issues.")
            lines.append("RECOMMENDATION: Review the contract document to locate missing clauses.")
            lines.append("")
        
        if blank_pct > 50.0:
            lines.append(f"RISK: {blank_pct:.1f}% of clauses are blank, indicating an incomplete contract.")
            lines.append("RECOMMENDATION: Complete all blank clause fields before project commencement.")
            lines.append("")
        
        if filled_pct < 50.0:
            lines.append(f"RISK: Low completeness score ({filled_pct:.1f}%) may indicate significant project risks.")
            lines.append("RECOMMENDATION: Prioritize filling critical clauses (dates, deadlines, payment terms).")
            lines.append("")
        
        if not missing_clauses and not blank_clauses:
            lines.append("The contract appears to be in good condition with all programme-critical")
            lines.append("clauses present and filled. Proceed with standard project planning processes.")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def generate_report_from_json(self, json_data: Dict[str, Any]) -> bytes:
        """
        Generate PDF report from JSON data using ReportGenerator.
        
        Args:
            json_data: Analysis JSON output from /api/analyze_contract
            
        Returns:
            bytes: PDF file as bytes
        """
        generator = ReportGenerator()
        return generator.generate_pdf(json_data)
