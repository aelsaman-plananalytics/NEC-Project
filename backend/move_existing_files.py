"""
Script to move existing output files to their correct folders.

Moves:
- analysis_*.json files → outputs/contracts/
- report_*.pdf, contract_analysis_report*.pdf → outputs/reports/
- validation_*.json files → outputs/validation/
"""

import os
import shutil
from pathlib import Path

# Base directory
base_dir = Path(__file__).parent / "app" / "outputs"

# Target directories
contracts_dir = base_dir / "contracts"
reports_dir = base_dir / "reports"
validation_dir = base_dir / "validation"

# Create target directories
contracts_dir.mkdir(parents=True, exist_ok=True)
reports_dir.mkdir(parents=True, exist_ok=True)
validation_dir.mkdir(parents=True, exist_ok=True)

# Move analysis JSON files
moved_contracts = 0
for file in base_dir.glob("analysis_*.json"):
    if file.parent == contracts_dir:
        continue  # Already in correct location
    dest = contracts_dir / file.name
    shutil.move(str(file), str(dest))
    print(f"Moved: {file.name} -> contracts/")
    moved_contracts += 1

# Move report PDF files
moved_reports = 0
for pattern in ["report_*.pdf", "contract_analysis_report*.pdf"]:
    for file in base_dir.glob(pattern):
        if file.parent == reports_dir:
            continue  # Already in correct location
        dest = reports_dir / file.name
        shutil.move(str(file), str(dest))
        print(f"Moved: {file.name} -> reports/")
        moved_reports += 1

# Move validation JSON files
moved_validation = 0
for file in base_dir.glob("validation_*.json"):
    if file.parent == validation_dir:
        continue  # Already in correct location
    dest = validation_dir / file.name
    shutil.move(str(file), str(dest))
    print(f"Moved: {file.name} -> validation/")
    moved_validation += 1

print(f"\n[FILE MIGRATION COMPLETE]")
print(f"Moved {moved_contracts} contract analysis files")
print(f"Moved {moved_reports} report files")
print(f"Moved {moved_validation} validation files")
