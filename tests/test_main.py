# tests/test_main.py
# Run with: pytest
from http import HTTPStatus
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from llm import get_llm_client
from main import app
from model import ShopItem

client = TestClient(app)


# region Basic endpoints
def test_read_root():
    response = client.get("/")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"Hello": "World"}


def test_read_item():
    response = client.get("/items/1")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"item_id": 1, "q": None}


def test_read_item_with_q():
    response = client.get("/items/1?q=test")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"item_id": 1, "q": "test"}


def test_read_item_invalid_id():
    response = client.get("/items/not-a-number")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_read_item_not_found():
    response = client.get("/items/101")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "Item not found"}


def test_create_item():
    json_payload = {
        "name": "Test Item",
        "description": "This is a test item",
        "price": 1,
        "tax": 2.5,
    }
    response = client.post("/items", json=json_payload)
    assert response.status_code == HTTPStatus.OK
    assert response.json() == json_payload


def test_create_item_invalid_payload():
    response = client.post("/items", json={"name": ["not", "a", "string"]})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# endregion


# region Security and output filtering
def test_secure_without_token_is_unauthorized():
    response = client.get("/secure")
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_secure_rejects_unknown_token():
    response = client.get("/secure", headers={"Authorization": "Bearer not-issued"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid or unknown token"}


def test_secure_accepts_issued_token():
    token = client.post("/token").json()["access_token"]
    response = client.get("/secure", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == HTTPStatus.OK
    assert "demo-user" in response.json()["message"]


def test_openapi_documents_the_bearer_scheme():
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert schemes["HTTPBearer"]["scheme"] == "bearer"


def test_create_user_never_returns_the_password():
    payload = {
        "username": "demo",
        "email": "demo@example.com",
        "password": "never-echo-me",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"username": "demo", "email": "demo@example.com"}


# endregion


# region The async trap
# Smoke tests only: the timing difference needs real parallel requests against
# a running server, which is what bench.py is for.
@pytest.mark.parametrize(
    ("path", "style"),
    [
        ("/sleep-blocking", "async def + time.sleep"),
        ("/sleep-async", "async def + asyncio.sleep"),
        ("/sleep-threaded", "def + time.sleep"),
    ],
)
def test_sleep_endpoints(path, style):
    response = client.get(path, params={"seconds": 0})
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"style": style}


# endregion


# region AI endpoints with a mocked LLM
# This is where Depends pays off: the tests swap the real LLM client for a
# fake, so they run without an API key, network access or Ollama.
class _FakeStream:
    """Mimic the streaming response of the OpenAI SDK."""

    def __init__(self, tokens: list[str]):
        self._tokens = iter(tokens)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            token = next(self._tokens)
        except StopIteration:
            raise StopAsyncIteration from None
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=token))]
        )


class FakeLLMClient:
    """Minimal stand-in for AsyncOpenAI - only what the app actually calls."""

    def __init__(self):
        completions = SimpleNamespace(create=self._create, parse=self._parse)
        self.chat = SimpleNamespace(completions=completions)

    async def _create(self, **kwargs):
        return _FakeStream(["Hallo", " ", "Welt"])

    async def _parse(self, **kwargs):
        item = ShopItem(name="Fahrrad", description="wie neu", price=250)
        message = SimpleNamespace(parsed=item)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def fake_llm():
    app.dependency_overrides[get_llm_client] = FakeLLMClient
    yield
    app.dependency_overrides.clear()


def test_chat_streams_tokens(fake_llm):
    response = client.post("/chat", json={"prompt": "Sag Hallo"})
    assert response.status_code == HTTPStatus.OK
    assert response.text == "Hallo Welt"


def test_imagine_streams_html(fake_llm):
    response = client.get("/imagine/snake-game")
    assert response.status_code == HTTPStatus.OK
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == "Hallo Welt"


def test_extract_item_returns_shop_item(fake_llm):
    response = client.post(
        "/extract-item",
        json={"text": "Verkaufe mein Fahrrad, wie neu, fuer 250 Franken."},
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["name"] == "Fahrrad"
    assert body["price"] == 250


# endregion
