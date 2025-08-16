# Search Enhancement Simplification Plan

## Current Problems - Brittleness Analysis

### 1. **Over-Complex Pipeline Architecture**
- Three-stage pipeline: NLP extraction → LLM planning → JSON execution
- Each stage can fail independently, requiring complex error handling
- Far too complex for basic search query enhancement

### 2. **Multiple Fragile Dependencies**
- spaCy (requires model download: `en_core_web_sm`)
- YAKE keyword extraction
- KeyBERT + sentence-transformers (optional but complex)
- Multiple fallback chains when dependencies fail

### 3. **Brittle LLM JSON Parsing**
- Relies on LLM returning perfect JSON format
- Complex parsing logic to handle markdown code blocks
- Single malformed response breaks the entire enhancement
- JSON schema validation adds unnecessary complexity

### 4. **Configuration Explosion**
- 6 enhancement modes (auto, disabled, fast, semantic, hybrid, adaptive)
- 4 extraction backends (yake_only, keybert_only, hybrid, adaptive)
- Technical levels, timeframes, performance modes, timeout configs
- Each combination can behave differently and fail in unique ways

### 5. **Cascading Failure Points**
```
spaCy fails → KeyBERT fails → AI client fails → LLM timeouts → JSON parsing fails
```
Each failure requires its own fallback logic, creating maintenance nightmare

### 6. **Heavy Resource Overhead**
- Loading multiple ML models on startup
- Complex caching mechanisms
- Multiple AI API calls per search

## Proposed Simpler, More Resilient Design

### **Single-Step Approach**
Replace entire pipeline with:
1. Simple prompt: "Suggest 2-3 alternative search queries for: {original_query}"
2. Parse response as plain text (not JSON)
3. Use original query if anything fails

### **Eliminate Dependencies**
- Remove spaCy, YAKE, KeyBERT entirely
- Use basic string processing if keyword extraction needed
- Let the AI handle all intelligence

### **Two-Mode Configuration**
- `enhanced`: Use AI to suggest alternatives (default)
- `disabled`: Use original query only
- Remove all other complexity

### **Robust Fallback**
```python
try:
    enhanced_queries = await simple_ai_enhance(query)
except:
    enhanced_queries = [query]  # Always fallback to original
```

## Key Benefits of Simplified Approach

1. **Massive reduction in complexity** - 90% less code
2. **Fewer failure points** - Single try/catch vs cascading failures
3. **No external ML dependencies** - Just use existing AI client
4. **Easier to debug and maintain**
5. **More predictable behavior**
6. **Faster startup time** - No model loading
7. **Better resource usage** - No background ML processes

## Implementation Strategy

1. Create new simple enhancement module alongside existing one
2. Add feature flag to switch between old/new systems
3. Test new system thoroughly
4. Gradually migrate users to new system
5. Remove old complex system once proven

## Files to Modify/Remove

**Remove entirely:**
- `nova/search/enhancement/extractors.py`
- `nova/search/enhancement/classifier.py`
- Most of `nova/search/enhancement/enhancer.py`

**Simplify:**
- `nova/search/models.py` - Remove complex models
- `nova/tools/built_in/web_search.py` - Simplify parameters
- Configuration - Reduce options to just `enhanced`/`disabled`

**Create:**
- `nova/search/enhancement/simple_enhancer.py` - New minimal implementation

The current system is a classic over-engineering case - the complexity far exceeds the value delivered. A much simpler approach would be more reliable, maintainable, and actually more resilient.
