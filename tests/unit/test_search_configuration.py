"""Tests for search configuration validation and defaults"""

import pytest
from pydantic import ValidationError

from nova.models.config import NovaConfig, SearchConfig
from nova.search.models import SearchEnhancementMode


class TestSearchConfigurationValidation:
    """Test search configuration validation"""

    def test_default_search_config(self):
        """Test that default search configuration is valid"""
        config = SearchConfig()

        # Verify all defaults
        assert config.enabled is True
        assert config.default_provider == "duckduckgo"
        assert config.max_results == 5
        assert config.use_ai_answers is True
        assert config.default_enhancement == "fast"
        assert config.enable_conversation_context is True
        assert config.context_messages_count == 5
        assert config.default_technical_level == "intermediate"
        assert config.default_timeframe == "any"
        assert config.performance_mode is True
        assert config.extraction_backend == "yake_only"
        assert config.enable_keybert is False
        assert config.yake_max_keywords == 10
        assert config.keybert_max_keywords == 6
        assert config.keybert_model == "all-MiniLM-L6-v2"

    def test_valid_provider_validation(self):
        """Test validation of search providers"""
        valid_providers = ["duckduckgo", "google", "bing"]

        for provider in valid_providers:
            config = SearchConfig(default_provider=provider)
            assert config.default_provider == provider

    def test_invalid_provider_validation(self):
        """Test rejection of invalid search providers"""
        invalid_providers = ["yahoo", "baidu", "yandex", "invalid"]

        for provider in invalid_providers:
            with pytest.raises(ValidationError) as exc_info:
                SearchConfig(default_provider=provider)
            assert "Provider must be one of" in str(exc_info.value)

    def test_enhancement_mode_validation(self):
        """Test validation of enhancement modes"""
        valid_modes = ["auto", "disabled", "fast", "semantic", "hybrid", "adaptive"]

        for mode in valid_modes:
            config = SearchConfig(default_enhancement=mode)
            assert config.default_enhancement == mode

    def test_invalid_enhancement_mode_validation(self):
        """Test rejection of invalid enhancement modes"""
        invalid_modes = ["slow", "invalid", "super_fast", "ai_powered"]

        for mode in invalid_modes:
            with pytest.raises(ValidationError) as exc_info:
                SearchConfig(default_enhancement=mode)
            assert "Enhancement mode must be one of" in str(exc_info.value)

    def test_technical_level_validation(self):
        """Test validation of technical levels"""
        valid_levels = ["beginner", "intermediate", "expert"]

        for level in valid_levels:
            config = SearchConfig(default_technical_level=level)
            assert config.default_technical_level == level

    def test_invalid_technical_level_validation(self):
        """Test rejection of invalid technical levels"""
        invalid_levels = ["novice", "advanced", "professional", "invalid"]

        for level in invalid_levels:
            with pytest.raises(ValidationError) as exc_info:
                SearchConfig(default_technical_level=level)
            assert "Technical level must be one of" in str(exc_info.value)

    def test_timeframe_validation(self):
        """Test validation of timeframes"""
        valid_timeframes = ["recent", "past_year", "any"]

        for timeframe in valid_timeframes:
            config = SearchConfig(default_timeframe=timeframe)
            assert config.default_timeframe == timeframe

    def test_invalid_timeframe_validation(self):
        """Test rejection of invalid timeframes"""
        invalid_timeframes = ["past_month", "last_week", "today", "invalid"]

        for timeframe in invalid_timeframes:
            with pytest.raises(ValidationError) as exc_info:
                SearchConfig(default_timeframe=timeframe)
            assert "Timeframe must be one of" in str(exc_info.value)

    def test_extraction_backend_validation(self):
        """Test validation of extraction backends"""
        valid_backends = ["yake_only", "keybert_only", "hybrid", "adaptive"]

        for backend in valid_backends:
            config = SearchConfig(extraction_backend=backend)
            assert config.extraction_backend == backend

    def test_invalid_extraction_backend_validation(self):
        """Test rejection of invalid extraction backends"""
        invalid_backends = ["spacy_only", "nltk", "transformers", "invalid"]

        for backend in invalid_backends:
            with pytest.raises(ValidationError) as exc_info:
                SearchConfig(extraction_backend=backend)
            assert "Extraction backend must be one of" in str(exc_info.value)

    def test_max_results_validation(self):
        """Test validation of max_results constraints"""
        # Valid values
        valid_max_results = [1, 5, 10, 25, 50]
        for max_results in valid_max_results:
            config = SearchConfig(max_results=max_results)
            assert config.max_results == max_results

        # Invalid values
        invalid_max_results = [0, -1, 51, 100]
        for max_results in invalid_max_results:
            with pytest.raises(ValidationError):
                SearchConfig(max_results=max_results)

    def test_keyword_limits_validation(self):
        """Test validation of keyword extraction limits"""
        # Valid YAKE keyword limits
        for limit in [1, 10, 25, 50]:
            config = SearchConfig(yake_max_keywords=limit)
            assert config.yake_max_keywords == limit

        # Invalid YAKE keyword limits
        for limit in [0, -1, 51, 100]:
            with pytest.raises(ValidationError):
                SearchConfig(yake_max_keywords=limit)

        # Valid KeyBERT keyword limits
        for limit in [1, 6, 15, 20]:
            config = SearchConfig(keybert_max_keywords=limit)
            assert config.keybert_max_keywords == limit

        # Invalid KeyBERT keyword limits
        for limit in [0, -1, 21, 50]:
            with pytest.raises(ValidationError):
                SearchConfig(keybert_max_keywords=limit)

    def test_context_messages_count_validation(self):
        """Test validation of context message count"""
        # Valid values
        for count in [0, 5, 10, 20]:
            config = SearchConfig(context_messages_count=count)
            assert config.context_messages_count == count

        # Invalid values
        for count in [-1, 21, 50]:
            with pytest.raises(ValidationError):
                SearchConfig(context_messages_count=count)


