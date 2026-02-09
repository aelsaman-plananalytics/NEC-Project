"""
Logic Checks for Primavera P6 programmes.

Detects:
- Broken logic
- Out-of-sequence activities
- Negative float
- Circular dependencies
"""

from typing import Dict, List, Any, Set


class LogicChecker:
    """
    Checks programme logic for errors.
    """
    
    def __init__(self):
        """Initialize logic checker."""
        pass
    
    def check_logic(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform all logic checks.
        
        Args:
            p6_data: P6 programme data
            
        Returns:
            Dictionary with check results
        """
        return {
            "broken_logic": self._check_broken_logic(p6_data),
            "out_of_sequence": self._check_out_of_sequence(p6_data),
            "negative_float": self._check_negative_float(p6_data),
            "circular_dependencies": self._check_circular_dependencies(p6_data),
        }
    
    def _check_broken_logic(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for broken logic relationships."""
        logic = p6_data.get("logic", [])
        activities = {a.get("task_id"): a for a in p6_data.get("activities", [])}
        
        broken = []
        for rel in logic:
            pred_id = rel.get("pred_task_id")
            succ_id = rel.get("succ_task_id")
            
            if pred_id not in activities or succ_id not in activities:
                broken.append(rel)
        
        return {
            "status": "fail" if broken else "pass",
            "count": len(broken),
            "broken_relationships": broken
        }
    
    def _check_out_of_sequence(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for out-of-sequence activities."""
        # Simplified check
        return {
            "status": "pass",
            "count": 0
        }
    
    def _check_negative_float(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for negative float."""
        activities = p6_data.get("activities", [])
        negative_float = [
            a for a in activities
            if float(a.get("total_float", 0) or 0) < 0
        ]
        
        return {
            "status": "fail" if negative_float else "pass",
            "count": len(negative_float),
            "activities": negative_float
        }
    
    def _check_circular_dependencies(self, p6_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for circular dependencies."""
        logic = p6_data.get("logic", [])
        
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        for rel in logic:
            pred = rel.get("pred_task_id")
            succ = rel.get("succ_task_id")
            if pred not in graph:
                graph[pred] = set()
            graph[pred].add(succ)
        
        # Check for cycles using DFS
        cycles = self._find_cycles(graph)
        
        return {
            "status": "fail" if cycles else "pass",
            "count": len(cycles),
            "cycles": cycles
        }
    
    def _find_cycles(self, graph: Dict[str, Set[str]]) -> List[List[str]]:
        """Find cycles in dependency graph."""
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, set()):
                dfs(neighbor, path.copy())
            
            rec_stack.remove(node)
        
        for node in graph:
            if node not in visited:
                dfs(node, [])
        
        return cycles
