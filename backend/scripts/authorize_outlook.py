"""
One-time interactive authorization for Outlook draft-creation.

Run this once per machine (and again only if the token cache is deleted or
fully expires). It signs in via Microsoft's device-code flow - you'll be
given a URL and a short code; open the URL on any device, enter the code,
and sign in AS THE MAILBOX YOU WANT DRAFTS CREATED IN (e.g.
ajeppu@egglighting.com), not necessarily your own account.

Requires MS_GRAPH_CLIENT_ID and MS_GRAPH_TENANT_ID in backend/.env - see
README.md "Outlook draft setup" for the Azure app-registration steps that
produce those values.

Usage (from backend/):
    venv\\Scripts\\python.exe scripts\\authorize_outlook.py
"""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from outlook_client import SCOPES, build_app, load_token_cache, save_token_cache  # noqa: E402

load_dotenv()


def main() -> None:
    if not os.getenv("MS_GRAPH_CLIENT_ID") or not os.getenv("MS_GRAPH_TENANT_ID"):
        print("Set MS_GRAPH_CLIENT_ID and MS_GRAPH_TENANT_ID in backend/.env first.")
        raise SystemExit(1)

    cache = load_token_cache()
    app = build_app(cache)

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"Failed to start device flow: {flow.get('error_description', flow)}")
        raise SystemExit(1)

    print(flow["message"])  # "To sign in, use a web browser to open ... and enter the code ... to authenticate."
    print("\nSign in as the mailbox you want drafts created in (e.g. ajeppu@egglighting.com).")

    result = app.acquire_token_by_device_flow(flow)  # blocks until sign-in completes (or it times out)

    if "access_token" not in result:
        print(f"Authorization failed: {result.get('error_description', result)}")
        raise SystemExit(1)

    save_token_cache(cache)
    account = result.get("id_token_claims", {}).get("preferred_username", "unknown account")
    print(f"\nAuthorized as {account}. Token cache saved to backend/.msal_token_cache.bin")
    print("The backend can now create Outlook drafts without further interaction.")


if __name__ == "__main__":
    main()
