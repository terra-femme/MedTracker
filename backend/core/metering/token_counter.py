"""
Token Counter - Cost Tracking
=============================
Tracks token usage and costs across all LLM calls.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, date, timezone


@dataclass
class TokenUsage:
    """Record of token usage for a single call"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    model: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_name: Optional[str] = None


class TokenCounter:
    """
    Track token usage across all LLM calls.
    
    Supports:
    - Multiple models with different pricing
    - Daily budget tracking
    - Per-agent cost attribution
    """
    
    # Cost per 1K tokens (input, output)
    # Prices as of early 2024 - update as needed
    PRICING = {
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
        'gpt-3.5-turbo': {'input': 0.0015, 'output': 0.002},
        'gpt-3.5-turbo-16k': {'input': 0.003, 'output': 0.004},
        # Ollama models are free (local)
        'ollama': {'input': 0.0, 'output': 0.0},
        'ollama/llama3': {'input': 0.0, 'output': 0.0},
        'ollama/mistral': {'input': 0.0, 'output': 0.0},
        'ollama/phi3': {'input': 0.0, 'output': 0.0},
        # Default for unknown models
        'default': {'input': 0.0, 'output': 0.0}
    }
    
    # Approximate tokens per character (rough estimate)
    CHARS_PER_TOKEN = 4
    
    def __init__(self, daily_budget_usd: Optional[float] = None):
        self.usage_history: List[TokenUsage] = []
        self.daily_budget_usd = daily_budget_usd
        self._estimate_cache: Dict[str, int] = {}
    
    def estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count"""
        # Simple estimation: ~4 chars per token for English
        return max(1, len(text) // self.CHARS_PER_TOKEN)
    
    def record_usage(
        self,
        prompt: str,
        completion: str,
        model: str,
        agent_name: Optional[str] = None
    ) -> TokenUsage:
        """
        Record token usage for an LLM call.
        
        Args:
            prompt: The input prompt
            completion: The generated response
            model: Model name used
            agent_name: Optional agent name for attribution
            
        Returns:
            TokenUsage record
        """
        # Estimate tokens (since we may not have actual counts)
        prompt_tokens = self.estimate_tokens(prompt)
        completion_tokens = self.estimate_tokens(completion)
        
        # Get pricing
        pricing = self.PRICING.get(model, self.PRICING['default'])
        
        cost = (
            prompt_tokens / 1000 * pricing['input'] +
            completion_tokens / 1000 * pricing['output']
        )
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=cost,
            model=model,
            agent_name=agent_name
        )
        
        self.usage_history.append(usage)
        return usage
    
    def get_daily_usage(self, target_date: Optional[date] = None) -> Dict:
        """
        Get usage summary for a specific date.
        
        Args:
            target_date: Date to summarize (defaults to today)
            
        Returns:
            Dictionary with usage statistics
        """
        target = target_date or date.today()
        
        day_usage = [
            u for u in self.usage_history
            if u.timestamp.date() == target
        ]
        
        if not day_usage:
            return {
                'date': target.isoformat(),
                'calls': 0,
                'total_tokens': 0,
                'total_cost_usd': 0.0,
                'by_model': {},
                'by_agent': {}
            }
        
        # Aggregate by model
        by_model: Dict[str, Dict] = {}
        by_agent: Dict[str, Dict] = {}
        
        for usage in day_usage:
            # By model
            model = usage.model
            if model not in by_model:
                by_model[model] = {'calls': 0, 'tokens': 0, 'cost': 0.0}
            by_model[model]['calls'] += 1
            by_model[model]['tokens'] += usage.total_tokens
            by_model[model]['cost'] += usage.estimated_cost_usd
            
            # By agent
            agent = usage.agent_name or 'unknown'
            if agent not in by_agent:
                by_agent[agent] = {'calls': 0, 'tokens': 0, 'cost': 0.0}
            by_agent[agent]['calls'] += 1
            by_agent[agent]['tokens'] += usage.total_tokens
            by_agent[agent]['cost'] += usage.estimated_cost_usd
        
        return {
            'date': target.isoformat(),
            'calls': len(day_usage),
            'total_tokens': sum(u.total_tokens for u in day_usage),
            'total_cost_usd': sum(u.estimated_cost_usd for u in day_usage),
            'by_model': by_model,
            'by_agent': by_agent
        }
    
    def check_budget(self) -> bool:
        """Check if we're within daily budget"""
        if self.daily_budget_usd is None:
            return True
        
        today_cost = self.get_daily_usage()['total_cost_usd']
        return today_cost < self.daily_budget_usd
    
    def get_budget_status(self) -> Dict:
        """Get detailed budget status"""
        if self.daily_budget_usd is None:
            return {
                'budget_enabled': False,
                'status': 'unlimited'
            }
        
        today_usage = self.get_daily_usage()
        spent = today_usage['total_cost_usd']
        remaining = self.daily_budget_usd - spent
        percent_used = (spent / self.daily_budget_usd) * 100
        
        status = 'OK'
        if percent_used >= 100:
            status = 'OVER_BUDGET'
        elif percent_used >= 90:
            status = 'CRITICAL'
        elif percent_used >= 75:
            status = 'WARNING'
        
        return {
            'budget_enabled': True,
            'daily_budget_usd': self.daily_budget_usd,
            'spent_today_usd': spent,
            'remaining_usd': remaining,
            'percent_used': percent_used,
            'status': status
        }
    
    def get_summary(self) -> Dict:
        """Get overall usage summary"""
        if not self.usage_history:
            return {'calls': 0, 'total_cost_usd': 0.0}
        
        return {
            'total_calls': len(self.usage_history),
            'total_tokens': sum(u.total_tokens for u in self.usage_history),
            'total_cost_usd': sum(u.estimated_cost_usd for u in self.usage_history),
            'today': self.get_daily_usage(),
            'budget': self.get_budget_status()
        }


# Singleton instance
_counter = None

def get_token_counter() -> TokenCounter:
    """Get singleton token counter"""
    global _counter
    if _counter is None:
        _counter = TokenCounter()
    return _counter
