"""
XER Loader for Primavera P6 files.

Parses Primavera XER file and extracts:
- Activities
- Calendars
- WBS
- Logic (relationships)
- Constraints
- Normalizes dates to ISO8601
"""

import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path


class XERLoader:
    """
    Loads and parses Primavera P6 XER files.
    """
    
    def __init__(self):
        """Initialize XER loader."""
        pass
    
    def load_xer(self, xer_path: str) -> Dict[str, Any]:
        """
        Load XER file and extract structured data.
        
        Args:
            xer_path: Path to XER file
            
        Returns:
            Dictionary with:
            {
                "activities": [...],
                "calendars": [...],
                "wbs": [...],
                "logic": [...],
                "constraints": [...],
                "metadata": {...}
            }
        """
        if not Path(xer_path).exists():
            raise FileNotFoundError(f"XER file not found: {xer_path}")
        
        with open(xer_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse XER format (Primavera P6 uses TASK table; fallback to ACTIVITY)
        activities = self._parse_task_table(content)
        if not activities:
            activities = self._parse_activities(content)
        calendars = self._parse_calendars(content)
        wbs = self._parse_wbs(content)
        logic = self._parse_logic(content)
        constraints = self._parse_constraints(content)
        metadata = self._parse_metadata(content)
        if not metadata.get("data_date") and activities:
            metadata["data_date"] = self._earliest_start_from_activities(activities)
        
        return {
            "activities": activities,
            "calendars": calendars,
            "wbs": wbs,
            "logic": logic,
            "constraints": constraints,
            "metadata": metadata,
        }
    
    def _parse_task_table(self, content: str) -> List[Dict[str, Any]]:
        """Parse TASK table from XER (%T TASK, %F header, %R rows). Used for programme vs contract comparison."""
        activities = []
        # Section runs from %T\tTASK until next %T\t or %E
        task_match = re.search(r'%T\s+TASK\s*\n(.*?)(?=%T\s+|%E\s*\n|$)', content, re.DOTALL)
        if not task_match:
            return activities
        section = task_match.group(1)
        lines = [ln for ln in section.split('\n') if ln.strip()]
        if not lines:
            return activities
        # First line is %F\tcol1\tcol2\t...
        header_line = lines[0]
        if not header_line.startswith('%F'):
            return activities
        headers = header_line.split('\t')[1:]
        headers = [h.strip() for h in headers if h.strip()]
        for line in lines[1:]:
            if not line.startswith('%R'):
                continue
            values = line.split('\t')[1:]
            if len(values) < len(headers):
                continue
            row = {}
            for i, h in enumerate(headers):
                if i < len(values):
                    row[h] = values[i].strip()
            # Map to common activity shape and normalize dates
            date_fields = [
                'early_start_date', 'early_end_date', 'act_start_date', 'act_end_date',
                'target_start_date', 'target_end_date', 'late_start_date', 'late_end_date'
            ]
            for f in date_fields:
                if f in row and row[f]:
                    row[f] = self._normalize_date(row[f])
            start = row.get('early_start_date') or row.get('act_start_date') or row.get('target_start_date')
            end = row.get('early_end_date') or row.get('act_end_date') or row.get('target_end_date')
            row['start_date'] = start
            row['finish_date'] = end
            row['task_id'] = row.get('task_id', '')
            row['task_name'] = row.get('task_name', '')
            row['task_type'] = row.get('task_type', '')
            row['calendar_id'] = row.get('clndr_id', '')
            row['total_float'] = row.get('total_float_hr_cnt')
            if row.get('total_float_hr_cnt') is not None:
                try:
                    row['total_float'] = float(row['total_float_hr_cnt'])
                except (TypeError, ValueError):
                    pass
            activities.append(row)
        return activities
    
    def _earliest_start_from_activities(self, activities: List[Dict[str, Any]]) -> Optional[str]:
        """Earliest start date across activities for data_date fallback."""
        out = None
        for a in activities:
            s = a.get('start_date') or a.get('early_start_date') or a.get('act_start_date')
            if s and (out is None or s < out):
                out = s
        return out
    
    def _parse_activities(self, content: str) -> List[Dict[str, Any]]:
        """Parse ACTIVITY section (legacy XER)."""
        activities = []
        activity_match = re.search(r'%T\tACTIVITY(.*?)%E\tACTIVITY', content, re.DOTALL)
        if not activity_match:
            return activities
        activity_section = activity_match.group(1)
        lines = activity_section.split('\n')
        if len(lines) < 2:
            return activities
        headers = lines[0].split('\t')
        for line in lines[1:]:
            if not line.strip():
                continue
            values = line.split('\t')
            if len(values) < len(headers):
                continue
            activity = {}
            for i, header in enumerate(headers):
                if i < len(values):
                    activity[header.strip()] = values[i].strip()
            for date_field in ['start_date', 'finish_date', 'actual_start', 'actual_finish']:
                if date_field in activity:
                    activity[date_field] = self._normalize_date(activity[date_field])
            activities.append(activity)
        return activities
    
    def _parse_calendars(self, content: str) -> List[Dict[str, Any]]:
        """Parse CALENDAR table (%F header, %R rows) for programme vs contract (e.g. weather)."""
        calendars = []
        cal_match = re.search(r'%T\s+CALENDAR\s*\n(.*?)(?=%T\s+|%E\s*\n|$)', content, re.DOTALL)
        if not cal_match:
            return calendars
        section = cal_match.group(1)
        lines = [ln for ln in section.split('\n') if ln.strip()]
        if len(lines) < 2 or not lines[0].startswith('%F'):
            return calendars
        headers = [h.strip() for h in lines[0].split('\t')[1:] if h.strip()]
        for line in lines[1:]:
            if not line.startswith('%R'):
                continue
            values = line.split('\t')[1:]
            if len(values) < len(headers):
                continue
            row = dict(zip(headers, values))
            calendars.append({
                "clndr_id": row.get("clndr_id", "").strip(),
                "clndr_name": row.get("clndr_name", "").strip(),
            })
        return calendars
    
    def _parse_wbs(self, content: str) -> List[Dict[str, Any]]:
        """Parse PROJWBS from XER: wbs_id, parent_wbs_id, wbs_name for WBS path building."""
        wbs = []
        wbs_match = re.search(r'%T\s+PROJWBS\s*\n(.*?)%E\s+PROJWBS', content, re.DOTALL)
        if not wbs_match:
            return wbs
        section = wbs_match.group(1)
        lines = [ln for ln in section.split('\n') if ln.strip()]
        if len(lines) < 2 or not lines[0].startswith('%F'):
            return wbs
        headers = [h.strip() for h in lines[0].split('\t')[1:] if h.strip()]
        for line in lines[1:]:
            if not line.startswith('%R'):
                continue
            values = line.split('\t')[1:]
            if len(values) < len(headers):
                continue
            row = dict(zip(headers, values))
            wbs_id = (row.get('wbs_id') or row.get('proj_node_id') or '').strip()
            wbs_name = (row.get('wbs_name') or row.get('name') or '').strip()
            parent_wbs_id = (row.get('parent_wbs_id') or '').strip()
            if wbs_id or wbs_name:
                wbs.append({
                    'wbs_id': wbs_id,
                    'parent_wbs_id': parent_wbs_id,
                    'wbs_name': wbs_name,
                })
        return wbs
    
    def _parse_logic(self, content: str) -> List[Dict[str, Any]]:
        """Parse TASKPRED (%F header, %R rows) into logic with pred_task_id, succ_task_id."""
        logic = []
        pred_match = re.search(r'%T\s+TASKPRED\s*\n(.*?)(?=%T\s+|%E\s*\n|$)', content, re.DOTALL)
        if not pred_match:
            return logic
        section = pred_match.group(1)
        lines = [ln for ln in section.split('\n') if ln.strip()]
        if len(lines) < 2 or not lines[0].startswith('%F'):
            return logic
        headers = [h.strip() for h in lines[0].split('\t')[1:] if h.strip()]
        for line in lines[1:]:
            if not line.startswith('%R'):
                continue
            values = line.split('\t')[1:]
            if len(values) < len(headers):
                continue
            row = dict(zip(headers, values))
            logic.append({
                "pred_task_id": row.get("pred_task_id", "").strip(),
                "succ_task_id": row.get("task_id", "").strip(),
                "task_id": row.get("task_id", "").strip(),
                "pred_type": row.get("pred_type", "").strip(),
            })
        return logic
    
    def _parse_constraints(self, content: str) -> List[Dict[str, Any]]:
        """Parse constraints from XER content."""
        constraints = []
        
        # Find TASK section for constraints
        # (Simplified for now)
        return constraints
    
    def _parse_metadata(self, content: str) -> Dict[str, Any]:
        """Parse metadata from XER (PROJECT table, ERMHDR, data date)."""
        metadata = {}
        # PROJECT table: %T PROJECT, %F col1\tcol2..., %R val1\tval2...
        proj_match = re.search(r'%T\s+PROJECT\s*\n(.*?)(?=%T\s+|%E\s*\n|$)', content, re.DOTALL)
        if proj_match:
            section = proj_match.group(1)
            lines = [ln for ln in section.split('\n') if ln.strip()]
            if len(lines) >= 2 and lines[0].startswith('%F') and lines[1].startswith('%R'):
                headers = lines[0].split('\t')[1:]
                values = lines[1].split('\t')[1:]
                proj = dict(zip(headers, values))
                for k, v in proj.items():
                    if v:
                        proj[k] = v.strip()
                metadata['plan_start_date'] = self._normalize_date(proj.get('plan_start_date', ''))
                metadata['plan_end_date'] = self._normalize_date(proj.get('plan_end_date', ''))
                metadata['data_date'] = metadata.get('data_date') or self._normalize_date(
                    proj.get('last_tasksum_date') or proj.get('scd_end_date') or ''
                )
        # ERMHDR line: ERMHDR	22.12	2026-01-28	Project	...
        erm = re.search(r'ERMHDR\t[^\t]+\t([^\t]+)', content)
        if erm and not metadata.get('data_date'):
            metadata['data_date'] = self._normalize_date(erm.group(1).strip())
        if not metadata.get('data_date'):
            data_date_match = re.search(r'%F\tDATA_DATE\t(.*?)\n', content)
            if data_date_match:
                metadata['data_date'] = self._normalize_date(data_date_match.group(1).strip())
        return metadata
    
    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date to ISO8601 (date only for comparison with contract)."""
        if not date_str or str(date_str).strip() in ('', 'None', 'NULL'):
            return None
        date_str = str(date_str).strip()
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y%m%d',
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:19].rstrip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                continue
        return date_str[:10] if len(date_str) >= 10 else date_str
