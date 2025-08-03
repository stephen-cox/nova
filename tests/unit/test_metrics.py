"""Tests for LLM metrics collection system"""

import tempfile
from datetime import datetime
from pathlib import Path

from nova.core.metrics import (
    ContextAnalysis,
    ContextStatus,
    LLMMetrics,
    MetricLevel,
    MetricsCollector,
    TokenUsage,
    configure_metrics,
    get_metrics_collector,
)


class TestTokenUsage:
    """Test token usage calculations"""

    def test_token_usage_creation(self):
        """Test creating token usage"""
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)

        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

    def test_efficiency_ratio(self):
        """Test efficiency ratio calculation"""
        usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.efficiency_ratio == 0.5

        # Test with zero input tokens
        usage_zero = TokenUsage(input_tokens=0, output_tokens=50, total_tokens=50)
        assert usage_zero.efficiency_ratio == 0.0


class TestContextAnalysis:
    """Test context analysis functionality"""

    def test_context_analysis_creation(self):
        """Test creating context analysis"""
        analysis = ContextAnalysis(
            total_messages=10,
            context_tokens=1000,
            max_context_tokens=4096,
            utilization_percent=24.4,
            status=ContextStatus.OPTIMAL,
            optimization_suggestions=["Test suggestion"],
        )

        assert analysis.total_messages == 10
        assert analysis.context_tokens == 1000
        assert analysis.utilization_percent == 24.4
        assert analysis.status == ContextStatus.OPTIMAL
        assert "Test suggestion" in analysis.optimization_suggestions

    def test_default_optimization_suggestions(self):
        """Test default empty optimization suggestions"""
        analysis = ContextAnalysis(
            total_messages=5,
            context_tokens=500,
            max_context_tokens=4096,
            utilization_percent=12.2,
            status=ContextStatus.OPTIMAL,
        )

        assert analysis.optimization_suggestions == []


