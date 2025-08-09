# Enhanced Search Implementation Plan

## Overview

This plan implements intelligent web search with context-aware query enhancement for Nova AI Assistant. The enhancement system uses a three-stage pipeline: NLP extraction → LLM optimization → JSON-driven execution, replacing both the `web_search` tool and `/search` command with enhanced versions.

## Key Features

- **Three-stage enhancement pipeline**: spaCy + YAKE/KeyBERT → LLM → structured search execution
- **Swappable NLP backends**: YAKE (fast, default) and KeyBERT (semantic, optional)
- **Conversation context integration**: Automatic context injection from chat history
- **Performance flexibility**: Multiple enhancement modes from disabled to hybrid
- **Comprehensive configuration**: User-configurable defaults and preferences
- **Backward compatibility**: All existing usage patterns continue to work

## Phase 1: Create Modular Search Architecture

### 1.1 New Directory Structure

```
nova/
├── search/                          # NEW: Dedicated search module
│   ├── __init__.py                 # Search module exports
│   ├── engines/                    # Search engine implementations
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract search engine
│   │   ├── duckduckgo.py          # DuckDuckGo implementation
│   │   ├── google.py              # Google Search implementation
│   │   └── bing.py                # Bing implementation
│   ├── enhancement/               # Query enhancement components
│   │   ├── __init__.py
│   │   ├── extractors.py          # Keyword extraction (YAKE/KeyBERT)
│   │   ├── enhancer.py            # Main enhancement logic
│   │   └── classifier.py          # Term classification
│   ├── models.py                  # Search-specific models
│   ├── config.py                  # Search configuration
│   ├── manager.py                 # Main search manager (replaces core/search.py)
│   └── utils.py                   # Search utilities
├── tools/built_in/
│   └── web_search.py              # UPDATED: Enhanced web search tool
└── core/
    └── search.py                  # DEPRECATED: Will be removed
```

### 1.2 File Structure Details

**nova/search/__init__.py**
```python
"""Enhanced search module with intelligent query enhancement"""

from .manager import EnhancedSearchManager
from .models import SearchResult, SearchResponse, EnhancedSearchPlan
from .config import SearchConfig
from .enhancement import QueryEnhancer

__all__ = [
    "EnhancedSearchManager",
    "SearchResult",
    "SearchResponse",
    "EnhancedSearchPlan",
    "SearchConfig",
    "QueryEnhancer"
]
```

**nova/search/models.py**
```python
"""Search-specific models and data structures"""
# Move SearchResult, SearchResponse from core/search.py
# Add new models: EnhancedSearchPlan, KeywordExtractionResult, etc.
```

**nova/search/config.py**
```python
"""Search configuration management"""
# Consolidate all search-related configuration
# Include extraction backend settings, performance options
```

**nova/search/manager.py**
```python
"""Main search manager replacing core/search.py functionality"""
# Enhanced SearchManager with query enhancement integration
# Backward compatibility with existing SearchManager interface
```

## Phase 2: Replace web_search Tool and /search Command

### 2.1 Enhanced web_search Tool Signature

```python
# nova/tools/built_in/web_search.py - COMPLETE REPLACEMENT

@tool(
    description="Intelligent web search with context-aware query enhancement",
    permission_level=PermissionLevel.ELEVATED,
    category=ToolCategory.INFORMATION,
    tags=["web", "search", "nlp", "enhanced"],
    examples=[
        ToolExample(
            description="Enhanced search with automatic optimization",
            arguments={"query": "Python async programming", "enhancement": "auto"},
            expected_result="Optimized search queries with extracted keywords",
        ),
        ToolExample(
            description="Fast search without enhancement",
            arguments={"query": "exact search terms", "enhancement": "disabled"},
            expected_result="Direct search results without query modification",
        ),
        ToolExample(
            description="Semantic search for complex topics",
            arguments={"query": "machine learning deployment", "enhancement": "semantic"},
            expected_result="Semantically enhanced search with KeyBERT extraction",
        ),
    ],
)
async def web_search(
    query: str,
    enhancement: str = None,  # Will use config default if None
    provider: str = None,     # Will use config default if None
    max_results: int = None,  # Will use config default if None
    include_content: bool = True,
    timeframe: str = None,    # Will use config default if None
    technical_level: str = None,  # Will use config default if None
) -> dict:
    """
    Enhanced web search with intelligent query optimization.

    Enhancement modes:
    - auto: Automatically choose best enhancement (YAKE + context)
    - disabled: No enhancement, direct search
    - fast: YAKE-only enhancement (~50ms)
    - semantic: KeyBERT semantic enhancement (~200-500ms)
    - hybrid: YAKE + KeyBERT for best accuracy (~300-600ms)

    Args:
        query: Search query or question
        enhancement: Enhancement mode to use (uses config default if None)
        provider: Search provider (duckduckgo, google, bing)
        max_results: Maximum results to return (1-20)
        include_content: Extract detailed content from pages
        timeframe: Preferred time range for results
        technical_level: Adjust query complexity

    Returns:
        Enhanced search results with optimization details
    """
```

