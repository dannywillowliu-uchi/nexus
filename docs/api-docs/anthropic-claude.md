# Anthropic Claude API Reference

## Base URL
`https://api.anthropic.com`

## Authentication
API key via header: `x-api-key: YOUR_ANTHROPIC_API_KEY`
Also requires: `anthropic-version: 2023-06-01`

## Models
- `claude-opus-4-6` — Most capable, complex reasoning
- `claude-sonnet-4-6` — Fast + capable balance
- `claude-haiku-4-5-20251001` — Fastest, cheapest

## Core Endpoint

### POST /v1/messages
Create a message (completion).

```json
{
	"model": "claude-sonnet-4-6",
	"max_tokens": 4096,
	"messages": [
		{"role": "user", "content": "Analyze this protein interaction..."}
	],
	"system": "You are a biomedical research assistant.",
	"temperature": 0.7
}
```

**Response:**
```json
{
	"id": "msg_...",
	"type": "message",
	"role": "assistant",
	"content": [{"type": "text", "text": "..."}],
	"model": "claude-sonnet-4-6",
	"stop_reason": "end_turn",
	"usage": {"input_tokens": 42, "output_tokens": 128}
}
```

## Streaming
Set `"stream": true` in request body. Returns SSE events:
- `message_start` — Message metadata
- `content_block_start` — New content block
- `content_block_delta` — Incremental text (`{"type": "text_delta", "text": "..."}`)
- `content_block_stop` — Block complete
- `message_delta` — Stop reason, usage
- `message_stop` — Stream complete

## Tool Use
```json
{
	"model": "claude-sonnet-4-6",
	"max_tokens": 1024,
	"tools": [
		{
			"name": "search_pubmed",
			"description": "Search PubMed for papers",
			"input_schema": {
				"type": "object",
				"properties": {
					"query": {"type": "string"},
					"max_results": {"type": "integer", "default": 10}
				},
				"required": ["query"]
			}
		}
	],
	"messages": [{"role": "user", "content": "Find papers about curcumin and inflammation"}]
}
```

When the model wants to use a tool, response contains:
```json
{
	"content": [
		{"type": "text", "text": "I'll search for relevant papers."},
		{"type": "tool_use", "id": "toolu_...", "name": "search_pubmed", "input": {"query": "curcumin inflammation"}}
	],
	"stop_reason": "tool_use"
}
```

Return tool results:
```json
{
	"role": "user",
	"content": [
		{"type": "tool_result", "tool_use_id": "toolu_...", "content": "Found 42 papers..."}
	]
}
```

## Rate Limits
- Tier 1 (default): 50 req/min, 40K input tokens/min, 8K output tokens/min
- Tier 4: 4000 req/min, 400K input tokens/min, 80K output tokens/min
- Rate limit headers: `anthropic-ratelimit-requests-remaining`, `retry-after`

## Python SDK
```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY env var

message = client.messages.create(
	model="claude-sonnet-4-6",
	max_tokens=4096,
	messages=[{"role": "user", "content": "..."}],
)
print(message.content[0].text)
```

Async:
```python
client = anthropic.AsyncAnthropic()
message = await client.messages.create(...)
```

Streaming:
```python
with client.messages.stream(model="claude-sonnet-4-6", max_tokens=1024, messages=[...]) as stream:
	for text in stream.text_stream:
		print(text, end="")
```

## Error Codes
- 400: Invalid request (bad params)
- 401: Invalid API key
- 403: Permission denied
- 429: Rate limited (retry with backoff)
- 500: Internal error
- 529: API overloaded

## Nexus Usage
- Reasoning agent uses Claude for hypothesis evaluation and ABC triple scoring
- Literature agent uses Claude for paper extraction and summarization
- Pipeline uses tool_use for agent-driven validation orchestration

## Source
- https://docs.anthropic.com/en/api/messages
- https://docs.anthropic.com/en/docs/build-with-claude/tool-use
