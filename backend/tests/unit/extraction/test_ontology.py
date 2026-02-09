"""
Test script for EngineeringOntology class with realistic engineering test subjects.

Run this script to test all ontology functions:
    python test_ontology.py
"""

from app.services.extraction.core.ontology import EngineeringOntology


def test_abbreviation_expansion():
    """Test abbreviation expansion with realistic engineering text."""
    print("=" * 60)
    print("TEST 1: Abbreviation Expansion")
    print("=" * 60)
    
    # Realistic engineering text samples
    test_subjects = [
        # Multi-word patterns
        "PC unit installation",
        "MS pipe network",
        "SS pipe for drainage",
        "RC wall construction",
        "RC slab at chainage 100+000",
        "HDPE pipe installation",
        
        # Standalone abbreviations
        "RC structure",
        "WRC tank",
        "GI pipe",
        "MS beam",
        "SS fittings",
        "UB section",
        "UC column",
        
        # Hyphenated
        "RC-wall at Ch 50+200",
        "MS-pipe system",
        "SS-bracket mounting",
        
        # Parentheses
        "Install (RC) culvert",
        "Use (PC) units",
        "Supply (MS) pipe",
        
        # With numbers
        "RW1 and RW2",
        "MH1, MH2, MH3",
        "CB-100 installation",
        
        # Mixed contexts
        "PC unit and MS pipe network",
        "RC-wall with SS brackets",
        "(RC) culvert at (PC) location",
        
        # Should NOT expand (false positives)
        "access road construction",
        "account for variations",
        "accurate measurement",
    ]
    
    print("Testing abbreviation expansion on realistic engineering text:\n")
    for text in test_subjects:
        result = EngineeringOntology.expand_abbreviations(text)
        print(f"  '{text}'")
        print(f"  -> '{result}'\n")


def test_action_normalization():
    """Test action verb normalization with realistic phrases."""
    print("=" * 60)
    print("TEST 2: Action Normalization")
    print("=" * 60)
    
    # Realistic engineering action phrases
    test_subjects = [
        # Installation actions
        "Installing PC units",
        "Placement of MS pipe",
        "Fit SS brackets",
        "Mount RC panels",
        "Fix GI pipes",
        "Erect steel structure",
        
        # Earthworks
        "Excavate foundation",
        "Dig trench",
        "Cut slope",
        "Fill embankment",
        "Backfill around pipe",
        "Compact soil",
        
        # Construction
        "Construct bridge",
        "Build retaining wall",
        "Form concrete",
        "Pour RC slab",
        "Cast in situ",
        
        # Removal
        "Remove existing structure",
        "Demolish building",
        "Strip topsoil",
        "Clear vegetation",
        
        # Testing
        "Test pipe system",
        "Inspect structure",
        "Verify compliance",
        
        # Mixed/complex
        "Installing, placement, and construction",
        "Excavation and backfilling operations",
        "Removal and disposal of materials",
    ]
    
    print("Testing action normalization on realistic engineering phrases:\n")
    for text in test_subjects:
        result = EngineeringOntology.normalize_actions(text)
        print(f"  '{text}'")
        print(f"  -> '{result}'\n")