### 2.2 Backward Compatibility Strategy

```python
# Maintain existing function signatures for compatibility
async def web_search(
    query: str,
    provider: str = None,     # Use config default
    max_results: int = None,  # Use config default
    include_content: bool = True,
    # NEW parameters with defaults to maintain compatibility
    enhancement: str = None,  # Use config default
    timeframe: str = None,    # Use config default
    technical_level: str = None,  # Use config default
) -> dict:
    """Backward compatible web search with optional enhancement"""

    # Get configuration defaults
    from nova.core.config import get_config
    config = get_config()

    # Apply configuration defaults for None values
    enhancement = enhancement or config.search.default_enhancement.value
    provider = provider or config.search.default_provider
    max_results = max_results or config.search.max_results
    timeframe = timeframe or config.search.default_timeframe
    technical_level = technical_level or config.search.default_technical_level

    # Rest of implementation...
```

### 2.3 Enhanced /search Command Design

**Current /search Command Signature:**
```bash
/search <query> [--provider <provider>] [--max <number>]
/s <query> [--provider <provider>] [--max <number>]
```

**Enhanced /search Command Signature:**
```bash
/search <query> [--provider <provider>] [--max <number>] [--enhancement <mode>] [--technical-level <level>] [--timeframe <time>]
/s <query> [--provider <provider>] [--max <number>] [--enhancement <mode>] [--technical-level <level>] [--timeframe <time>]
```

**New Parameters:**
- `--enhancement <mode>`: auto, disabled, fast, semantic, hybrid (uses config default)
- `--technical-level <level>`: beginner, intermediate, expert (uses config default)
- `--timeframe <time>`: recent, past_year, any (uses config default)

### 2.4 Updated Chat Command Handler

```python
# nova/core/chat.py - Updated _handle_search_command method

def _handle_search_command(self, search_args: str, session: ChatSession) -> None:
    """Handle enhanced web search command with intelligent query optimization"""
    if not search_args:
        print_error("Please provide a search query")
        print_info("Usage: /search <query> [--provider <provider>] [--max <number>] [--enhancement <mode>]")
        print_info("Enhancement modes: auto (default), disabled, fast, semantic, hybrid")
        return

    # Check if search is enabled
    if not self.config.search.enabled:
        print_error("Web search is disabled in configuration")
        return

    # Parse enhanced search arguments
    args = self._parse_enhanced_search_args(search_args)
    if not args:
        return

    query = args["query"]
    provider = args.get("provider") or self.config.search.default_provider
    max_results = args.get("max_results") or self.config.search.max_results
    enhancement = args.get("enhancement") or self.config.search.default_enhancement.value
    technical_level = args.get("technical_level") or self.config.search.default_technical_level
    timeframe = args.get("timeframe") or self.config.search.default_timeframe

    try:
        print_info(f"🔍 Searching for: {query}")
        if enhancement != "disabled":
            print_info(f"✨ Using {enhancement} enhancement mode...")

        # Get conversation context for enhancement
        conversation_context = self._get_search_context(session)

        # Execute enhanced search using the new web_search tool
        search_response = asyncio.run(self._execute_enhanced_search(
            query=query,
            provider=provider,
            max_results=max_results,
            enhancement=enhancement,
            technical_level=technical_level,
            timeframe=timeframe,
            conversation_context=conversation_context,
            session=session
        ))

        # Display enhancement details if used
        if enhancement != "disabled" and "enhancement_details" in search_response:
            self._display_enhancement_info(search_response["enhancement_details"])

        # Generate AI-powered response using search results
        if self.config.search.ai_response:
            print_info("🤖 Generating AI-powered response...")
            ai_response = self._generate_search_ai_response(
                query, search_response, session
            )

            # Print the AI response
            print_message("Nova", ai_response)

            # Add to conversation history
            session.add_user_message(f"/search {query}")
            session.add_assistant_message(ai_response)
        else:
            # Display enhanced search results
            self._display_enhanced_search_results(search_response)

    except Exception as e:
        print_error(f"Enhanced search failed: {e}")
        print_info("Try using --enhancement disabled for basic search")
```

