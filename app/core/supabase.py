"""Thin httpx wrapper around Supabase REST + Postgrest endpoints."""
import os
from typing import Any

import httpx


class SupabaseClient:
    """Service-role client. Bypasses RLS — use only in server code.

    Lazy: env vars are read on first use, so a missing var fails the
    first request rather than crashing on import. Makes test setup
    easier (set env, then import).
    """

    _client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set",
            )
        self._client = httpx.AsyncClient(
            base_url=f"{url}/rest/v1",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        return self._client

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": columns}
        if order:
            params["order"] = order
        if limit:
            params["limit"] = str(limit)
        client = self._get_client()
        res = await client.get(f"/{table}", params=params)
        res.raise_for_status()
        return res.json()

    async def insert(
        self, table: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        client = self._get_client()
        res = await client.post(
            f"/{table}",
            json=payload,
            headers={"Prefer": "return=representation"},
        )
        res.raise_for_status()
        return res.json()[0]


supabase = SupabaseClient()