def test_discipline_detection():
    """Test discipline detection with realistic scope descriptions."""
    print("=" * 60)
    print("TEST 3: Discipline Detection (Single String)")
    print("=" * 60)
    
    # Realistic engineering scope descriptions
    test_subjects = [
        # Structures
        "RC culvert construction",
        "Bridge deck installation",
        "Retaining wall with RC panels",
        "Steel beam and column erection",
        "Foundation piling works",
        
        # Highways
        "Pavement construction",
        "Carriageway resurfacing",
        "Footway and kerb installation",
        "Asphalt and bitumen works",
        "Roadway improvements",
        
        # Drainage
        "Culvert and drainage pipe",
        "Manhole installation",
        "Catch basin and gully",
        "Storm water system",
        "Foul water sewer",
        
        # Earthworks
        "Excavation and cut slope",
        "Embankment construction",
        "Soil compaction",
        "Earth moving operations",
        "Grading and backfill",
        
        # M&E
        "Electrical installation",
        "Mechanical systems",
        "Lighting and power",
        "Cable and conduit",
        "M&E services",
        
        # Utilities
        "Water main installation",
        "Gas main and service",
        "Telecom duct",
        "Utility corridor",
        "Underground services",
        
        # Temporary works
        "Temporary shoring",
        "Scaffold erection",
        "Falsework installation",
        "Site establishment",
        
        # Mixed/complex
        "RC culvert with drainage pipe and access road",
        "Bridge construction with M&E services",
        "Highway works including pavement and drainage",
    ]
    
    print("Testing discipline detection on realistic scope descriptions:\n")
    for text in test_subjects:
        result = EngineeringOntology.detect_discipline(text)
        print(f"  '{text}'")
        print(f"  -> '{result}'\n")


def test_asset_detection():
    """Test asset detection with realistic asset descriptions."""
    print("=" * 60)
    print("TEST 4: Asset Detection (Canonicalized)")
    print("=" * 60)
    
    # Realistic asset descriptions
    test_subjects = [
        # Culverts
        "Box culvert installation",
        "Pipe culvert at chainage 100+000",
        "Multi-cell culvert",
        "Arch culvert construction",
        
        # Bridges
        "Bridge deck",
        "Footbridge installation",
        "Overbridge construction",
        "Viaduct structure",
        
        # Retaining walls
        "Retaining wall",
        "Gabion wall",
        "Reinforced earth wall",
        "Concrete retaining wall",
        "Masonry wall",
        
        # Drainage/manholes
        "Manhole installation",
        "Catch basin",
        "Gully and inspection chamber",
        "Drainage chamber",
        
        # Pavement/highways
        "Pavement construction",
        "Carriageway resurfacing",
        "Footway and cycleway",
        "Kerb and verge",
        
        # Earthworks
        "Embankment construction",
        "Cut slope stabilization",
        "Fill slope",
        "Batter and berm",
        
        # Utilities
        "Water main",
        "Gas main installation",
        "Telecom duct",
        "Service duct",
        
        # Mixed
        "Culverts and bridges",
        "Retaining wall with drainage",
        "Pavement and carriageway",
        "Manholes and catch basins",
    ]
    
    print("Testing asset detection on realistic asset descriptions:\n")
    for text in test_subjects:
        result = EngineeringOntology.detect_assets(text)
        print(f"  '{text}'")
        print(f"  -> {result}\n")


def test_material_detection():
    """Test material detection with realistic material descriptions."""
    print("=" * 60)
    print("TEST 5: Material Detection (Canonicalized)")
    print("=" * 60)
    
    # Realistic material descriptions
    test_subjects = [
        # Concrete
        "Reinforced concrete",
        "RC structure",
        "Precast concrete units",
        "Plain cement concrete",
        "Water retaining concrete",
        
        # Steel
        "Mild steel pipe",
        "MS beam",
        "Stainless steel",
        "SS fittings",
        "Steel reinforcement",
        
        # Asphalt/Bitumen
        "Asphalt concrete",
        "AC pavement",
        "Bitumen works",
        "Dense bituminous macadam",
        "DBM layer",
        
        # Plastics
        "HDPE pipe",
        "PVC conduit",
        "GRP panels",
        
        # Other materials
        "Clay pipe",
        "Brick masonry",
        "Stone aggregate",
        "Timber formwork",
        "Soil compaction",
        
        # Mixed
        "Concrete and steel",
        "RC and MS",
        "Asphalt and bitumen",
        "HDPE and PVC",
    ]
    
    print("Testing material detection on realistic material descriptions:\n")
    for text in test_subjects:
        result = EngineeringOntology.detect_materials(text)
        print(f"  '{text}'")
        print(f"  -> {result}\n")


