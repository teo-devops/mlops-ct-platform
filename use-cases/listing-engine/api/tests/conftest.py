from __future__ import annotations

import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app

CAT_URL = settings.categorizer_url
FRAUD_URL = settings.fraud_url


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
        mock.post(CAT_URL).respond(json={"predictions": [[0.02, 0.9, 0.02, 0.02, 0.02, 0.02]]})
        mock.post(FRAUD_URL).respond(json={"predictions": [[0.95, 0.05]]})
        yield mock
