from __future__ import annotations

import os

import pytest
import respx
from httpx import ASGITransport, AsyncClient

MODELS = __MODELS_LIST_PY__
URLS = {m: f"http://{m}-predictor.test.svc/v1/models/{m}:predict" for m in MODELS}
for m in MODELS:
    os.environ[f"CT_MODEL_{m.upper().replace('-', '_')}_URL"] = URLS[m]
    os.environ[f"CT_MODEL_{m.upper().replace('-', '_')}_VERSION"] = "1"

from app.main import app  # env first: the app reads the model endpoints on startup


@pytest.fixture
async def client():
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c,
    ):
        yield c


@pytest.fixture
def models():
    with respx.mock(assert_all_called=False) as mock:
        for m in MODELS:
            mock.post(URLS[m]).respond(json={"predictions": [__PREDICTION_SAMPLE__]})
        yield mock
