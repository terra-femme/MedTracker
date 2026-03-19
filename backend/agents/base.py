"""
BaseAgent - Foundation for All Agents
=====================================
Provides common functionality:
- Guardrail integration
- Telemetry logging
- Cost tracking
- Error handling
- Performance measurement
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone

# Import guardrails
from ..core.guardrails import (
    PIIDetector,
    MedicalContentFilter,
    ResponseValidator,
    SafetyFlag,
    PHIDetectionResult,
    ContentFilterResult,
    ValidationResult,
)
from ..core.telemetry import StructuredLogger
from ..core.metering import TokenCounter


class AgentInput(BaseModel):
    """Standardized input to any agent"""
    query: str = Field(..., description="User query or instruction")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    conversation_history: List[Dict] = Field(default_factory=list, description="Previous messages")
    user_medications: List[Dict] = Field(default_factory=list, description="User's medications")
    allergies: List[str] = Field(default_factory=list, description="User's allergies")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    class Config:
        arbitrary_types_allowed = True


class AgentOutput(BaseModel):
    """Standardized output from any agent"""
    success: bool = Field(..., description="Whether processing succeeded")
    response: str = Field(..., description="Agent's response")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    safety_flags: List[SafetyFlag] = Field(default_factory=list, description="Safety alerts")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    processing_time_ms: float = Field(default=0.0, description="Processing time")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent_name: str = Field(default="unknown", description="Name of the agent")
    
    class Config:
        arbitrary_types_allowed = True


class BaseAgent(ABC):
    """
    Base class for all MedTracker agents.
    
    Features:
    - Automatic guardrail application
    - Structured logging
    - Cost tracking
    - Performance measurement
    - Error handling with fallbacks
    """
    
    name: str = "base_agent"
    description: str = "Base agent - override in subclass"
    
    def __init__(
        self,
        telemetry: Optional[StructuredLogger] = None,
        cost_meter: Optional[TokenCounter] = None,
        enable_guardrails: bool = True,
        enable_logging: bool = True
    ):
        self.telemetry = telemetry or StructuredLogger(self.name)
        self.cost_meter = cost_meter or TokenCounter()
        self.enable_guardrails = enable_guardrails
        self.enable_logging = enable_logging
        
        # Guardrail components
        self.pii_detector = PIIDetector()
        self.content_filter = MedicalContentFilter()
        self.validator = ResponseValidator()
        
        # Statistics
        self.call_count = 0
        self.error_count = 0
        self.total_processing_time_ms = 0.0
    
    async def run(self, input_data: AgentInput) -> AgentOutput:
        """
        Execute the agent with full instrumentation.
        
        This is the main entry point - don't override this,
        override _process() instead.
        """
        start_time = time.time()
        self.call_count += 1
        
        # Generate session ID if not provided
        pipeline_id = input_data.session_id or str(uuid.uuid4())
        
        # Log start
        if self.enable_logging:
            self.telemetry.log_agent_start(
                agent_name=self.name,
                pipeline_id=pipeline_id,
                input_summary=self._summarize_input(input_data)
            )
        
        try:
            # === GUARDRAIL: Input Validation ===
            if self.enable_guardrails:
                input_check = self._apply_input_guardrails(input_data)
                if not input_check['is_safe']:
                    return self._create_guardrail_failure(
                        input_check['reason'],
                        input_check['flags'],
                        start_time
                    )
            
            # === CORE PROCESSING ===
            result = await self._process(input_data)
            result.agent_name = self.name
            
            # === GUARDRAIL: Output Validation ===
            if self.enable_guardrails:
                result = self._apply_output_guardrails(result, input_data)
            
            # Calculate timing
            duration_ms = (time.time() - start_time) * 1000
            result.processing_time_ms = duration_ms
            self.total_processing_time_ms += duration_ms
            
            # Log success
            if self.enable_logging:
                self.telemetry.log_agent_complete(
                    agent_name=self.name,
                    pipeline_id=pipeline_id,
                    duration_ms=duration_ms,
                    output_summary={'response_preview': result.response[:100]},
                    success=True
                )
            
            return result
            
        except Exception as e:
            self.error_count += 1
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            if self.enable_logging:
                self.telemetry.log_agent_error(
                    agent_name=self.name,
                    pipeline_id=pipeline_id,
                    error=str(e),
                    duration_ms=duration_ms
                )
            
            return await self._handle_error(e, input_data, duration_ms)
    
    @abstractmethod
    async def _process(self, input_data: AgentInput) -> AgentOutput:
        """
        Override this method to implement agent logic.
        
        Args:
            input_data: Validated and sanitized input
            
        Returns:
            AgentOutput with response and metadata
        """
        pass
    
    async def _handle_error(
        self,
        error: Exception,
        input_data: AgentInput,
        duration_ms: float
    ) -> AgentOutput:
        """
        Handle processing errors.
        Override for custom error handling.
        """
        return AgentOutput(
            success=False,
            response=f"Error in {self.name}: {str(error)}",
            processing_time_ms=duration_ms,
            agent_name=self.name,
            metadata={'error_type': type(error).__name__}
        )
    
    def _apply_input_guardrails(self, input_data: AgentInput) -> Dict:
        """
        Apply safety checks to input.
        
        Returns:
            Dict with 'is_safe', 'reason', and 'flags'
        """
        flags = []
        
        # Check 1: PII Detection
        pii_result = self.pii_detector.detect(input_data.query)
        if pii_result.contains_phi:
            flags.append(SafetyFlag(
                level="warning",
                category="pii",
                message=f"PII detected in input: {', '.join(pii_result.phi_types)}",
                action_required=False
            ))
            # Redact the query for processing
            input_data.query = pii_result.redacted_text
        
        # Check 2: Content Filter (emergency detection)
        filter_result = self.content_filter.check_input(input_data.query)
        if not filter_result.is_safe:
            flags.append(SafetyFlag(
                level="critical",
                category="content",
                message=filter_result.reason,
                action_required=True
            ))
            return {
                'is_safe': False,
                'reason': filter_result.reason,
                'flags': flags
            }
        
        return {
            'is_safe': True,
            'reason': 'Input passed guardrails',
            'flags': flags
        }
    
    def _apply_output_guardrails(
        self,
        output: AgentOutput,
        input_data: AgentInput
    ) -> AgentOutput:
        """
        Apply safety checks to output.
        Modifies output in place and returns it.
        """
        # Check 1: Content Filter
        filter_result = self.content_filter.check_response(
            output.response,
            {'intent': output.metadata.get('intent', 'unknown')}
        )
        
        if not filter_result.is_safe:
            output.safety_flags.append(SafetyFlag(
                level="critical",
                category="content",
                message=filter_result.reason,
                action_required=True
            ))
            # Replace response with safe fallback
            output.response = self._safe_fallback_response(filter_result.blocked_categories)
            output.metadata['guardrail_triggered'] = True
            output.metadata['original_blocked'] = True
            
            if self.enable_logging:
                self.telemetry.log_guardrail_triggered(
                    guardrail_type='content_filter',
                    action='blocked_response',
                    details={'categories': filter_result.blocked_categories},
                    pipeline_id=input_data.session_id
                )
        
        # Check 2: Response Validation
        validation = self.validator.validate_response(
            output.response,
            intent=output.metadata.get('intent', 'general')
        )
        
        if not validation.is_valid:
            output.safety_flags.append(SafetyFlag(
                level="warning",
                category="other",
                message=f"Validation issues: {', '.join(validation.errors[:3])}",
                action_required=False
            ))
            output.metadata['validation_errors'] = validation.errors
            output.metadata['validation_warnings'] = validation.warnings
        
        return output
    
    def _create_guardrail_failure(
        self,
        reason: str,
        flags: List[SafetyFlag],
        start_time: float
    ) -> AgentOutput:
        """Create output for guardrail failure"""
        duration_ms = (time.time() - start_time) * 1000
        
        return AgentOutput(
            success=False,
            response=f"Request blocked by safety guardrails: {reason}",
            safety_flags=flags,
            processing_time_ms=duration_ms,
            agent_name=self.name,
            metadata={'guardrail_blocked': True, 'reason': reason}
        )
    
    def _safe_fallback_response(self, blocked_categories: List[str]) -> str:
        """Generate safe fallback when content is blocked"""
        if 'emergency_detected' in blocked_categories:
            return """**THIS SOUNDS LIKE IT COULD BE AN EMERGENCY**

