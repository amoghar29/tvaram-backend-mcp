import os

DEFAULT_CLIENT_ID = "tvram-mcp"
DEFAULT_CLIENT_SECRET = "local-dev-secret"

API_BASE = "/api"
API_VERSION = "/v1"
API_PREFIX = f"{API_BASE}{API_VERSION}"

MOCK_HOST = os.environ.get("MOCK_HOST", "127.0.0.1")
MOCK_PORT = int(os.environ.get("MOCK_PORT", "8000"))

MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8001"))

MCP_BASE_URL = os.environ.get("MCP_BASE_URL", f"http://{MCP_HOST}:{MCP_PORT}")
MCP_AUTH_ENABLED = os.environ.get("MCP_AUTH", "true").strip().lower() not in {
    "0",
    "false",
    "no",
}
MCP_SCOPE = "email:verify"

SERVER_CLIENT_ID = os.environ.get("MOCK_CLIENT_ID", DEFAULT_CLIENT_ID)
SERVER_CLIENT_SECRET = os.environ.get("MOCK_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)
TOKEN_TTL_SECONDS = int(os.environ.get("MOCK_TOKEN_TTL_SECONDS", "300"))

VERIFIER_BASE_URL = os.environ.get("VERIFIER_BASE_URL", f"http://{MOCK_HOST}:{MOCK_PORT}")
VERIFIER_CLIENT_ID = os.environ.get("VERIFIER_CLIENT_ID", DEFAULT_CLIENT_ID)
VERIFIER_CLIENT_SECRET = os.environ.get("VERIFIER_CLIENT_SECRET", DEFAULT_CLIENT_SECRET)

MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 0.25
TOKEN_EXPIRY_MARGIN_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 10.0
