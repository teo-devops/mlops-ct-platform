"""Serving contract client: KServe v1 protocol over HTTP."""

from __future__ import annotations

import asyncio
import time

import httpx
from ctserve import metrics


class ModelError(Exception):
    pass


class KServeClient:
    def __init__(self, use_case: str) -> None:
        self.use_case = use_case
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=0.5),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def predict_proba(
        self, model: str, url: str, features: dict, timeout: float
    ) -> list[float]:
        """One instance in, one probability vector out.

        KServe v1: each instance is a dict column -> list of values, which the
        sklearn runtime turns into a DataFrame row.
        """
        payload = {"instances": [{k: [v] for k, v in features.items()}]}
        t0 = time.perf_counter()
        outcome = "ok"
        try:
            async with asyncio.timeout(timeout):
                r = await self._client.post(url, json=payload)
            if r.status_code != 200:
                outcome = "error"
                raise ModelError(f"{model}: HTTP {r.status_code} {r.text[:120]}")
            preds = r.json().get("predictions")
            if not preds:
                outcome = "error"
                raise ModelError(f"{model}: empty predictions")
            return [float(x) for x in preds[0]]
        except TimeoutError as e:
            outcome = "timeout"
            raise ModelError(f"{model}: timeout after {timeout}s") from e
        except httpx.HTTPError as e:
            outcome = "error"
            raise ModelError(f"{model}: {e.__class__.__name__}") from e
        finally:
            metrics.UPSTREAM.labels(self.use_case, model, outcome).observe(time.perf_counter() - t0)
