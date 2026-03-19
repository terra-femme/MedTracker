"""
Structured Logger - JSON Logging
================================
Production-grade JSON logging for observability.
"""

import json
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from enum import Enum


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class StructuredLogger:
    """
    JSON-structured logger for production observability.
    
    Outputs structured JSON that can be ingested by:
    - ELK stack
    - Datadog
    - Splunk
    - CloudWatch
    """
    
    def __init__(self, name: str, min_level: LogLevel = LogLevel.INFO):
        self.name = name
        self.min_level = min_level
        self._logs_written = 0
    
    def _log(
        self,
        level: LogLevel,
        event: str,
        message: str = "",
        context: Optional[Dict] = None,
        extra: Optional[Dict] = None
    ):
        """Internal log method"""
        # Check level
        if self._level_value(level) < self._level_value(self.min_level):
            return
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": self.name,
            "level": level.value,
            "event": event,
            "message": message,
        }
        
        if context:
            log_entry["context"] = context
        
        if extra:
            log_entry["extra"] = extra
        
        # Write to stdout
        print(json.dumps(log_entry, default=str))
        self._logs_written += 1
    
    def _level_value(self, level: LogLevel) -> int:
        """Get numeric value for level comparison"""
        values = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4
        }
        return values.get(level, 1)
    
    # Public API
    def debug(self, event: str, message: str = "", context: Optional[Dict] = None):
        self._log(LogLevel.DEBUG, event, message, context)
    
    def info(self, event: str, message: str = "", context: Optional[Dict] = None):
        self._log(LogLevel.INFO, event, message, context)
    
    def warning(self, event: str, message: str = "", context: Optional[Dict] = None):
        self._log(LogLevel.WARNING, event, message, context)
    
    def error(self, event: str, message: str = "", context: Optional[Dict] = None):
        self._log(LogLevel.ERROR, event, message, context)
    
    def critical(self, event: str, message: str = "", context: Optional[Dict] = None):
        self._log(LogLevel.CRITICAL, event, message, context)
    
    # Agent-specific logging
    def log_agent_start(
        self,
        agent_name: str,
        pipeline_id: str,
        input_summary: Optional[Dict] = None
    ):
        """Log agent execution start"""
        self.info(
            event="agent.started",
            message=f"Agent {agent_name} started",
            context={
                "agent": agent_name,
                "pipeline_id": pipeline_id,
                "input_summary": input_summary or {}
            }
        )
    
    def log_agent_complete(
        self,
        agent_name: str,
        pipeline_id: str,
        duration_ms: float,
        output_summary: Optional[Dict] = None,
        success: bool = True
    ):
        """Log agent execution completion"""
        self.info(
            event="agent.completed",
            message=f"Agent {agent_name} completed in {duration_ms:.2f}ms",
            context={
                "agent": agent_name,
                "pipeline_id": pipeline_id,
                "duration_ms": duration_ms,
                "success": success,
                "output_summary": output_summary or {}
            }
        )
    
    def log_agent_error(
        self,
        agent_name: str,
        pipeline_id: str,
        error: str,
        duration_ms: float
    ):
        """Log agent execution error"""
        self.error(
            event="agent.error",
            message=f"Agent {agent_name} failed: {error}",
            context={
                "agent": agent_name,
                "pipeline_id": pipeline_id,
                "duration_ms": duration_ms,
                "error": error
            }
        )
    
    def log_safety_event(
        self,
        event_type: str,
        severity: str,
        details: Dict,
        pipeline_id: Optional[str] = None
    ):
        """Log safety-related events"""
        level = LogLevel.WARNING
        if severity in ['critical', 'emergency']:
            level = LogLevel.ERROR
        
        context = {
            "event_type": event_type,
            "severity": severity,
            "details": details
        }
        if pipeline_id:
            context["pipeline_id"] = pipeline_id
        
        self._log(
            level=level,
            event="safety.event",
            message=f"Safety event: {event_type}",
            context=context
        )
    
    def log_guardrail_triggered(
        self,
        guardrail_type: str,
        action: str,
        details: Dict,
        pipeline_id: Optional[str] = None
    ):
        """Log guardrail activation"""
        context = {
            "guardrail_type": guardrail_type,
            "action": action,
            "details": details
        }
        if pipeline_id:
            context["pipeline_id"] = pipeline_id
        
        self.warning(
            event="guardrail.triggered",
            message=f"Guardrail {guardrail_type} triggered: {action}",
            context=context
        )
    
    def get_stats(self) -> Dict:
        """Get logger statistics"""
        return {
            "logs_written": self._logs_written,
            "logger_name": self.name,
            "min_level": self.min_level.value
        }