## Phase 3: Implementation Phases

### Phase 3A: Foundation (Week 1)

**Dependencies Update:**
```bash
# Add core NLP dependencies
uv add spacy yake

# Download spaCy model
uv run python -m spacy download en_core_web_sm

# Optional semantic enhancement
uv add keybert sentence-transformers --optional
```

**Tasks:**
1. **Create nova/search/ directory structure**
2. **Move existing search functionality:**
   - Migrate `nova/core/search.py` → `nova/search/engines/`
   - Extract SearchResult, SearchResponse models → `nova/search/models.py`
   - Create base search engine interface
3. **Implement keyword extraction:**
   - `nova/search/enhancement/extractors.py` (YAKE + KeyBERT)
   - Basic term classification logic
4. **Update imports across codebase**
5. **Ensure backward compatibility**

### Phase 3B: Core Enhancement (Week 2)

**Tasks:**
1. **Implement query enhancement pipeline:**
   - `nova/search/enhancement/enhancer.py` - Main enhancement logic
   - `nova/search/enhancement/classifier.py` - Term prioritization
   - Three-stage pipeline: NLP → LLM → JSON
2. **Create enhanced search manager:**
   - `nova/search/manager.py` - Replaces core/search.py
   - Integration with enhancement pipeline
   - Result merging and deduplication
3. **Add configuration system:**
   - `nova/search/config.py` - Centralized search configuration
   - Integration with existing NovaConfig

### Phase 3C: Tool and Chat Integration (Week 3)

**Tasks:**
1. **Replace web_search tool:**
   - Complete rewrite of `nova/tools/built_in/web_search.py`
   - Maintain backward compatibility
   - Add enhancement mode parameter with config defaults
2. **Enhanced /search command integration:**
   - Update `_handle_search_command()` method in `nova/core/chat.py`
   - Add argument parsing for new enhancement options
   - Integrate conversation context extraction
   - Add enhancement information display
3. **Add conversation context integration:**
   - Auto-inject context from chat history
   - Conversation-aware enhancement
4. **Performance optimization:**
   - Caching layer for enhanced queries
   - Lazy model loading
   - Performance metrics

### Phase 3D: Testing & Polish (Week 4)

**Tasks:**
1. **Comprehensive testing:**
   - Unit tests for all enhancement components
   - Integration tests for web_search tool and /search command
   - Performance benchmarks
2. **Documentation:**
   - Update CLAUDE.md with new search capabilities
   - Add usage examples and performance guidance
3. **Migration:**
   - Remove deprecated `nova/core/search.py`
   - Update all imports
   - Clean up old test files

## Phase 4: Enhanced Configuration System

### 4.1 Updated SearchConfig with Enhancement Options