def test_pattern_detection():
    """Test pattern detection with realistic engineering text."""
    print("=" * 60)
    print("TEST 6: Pattern Detection")
    print("=" * 60)
    
    # Realistic engineering text with patterns
    test_subjects = [
        # Chainage patterns
        "Install at Ch 123+450",
        "Work at Chainage 456+789",
        "Between Ch 100+000 and Ch 200+000",
        "At chainage 50+250",
        
        # Drawing references
        "Per DRG-100",
        "See SHT03 for details",
        "Refer to GA-200",
        "As per DRAWING-123",
        "Sheet 05 shows",
        "GEN-001 general arrangement",
        
        # Activity codes
        "Activity A10234",
        "Task 0100-STR-CH124",
        "Work item A1234",
        "Activity code B5678",
        
        # Mixed patterns
        "Install PC unit at Ch 123+450 per DRG-100, activity A10234",
        "At Chainage 200+000, see SHT05, complete activity 0200-DRN-MH01",
        "Work between Ch 100+000 and Ch 150+000, refer GA-300",
    ]
    
    print("Testing pattern detection on realistic engineering text:\n")
    for text in test_subjects:
        chainages = EngineeringOntology.detect_chainages(text)
        drawings = EngineeringOntology.detect_drawings(text)
        codes = EngineeringOntology.detect_activity_codes(text)
        
        print(f"  '{text}'")
        if chainages:
            print(f"    Chainages: {chainages}")
        if drawings:
            print(f"    Drawings: {drawings}")
        if codes:
            print(f"    Activity codes: {codes}")
        if not chainages and not drawings and not codes:
            print(f"    No patterns detected")
        print()


def test_integration():
    """Test integrated workflow on realistic scope items."""
    print("=" * 60)
    print("TEST 7: Integrated Workflow (Realistic Scope Items)")
    print("=" * 60)
    
    # Realistic NEC scope item descriptions
    test_subjects = [
        "Installing PC unit and MS pipe at Ch 123+450 per DRG-100",
        "Construct RC culvert at Chainage 200+000, refer SHT05",
        "Placement of HDPE pipe for drainage system, activity A10234",
        "Excavate and install manhole at Ch 150+250 per GA-200",
        "Construct retaining wall with RC panels, see DRG-150",
        "Install SS pipe and fittings for water main, activity B5678",
        "Pavement construction with AC and DBM layers at Ch 100+000",
        "Erect steel bridge structure, refer DRAWING-300",
        "Backfill and compact around RC culvert at Chainage 175+500",
        "Install electrical conduit and cable, per M&E drawing SHT10",
    ]
    
    print("Testing complete pipeline on realistic scope items:\n")
    for i, text in enumerate(test_subjects, 1):
        print(f"{'='*60}")
        print(f"SCOPE ITEM {i}: '{text}'")
        print(f"{'='*60}")
        
        expanded = EngineeringOntology.expand_abbreviations(text)
        print(f"After abbreviation expansion: '{expanded}'")
        
        normalized = EngineeringOntology.normalize_actions(expanded)
        print(f"After action normalization: '{normalized}'")
        
        discipline = EngineeringOntology.detect_discipline(text)
        print(f"Detected discipline: '{discipline}'")
        
        assets = EngineeringOntology.detect_assets(text)
        print(f"Detected assets: {assets}")
        
        materials = EngineeringOntology.detect_materials(text)
        print(f"Detected materials: {materials}")
        
        chainages = EngineeringOntology.detect_chainages(text)
        if chainages:
            print(f"Detected chainages: {chainages}")
        
        drawings = EngineeringOntology.detect_drawings(text)
        if drawings:
            print(f"Detected drawings: {drawings}")
        
        codes = EngineeringOntology.detect_activity_codes(text)
        if codes:
            print(f"Detected activity codes: {codes}")
        
        print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ENGINEERING ONTOLOGY TEST SUITE")
    print("=" * 60 + "\n")
    
    test_abbreviation_expansion()
    test_action_normalization()
    test_discipline_detection()
    test_asset_detection()
    test_material_detection()
    test_pattern_detection()
    test_integration()
    
    print("=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60 + "\n")
