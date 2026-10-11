---
topic: python/fastapi-capability-dependencies
priority: P3
applies_to: "FastAPI 0.143.0 docs and Uvicorn 0.54.0 docs (release tags)"
retrieved_utc: 2026-10-11
sources: [S-ayprwh67, S-ejipyz2z, S-taoszxoo, S-a67xbp56, S-fwvusq4t, S-7ows5rub, S-uhdkuqjs, S-fwsrgnx2, S-dnaai5ya, S-b6za35dg, S-xvyw57kk]
status: partial
---

# FastAPI: per-route capability dependencies, Security scopes, lifespan and composing roles by flag

## Summary
FastAPI lets a dependency guard a single route, a router or the whole app, and `Security(dep,
scopes=[...])` together with `SecurityScopes` lets one central check enforce a different set of
scopes on each route. This article covers those mechanisms (FastAPI 0.143.0 docs), the `lifespan`
startup/shutdown context manager, and how Uvicorn 0.54.0 runs an app in one process or several. The
"capability dependency" name and the idea of composing a single-process service from roles chosen by
a flag are ours: they are derived from the documented pieces and marked `DER`. How one Python
package carries the roles as optional extras is in `arch/python-single-package-extras.md`.

## Facts
- A `list` of `Depends()` passed as `dependencies` to a path operation decorator is run like normal
  dependencies, can raise exceptions, and its return values are not passed to the function. [DOC S-ayprwh67]
- `dependencies` can also be given to the `FastAPI` application, in which case they apply to every
  path operation in it. [DOC S-ejipyz2z]
- `APIRouter(dependencies=[...])` adds the dependencies to every path operation in the router, with
  no value passed to the function; the order is router dependencies, then decorator `dependencies`,
  then normal parameter dependencies, and `Security` dependencies with `scopes` can be listed there
  too. [DOC S-uhdkuqjs]
- `app.include_router(router, prefix=..., tags=..., responses=..., dependencies=[...])` adds those
  settings without editing the router, which the docs present for a router shared with other
  projects; the same router may be included several times with different prefixes. [DOC S-uhdkuqjs]
- Included routers are not mounted or isolated: FastAPI keeps the routers' path operations active and
  combines prefixes, dependencies, tags and responses when handling requests and building OpenAPI.
  [DOC S-uhdkuqjs]
- `Security` is a subclass of `Depends` with one extra parameter, `scopes` (a list of strings); using
  it, rather than `Depends`, lets FastAPI use the scopes internally and document them in OpenAPI.
  [DOC S-a67xbp56]
- A `SecurityScopes` parameter (from `fastapi.security`) has `scopes`, the list of scopes required by
  that dependency and by all dependants for the specific path operation, and `scope_str`, the same
  scopes joined by spaces; the docs put `scope_str` in the `WWW-Authenticate` header. [DOC S-a67xbp56]
- Because `SecurityScopes` holds the scopes of all dependants, a central dependency can verify the
  token once and each path operation declares its own scope requirements, checked independently per
  route. [DOC S-a67xbp56]