```python
# nova/models/config.py - Enhanced SearchConfig

class SearchEnhancementMode(str, Enum):
    """Available search enhancement modes"""
    AUTO = "auto"           # Automatically choose best enhancement
    DISABLED = "disabled"   # No enhancement, direct search
    FAST = "fast"          # YAKE-only enhancement (~50ms)
    SEMANTIC = "semantic"   # KeyBERT semantic analysis (~200-500ms)
    HYBRID = "hybrid"      # Combined YAKE + KeyBERT (~300-600ms)
    ADAPTIVE = "adaptive"  # Choose based on query complexity

class SearchConfig(BaseModel):
    """Configuration for web search functionality"""

    # Existing configuration
    enabled: bool = Field(default=True, description="Enable web search functionality")
    default_provider: str = Field(
        default="duckduckgo", description="Default search provider"
    )
    max_results: int = Field(
        default=5, description="Default maximum search results", gt=0, le=50
    )
    ai_response: bool = Field(  # Renamed from use_ai_answers for consistency
        default=True,
        description="Generate AI-powered answers from search results instead of showing raw results",
    )
    google: dict[str, str] = Field(
        default_factory=dict,
        description="Google Custom Search configuration (api_key, search_engine_id)",
    )
    bing: dict[str, str] = Field(
        default_factory=dict, description="Bing Search API configuration (api_key)"
    )

    # NEW: Search Enhancement Configuration
    default_enhancement: SearchEnhancementMode = Field(
        default=SearchEnhancementMode.FAST,
        description="Default search enhancement mode for /search command and web_search tool"
    )
    enable_conversation_context: bool = Field(
        default=True,
        description="Use recent conversation history to enhance search queries"
    )
    context_messages_count: int = Field(
        default=5,
        description="Number of recent messages to use for context",
        ge=0, le=20
    )
    default_technical_level: str = Field(
        default="intermediate",
        description="Default technical level for search queries",
        pattern="^(beginner|intermediate|expert)$"
    )
    default_timeframe: str = Field(
        default="any",
        description="Default timeframe preference for search results",
        pattern="^(recent|past_year|any)$"
    )

    # Performance and Caching
    enhancement_cache_enabled: bool = Field(
        default=True,
        description="Cache enhanced queries to improve performance"
    )
    enhancement_cache_duration_minutes: int = Field(
        default=15,
        description="How long to cache enhanced queries",
        gt=0, le=1440  # Max 24 hours
    )
    performance_mode: bool = Field(
        default=True,
        description="Prioritize speed over semantic accuracy in enhancements"
    )

    # Keyword Extraction Configuration
    extraction_backend: str = Field(
        default="yake_only",
        description="Keyword extraction backend",
        pattern="^(yake_only|keybert_only|hybrid|adaptive)$"
    )
    enable_keybert: bool = Field(
        default=False,
        description="Enable KeyBERT semantic extraction (requires additional dependencies)"
    )
    yake_max_keywords: int = Field(
        default=10,
        description="Maximum keywords to extract using YAKE",
        gt=0, le=50
    )
    keybert_max_keywords: int = Field(
        default=6,
        description="Maximum keywords to extract using KeyBERT",
        gt=0, le=20
    )
    keybert_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="KeyBERT model name for semantic extraction"
    )
```

### 4.2 Configuration File Examples

**nova-config.yaml with search enhancement:**
```yaml
# nova-config.yaml
search:
  enabled: true
  default_provider: "duckduckgo"
  max_results: 5
  ai_response: true

  # Enhancement Configuration
  default_enhancement: "fast"           # fast, semantic, hybrid, disabled, auto
  enable_conversation_context: true
  context_messages_count: 5
  default_technical_level: "intermediate"  # beginner, intermediate, expert
  default_timeframe: "any"             # recent, past_year, any

  # Performance Options
  enhancement_cache_enabled: true
  enhancement_cache_duration_minutes: 15
  performance_mode: true

  # Keyword Extraction
  extraction_backend: "yake_only"      # yake_only, keybert_only, hybrid
  enable_keybert: false               # Set to true for semantic enhancement
  yake_max_keywords: 10
  keybert_max_keywords: 6
  keybert_model: "all-MiniLM-L6-v2"

# For users who want semantic enhancement
# search:
#   default_enhancement: "semantic"
#   enable_keybert: true
#   extraction_backend: "hybrid"
#   performance_mode: false
```

## Phase 5: Three-Stage Enhancement Architecture

### 5.1 Swappable KeyBERT/YAKE Architecture

