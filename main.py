# main.py
# Live-coding demo: FastAPI in Action
# Start: fastapi dev main.py
import asyncio
import secrets
import time
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from openai import AsyncOpenAI

from llm import LLM_MODEL, get_llm_client
from model import ChatRequest, ExtractRequest, ShopItem, UserIn, UserOut

app = FastAPI(title="FastAPI Live-Coding Demo")
templates = Jinja2Templates(directory="templates")


# region Step 1: Hello World
@app.get("/")
def home():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    if item_id > 100:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"item_id": item_id, "q": q}


# endregion


# region Step 3: Pydantic model as request body
@app.post("/items")
def create_item(item: ShopItem):
    return item


# endregion


# region Step 3b: Security as a sub-dependency
# The chain /secure -> get_authenticated_user -> HTTPBearer is resolved (and
# cached) once per request. HTTPBearer reads the "Authorization: Bearer <token>"
# header and puts the Authorize button plus the security scheme into /docs.
security = HTTPBearer()

# In-memory only: every issued token is gone when the server restarts.
issued_tokens: set[str] = set()


def get_access_token() -> str:
    """Create a random pseudo access token (placeholder for RSA/JWT)."""
    return secrets.token_urlsafe(32)


@app.post("/token")
def issue_token():
    """Hand out a bearer token to paste into the Authorize dialog in /docs."""
    token = get_access_token()
    issued_tokens.add(token)
    return {"access_token": token, "token_type": "bearer"}


def get_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserOut:
    """Read the token from the request and reject anything we did not issue."""
    if credentials.credentials not in issued_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unknown token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return UserOut(username="demo-user", email="demo@example.com")


@app.get("/secure")
def read_secure(user: Annotated[UserOut, Depends(get_authenticated_user)]):
    return {"message": f"Hello {user.username}, your token checks out."}


# endregion


# region Step 3c: response_model as an output filter
@app.post("/users", response_model=UserOut)
def create_user(user: UserIn):
    """Take a password in, never hand it back out."""
    # The full UserIn including the password is returned here, but
    # response_model=UserOut drops every field it does not declare.
    return user


# endregion


# region Step 3d: The async trap
# Three endpoints that sleep for exactly as long, yet behave completely
# differently under load. Measure it with bench.py while the server runs.
@app.get("/sleep-blocking")
async def sleep_blocking(seconds: float = 1.0):
    """Wrong: a blocking call inside async def stalls the whole event loop."""
    time.sleep(seconds)
    return {"style": "async def + time.sleep"}


@app.get("/sleep-async")
async def sleep_async(seconds: float = 1.0):
    """Right: await hands the event loop back, so requests overlap."""
    await asyncio.sleep(seconds)
    return {"style": "async def + asyncio.sleep"}


@app.get("/sleep-threaded")
def sleep_threaded(seconds: float = 1.0):
    """Plain def: FastAPI moves it to a threadpool, so it cannot block the loop."""
    time.sleep(seconds)
    return {"style": "def + time.sleep"}


# endregion


# region Step 4: AI endpoints + dependency injection
# Injecting the LLM client works like a DB session: configured centrally,
# reusable, and swappable in tests via app.dependency_overrides.
LLMClient = Annotated[AsyncOpenAI, Depends(get_llm_client)]


@app.post("/chat")
async def chat(request: ChatRequest, client: LLMClient) -> StreamingResponse:
    """Stream the LLM answer token by token, like ChatGPT."""

    async def token_stream():
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": request.prompt}],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(token_stream(), media_type="text/plain")


@app.get("/chat-ui", response_class=HTMLResponse)
def chat_ui(request: Request):
    """Serve a page that calls /chat via fetch() and renders the token stream."""
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={"title": "LLM-Chat", "model": LLM_MODEL},
    )


@app.post("/extract-item")
async def extract_item(request: ExtractRequest, client: LLMClient) -> ShopItem:
    """Structured output: free text in, validated ShopItem out.

    The same Pydantic model from step 3 forces the LLM to return valid JSON.
    """
    completion = await client.chat.completions.parse(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extrahiere das Verkaufsangebot aus dem Text des Nutzers. "
                    "Erweitere die Beschreibung um möglichst gute "
                    "Verkaufschancen zu haben."
                ),
            },
            {"role": "user", "content": request.text},
        ],
        response_format=ShopItem,
    )
    return completion.choices[0].message.parsed


# endregion


# region Step 7: Finale - the infinite website
@app.get("/imagine/{page:path}")
async def imagine(page: str, client: LLMClient) -> StreamingResponse:
    """Invent a whole web page for any URL, streamed as the browser renders it."""

    async def html_stream():
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein Webserver. Antworte ausschliesslich mit einem "
                        "vollständigen, hübschen HTML-Dokument (CSS und JS inline) "
                        "- kein Markdown, keine Code-Fences. "
                        "Beginne direkt mit <!DOCTYPE html>."
                    ),
                },
                {"role": "user", "content": f"Erzeuge die Webseite zur URL: /{page}"},
            ],
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(html_stream(), media_type="text/html")


# endregion
