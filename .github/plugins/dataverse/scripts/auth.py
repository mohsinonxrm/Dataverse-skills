"""
auth.py — Acquire Dataverse tokens via Azure Identity.

Auth priority:
  1. Service principal (CLIENT_ID + CLIENT_SECRET in .env) — non-interactive
  2. Device code flow — opens browser automatically, retries once on expiry,
     then exits with a message on third failure.

Token caching:
  - Service principal: in-memory (tokens are short-lived, no persistent cache needed)
  - Device code: OS credential store (Windows Credential Manager, macOS Keychain,
    Linux libsecret) via TokenCachePersistenceOptions. An AuthenticationRecord is
    persisted alongside the token cache so that new processes can silently refresh
    without re-prompting the user.

Functions:
  load_env()            — loads .env into os.environ
  get_credential()      — returns a TokenCredential for use with DataverseClient
  get_token(scope=None) — returns a raw access token string

Usage:
    # For Web API scripts that need a Bearer token:
    from auth import get_token, load_env
    token = get_token()

    # For scripts using the Dataverse Python SDK:
    from auth import get_credential, load_env
    from PowerPlatform.Dataverse.client import DataverseClient
    load_env()
    client = DataverseClient(os.environ["DATAVERSE_URL"], get_credential())

Reads from .env in the repo root (parent of scripts/) or current working directory:
    DATAVERSE_URL      — required
    TENANT_ID          — required
    CLIENT_ID          — optional, enables service principal auth
    CLIENT_SECRET      — optional, enables service principal auth
"""

import os
import sys
import webbrowser
from pathlib import Path

# AuthenticationRecord is persisted here so new processes skip device code flow
_AUTH_RECORD_PATH = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / ".IdentityService" / "dataverse_cli_auth_record.json"

# Microsoft device codes expire after 900 seconds (15 minutes)
_DEVICE_CODE_TIMEOUT = 900

# Max auto-retries before giving up (opens browser on attempts 1 and 2,
# then exits with a message on attempt 3)
_MAX_AUTH_ATTEMPTS = 2


def load_env():
    """Load key=value pairs from .env into os.environ (does not overwrite existing vars).

    Searches for .env in two locations (first match wins):
      1. The repo root (parent of the directory containing this script)
      2. The current working directory
    This ensures ``cd scripts && python auth.py`` works the same as
    ``python scripts/auth.py`` from the repo root.
    """
    script_dir = Path(__file__).resolve().parent
    candidates = [script_dir.parent / ".env", Path(".env")]
    env_path = next((p for p in candidates if p.exists()), None)
    if env_path is not None:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _get_env_values():
    """Return (tenant_id, dataverse_url, client_id, client_secret) from env, or exit on missing required values."""
    load_env()
    tenant_id = os.environ.get("TENANT_ID")
    dataverse_url = os.environ.get("DATAVERSE_URL", "").rstrip("/")
    client_id = os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("CLIENT_SECRET")

    if not tenant_id or not dataverse_url:
        missing = [k for k, v in [("TENANT_ID", tenant_id), ("DATAVERSE_URL", dataverse_url)] if not v]
        print(f"ERROR: .env is missing required values: {', '.join(missing)}", flush=True)
        print("  Run the init sequence (/dataverse:init) to create .env.", flush=True)
        sys.exit(1)

    return tenant_id, dataverse_url, client_id, client_secret


def _build_device_code_credential(tenant_id, auth_record=None):
    """Create a fresh DeviceCodeCredential that auto-opens the browser."""
    from azure.identity import DeviceCodeCredential, TokenCachePersistenceOptions

    def _prompt_callback(verification_uri, user_code, _expires_on):
        webbrowser.open(verification_uri)
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\nBrowser opened -> URL: {verification_uri} [{timestamp}]", flush=True)
        print(f"Code: {user_code} (expires in {_DEVICE_CODE_TIMEOUT // 60} min)\n", flush=True)

    return DeviceCodeCredential(
        tenant_id=tenant_id,
        client_id="51f81489-12ee-4a9e-aaae-a2591f45987d",  # Well-known Microsoft Power Apps public client app ID
        prompt_callback=_prompt_callback,
        timeout=_DEVICE_CODE_TIMEOUT,
        cache_persistence_options=TokenCachePersistenceOptions(
            name="dataverse_cli",
            allow_unencrypted_storage=True,
        ),
        authentication_record=auth_record,
    )