**If this is a medical emergency:**
Call 911 immediately (or your local emergency number)

**If you suspect an overdose:**
Poison Control: 1-800-222-1222 (US)

I cannot provide emergency medical advice. Please seek immediate professional help."""
        
        return "I'm unable to provide that information. For medical advice, please consult your healthcare provider or pharmacist."
    
    def _summarize_input(self, input_data: AgentInput) -> Dict:
        """Create safe summary of input for logging"""
        # Sanitize query for logging
        safe_query = self.pii_detector.sanitize_for_logging(input_data.query, max_length=100)
        
        return {
            'query_preview': safe_query,
            'has_medications': len(input_data.user_medications) > 0,
            'has_allergies': len(input_data.allergies) > 0,
            'context_keys': list(input_data.context.keys())
        }
    
    def get_stats(self) -> Dict:
        """Get agent statistics"""
        avg_time = (
            self.total_processing_time_ms / self.call_count
            if self.call_count > 0 else 0
        )
        
        return {
            'agent_name': self.name,
            'total_calls': self.call_count,
            'errors': self.error_count,
            'error_rate': self.error_count / max(self.call_count, 1),
            'avg_processing_time_ms': avg_time,
            'guardrails_enabled': self.enable_guardrails,
            'logging_enabled': self.enable_logging
        }
    
    def health_check(self) -> Dict:
        """Check agent health"""
        error_rate = self.error_count / max(self.call_count, 1)
        
        status = "healthy"
        if error_rate > 0.5:
            status = "unhealthy"
        elif error_rate > 0.1:
            status = "degraded"
        
        return {
            'agent_name': self.name,
            'status': status,
            'error_rate_24h': error_rate,
            'total_calls': self.call_count,
            'details': self.get_stats()
        }