```python
"""Performance-optimized keyword extraction with swappable backends"""

class ExtractionBackend(str, Enum):
    """Available keyword extraction backends"""
    YAKE_ONLY = "yake_only"          # Fast, lightweight (default)
    KEYBERT_ONLY = "keybert_only"    # Semantic, requires transformers
    HYBRID = "hybrid"                # YAKE + KeyBERT for best results
    ADAPTIVE = "adaptive"            # Auto-choose based on query complexity

class HybridKeywordExtractor:
    """High-performance keyword extractor with swappable backends"""

    def extract_keywords_optimized(self, text: str, max_keywords: int = 10) -> List[KeywordResult]:
        """Extract keywords using the optimal strategy based on configuration"""

        if self.config.backend == ExtractionBackend.YAKE_ONLY:
            return self._extract_yake_only(text, max_keywords)

        elif self.config.backend == ExtractionBackend.KEYBERT_ONLY:
            return self._extract_keybert_only(text, max_keywords)

        elif self.config.backend == ExtractionBackend.HYBRID:
            return self._extract_hybrid(text, max_keywords)

        elif self.config.backend == ExtractionBackend.ADAPTIVE:
            return self._extract_adaptive(text, max_keywords)
```

### 5.2 Three-Stage Enhancement Pipeline

**Stage 1: NLP Term Extraction & Classification**
- spaCy finds named entities and technical terms
- YAKE/KeyBERT scores high-signal terms
- Output split into must_have_terms (entities + top terms) and nice_to_have_terms

**Stage 2: LLM-Guided Query Generation**
- Structured prompt forces LLM to use must-have terms
- LLM gets memory constraints (locale, preferred sites, recency)
- Include conversation context and user preferences

**Stage 3: JSON-Driven Search Execution**
- Parse LLM JSON response into search queries
- Execute multiple optimized queries in parallel
- Merge and deduplicate results with relevance ranking

```python
class StructuredQueryEnhancer:
    """Three-stage query enhancement: NLP → LLM → JSON execution"""

    async def enhance_query_structured(
        self,
        user_query: str,
        conversation_context: str = "",
        memory_constraints: SearchMemoryConstraints = None,
        max_queries: int = 3
    ) -> EnhancedSearchPlan:
        """
        Three-stage enhancement pipeline:
        1. NLP extracts and classifies terms
        2. LLM creates structured search plan with constraints
        3. JSON output drives search execution
        """

        # Stage 1: NLP Term Extraction
        extracted_terms = self._extract_and_classify_terms(user_query, conversation_context)

        # Stage 2: Structured LLM Planning
        if self.ai_client:
            search_plan = await self._generate_structured_search_plan(
                user_query=user_query,
                extracted_terms=extracted_terms,
                memory_constraints=memory_constraints or SearchMemoryConstraints(),
                max_queries=max_queries
            )
        else:
            # Fallback: rule-based query generation
            search_plan = self._fallback_search_plan(user_query, extracted_terms, max_queries)

        return search_plan
```

## Phase 6: Testing and Migration Strategy

### 6.1 Test Structure

```
tests/
├── unit/
│   ├── search/                     # NEW: Search module tests
│   │   ├── test_extractors.py     # YAKE/KeyBERT extraction tests
│   │   ├── test_enhancer.py       # Query enhancement tests
│   │   ├── test_classifier.py     # Term classification tests
│   │   ├── test_manager.py        # Search manager tests
│   │   └── test_engines.py        # Search engine tests
│   ├── test_tools_web_search.py   # UPDATED: Enhanced tool tests
│   └── test_chat_search_command.py # NEW: /search command tests
├── integration/
│   ├── test_search_flow.py        # END-to-end search testing
│   ├── test_search_chat_flow.py   # NEW: End-to-end /search testing
│   └── test_enhancement_performance.py  # Performance benchmarks
└── fixtures/
    └── search_test_data.py         # Test data for search scenarios
```

### 6.2 Migration Safety

**Gradual Migration Approach:**
1. **Phase 3A**: New search module alongside existing code
2. **Phase 3B**: Enhanced functionality available but not default
3. **Phase 3C**: New web_search tool and /search command with backward compatibility
4. **Phase 3D**: Remove deprecated code after verification

**Rollback Plan:**
- Keep `nova/core/search.py` until Phase 3D complete
- Feature flags for enhancement modes
- Automatic fallback to basic search on enhancement failure

### 6.3 Performance Testing

**Benchmark Suite:**
```python
class TestEnhancementPerformance:

    def test_yake_extraction_speed(self):
        """YAKE extraction should complete <50ms for typical queries"""

    def test_keybert_extraction_speed(self):
        """KeyBERT extraction timing (baseline for comparison)"""

    def test_enhancement_modes_comparison(self):
        """Compare all enhancement modes: disabled, fast, semantic, hybrid"""

    def test_memory_usage(self):
        """Memory footprint of different extraction backends"""

    def test_concurrent_searches(self):
        """Performance under concurrent search load"""
```

