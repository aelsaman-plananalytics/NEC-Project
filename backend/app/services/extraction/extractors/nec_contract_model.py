"""
NEC Contract Data Model for structured contract representation.

Defines dataclasses and models for Contract Data Part 1, Part 2,
Schedule of Drawings, and related structures.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class Employer:
    """Employer information from Contract Data Part 1."""
    name: str = ""
    address: str = ""
    representative: str = ""


@dataclass
class ProjectManager:
    """Project Manager information."""
    name: str = ""
    address: str = ""
    representative: str = ""
    delegations: List[str] = field(default_factory=list)


@dataclass
class TimeSection:
    """Time-related contract data."""
    starting_date: str = ""
    possession_dates: Dict[str, str] = field(default_factory=dict)
    completion_date: str = ""
    taking_over: str = ""
    first_programme_submission: str = ""
    revised_programme_interval: str = ""
    delay_damages: str = ""


@dataclass
class TestingDefects:
    """Testing and defects section."""
    defects_date: str = ""
    defect_correction_period: str = ""
    landscape_maintenance_period: str = ""


@dataclass
class PaymentSection:
    """Payment terms and conditions."""
    currency: str = ""
    assessment_interval: str = ""
    payment_period: str = ""
    interest_rate: str = ""
    retention_amount: str = ""
    contract_bond_amount: str = ""
    exchange_rates: str = ""
    assessment_dates_schedule: str = ""


@dataclass
class CompensationEvents:
    """Compensation events section."""
    weather_recording_location: str = ""
    weather_measurements: List[str] = field(default_factory=list)
    weather_data_source: str = ""


@dataclass
class RisksInsurance:
    """Risks and insurance section."""
    third_party_insurance: str = ""
    employee_insurance: str = ""
    non_recoverable_rta: str = ""
    contractors_all_risks: str = ""
    additional_employer_risks: str = ""
    contractors_liability: str = ""
    liability_duration: str = ""
    kpi_reporting_interval: str = ""
    additional_insurance: str = ""


@dataclass
class DisputesTermination:
    """Disputes and termination section."""
    adjudicator_nomination_body: str = ""
    adjudication_procedure: str = ""


@dataclass
class DrawingReference:
    """Single drawing reference from Schedule of Drawings."""
    size: str = ""
    number: str = ""
    revision: str = ""
    title: str = ""
    scale: str = ""
    status: str = ""
    series: str = ""


@dataclass
class ContractorData:
    """Contract Data Part 2 - Contractor information."""
    contractor_name: str = ""
    contractor_address: str = ""
    contractor_representative: str = ""
    direct_fee_percentage: str = ""
    subcontracted_fee_percentage: str = ""
    working_areas: str = ""
    key_persons: List[Dict[str, str]] = field(default_factory=list)
    works_information_design: str = ""
    programme_identified: str = ""
    adjudicator_acceptable: str = ""
    subcontractors: List[Dict[str, str]] = field(default_factory=list)
    insurance_details: Dict[str, Any] = field(default_factory=dict)
    quality_statement_location: str = ""
    parent_company_guarantee: str = ""


@dataclass
class ScheduleOfCostComponents:
    """Schedule of Cost Components data."""
    manufacture_fabrication_rates: Dict[str, str] = field(default_factory=dict)
    manufacture_overheads_percentage: str = ""
    design_rates: Dict[str, str] = field(default_factory=dict)
    site_employee_rates: Dict[str, str] = field(default_factory=dict)
    design_overheads_percentage: str = ""
    travelling_expenses_categories: str = ""
    working_area_overheads_percentage: str = ""
    people_overheads_percentage: str = ""
    equipment_list: str = ""
    equipment_adjustment_percentage: str = ""
    other_equipment_rates: Dict[str, str] = field(default_factory=dict)
    defined_cost_design_rates: Dict[str, str] = field(default_factory=dict)
    defined_cost_design_overheads: str = ""
    defined_cost_travelling_categories: str = ""


@dataclass
class ContractDataPart1:
    """Contract Data Part 1 - Data provided by Employer."""
    general: Dict[str, Any] = field(default_factory=dict)
    contractor_responsibilities: Dict[str, Any] = field(default_factory=dict)
    time: TimeSection = field(default_factory=TimeSection)
    testing_and_defects: TestingDefects = field(default_factory=TestingDefects)
    payment: PaymentSection = field(default_factory=PaymentSection)
    compensation_events: CompensationEvents = field(default_factory=CompensationEvents)
    title: str = ""
    risks_and_insurance: RisksInsurance = field(default_factory=RisksInsurance)
    disputes_and_termination: DisputesTermination = field(default_factory=DisputesTermination)
    schedule_of_drawings: List[DrawingReference] = field(default_factory=list)


@dataclass
class ContractDataPart2:
    """Contract Data Part 2 - Data provided by Contractor."""
    contractor_data: ContractorData = field(default_factory=ContractorData)
    schedule_of_cost_components: ScheduleOfCostComponents = field(default_factory=ScheduleOfCostComponents)


@dataclass
class NECContract:
    """Complete NEC Contract structure."""
    metadata: Dict[str, Any] = field(default_factory=dict)
    contract: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        def serialize_dataclass(obj):
            if isinstance(obj, (ContractDataPart1, ContractDataPart2, ContractorData, 
                              ScheduleOfCostComponents, TimeSection, TestingDefects,
                              PaymentSection, CompensationEvents, RisksInsurance,
                              DisputesTermination, DrawingReference)):
                result = {}
                for key, value in obj.__dict__.items():
                    if isinstance(value, list):
                        result[key] = [serialize_dataclass(item) if hasattr(item, '__dict__') else item for item in value]
                    elif isinstance(value, dict):
                        result[key] = {k: serialize_dataclass(v) if hasattr(v, '__dict__') else v for k, v in value.items()}
                    elif hasattr(value, '__dict__'):
                        result[key] = serialize_dataclass(value)
                    else:
                        result[key] = value
                return result
            return obj
        
        result = {
            "metadata": self.metadata,
            "contract": {}
        }
        
        if "part_1" in self.contract:
            result["contract"]["part_1"] = serialize_dataclass(self.contract["part_1"])
        if "part_2" in self.contract:
            result["contract"]["part_2"] = serialize_dataclass(self.contract["part_2"])
        
        return result