class TestMetricsCollector:
    """Test metrics collector functionality"""

    def test_basic_metrics_collector(self):
        """Test basic metrics collector initialization"""
        collector = MetricsCollector(level=MetricLevel.BASIC)
        assert collector.level == MetricLevel.BASIC
        assert collector.debug_log_path is None

    def test_debug_metrics_collector(self):
        """Test debug metrics collector with log file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "debug.log"
            collector = MetricsCollector(
                level=MetricLevel.DEBUG, debug_log_path=log_path
            )

            assert collector.level == MetricLevel.DEBUG
            assert collector.debug_log_path == log_path

    def test_token_estimation(self):
        """Test rough token estimation"""
        collector = MetricsCollector()

        messages = [
            {"role": "user", "content": "Hello world! How are you today?"},
            {"role": "assistant", "content": "I'm doing well, thank you for asking!"},
        ]

        estimated = collector._estimate_tokens(messages)
        assert estimated > 0
        # Rough estimate should be reasonable
        assert 10 < estimated < 50

    def test_context_analysis(self):
        """Test context window analysis"""
        collector = MetricsCollector()

        messages = [{"role": "user", "content": "Short message"}]
        max_tokens = 4096

        analysis = collector.analyze_context(messages, max_tokens)

        assert analysis.total_messages == 1
        assert analysis.context_tokens > 0
        assert analysis.max_context_tokens == max_tokens
        assert analysis.utilization_percent >= 0
        assert analysis.status == ContextStatus.OPTIMAL

    def test_context_warning_status(self):
        """Test context status determination"""
        collector = MetricsCollector()

        # Test optimal status (low utilization)
        messages_low = [{"role": "user", "content": "Short"}]
        analysis_low = collector.analyze_context(messages_low, 1000)
        assert analysis_low.status == ContextStatus.OPTIMAL

        # Test warning status (high utilization)
        long_content = "x" * 3000  # Long message to trigger high utilization
        messages_high = [{"role": "user", "content": long_content}]
        analysis_high = collector.analyze_context(messages_high, 1000)
        assert analysis_high.status in [ContextStatus.WARNING, ContextStatus.CRITICAL]

    def test_optimization_suggestions(self):
        """Test optimization suggestions generation"""
        collector = MetricsCollector()

        # Create scenario with many messages and high token usage
        messages = [{"role": "user", "content": "x" * 100}] * 25  # 25 messages
        analysis = collector.analyze_context(messages, 1000)

        suggestions = analysis.optimization_suggestions
        assert len(suggestions) > 0

        # Should suggest conversation pruning for many messages
        assert any("conversation pruning" in s.lower() for s in suggestions)

    def test_create_metrics(self):
        """Test comprehensive metrics creation"""
        collector = MetricsCollector()

        messages = [{"role": "user", "content": "Test message"}]
        response = "Test response"
        start_time = datetime.now()
        end_time = datetime.now()

        context_analysis = ContextAnalysis(
            total_messages=1,
            context_tokens=10,
            max_context_tokens=4096,
            utilization_percent=0.24,
            status=ContextStatus.OPTIMAL,
        )

        metrics = collector.create_metrics(
            conversation_id="test-123",
            provider="openai",
            model="gpt-4",
            messages=messages,
            response=response,
            request_start=start_time,
            response_complete=end_time,
            context_analysis=context_analysis,
            input_tokens=10,
            output_tokens=5,
            temperature=0.7,
            max_tokens=2000,
        )

        assert metrics.conversation_id == "test-123"
        assert metrics.provider == "openai"
        assert metrics.model == "gpt-4"
        assert metrics.token_usage.input_tokens == 10
        assert metrics.token_usage.output_tokens == 5
        assert metrics.temperature == 0.7
        assert metrics.max_tokens == 2000
        assert metrics.success is True

    def test_metrics_performance_calculations(self):
        """Test performance metric calculations"""
        collector = MetricsCollector()

        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 12, 0, 2)  # 2 seconds later

        context_analysis = ContextAnalysis(
            total_messages=1,
            context_tokens=10,
            max_context_tokens=4096,
            utilization_percent=0.24,
            status=ContextStatus.OPTIMAL,
        )

        metrics = collector.create_metrics(
            conversation_id="test-perf",
            provider="openai",
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            response="Response",
            request_start=start_time,
            response_complete=end_time,
            context_analysis=context_analysis,
            output_tokens=100,
        )

        assert metrics.total_response_time == 2.0
        assert metrics.tokens_per_second == 50.0  # 100 tokens / 2 seconds


class TestGlobalMetricsCollector:
    """Test global metrics collector functions"""

    def test_get_metrics_collector(self):
        """Test getting global metrics collector"""
        collector = get_metrics_collector()
        assert isinstance(collector, MetricsCollector)

        # Should return same instance on subsequent calls
        collector2 = get_metrics_collector()
        assert collector is collector2

    def test_configure_metrics(self):
        """Test configuring global metrics collector"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "test.log"

            configure_metrics(level=MetricLevel.DEBUG, debug_log_path=log_path)
            collector = get_metrics_collector()

            assert collector.level == MetricLevel.DEBUG
            assert collector.debug_log_path == log_path


class TestLLMMetrics:
    """Test LLM metrics dataclass"""

    def test_llm_metrics_creation(self):
        """Test creating LLM metrics"""
        token_usage = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150)

        context_analysis = ContextAnalysis(
            total_messages=5,
            context_tokens=500,
            max_context_tokens=4096,
            utilization_percent=12.2,
            status=ContextStatus.OPTIMAL,
        )

        start_time = datetime.now()
        end_time = datetime.now()

        metrics = LLMMetrics(
            timestamp=datetime.now(),
            conversation_id="test-conv",
            provider="openai",
            model="gpt-4",
            token_usage=token_usage,
            context_analysis=context_analysis,
            request_start_time=start_time,
            response_complete_time=end_time,
            message_count=2,
            response_length=100,
            temperature=0.7,
            max_tokens=2000,
        )

        assert metrics.conversation_id == "test-conv"
        assert metrics.provider == "openai"
        assert metrics.model == "gpt-4"
        assert metrics.token_usage == token_usage
        assert metrics.context_analysis == context_analysis
        assert metrics.message_count == 2
        assert metrics.response_length == 100