## Updated CLAUDE.md Documentation

```markdown
## Enhanced Web Search Commands

Nova includes intelligent search with context-aware query enhancement through both tools and chat commands.

### /search Command (Enhanced)

**Basic Usage:**
```bash
/search <query>                    # Uses your configured default enhancement
/s <query>                        # Short form
```

**Advanced Usage:**
```bash
/search <query> --enhancement fast              # YAKE keyword extraction (~50ms)
/search <query> --enhancement semantic          # KeyBERT semantic analysis (~200-500ms)
/search <query> --enhancement hybrid            # Combined YAKE + KeyBERT (~300-600ms)
/search <query> --enhancement disabled          # Direct search without enhancement

/search <query> --provider google --max 3       # Existing options still work
/search <query> --technical-level expert        # Adjust query complexity
/search <query> --timeframe recent              # Prefer recent results
```

### Tool Usage (Alternative)

```bash
/tool web_search query="Python async programming" enhancement="fast"
/tool web_search query="machine learning deployment" enhancement="semantic"
```

### Search Enhancement Configuration

Configure default search behavior in your configuration file:

```yaml
search:
  # Enhancement defaults (users can override per search)
  default_enhancement: "fast"           # auto, disabled, fast, semantic, hybrid
  enable_conversation_context: true     # Use chat history for context
  default_technical_level: "intermediate"  # beginner, intermediate, expert
  default_timeframe: "any"             # recent, past_year, any

  # Performance settings
  performance_mode: true               # Prioritize speed over accuracy
  enhancement_cache_enabled: true     # Cache enhanced queries

  # Advanced: Enable semantic analysis
  enable_keybert: false               # Set to true for KeyBERT
  extraction_backend: "yake_only"      # yake_only, keybert_only, hybrid
```

### CLI Configuration Commands

```bash
# Configure search enhancement defaults
uv run nova config search --enhancement fast --context --technical-level intermediate

# Show current search configuration
uv run nova config show search
```

### Performance Guidance

- Use **fast** or default for most queries (optimal speed/accuracy balance)
- Use **semantic** for complex technical topics or research
- Use **disabled** for exact phrase searches or when speed is critical
- The system automatically uses conversation context to improve search relevance
```

## Success Criteria

**Phase 3A Complete:**
- ✅ All existing search functionality working via new `nova/search/` module
- ✅ No breaking changes to existing API
- ✅ Basic YAKE keyword extraction working

**Phase 3B Complete:**
- ✅ Three-stage enhancement pipeline functional
- ✅ Multiple extraction backends (YAKE, KeyBERT, Hybrid) working
- ✅ LLM-guided query optimization with structured prompts

**Phase 3C Complete:**
- ✅ Enhanced `web_search` tool with new parameters and config defaults
- ✅ Enhanced `/search` command with new parameters and config defaults
- ✅ Backward compatibility maintained for both tool and command
- ✅ Conversation context integration working

**Phase 3D Complete:**
- ✅ All tests passing including performance benchmarks
- ✅ Documentation updated
- ✅ Old `nova/core/search.py` removed
- ✅ Performance targets met:
  - YAKE enhancement: <100ms
  - KeyBERT enhancement: <1000ms
  - Hybrid enhancement: <1500ms

## Dependencies

**Core Requirements (always installed):**
```toml
[project]
dependencies = [
    "spacy>=3.7.0",     # Core NLP (required)
    "yake>=0.4.8",      # Fast keyword extraction (required)
]
```

**Optional Semantic Enhancement:**
```toml
[project.optional-dependencies]
search-semantic = [
    "keybert>=0.8.0",               # Semantic keyword extraction
    "sentence-transformers>=2.2.0"  # BERT models for KeyBERT
]
```

**Installation:**
```bash
# Core enhanced search (YAKE-based)
uv add spacy yake
uv run python -m spacy download en_core_web_sm

# Optional: Full semantic enhancement
uv add keybert sentence-transformers --optional
```

This plan provides a comprehensive approach to implementing enhanced search functionality while maintaining backward compatibility, providing performance flexibility, and creating a robust foundation for future search enhancements.
