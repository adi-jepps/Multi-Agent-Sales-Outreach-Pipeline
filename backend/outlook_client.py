"""
Creates real Outlook drafts via Microsoft Graph - and only ever drafts. The
requested scope is Mail.ReadWrite, never Mail.Send, so the token this app
holds is structurally incapable of sending, not just well-behaved by
convention. The only Graph call made is POST /me/messages, which Microsoft's
own docs confirm always lands in the Drafts folder (isDraft: true) - actually
sending a message is a different operation this code never calls.

Authorization is a separate, one-time, human-run step - see
scripts/authorize_outlook.py. This module never prompts interactively; if no
cached token is available it raises, telling the caller to run that script.
"""

import os

import msal
import requests

TOKEN_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".msal_token_cache.bin")

SCOPES = ["Mail.ReadWrite"]
GRAPH_MESSAGES_URL = "https://graph.microsoft.com/v1.0/me/messages"


def _client_id() -> str:
    # Read lazily (not as a module-level constant) so this works regardless
    # of whether load_dotenv() ran before or after this module was imported.
    return os.getenv("MS_GRAPH_CLIENT_ID")


def authority() -> str:
    return f"https://login.microsoftonline.com/{os.getenv('MS_GRAPH_TENANT_ID')}"


def load_token_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, encoding="utf-8") as f:
            cache.deserialize(f.read())
    return cache


def save_token_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        with open(TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def build_app(cache: msal.SerializableTokenCache) -> msal.PublicClientApplication:
    """Public so scripts/authorize_outlook.py can build the same app instance
    for the one-time device-code sign-in."""
    return msal.PublicClientApplication(_client_id(), authority=authority(), token_cache=cache)


def _acquire_token() -> str:
    if not os.getenv("MS_GRAPH_CLIENT_ID") or not os.getenv("MS_GRAPH_TENANT_ID"):
        raise RuntimeError(
            "Outlook isn't configured - set MS_GRAPH_CLIENT_ID and MS_GRAPH_TENANT_ID in backend/.env."
        )

    cache = load_token_cache()
    app = build_app(cache)
    accounts = app.get_accounts()

    if not accounts:
        raise RuntimeError("Outlook isn't authorized yet - run `python scripts/authorize_outlook.py` once.")

    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    save_token_cache(cache)

    if not result or "access_token" not in result:
        raise RuntimeError(
            "Outlook authorization expired or was revoked - run `python scripts/authorize_outlook.py` again."
        )

    return result["access_token"]


def create_draft(subject: str, body: str, to_address: str) -> dict:
    """
    Creates a draft in the authorized mailbox's Drafts folder, addressed to
    to_address. Never sends - only ever calls POST /me/messages.
    """
    access_token = _acquire_token()

    response = requests.post(
        GRAPH_MESSAGES_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to_address}}],
        },
        timeout=30,
    )

    if response.status_code != 201:
        raise RuntimeError(f"Outlook API error ({response.status_code}): {response.text}")

    data = response.json()
    return {"id": data["id"], "web_link": data.get("webLink")}
