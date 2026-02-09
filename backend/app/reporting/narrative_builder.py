"""
Narrative Builder for Professional Reports.

Builds structured narrative content for reports.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class NarrativeBuilder:
    """
    Builds professional narrative content for reports.
    """
    
    def __init__(self):
        """Initialize narrative builder."""
        pass
    
    def build_narrative(
        self,
        extraction_data: Dict[str, Any],
        programme_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build complete narrative structure.
        
        Args:
            extraction_data: Contract extraction data
            programme_data: Optional P6 programme data
            
        Returns:
            Dictionary with narrative sections
        """
        return {
            "executive_summary": self._build_executive_summary(extraction_data),
            "contract_overview": self._build_contract_overview(extraction_data),
            "completeness_assessment": self._build_completeness_assessment(extraction_data),
            "risk_analysis": self._build_risk_analysis(extraction_data),
            "recommendations": self._build_recommendations(extraction_data),
            "programme_compliance": self._build_programme_compliance(programme_data) if programme_data else None,
        }
    
    def _build_executive_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build executive summary section."""
        completeness = data.get("contract_completeness", {})
        clauses = data.get("extracted_clauses", {})
        
        doc_type = completeness.get("document_type", "unknown")
        filled_pct = completeness.get("filled_percentage", 0.0)
        missing = completeness.get("mandatory_missing", 0)
        total = completeness.get("total_mandatory", 0)
        
        # Identify key missing clauses
        missing_clauses = []
        for clause_num in ["3.1", "3.3", "3.7", "5.5"]:
            clause = clauses.get(clause_num, {})
            if clause.get("status") in ["missing", "blank"]:
                missing_clauses.append(clause_num)
        
        return {
            "document_type": doc_type,
            "completeness_score": filled_pct,
            "missing_clauses": missing_clauses,
            "summary": f"This report provides a structured analysis of the NEC Contract Data. "
                      f"The document is classified as {doc_type.upper()} with {filled_pct:.1f}% completeness. "
                      f"{missing} of {total} mandatory clauses are missing."
        }
    
    def _build_contract_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build contract overview section."""
        metadata = data.get("metadata", {})
        clauses = data.get("extracted_clauses", {})
        
        # Extract key dates
        dates = {
            "starting": clauses.get("3.1", {}).get("value", "Not Provided"),
            "completion": clauses.get("3.3", {}).get("value", "Not Provided"),
            "possession": clauses.get("3.2", {}).get("value", "Not Provided"),
        }
        
        # Payment terms
        payment = {
            "assessment_interval": clauses.get("5.2", {}).get("value", "Not Provided"),
            "payment_period": clauses.get("5.3", {}).get("value", "Not Provided"),
            "retention": clauses.get("5.5", {}).get("value", "Not Provided"),
        }
        
        # Weather data
        weather = {
            "location": clauses.get("6.1", {}).get("value", "Not Provided"),
            "measurement": clauses.get("6.2", {}).get("value", "Not Provided"),
        }
        
        # Defects
        defects = {
            "defects_date": clauses.get("4.1", {}).get("value", "Not Provided"),
            "correction_period": clauses.get("4.2", {}).get("value", "Not Provided"),
        }
        
        return {
            "dates": dates,
            "payment_terms": payment,
            "weather_data": weather,
            "defects": defects,
            "metadata": {
                "filename": metadata.get("filename", "Unknown"),
                "total_pages": metadata.get("total_pages", 0),
            }
        }
    
    def _build_completeness_assessment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build completeness assessment section."""
        completeness = data.get("contract_completeness", {})
        clauses = data.get("extracted_clauses", {})
        
        # Build completeness table
        completeness_table = []
        for clause_num in sorted(clauses.keys()):
            clause = clauses[clause_num]
            completeness_table.append({
                "clause": clause_num,
                "title": clause.get("title", "N/A"),
                "status": clause.get("status", "unknown"),
            })
        
        return {
            "filled_percentage": completeness.get("filled_percentage", 0.0),
            "missing_clauses": completeness.get("missing_fields", []),
            "blank_clauses": completeness.get("blank_fields", []),
            "completeness_table": completeness_table,
            "placeholder_detection": {
                "count": len(completeness.get("blank_fields", [])),
                "clauses": completeness.get("blank_fields", [])
            }
        }
    
    def _build_risk_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build risk analysis section."""
        clauses = data.get("extracted_clauses", {})
        completeness = data.get("contract_completeness", {})
        
        critical_risks = []
        moderate_risks = []
        observations = []
        
        # Check for critical missing clauses
        critical_clauses = ["3.1", "3.3", "3.7", "5.5"]
        for clause_num in critical_clauses:
            clause = clauses.get(clause_num, {})
            if clause.get("status") in ["missing", "blank"]:
                critical_risks.append({
                    "clause": clause_num,
                    "risk": f"Missing {clause.get('title', clause_num)} prevents proper programme planning"
                })
        
        # Check for moderate risks
        moderate_clauses = ["3.5", "3.6", "4.2"]
        for clause_num in moderate_clauses:
            clause = clauses.get(clause_num, {})
            if clause.get("status") in ["missing", "blank"]:
                moderate_risks.append({
                    "clause": clause_num,
                    "risk": f"Missing {clause.get('title', clause_num)} creates uncertainty"
                })
        
        # Observations
        if completeness.get("is_template", False):
            observations.append("Contract appears to be a template, not a completed contract")
        
        if completeness.get("filled_percentage", 0) < 50:
            observations.append("Low completeness score indicates significant gaps")
        
        return {
            "critical_risks": critical_risks,
            "moderate_risks": moderate_risks,
            "observations": observations,
        }
    
    def _build_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build recommendations section."""
        completeness = data.get("contract_completeness", {})
        clauses = data.get("extracted_clauses", {})
        
        recommendations = {
            "legal": [],
            "programme_management": [],
            "risk_management": [],
        }
        
        # Legal recommendations
        if clauses.get("3.1", {}).get("status") in ["missing", "blank"]:
            recommendations["legal"].append("Populate Starting Date (3.1) - required for contract validity")
        
        if clauses.get("3.7", {}).get("status") in ["missing", "blank"]:
            recommendations["legal"].append("Specify Delay Damages (3.7) - critical for risk allocation")
        
        # Programme management recommendations
        if clauses.get("3.5", {}).get("status") in ["missing", "blank"]:
            recommendations["programme_management"].append("Define First Programme Submission requirement (3.5)")
        
        if clauses.get("3.6", {}).get("status") in ["missing", "blank"]:
            recommendations["programme_management"].append("Specify Revised Programme Interval (3.6)")
        
        # Risk management recommendations
        if completeness.get("filled_percentage", 0) < 80:
            recommendations["risk_management"].append("Complete all mandatory clauses to reduce project risk")
        
        if clauses.get("6.1", {}).get("status") in ["missing", "blank"]:
            recommendations["risk_management"].append("Provide Weather Recording Location (6.1) for compensation events")
        
        return recommendations
    
    def _build_programme_compliance(self, programme_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build programme compliance section."""
        if not programme_data:
            return None
        
        alignment = programme_data.get("nec_alignment", {})
        validation = alignment.get("validation", {})
        logic_checks = programme_data.get("logic_checks", {})
        schedule_health = programme_data.get("schedule_health", {})
        
        return {
            "nec_31_32_alignment": {
                "status": validation.get("overall_status", "unknown"),
                "details": validation
            },
            "critical_path": {
                "status": "analyzed",
                "issues": logic_checks.get("negative_float", {}).get("count", 0)
            },
            "missing_logic": {
                "count": logic_checks.get("broken_logic", {}).get("count", 0)
            },
            "schedule_quality_index": schedule_health.get("score", 0.0),
        }