_credential = None


def get_credential():
    """
    Return an Azure Identity TokenCredential, creating one on first call.

    The credential is cached for the lifetime of the process. Uses
    ClientSecretCredential when CLIENT_ID + CLIENT_SECRET are set,
    otherwise falls back to DeviceCodeCredential with persistent OS-level
    token caching.
    """
    global _credential
    if _credential is not None:
        return _credential

    tenant_id, _dataverse_url, client_id, client_secret = _get_env_values()

    try:
        from azure.identity import ClientSecretCredential
    except ImportError:
        print("ERROR: azure-identity not installed. Run: pip install azure-identity", flush=True)
        sys.exit(1)

    # Warn if only one of CLIENT_ID / CLIENT_SECRET is set
    if bool(client_id) != bool(client_secret):
        print("WARNING: Only one of CLIENT_ID / CLIENT_SECRET is set. Both are required for", flush=True)
        print("  service principal auth. Falling back to interactive device code flow.", flush=True)

    # Path 1: Service principal (non-interactive)
    if client_id and client_secret:
        _credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        # Path 2: Device code flow (interactive) with persistent OS-level token cache.
        # AuthenticationRecord tells the credential which cached account to silently
        # refresh, avoiding a device code prompt on every new process.
        _credential = _build_device_code_credential(tenant_id, _load_auth_record())

    return _credential


def _load_auth_record():
    """Load a persisted AuthenticationRecord, or return None."""
    if not _AUTH_RECORD_PATH.exists():
        return None
    try:
        from azure.identity import AuthenticationRecord
        return AuthenticationRecord.deserialize(_AUTH_RECORD_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None  # Corrupt or stale record — will re-authenticate


def _save_auth_record(record):
    """Persist an AuthenticationRecord for future silent refresh."""
    _AUTH_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    _AUTH_RECORD_PATH.write_text(record.serialize(), encoding="utf-8")


_auth_record_saved = False


def get_token(scope=None):
    """
    Acquire a raw access token string for the Dataverse environment.

    For device code flow, retries up to 2 times with a fresh code if the
    previous code expires (15-minute timeout each). On the third failure,
    exits with a message asking the user to re-run when ready.

    :param scope: OAuth2 scope. Defaults to "{DATAVERSE_URL}/.default".
    :returns: Access token string suitable for a Bearer Authorization header.
    """
    global _credential, _auth_record_saved
    load_env()
    dataverse_url = os.environ.get("DATAVERSE_URL", "").rstrip("/")
    if not scope:
        scope = f"{dataverse_url}/.default"

    credential = get_credential()

    # Service principal — no retry logic needed
    from azure.identity import DeviceCodeCredential
    if not isinstance(credential, DeviceCodeCredential):
        try:
            return credential.get_token(scope).token
        except Exception as e:
            print(f"ERROR: Failed to acquire access token: {e}", flush=True)
            print("  Check your credentials and .env configuration.", flush=True)
            sys.exit(1)

    # Device code flow — attempt with auto-retry on expiry
    tenant_id = os.environ.get("TENANT_ID")
    last_error = None

    for attempt in range(1, _MAX_AUTH_ATTEMPTS + 1):
        try:
            # First login ever — use authenticate() to persist the record
            if not _auth_record_saved and not _AUTH_RECORD_PATH.exists():
                record = _credential.authenticate(scopes=[scope])
                _save_auth_record(record)
                _auth_record_saved = True

            return _credential.get_token(scope).token

        except Exception as e:
            last_error = e
            if attempt < _MAX_AUTH_ATTEMPTS:
                print(f"\nSign-in expired or failed (attempt {attempt}/{_MAX_AUTH_ATTEMPTS}).", flush=True)
                print("Generating a new code and opening browser again...\n", flush=True)
                # Build a fresh credential with a new device code
                _credential = _build_device_code_credential(tenant_id, _load_auth_record())
            else:
                print(f"\nSign-in failed after {_MAX_AUTH_ATTEMPTS} attempts: {last_error}", flush=True)
                print("Please re-run this command when you are ready to authenticate.", flush=True)
                sys.exit(1)


if __name__ == "__main__":
    token = get_token()
    print(token)
