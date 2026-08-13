# tvram-backend-mcp

An MCP server that exposes email verification as a tool an agent can call.

[![Demo video](https://drive.google.com/thumbnail?id=1bLt6Izvmd2o1jFf0qVUxLTcWSwYfa2HD&sz=w1000)](https://drive.google.com/file/d/1bLt6Izvmd2o1jFf0qVUxLTcWSwYfa2HD/view?usp=sharing)

```
verify_email(address) -> { address, verdict: valid | invalid | risky, reason }
```

## Assumptions
- We only design and build the mcp servers and not the actual logic and implementation behind the email verification .
- MCP auth needs to be handled ( a demoable piece and not actual auth for now) , just a visual representation of it works . 


## The tool contract

This is what a model actually receives, from a live `tools/list`:

```json
{"name": "verify_email",
 "description": "Check whether an email address can receive mail. Returns a verdict of
   \"valid\" (well formed and not flagged), \"invalid\" (malformed, mail cannot be
   delivered), or \"risky\" (well formed but on a disposable provider, so delivery is
   unreliable), together with the reason the verdict was reached. Accepts one address
   per call.",
 "inputSchema": {"type": "object", "additionalProperties": false,
                 "properties": {"address": {"type": "string"}},
                 "required": ["address"]},
 "outputSchema": {"type": "object",
   "properties": {
     "address": {"type": "string", "description": "The address that was checked, lowercased."},
     "verdict": {"type": "string", "enum": ["valid", "invalid", "risky"],
                 "description": "valid: syntax is well formed and the address looks
                   deliverable. invalid: syntax is malformed, the address cannot receive
                   mail. risky: syntax is well formed but the domain is a disposable
                   provider, so delivery is unreliable."},
     "reason":  {"type": "string", "description": "Which rule produced the verdict."}},
   "required": ["address", "verdict", "reason"]}}
```

Results come back as `structuredContent`, so an agent branches on `verdict` without
parsing prose:

```json
{"address": "alice@example.com",    "verdict": "valid",   "reason": "syntax is well formed and the domain is not flagged"}
{"address": "not-an-email",         "verdict": "invalid", "reason": "address does not match the expected email syntax"}
{"address": "alice@mailinator.com", "verdict": "risky",   "reason": "mailinator.com is a disposable email provider"}
```

### Design choices

- Reason for all result irrespective of valid/risky/invalid . 
- Standalone service that can be run .

## Error handling

- Return only user related errors and not system internal errors, in case of system error just return `internal server error`

## Retry and backoff

`MAX_RETRIES = 2` with `0.25 * 2**attempt` — three attempts over roughly 0.75s of waiting.

- Only 5xx errors are retried since its related to the sever handling whereas 4xx errors means the user/api input is not valid .

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run python mock_server.py    # mock backend       on 127.0.0.1:8000
uv run python mcp_server.py     # MCP server
```

Copy `.env.example` to `.env` to change anything; every value there is already the
built-in default, so it runs with no configuration at all.

### Connecting an agent

With both servers running:

```bash
claude mcp add --transport http tvram-email-verification http://127.0.0.1:8001/mcp
```

Then `/mcp` → select the server → **Authenticate**. A browser opens a consent screen;
approving redirects back and the connection completes.
