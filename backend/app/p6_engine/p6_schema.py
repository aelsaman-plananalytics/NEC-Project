"""
P6 Schema Definitions.
"""

from typing import Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class P6Schema:
    """Schema for P6 programme data."""
    
    @staticmethod
    def create_programme_output(
        activities: List[Dict[str, Any]],
        logic_checks: Dict[str, Any],
        nec_alignment: Dict[str, Any],
        schedule_health: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create complete programme output dictionary.
        
        Args:
            activities: List of activities
            logic_checks: Logic check results
            nec_alignment: NEC-P6 alignment results
            schedule_health: Schedule health assessment
            
        Returns:
            Complete programme output dictionary
        """
        return {
            "activities": activities,
            "logic_checks": logic_checks,
            "nec_alignment": nec_alignment,
            "schedule_health": schedule_health,
        }
