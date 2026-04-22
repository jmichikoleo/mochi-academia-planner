"""Supabase client factories.

Two clients are exposed:
  - `get_admin_client()` — uses the service role key for privileged server-side ops
    (used sparingly; most data reads/writes flow through the user's own client so RLS
    policies can enforce per-user access).
  - `get_user_client(access_token)` — a PostgREST client that carries the user's JWT
    so Supabase can identify auth.uid() for Row-Level Security.
"""
import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_admin_client() -> Client:
    """Service-role client. Bypasses RLS — use only for admin tasks."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY in env.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_anon_client() -> Client:
    """Anon client — used for signup/login where no JWT exists yet."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY in env.")
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_user_client(access_token: str, refresh_token: str = "") -> Client:
    """Per-request client authenticated as the signed-in user.

    Passing the user's JWT lets Postgres RLS policies see `auth.uid()`, so every
    query automatically scopes to the current user's rows.
    """
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(access_token)
    # Keep the GoTrue client in sync so storage/auth calls also use this token.
    try:
        client.auth.set_session(access_token, refresh_token or access_token)
    except Exception:
        # set_session may fail if refresh_token is missing; PostgREST auth is the
        # critical part for DB access, so we swallow this quietly.
        pass
    return client
