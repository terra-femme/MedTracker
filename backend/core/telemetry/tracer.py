"""
Simple Tracer - Performance Tracking
====================================
Lightweight tracing for agent execution timing.
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TraceSpan:
    """A single span in a trace"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    tags: Dict = field(default_factory=dict)
    
    def finish(self):
        """Mark span as complete"""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000


class SimpleTracer:
    """
    Simple tracer for tracking agent execution.
    
    Not a full distributed tracing system, but enough for:
    - Measuring agent response times
    - Identifying bottlenecks
    - Debugging slow operations
    """
    
    def __init__(self):
        self.spans: List[TraceSpan] = []
        self.current_spans: Dict[str, TraceSpan] = {}
    
    def start_span(self, name: str, tags: Optional[Dict] = None) -> TraceSpan:
        """Start a new trace span"""
        span = TraceSpan(
            name=name,
            start_time=time.time(),
            tags=tags or {}
        )
        self.current_spans[name] = span
        return span
    
    def finish_span(self, name: str):
        """Finish a span and move it to completed list"""
        if name in self.current_spans:
            span = self.current_spans.pop(name)
            span.finish()
            self.spans.append(span)
            return span.duration_ms
        return None
    
    def get_trace_summary(self) -> Dict:
        """Get summary of all traces"""
        if not self.spans:
            return {"spans": 0}
        
        durations = [s.duration_ms for s in self.spans if s.duration_ms]
        
        return {
            "total_spans": len(self.spans),
            "active_spans": len(self.current_spans),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "spans_by_name": self._group_by_name()
        }
    
    def _group_by_name(self) -> Dict:
        """Group spans by name for analysis"""
        by_name: Dict[str, List[float]] = {}
        for span in self.spans:
            if span.name not in by_name:
                by_name[span.name] = []
            if span.duration_ms:
                by_name[span.name].append(span.duration_ms)
        
        # Calculate averages
        return {
            name: {
                "count": len(durations),
                "avg_ms": sum(durations) / len(durations),
                "max_ms": max(durations),
                "min_ms": min(durations)
            }
            for name, durations in by_name.items()
        }
    
    def reset(self):
        """Clear all traces"""
        self.spans = []
        self.current_spans = {}
