# FastAPI Feature Tour

A small, runnable FastAPI application that demonstrates the framework's core
features one topic at a time: request validation, dependency injection,
bearer-token security, response filtering, async behaviour under load, and
streaming responses from a large language model.

Each topic sits in its own folded region in [`main.py`](main.py) and has
matching tests, so every feature can be read, run and verified on its own.

> [!WARNING]
> This is a teaching project, not a template for production. `POST /token`
> hands a valid token to anyone who asks, issued tokens are kept in memory and
> never expire, the LLM endpoints are unauthenticated and cost money on every
> call, and `GET /imagine/...` renders model-generated HTML and JavaScript
> without any sanitising. Do not deploy this as-is.

## Requirements

- Python 3.10 or newer
- An OpenAI API key, for the LLM endpoints only

## Quickstart

Dependencies are managed with [uv](https://docs.astral.sh/uv/) and pinned in
`uv.lock`:

```bash
uv sync
```

Copy `.env.example` to `.env` and add your key:

```
OPENAI_API_KEY=sk-...
```

Start the development server with auto-reload:

```bash
uv run fastapi dev main.py
```

Then open <http://127.0.0.1:8000/docs> for the generated OpenAPI documentation,
or <http://127.0.0.1:8000/chat-ui> for the streaming chat page.

Endpoints that do not talk to the model work without an API key. The LLM
endpoints fail with an explicit error message when `OPENAI_API_KEY` is missing.

## What it demonstrates

| Endpoint | FastAPI feature |
|---|---|
| `GET /`, `GET /items/{item_id}` | Path and query parameters, automatic type validation, `HTTPException` |
| `POST /items` | Pydantic model as a validated request body |
| `POST /token`, `GET /secure` | `HTTPBearer` security as a dependency, including the Authorize button in `/docs` |
| `POST /users` | `response_model` as an output filter that drops undeclared fields |
| `GET /sleep-blocking`, `/sleep-async`, `/sleep-threaded` | How blocking calls, `await` and the threadpool behave under concurrency |
| `POST /chat`, `GET /chat-ui` | `StreamingResponse` token by token, rendered by a Jinja2 template |
| `POST /extract-item` | Structured model output validated against a Pydantic schema |
| `GET /imagine/{page}` | A streamed HTML document generated per request |

## The async trap

The three `/sleep-*` endpoints sleep for exactly as long but behave very
differently under load. With the server running, measure it:

```bash
uv run python bench.py
```

```
10 parallel requests, 1.0s sleep each

async def + time.sleep    (blocks the loop)   10.0s
async def + asyncio.sleep (correct)            1.0s
def + time.sleep          (threadpool)         1.0s
```

A single blocking call inside `async def` serialises the entire server,
including requests to unrelated endpoints. `async def` is not a performance
switch; it is a promise that everything inside is awaitable. Code that cannot
keep that promise belongs in a plain `def`, which FastAPI moves to a threadpool
on its own. That threadpool is capped at 40 threads, so beyond roughly that
many concurrent requests the correct `async` version pulls ahead.

## Project layout

```
main.py            all endpoints, grouped into folded regions per topic
model.py           Pydantic models for requests and responses
llm.py             the LLM client as an injectable dependency
templates/         Jinja2 templates for the chat page
tests/             pytest suite, with the LLM client mocked out
bench.py           concurrency measurement for the /sleep-* endpoints
TALK.md            walkthrough of the features in presentation order
```

The regions in `main.py` are numbered to match the walkthrough in
[`TALK.md`](TALK.md). In VS Code, `Ctrl+K Ctrl+8` folds them all and
`Ctrl+K Ctrl+9` unfolds them, which makes it easy to read one topic at a time.

## Development

```bash
uv run pytest         # 18 tests, no API key or network required
uv run ruff check .   # lint
uv run ruff format .  # format
```

The test suite replaces the LLM client through `app.dependency_overrides`, so
it runs offline and without credentials. That substitution is the main reason
the client is injected as a dependency in the first place.

## License

MIT, see [LICENSE](LICENSE).
