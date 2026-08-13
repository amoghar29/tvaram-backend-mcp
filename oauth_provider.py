import secrets
from urllib.parse import urlencode

from fastmcp.server.auth.providers.in_memory import InMemoryOAuthProvider
from mcp.server.auth.provider import (
    AuthorizationParams,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

CONSENT_PATH = "/consent"

SCOPE_DESCRIPTIONS = {
    "email:verify": "Check whether an email address is deliverable",
}

CONSENT_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Authorize access</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, sans-serif;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0; background: Canvas; color: CanvasText;
  }}
  .card {{
    width: min(28rem, calc(100vw - 3rem));
    border: 1px solid color-mix(in srgb, CanvasText 15%, transparent);
    border-radius: 12px; padding: 1.75rem;
  }}
  h1 {{ font-size: 1.15rem; margin: 0 0 .35rem; }}
  .sub {{ margin: 0 0 1.25rem; opacity: .7; font-size: .9rem; }}
  ul {{ list-style: none; padding: 0; margin: 0 0 1.5rem; }}
  li {{
    padding: .6rem .75rem; border-radius: 8px; font-size: .9rem;
    background: color-mix(in srgb, CanvasText 6%, transparent);
  }}
  li + li {{ margin-top: .4rem; }}
  form {{ display: flex; gap: .6rem; }}
  button {{
    flex: 1; padding: .6rem 1rem; border-radius: 8px; font: inherit;
    font-weight: 500; cursor: pointer;
    border: 1px solid color-mix(in srgb, CanvasText 20%, transparent);
    background: transparent; color: inherit;
  }}
  button[value="approve"] {{ background: CanvasText; color: Canvas; border-color: CanvasText; }}
</style>
<div class="card">
  <h1>Authorize {client_name}</h1>
  <p class="sub">is requesting access to <strong>tvram-email-verification</strong></p>
  <ul>{scopes}</ul>
  <form method="post" action="{action}">
    <input type="hidden" name="pending" value="{pending}">
    <button name="decision" value="deny">Deny</button>
    <button name="decision" value="approve">Approve</button>
  </form>
</div>
"""


class ConsentOAuthProvider(InMemoryOAuthProvider):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pending: dict[str, tuple[OAuthClientInformationFull, AuthorizationParams]] = {}

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Park the request and send the browser to the consent screen.

        The handler 302s to whatever this returns, so returning our own page
        interposes the human step. `super().authorize` is what actually mints the
        code, and it only runs once someone clicks Approve.
        """
        pending = secrets.token_urlsafe(16)
        self._pending[pending] = (client, params)
        return f"{self._external_url(CONSENT_PATH)}?{urlencode({'pending': pending})}"

    def _external_url(self, path: str) -> str:
        return f"{str(self.base_url).rstrip('/')}{path}"

    async def _render_consent(self, request: Request) -> Response:
        pending = request.query_params.get("pending", "")
        parked = self._pending.get(pending)
        if parked is None:
            return HTMLResponse("<p>This authorization request expired.</p>", status_code=400)

        client, params = parked
        scopes = params.scopes or list(SCOPE_DESCRIPTIONS)
        return HTMLResponse(
            CONSENT_PAGE.format(
                client_name=client.client_name or client.client_id,
                action=CONSENT_PATH,
                pending=pending,
                scopes="".join(
                    f"<li>{SCOPE_DESCRIPTIONS.get(scope, scope)}</li>" for scope in scopes
                ),
            )
        )

    async def _submit_consent(self, request: Request) -> Response:
        form = await request.form()
        pending = str(form.get("pending", ""))

        parked = self._pending.pop(pending, None)
        if parked is None:
            return HTMLResponse("<p>This authorization request expired.</p>", status_code=400)

        client, params = parked

        if form.get("decision") != "approve":
            return RedirectResponse(
                construct_redirect_uri(
                    str(params.redirect_uri),
                    error="access_denied",
                    error_description="the user declined the request",
                    state=params.state,
                ),
                status_code=302,
            )

        return RedirectResponse(await super().authorize(client, params), status_code=302)

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        return [
            *super().get_routes(mcp_path),
            Route(CONSENT_PATH, self._render_consent, methods=["GET"]),
            Route(CONSENT_PATH, self._submit_consent, methods=["POST"]),
        ]
