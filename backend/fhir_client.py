"""
FHIR R4 client — connects to a HAPI FHIR server.

Supports: GET (read/search), POST (create), PUT (update), transaction bundles.
Every call uses tenacity retry/backoff for transient failures.
Distinguishes "resource not found" (FHIRNotFoundError) from transport/protocol
failures (FHIRClientError) so callers can handle each case appropriately.
"""

import json
import logging
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from config import FHIR_BASE_URL, FHIR_TIMEOUT_SECONDS


log = logging.getLogger(__name__)


class FHIRNotFoundError(Exception):
    """The requested FHIR resource does not exist."""


class FHIRClientError(Exception):
    """Transport or protocol error talking to the FHIR server."""


class FHIRValidationError(FHIRClientError):
    """FHIR server rejected the resource (HTTP 400/422)."""


_transport_errors = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.TransportError,
)


class FHIRClient:
    """Thread-safe FHIR client. Reuse one instance per process."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or FHIR_BASE_URL).rstrip("/")
        self._client = httpx.Client(
            timeout=timeout or FHIR_TIMEOUT_SECONDS,
            headers={"Accept": "application/fhir+json"},
        )

    # ------------------------------------------------------------
    # Transport errors only get retried with backoff. HTTP status
    # codes are handled below, not here.
    # ------------------------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
        retry=retry_if_exception_type(_transport_errors),
        reraise=True,
    )
    def _request(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        resp = self._client.request(method, url, **kwargs)
        return resp

    # ------------------------------------------------------------
    # Resource calls
    # ------------------------------------------------------------
    def read(self, resource_type: str, resource_id: str) -> dict:
        return self._parse("GET", f"{self.base_url}/{resource_type}/{resource_id}")

    def search(
        self, resource_type: str, params: dict | None = None
    ) -> list[dict]:
        params = params or {}
        return self._parse(
            "GET", f"{self.base_url}/{resource_type}", params=params
        )

    def create(self, resource: dict) -> dict:
        return self._parse(
            "POST",
            f"{self.base_url}/{resource.get('resourceType', 'Resource')}",
            json=resource,
        )

    def update(self, resource_type: str, resource_id: str, resource: dict) -> dict:
        return self._parse(
            "PUT",
            f"{self.base_url}/{resource_type}/{resource_id}",
            json=resource,
        )

    def transaction(self, bundle: dict) -> dict:
        """POST a FHIR transaction Bundle. Used to upload many resources at once."""
        return self._parse("POST", f"{self.base_url}/", json=bundle)

    def _parse(self, method: str, url: str, **kwargs) -> dict:
        resp = self._request(method, url, **kwargs)
        content_type = resp.headers.get("content-type", "")

        # Empty successful response (e.g. some update endpoints)
        if resp.status_code in (200, 201) and not resp.content:
            return {}

        try:
            body = resp.json() if resp.content else {}
        except json.JSONDecodeError:
            body = {}

        if resp.status_code == 404:
            raise FHIRNotFoundError(f"Not found: {method} {url}")
        if resp.status_code in (400, 422):
            raise FHIRValidationError(f"FHIR rejected request: {body}")
        if resp.status_code >= 300:
            raise FHIRClientError(
                f"FHIR error {resp.status_code} for {method} {url}: {body}"
            )

        return body

    def close(self) -> None:
        self._client.close()


# Singleton used across the app unless a caller needs a custom instance.
_default: FHIRClient | None = None


def get_client() -> FHIRClient:
    global _default
    if _default is None:
        _default = FHIRClient()
    return _default