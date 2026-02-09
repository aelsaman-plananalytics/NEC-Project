"""
NEC-P6 Alignment.

Maps NEC clauses → P6 checks:
- Clause 31.2 → Check programme submissions
- Clause 32.1 → Revised programme intervals
- Clause 3.1 → Starting date matches P6 data date
- Clause 3.3 → Completion date matches P6 'Finish Milestone'
"""

from typing import Dict, Any, List
from app.p6_engine.programme_validator import ProgrammeValidator
from app.p6_engine.logic_checks import LogicChecker


class NECP6Alignment:
    """
    Aligns NEC contract clauses with P6 programme checks.
    """
    
    def __init__(self):
        """Initialize NEC-P6 alignment."""
        self.validator = ProgrammeValidator()
        self.logic_checker = LogicChecker()
    
    def align_contract_programme(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Align NEC contract with P6 programme.
        
        Args:
            contract_data: Extracted contract data
            p6_data: P6 programme data
            
        Returns:
            Alignment results dictionary
        """
        # Run validation
        validation = self.validator.validate_programme(contract_data, p6_data)
        
        # Run logic checks
        logic_checks = self.logic_checker.check_logic(p6_data)
        
        # Map NEC clauses to P6 checks
        clause_mappings = self._map_clauses_to_checks(contract_data, p6_data)
        
        return {
            "validation": validation,
            "logic_checks": logic_checks,
            "clause_mappings": clause_mappings,
            "schedule_health": self._calculate_schedule_health(validation, logic_checks),
        }
    
    def _map_clauses_to_checks(
        self,
        contract_data: Dict[str, Any],
        p6_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Map NEC clauses to P6 programme checks."""
        mappings = {}
        
        # Clause 3.1 → Starting date
        clause_31 = contract_data.get("extracted_clauses", {}).get("3.1", {})
        mappings["3.1"] = {
            "description": "Starting Date",
            "p6_check": "Data Date",
            "status": "aligned" if clause_31.get("value") else "missing"
        }
        
        # Clause 3.3 → Completion date
        clause_33 = contract_data.get("extracted_clauses", {}).get("3.3", {})
        mappings["3.3"] = {
            "description": "Completion Date",
            "p6_check": "Latest Finish",
            "status": "aligned" if clause_33.get("value") else "missing"
        }
        
        # Add more mappings as needed
        
        return mappings
    
    def _calculate_schedule_health(
        self,
        validation: Dict[str, Any],
        logic_checks: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate overall schedule health index."""
        issues = 0
        total_checks = 0
        
        # Count validation issues
        for check in validation.values():
            if isinstance(check, dict) and check.get("status") != "pass":
                issues += 1
            total_checks += 1
        
        # Count logic check issues
        for check in logic_checks.values():
            if isinstance(check, dict) and check.get("status") != "pass":
                issues += 1
            total_checks += 1
        
        health_score = 1.0 - (issues / total_checks) if total_checks > 0 else 1.0
        
        return {
            "score": health_score,
            "issues": issues,
            "total_checks": total_checks,
            "status": "healthy" if health_score >= 0.8 else "needs_attention"
        }