class TestSearchConfigurationIntegration:
    """Test search configuration integration with main Nova config"""

    def test_default_nova_config_with_search(self):
        """Test that Nova config includes valid search configuration"""
        config = NovaConfig()

        # Verify search config exists and is valid
        assert hasattr(config, "search")
        assert isinstance(config.search, SearchConfig)

        # Check some key defaults
        assert config.search.enabled is True
        assert config.search.default_provider == "duckduckgo"
        assert config.search.default_enhancement == "fast"

    def test_nova_config_with_custom_search_settings(self):
        """Test Nova config with custom search settings"""
        custom_config_data = {
            "search": {
                "enabled": False,
                "default_provider": "google",
                "max_results": 10,
                "default_enhancement": "semantic",
                "default_technical_level": "expert",
                "default_timeframe": "recent",
                "yake_max_keywords": 20,
                "keybert_max_keywords": 10,
            }
        }

        config = NovaConfig(**custom_config_data)

        # Verify custom settings are applied
        assert config.search.enabled is False
        assert config.search.default_provider == "google"
        assert config.search.max_results == 10
        assert config.search.default_enhancement == "semantic"
        assert config.search.default_technical_level == "expert"
        assert config.search.default_timeframe == "recent"
        assert config.search.yake_max_keywords == 20
        assert config.search.keybert_max_keywords == 10

    def test_nova_config_with_invalid_search_settings(self):
        """Test Nova config rejects invalid search settings"""
        invalid_configs = [
            {"search": {"default_provider": "invalid_provider"}},
            {"search": {"default_enhancement": "invalid_mode"}},
            {"search": {"default_technical_level": "invalid_level"}},
            {"search": {"default_timeframe": "invalid_timeframe"}},
            {"search": {"max_results": 0}},
            {"search": {"max_results": 100}},
            {"search": {"yake_max_keywords": -1}},
            {"search": {"keybert_max_keywords": 50}},
            {"search": {"context_messages_count": -1}},
        ]

        for invalid_config in invalid_configs:
            with pytest.raises(ValidationError):
                NovaConfig(**invalid_config)


