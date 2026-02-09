"""
Contract Section Classifier for NEC Engineering Analysis System.

Classifies contract text into different section types to determine
which lines should be processed for feature extraction and matching.
"""

import re
from typing import List, Dict, Set


class ContractClassifier:
    """
    Classifies contract text into section types.
    
    Categories:
    - scope_work: Actual construction-related work items
    - admin_general: General administrative content
    - roles: Role definitions (Employer, Contractor, Project Manager, etc.)
    - responsibilities: Responsibility assignments
    - payment: Payment terms and conditions
    - insurance: Insurance requirements
    - programme: Programme and scheduling
    - disputes: Dispute resolution procedures
    - risk_register: Risk management
    - drawings_schedule: Drawing references
    - definitions: Definition sections
    """
    
    # Keywords for scope_work (construction activities)
    SCOPE_WORK_KEYWORDS: Set[str] = {
        # Construction actions
        "construct", "construction", "constructing",
        "install", "installation", "installing",
        "demolish", "demolition", "demolishing",
        "excavate", "excavation", "excavating",
        "build", "building", "erect", "erecting",
        "lay", "laying", "place", "placing",
        "form", "forming", "cast", "casting",
        "pour", "pouring", "compact", "compacting",
        "backfill", "backfilling", "remove", "removing",
        "replace", "replacing", "upgrade", "upgrading",
        "modify", "modifying", "extend", "extending",
        "repair", "repairing", "reconstruct", "reconstructing",
        "resurface", "resurfacing", "divert", "diverting",
        "refurbish", "refurbishing",
        
        # Construction assets/materials
        "pavement", "carriageway", "footway", "kerb", "kerbs",
        "bridge", "bridges", "culvert", "culverts",
        "retaining wall", "retaining walls", "earthworks",
        "drainage", "manhole", "manholes", "pipe", "pipes",
        "ditch", "ditches", "fence", "fences",
        "guardrail", "guardrails", "lighting", "signage",
        "junction", "junctions", "crossing", "crossings",
        "access", "road", "roads", "highway", "highways",
        "pavement", "pavements", "concrete", "steel",
        "reinforced concrete", "precast", "bitumen",
        "asphalt", "macadam"
    }
    
    # Keywords for roles
    ROLES_KEYWORDS: Set[str] = {
        "employer", "contractor", "project manager", "supervisor",
        "quantity surveyor", "cdm coordinator", "adjudicator",
        "representative", "delegation", "delegations",
        "key person", "key persons", "personnel"
    }
    
    # Keywords for responsibilities
    RESPONSIBILITIES_KEYWORDS: Set[str] = {
        "responsible", "responsibility", "responsibilities",
        "liable", "liability", "obligation", "obligations",
        "duty", "duties", "must", "shall", "will",
        "ensure", "ensures", "provide", "provides"
    }
    
    # Keywords for payment
    PAYMENT_KEYWORDS: Set[str] = {
        "payment", "payments", "pay", "paid",
        "currency", "sterling", "pound", "pounds",
        "assessment", "assessments", "assessment interval",
        "payment period", "interest rate", "retention",
        "bond", "guarantee", "exchange rate", "exchange rates",
        "fee", "fees", "percentage", "cost", "costs",
        "price", "prices", "pricing"
    }
    
    # Keywords for insurance
    INSURANCE_KEYWORDS: Set[str] = {
        "insurance", "insurances", "insured", "insure",
        "third party", "employee insurance", "public liability",
        "contractors all risks", "car insurance",
        "professional indemnity", "indemnity",
        "liability", "liabilities", "cover", "coverage"
    }
    
    # Keywords for programme
    PROGRAMME_KEYWORDS: Set[str] = {
        "programme", "programmes", "programming",
        "schedule", "schedules", "scheduling",
        "starting date", "completion date", "possession",
        "delay", "delays", "time", "period", "periods",
        "deadline", "deadlines", "milestone", "milestones",
        "revised programme", "first programme"
    }
    
    # Keywords for disputes
    DISPUTES_KEYWORDS: Set[str] = {
        "dispute", "disputes", "disagreement", "disagreements",
        "adjudication", "adjudicator", "adjudicators",
        "arbitration", "arbitrator", "arbitrators",
        "mediation", "mediator", "mediators",
        "termination", "terminate", "terminated",
        "law", "legal", "jurisdiction"
    }
    
    # Keywords for risk register
    RISK_REGISTER_KEYWORDS: Set[str] = {
        "risk", "risks", "risk register", "risk management",
        "hazard", "hazards", "safety", "health and safety",
        "cdm", "construction design management",
        "method statement", "method statements"
    }
    
    # Keywords for drawings schedule
    DRAWINGS_SCHEDULE_KEYWORDS: Set[str] = {
        "drawing", "drawings", "schedule of drawings",
        "schedule a", "schedule b", "drg", "drgs",
        "sheet", "sheets", "revision", "revisions",
        "scale", "scales", "elw", "series"
    }
    
    # Keywords for definitions
    DEFINITIONS_KEYWORDS: Set[str] = {
        "definition", "definitions", "defined", "define",
        "means", "meaning", "meanings", "term", "terms",
        "abbreviation", "abbreviations", "acronym", "acronyms"
    }
    
    # General admin keywords (fallback)
    ADMIN_KEYWORDS: Set[str] = {
        "employer", "adjudicator", "insurance", "currency",
        "payment", "supervisor", "cdm coordinator",
        "project manager", "contractor", "contract",
        "agreement", "clause", "clauses", "section", "sections"
    }
    
    @staticmethod
    def detect_section_type(text: str) -> str:
        """
        Detect the section type of contract text.
        
        Classification rules:
        1. If text contains construction keywords → "scope_work"
        2. If text contains role keywords → "roles"
        3. If text contains responsibility keywords → "responsibilities"
        4. If text contains payment keywords → "payment"
        5. If text contains insurance keywords → "insurance"
        6. If text contains programme keywords → "programme"
        7. If text contains dispute keywords → "disputes"
        8. If text contains risk register keywords → "risk_register"
        9. If text contains drawings schedule keywords → "drawings_schedule"
        10. If text contains definition keywords → "definitions"
        11. If text contains admin keywords → "admin_general"
        12. Otherwise → "admin_general" (default)
        
        Args:
            text: Contract text to classify
            
        Returns:
            str: Section type category
        """
        if not text or not text.strip():
            return "admin_general"
        
        text_lower = text.lower()
        
        # Check for scope_work first (construction activities)
        # This is the most important classification
        scope_keywords_found = [
            keyword for keyword in ContractClassifier.SCOPE_WORK_KEYWORDS
            if keyword in text_lower
        ]
        if scope_keywords_found:
            return "scope_work"
        
        # Check for specific admin categories
        if any(keyword in text_lower for keyword in ContractClassifier.ROLES_KEYWORDS):
            return "roles"
        
        if any(keyword in text_lower for keyword in ContractClassifier.RESPONSIBILITIES_KEYWORDS):
            return "responsibilities"
        
        if any(keyword in text_lower for keyword in ContractClassifier.PAYMENT_KEYWORDS):
            return "payment"
        
        if any(keyword in text_lower for keyword in ContractClassifier.INSURANCE_KEYWORDS):
            return "insurance"
        
        if any(keyword in text_lower for keyword in ContractClassifier.PROGRAMME_KEYWORDS):
            return "programme"
        
        if any(keyword in text_lower for keyword in ContractClassifier.DISPUTES_KEYWORDS):
            return "disputes"
        
        if any(keyword in text_lower for keyword in ContractClassifier.RISK_REGISTER_KEYWORDS):
            return "risk_register"
        
        if any(keyword in text_lower for keyword in ContractClassifier.DRAWINGS_SCHEDULE_KEYWORDS):
            return "drawings_schedule"
        
        if any(keyword in text_lower for keyword in ContractClassifier.DEFINITIONS_KEYWORDS):
            return "definitions"
        
        # Check for general admin keywords
        if any(keyword in text_lower for keyword in ContractClassifier.ADMIN_KEYWORDS):
            return "admin_general"
        
        # Default to admin_general
        return "admin_general"
    
    @staticmethod
    def is_scope_work(text: str) -> bool:
        """
        Check if text is scope_work (construction-related).
        
        Args:
            text: Contract text to check
            
        Returns:
            bool: True if text is scope_work, False otherwise
        """
        return ContractClassifier.detect_section_type(text) == "scope_work"
    
    @staticmethod
    def is_admin(text: str) -> bool:
        """
        Check if text is administrative (not scope_work).
        
        Args:
            text: Contract text to check
            
        Returns:
            bool: True if text is administrative, False otherwise
        """
        section_type = ContractClassifier.detect_section_type(text)
        return section_type != "scope_work"