- The scopes tutorial example raises `HTTPException` with status 401 and a `WWW-Authenticate` header
  both for invalid credentials and for a token lacking a required scope (detail "Not enough
  permissions"); it uses status 400 for an inactive user and does not use 403. [CODE S-fwvusq4t: docs_src/security/tutorial005_an_py310.py#get_current_user]
- `app.dependency_overrides` is a plain `dict` from the original dependency function to a
  replacement; it works for a dependency used in a path operation function, a decorator
  `dependencies` list or an `include_router()` call, and `app.dependency_overrides = {}` resets it.
  [DOC S-7ows5rub]
- The `lifespan` parameter of `FastAPI` takes an async context manager (an `@asynccontextmanager`
  function with a `yield`): code before the `yield` runs once before requests are accepted, code
  after it runs at shutdown; when `lifespan` is given the `startup` and `shutdown` event handlers
  are not called, and lifespan events run only for the main application, not mounted sub
  applications. [DOC S-taoszxoo]
- Uvicorn enables the ASGI lifespan protocol automatically when the app supports it and can switch it
  off with `--lifespan off`; the lifespan runs once per application instance, so with several
  workers each worker runs it independently, and it runs as a sibling task of the request-handling
  task (a `ContextVar` set in it is not visible to the app task). [DOC S-xvyw57kk]
- `uvicorn.run("main:app", ...)` is the programmatic equivalent of the CLI; passing an app object
  works only without `workers` or `reload`, so the docs recommend the import string; `uvicorn.Config`
  with `uvicorn.Server` gives more control, and `await server.serve()` runs Uvicorn from an already
  running event loop. [DOC S-b6za35dg]
- The `--factory` flag loads the application from a factory function called with no arguments that
  returns an ASGI app, for example `uvicorn --factory main:create_app`. [DOC S-b6za35dg]
- `--workers N` starts several worker processes (Uvicorn uses `spawn`, not pre-fork); `--reload` and
  `--workers` are mutually exclusive. [DOC S-dnaai5ya]
- The FastAPI docs say the `fastapi` command runs Uvicorn as a single process, and that on Kubernetes
  one will usually not use workers but run one Uvicorn process per container. [DOC S-fwsrgnx2]
- A per-route "capability" is derived, not a FastAPI term: put one central check in a dependency that
  takes `SecurityScopes`, and declare each route's required capability as
  `Security(check, scopes=["<capability>"])` on the route, its router or `include_router`. [DER S-a67xbp56, S-uhdkuqjs: Security, SecurityScopes and router dependencies]
- Composing roles by flag is derived: `include_router` is an ordinary method call, so the entry
  point can call it only for the roles a settings value or CLI option enables; a role that was not
  included has no routes and answers 404, as observed when running the snippet below. [DER S-uhdkuqjs: include_router; behaviour observed with FastAPI 0.143.0]
- Background work for a role (a poller or consumer) in the same process is derived: the lifespan
  page shows loading a resource before `yield` and releasing it after, so creating an
  `asyncio.create_task(...)` before the `yield` and cancelling it after is a use of that same hook,
  but no page read shows it. With `--workers N` that task would run once per worker, so a single
  process is the matching deployment. [DER S-taoszxoo, S-xvyw57kk, S-dnaai5ya: lifespan semantics and per-worker lifespan]
- Whether FastAPI or the OAuth2 specification recommends status 403 (rather than 401 with
  `WWW-Authenticate`) for an authenticated caller lacking a scope is not stated on the pages read. [UNK]

## Reference
| Level | Where to declare | Order of execution |
| --- | --- | --- |
| App | `FastAPI(dependencies=[...])` | with each router's |
| Router | `APIRouter(dependencies=[...])` or `include_router(..., dependencies=[...])` | first |
| Route | decorator `dependencies=[...]` | after router |
| Parameter | `Depends` / `Security` parameters | last |
| Test | `app.dependency_overrides[orig] = fake` | replaces the original |

## Examples
- SNIPPET: capability scopes on an included router, a role enabled by a set of flags, and a poller task started in `lifespan`; context: FastAPI 0.143.0, Python 3.14, `fastapi.testclient.TestClient` with httpx (Starlette printed a deprecation warning for using httpx with its test client); checked: run [DER S-uhdkuqjs, S-a67xbp56, S-taoszxoo: include_router dependencies, SecurityScopes, lifespan]

```python
import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Header, HTTPException, Security
from fastapi.security import SecurityScopes


def require_scopes(security_scopes: SecurityScopes, x_scopes: str = Header("")) -> None:
    granted = set(x_scopes.split())
    if not set(security_scopes.scopes) <= granted:
        raise HTTPException(
            status_code=401,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'},
        )


admin = APIRouter(prefix="/admin")


@admin.get("/hosts")
def list_hosts() -> list[str]:
    return ["PL-LT-00123"]


async def poll_forever(ticks: list[int]) -> None:
    while True:
        ticks.append(1)
        await asyncio.sleep(0.01)


def create_app(roles: frozenset[str]) -> FastAPI:
    ticks: list[int] = []

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(poll_forever(ticks)) if "poller" in roles else None
        yield
        if task is not None:
            task.cancel()

    app = FastAPI(lifespan=lifespan)
    if "admin" in roles:
        app.include_router(admin, dependencies=[Security(require_scopes, scopes=["admin"])])
    return app
```

Run with `create_app(frozenset({"admin"}))`: a request to `/admin/hosts` without the `X-Scopes`
header returned 401 with `WWW-Authenticate: Bearer scope="admin"`, and with `X-Scopes: admin` it
returned the list; with `create_app(frozenset())` the same path returned 404. The header stands in
for a verified token and is not an authentication scheme.
