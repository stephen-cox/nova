"""LLM interaction metrics collection and monitoring"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class ContextStatus(Enum):
    """Context window utilization status"""

    OPTIMAL = "optimal"  # < 70% utilization
    WARNING = "warning"  # 70-90% utilization
    CRITICAL = "critical"  # > 90% utilization
    TRUNCATED = "truncated"  # Content was truncated


class MetricLevel(Enum):
    """Metric collection detail level"""

    BASIC = "basic"  # Just essential metrics
    DETAILED = "detailed"  # Include timing and context analysis
    DEBUG = "debug"  # Full request/response logging


@dataclass
class TokenUsage:
    """Token usage information"""

    input_tokens: int
    output_tokens: int
    total_tokens: int

    @property
    def efficiency_ratio(self) -> float:
        """Output tokens per input token (higher = more efficient)"""
        return self.output_tokens / self.input_tokens if self.input_tokens > 0 else 0.0


@dataclass
class ContextAnalysis:
    """Context window analysis and optimization info"""

    total_messages: int
    context_tokens: int
    max_context_tokens: int
    utilization_percent: float
    status: ContextStatus
    truncated_messages: int = 0
    optimization_suggestions: list[str] = None

    def __post_init__(self):
        if self.optimization_suggestions is None:
            self.optimization_suggestions = []


@dataclass
class LLMMetrics:
    """Comprehensive LLM interaction metrics"""

    # Request metadata
    timestamp: datetime
    conversation_id: str
    provider: str
    model: str

    # Token usage
    token_usage: TokenUsage

    # Context analysis
    context_analysis: ContextAnalysis

    # Performance
    request_start_time: datetime
    response_complete_time: datetime

    # Request details
    message_count: int
    response_length: int

    # Optional fields with defaults
    time_to_first_token: float | None = None  # For streaming responses
    temperature: float = 0.0
    max_tokens: int = 0
    success: bool = True
    error_message: str | None = None

    @property
    def total_response_time(self) -> float:
        """Total time from request start to completion (seconds)"""
        return (self.response_complete_time - self.request_start_time).total_seconds()

    @property
    def tokens_per_second(self) -> float:
        """Output tokens generated per second"""
        if self.total_response_time > 0 and self.token_usage.output_tokens > 0:
            return self.token_usage.output_tokens / self.total_response_time
        return 0.0


class MetricsCollector:
    """Collects and manages LLM interaction metrics"""

    def __init__(
        self, level: MetricLevel = MetricLevel.BASIC, debug_log_path: Path | None = None
    ):
        self.level = level
        self.debug_log_path = debug_log_path
        self.logger = logging.getLogger(__name__)

        # Initialize debug logging if requested
        if debug_log_path and level == MetricLevel.DEBUG:
            self._setup_debug_logging()

    def _setup_debug_logging(self):
        """Setup debug file logging for LLM interactions"""
        debug_handler = logging.FileHandler(self.debug_log_path)
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        debug_handler.setFormatter(debug_formatter)

        # Create debug logger specifically for LLM interactions
        self.debug_logger = logging.getLogger(f"{__name__}.debug")
        self.debug_logger.setLevel(logging.DEBUG)
        self.debug_logger.addHandler(debug_handler)
        self.debug_logger.propagate = False

    def log_request(
        self, provider: str, model: str, messages: list[dict[str, str]], **kwargs
    ) -> None:
        """Log LLM request details"""
        if self.level != MetricLevel.DEBUG:
            return

        request_data = {
            "type": "request",
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "message_count": len(messages),
            "messages": (
                messages
                if self.level == MetricLevel.DEBUG
                else [
                    {"role": m.get("role"), "content_length": len(m.get("content", ""))}
                    for m in messages
                ]
            ),
            "parameters": kwargs,
        }

        if hasattr(self, "debug_logger"):
            self.debug_logger.debug(
                f"LLM_REQUEST: {json.dumps(request_data, indent=2, default=str)}"
            )

    def log_response(
        self, provider: str, model: str, response: str, metrics: LLMMetrics
    ) -> None:
        """Log LLM response details"""
        if self.level != MetricLevel.DEBUG:
            return

        response_data = {
            "type": "response",
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "response_length": len(response),
            "response": (
                response
                if self.level == MetricLevel.DEBUG
                else f"[{len(response)} characters]"
            ),
            "metrics": asdict(metrics),
        }

        if hasattr(self, "debug_logger"):
            self.debug_logger.debug(
                f"LLM_RESPONSE: {json.dumps(response_data, indent=2, default=str)}"
            )

    def analyze_context(
        self,
        messages: list[dict[str, str]],
        max_context_tokens: int,
        estimated_tokens: int | None = None,
    ) -> ContextAnalysis:
        """Analyze context window usage and provide optimization suggestions"""

        # Estimate tokens if not provided
        if estimated_tokens is None:
            estimated_tokens = self._estimate_tokens(messages)

        utilization = (estimated_tokens / max_context_tokens) * 100

        # Determine status
        if utilization < 70:
            status = ContextStatus.OPTIMAL
        elif utilization < 90:
            status = ContextStatus.WARNING
        else:
            status = ContextStatus.CRITICAL

        # Generate optimization suggestions
        suggestions = []
        if utilization > 80:
            suggestions.append("Consider summarizing older messages")
        if utilization > 90:
            suggestions.append("Context window nearly full - truncation likely")
        if len(messages) > 20:
            suggestions.append("Consider conversation pruning")

        return ContextAnalysis(
            total_messages=len(messages),
            context_tokens=estimated_tokens,
            max_context_tokens=max_context_tokens,
            utilization_percent=utilization,
            status=status,
            optimization_suggestions=suggestions,
        )

    def _estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """Rough token estimation for context analysis"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        # Rough estimate: ~4 characters per token for English text
        return int(total_chars / 4)

    def create_metrics(
        self,
        conversation_id: str,
        provider: str,
        model: str,
        messages: list[dict[str, str]],
        response: str,
        request_start: datetime,
        response_complete: datetime,
        context_analysis: ContextAnalysis,
        input_tokens: int = 0,
        output_tokens: int = 0,
        time_to_first_token: float | None = None,
        **kwargs,
    ) -> LLMMetrics:
        """Create comprehensive metrics for an LLM interaction"""

        token_usage = TokenUsage(
            input_tokens=input_tokens or self._estimate_tokens(messages),
            output_tokens=output_tokens
            or self._estimate_tokens([{"content": response}]),
            total_tokens=(input_tokens or 0) + (output_tokens or 0),
        )

        return LLMMetrics(
            timestamp=datetime.now(),
            conversation_id=conversation_id,
            provider=provider,
            model=model,
            token_usage=token_usage,
            context_analysis=context_analysis,
            request_start_time=request_start,
            response_complete_time=response_complete,
            time_to_first_token=time_to_first_token,
            message_count=len(messages),
            response_length=len(response),
            temperature=kwargs.get("temperature", 0.0),
            max_tokens=kwargs.get("max_tokens", 0),
            success=True,
        )

    def print_context_warning(self, analysis: ContextAnalysis) -> None:
        """Print context utilization warnings to console"""
        if analysis.status == ContextStatus.WARNING:
            self.logger.warning(
                f"Context window {analysis.utilization_percent:.1f}% full "
                f"({analysis.context_tokens}/{analysis.max_context_tokens} tokens)"
            )
        elif analysis.status == ContextStatus.CRITICAL:
            self.logger.error(
                f"Context window {analysis.utilization_percent:.1f}% full - "
                f"truncation likely ({analysis.context_tokens}/{analysis.max_context_tokens} tokens)"
            )

        if analysis.optimization_suggestions:
            for suggestion in analysis.optimization_suggestions:
                self.logger.info(f"💡 Optimization: {suggestion}")


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def configure_metrics(
    level: MetricLevel = MetricLevel.BASIC, debug_log_path: Path | None = None
) -> None:
    """Configure global metrics collection"""
    global _metrics_collector
    _metrics_collector = MetricsCollector(level=level, debug_log_path=debug_log_path)