class TestSearchEnhancementModeEnum:
    """Test SearchEnhancementMode enum validation"""

    def test_valid_enhancement_modes(self):
        """Test all valid enhancement modes can be created"""
        valid_modes = ["auto", "disabled", "fast", "semantic", "hybrid", "adaptive"]

        for mode_str in valid_modes:
            mode = SearchEnhancementMode(mode_str)
            assert mode.value == mode_str

    def test_invalid_enhancement_modes(self):
        """Test invalid enhancement modes are rejected"""
        invalid_modes = ["slow", "invalid", "super_fast", "ai", ""]

        for mode_str in invalid_modes:
            with pytest.raises(ValueError):
                SearchEnhancementMode(mode_str)

    def test_enhancement_mode_equality(self):
        """Test enhancement mode equality"""
        mode1 = SearchEnhancementMode.FAST
        mode2 = SearchEnhancementMode("fast")

        assert mode1 == mode2
        assert mode1.value == "fast"
        assert mode2.value == "fast"

    def test_enhancement_mode_string_representation(self):
        """Test string representation of enhancement modes"""
        mode = SearchEnhancementMode.SEMANTIC
        # The exact string representation may vary, but should contain the mode name
        assert "SEMANTIC" in str(mode)
        assert mode.value == "semantic"
        assert "semantic" in repr(mode).lower()


class TestConfigurationEdgeCases:
    """Test configuration edge cases and corner cases"""

    def test_empty_search_config(self):
        """Test creating search config with empty dict"""
        config = SearchConfig(**{})

        # Should use all defaults
        assert config.enabled is True
        assert config.default_provider == "duckduckgo"

    def test_partial_search_config(self):
        """Test creating search config with partial settings"""
        partial_config = {
            "enabled": False,
            "max_results": 15,
            "default_enhancement": "hybrid",
        }

        config = SearchConfig(**partial_config)

        # Should use provided values and defaults for the rest
        assert config.enabled is False
        assert config.max_results == 15
        assert config.default_enhancement == "hybrid"
        assert config.default_provider == "duckduckgo"  # Default

    def test_search_config_with_extra_fields(self):
        """Test search config ignores extra fields"""
        config_with_extra = {
            "enabled": True,
            "default_provider": "google",
            "extra_field": "should_be_ignored",
            "another_extra": 123,
        }

        # Should not raise an error and should ignore extra fields
        config = SearchConfig(**config_with_extra)
        assert config.enabled is True
        assert config.default_provider == "google"
        assert not hasattr(config, "extra_field")
        assert not hasattr(config, "another_extra")

    def test_search_config_type_coercion(self):
        """Test automatic type coercion in search config"""
        config_data = {
            "enabled": "true",  # String that should be coerced to bool
            "max_results": "10",  # String that should be coerced to int
        }

        config = SearchConfig(**config_data)

        # Should coerce types correctly
        assert config.enabled is True
        assert config.max_results == 10

    def test_google_and_bing_config_structure(self):
        """Test Google and Bing configuration structure"""
        google_config = {
            "api_key": "test_google_key",
            "search_engine_id": "test_engine_id",
        }

        bing_config = {
            "api_key": "test_bing_key",
        }

        config = SearchConfig(
            google=google_config,
            bing=bing_config,
        )

        assert config.google["api_key"] == "test_google_key"
        assert config.google["search_engine_id"] == "test_engine_id"
        assert config.bing["api_key"] == "test_bing_key"

    def test_keybert_model_names(self):
        """Test various KeyBERT model names are accepted"""
        model_names = [
            "all-MiniLM-L6-v2",
            "all-mpnet-base-v2",
            "paraphrase-multilingual-MiniLM-L12-v2",
            "custom-model-name",
        ]

        for model_name in model_names:
            config = SearchConfig(keybert_model=model_name)
            assert config.keybert_model == model_name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
