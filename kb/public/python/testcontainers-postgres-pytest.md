---
topic: python/testcontainers-postgres-pytest
priority: P3
applies_to: "testcontainers-python 4.15.0 (PostgresContainer, Python >=3.10), pytest, Docker-API compatible runtime; GitLab docker:dind notes from GitLab docs master@55bfaf7f"
retrieved_utc: 2026-10-11
sources: [S-2ibe4s6m, S-a525e6ew, S-geebp6gt, S-xbqajqu2, S-iastzky2, S-pw5sn74s, S-x7ub2eqf, S-pgxen5ty, S-ld5hflyc, S-futhpvg4, S-qx4duaky, S-xevnmrbh, S-y6d7rxoj, S-epepjb6f, S-bb3uummy]
status: partial
---

# pytest with testcontainers-python and a Postgres container

## Summary
testcontainers-python (Apache-2.0, release 4.15.0 read here) starts a throwaway Postgres in Docker
from a pytest test or fixture: `PostgresContainer` is a context manager, builds a SQLAlchemy-style
connection URL with `get_connection_url()`, waits for Postgres itself, and a "Ryuk" reaper container
removes it if the Python process dies. It needs a Docker-API compatible runtime on the machine that
runs the tests; under GitLab CI that means a runner with `docker:dind` (privileged) or a mounted
socket. Fixture scopes are in `python/pytest.md`; async driver use is in
`python/sqlalchemy-asyncio-asyncpg.md`. The project's docs do not describe a pytest fixture or a
GitLab CI setup for testcontainers-python; the fixture below is our derivation.

## Facts
- In release 4.15.0 the class is `testcontainers.community.postgres.PostgresContainer`; the older
  import path `testcontainers.postgres` still works but is a shim that emits a `DeprecationWarning`
  telling you to use `testcontainers.community.postgres`. The PostgreSQL module page says the module
  exists since testcontainers-python v4.6.0. [CODE S-a525e6ew: src/testcontainers/postgres.py#PostgresContainer]
- The module's docs page installs the module with `pip install testcontainers[postgres] sqlalchemy
  psycopg2`. [DOC S-geebp6gt]
- In `pyproject.toml` the `postgres` extra lists no packages, so SQLAlchemy and a DB driver are not
  pulled in by the extra. The core package depends on `docker`, `urllib3`, `wrapt`,
  `typing-extensions` and `python-dotenv`, requires Python >= 3.10 and is licensed Apache-2.0.
  [CODE S-xbqajqu2: pyproject.toml#project.optional-dependencies]
- Constructor: `PostgresContainer(image="postgres:latest", port=5432, username=None, password=None,
  dbname=None, driver="psycopg2", **kwargs)`. Username, password and database name each default to
  the `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` environment variable of the test process,
  and failing that to the literal `test`. The old keyword `user` is routed through
  `raise_for_deprecated_parameter` in favour of `username`. Pin the image tag: the default is
  `postgres:latest`. [CODE S-2ibe4s6m: src/testcontainers/community/postgres/__init__.py#PostgresContainer.__init__]
- On start the module passes the three values to the container as `POSTGRES_USER`,
  `POSTGRES_PASSWORD` and `POSTGRES_DB` and exposes container port 5432 (mapped to a random host
  port). [CODE S-2ibe4s6m: src/testcontainers/community/postgres/__init__.py#PostgresContainer._configure]
- `get_connection_url(host=None, driver=<unset>)` returns
  `postgresql+<driver>://<user>:<quoted password>@<host>:<mapped port>/<dbname>`. The driver comes
  from the constructor (`psycopg2` by default); the `driver` argument of the method overrides it, and
  `driver=None` gives a plain `postgresql://` URL. The password is percent-quoted (a space and `+` stay
  literal), host comes from `get_container_host_ip()` and the port from `get_exposed_port()`; calling
  it before the container started raises `ContainerStartException`. [CODE S-iastzky2: src/testcontainers/core/generic.py#DbContainer._create_connection_url]
- The driver name is interpolated into the URL scheme as given, and the repository's tests start
  the module with `driver="psycopg2"`, `"psycopg"` (v3) and `"pg8000"`; none of them uses `asyncpg`.
  Passing `driver="asyncpg"` therefore yields `postgresql+asyncpg://...`, a URL meant for
  `create_async_engine`. [DER S-2ibe4s6m, S-epepjb6f: scheme built by f-string `postgresql+{driver}`; tests list the drivers exercised]
- Readiness is checked inside the container: `PostgresContainer._connect` runs `psql ... -c 'select
  version();'` against `127.0.0.1` through an exec wait strategy, so `start()` returns once
  Postgres answers, and no Python driver or SQLAlchemy call is needed during startup (a repository
  test monkeypatches `sqlalchemy.create_engine` to prove it). The `DbContainer` base class it
  inherits is itself marked deprecated for removal in its docstring. [CODE S-2ibe4s6m: src/testcontainers/community/postgres/__init__.py#PostgresContainer._connect]
- `DockerContainer` is a context manager: `__enter__` calls `start()` and, if start fails, calls
  `__exit__` before re-raising; `stop()` removes the container with `force=True` and deletes its
  anonymous volumes. [CODE S-pw5sn74s: src/testcontainers/core/container.py#DockerContainer.__enter__]
- The getting-started page (written with a Redis container) shows one container per test, each on
  its own random host port, and says that is what supports parallel test execution; a
  context-manager exit removes the container. [DOC S-y6d7rxoj]
- A directory of `.sql` files can seed the database: the repository's test maps a script to
  `/docker-entrypoint-initdb.d/<name>.sql` with `with_volume_mapping(host, container)` before
  starting, using the standard `postgres` image entrypoint behaviour. [CODE S-epepjb6f: tests/community/postgres/test_postgres.py#test_show_how_to_initialize_db_via_initdb_dir]
- Testcontainers requires a Docker-API compatible container runtime. It is actively tested against
  recent Docker on Linux and Docker Desktop on Mac and Windows; alternative runtimes (Podman is
  documented with `DOCKER_HOST` pointing at the Podman socket) are not part of the main test flow,
  so some features may be missing. [DOC S-qx4duaky]
- Docker host detection tries in order: `tc.host` in `~/.testcontainers.properties`, `TC_HOST` or
  `TESTCONTAINERS_HOST_OVERRIDE`, `DOCKER_HOST`, the current Docker context, the default socket,
  `docker.host` from the properties file, then rootless socket locations; if none works it raises
  `DockerHostError`. Environment variables win over the properties file and are the documented
  choice for CI. [DOC S-ld5hflyc]
- Host address for the published port: the configuration page says the default connection mode is
  `bridge_ip`, but the code returns `docker_host` unless the test process itself runs inside a
  container with a local Docker host; inside a container it picks `bridge_ip` when a shared host
  network is found (Docker-outside-of-Docker) and `gateway_ip` otherwise (Docker-in-Docker).
  `TESTCONTAINERS_CONNECTION_MODE` forces one; `TC_HOST` / `TESTCONTAINERS_HOST_OVERRIDE` replaces the
  host that `docker_host` mode returns. [CODE S-pgxen5ty: src/testcontainers/core/docker_client.py#DockerClient.get_connection_mode]
- Ryuk: the garbage-collector page says a "Ryuk" reaper container starts with the first test
  container and removes test containers when the Python process exits or is killed; it recommends
  not disabling it, and `TESTCONTAINERS_RYUK_DISABLED=true` turns it off. The configuration page
  lists "consider disabling Ryuk if your environment already handles container cleanup". [DOC S-futhpvg4]
- In code, `DockerContainer.start()` creates the reaper (image `testcontainers/ryuk:0.8.1` by default,
  overridable with `RYUK_CONTAINER_IMAGE`) unless `ryuk_disabled` is true, and the reaper mounts the
  Docker socket read-write. Boolean settings accept `yes`, `true`, `t`, `y`, `1` from the environment
  or the properties file. Ryuk's privileged flag reads `TESTCONTAINERS_RYUK_PRIVILEGED`; the garbage
  collector page names it `TESTCONTAINERS_RYUK_CONTAINER_PRIVILEGED`, which the code does not read. [CODE S-x7ub2eqf: src/testcontainers/core/config.py#TestcontainersConfiguration.ryuk_disabled]
- Wait tuning: `TC_MAX_TRIES` (default 120) and `TC_POOLING_INTERVAL` (default 1 second) bound
  how long testcontainers retries a wait, so the default overall wait is about 120 seconds. The wait
  strategies page lists log-based, HTTP-based and custom waits for `GenericContainer`; database
  containers such as `PostgresContainer` wait for a connection on their own. [DOC S-xevnmrbh]
- GitLab CI with a Docker executor and the `docker:dind` service: the runner must be registered
  privileged. With TLS (the default from Docker 19.03.12) the job sets `DOCKER_TLS_CERTDIR: "/certs"`,
  mounts `/certs/client`, and the Docker client sets `DOCKER_HOST` itself; without TLS the job sets
  `DOCKER_HOST: tcp://docker:2375` and `DOCKER_TLS_CERTDIR: ""`. The service is reachable under the
  hostname `docker`, and each job gets its own isolated Docker daemon. GitLab says to pin the image
  tag (the page uses `docker:24.0.5`). [DOC S-bb3uummy]
- Under that setup testcontainers-python sees a TCP `DOCKER_HOST` whose host is `docker`, not a
  local address, so it selects `docker_host` mode and returns `docker` as the host of
  `get_connection_url()`. The published Postgres port is then on the dind service, not on the job
  container's `localhost`. [DER S-pgxen5ty, S-bb3uummy: `get_connection_mode` returns `docker_host` when the Docker host is not localhost; `host()` returns the hostname of a `tcp://` base URL; GitLab doc gives `tcp://docker:2375`]
- Not confirmed by any page read: that the Ryuk reaper starts and can mount its socket under GitLab
  `docker:dind`, and whether testcontainers-python's own docs say anything about GitLab CI. [UNK]

## Reference
| Setting (env var) | Default | Effect |
| --- | --- | --- |
| `TESTCONTAINERS_RYUK_DISABLED` | `false` | no reaper container |
| `RYUK_CONTAINER_IMAGE` | `testcontainers/ryuk:0.8.1` | reaper image |
| `TESTCONTAINERS_RYUK_PRIVILEGED` | `false` | run reaper privileged |
| `RYUK_RECONNECTION_TIMEOUT` | `10s` | reaper reconnection wait |
| `TC_HOST` / `TESTCONTAINERS_HOST_OVERRIDE` | unset | host used to reach published ports |
| `TESTCONTAINERS_CONNECTION_MODE` | auto | `bridge_ip`, `gateway_ip`, `docker_host` |
| `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE` | unset | socket path for Ryuk and compose |
| `TC_MAX_TRIES`, `TC_POOLING_INTERVAL` | 120, 1 | wait attempts and interval (s) |
| `DOCKER_HOST`, `DOCKER_TLS_VERIFY`, `DOCKER_CERT_PATH` | unset | Docker daemon address and TLS |

Values read from src/testcontainers/core/config.py at 4.15.0 and the configuration page; the
property names for `~/.testcontainers.properties` are on that page.

`arch/podman-api-socket.md` covers Podman's Docker-compatible socket (`podman.socket`, its rootless and rootful paths, and its security model) for a `DOCKER_HOST` that points at Podman.

## Examples
- SNIPPET: session-scoped pytest fixture that starts one Postgres 16 container for the whole test
  session and yields a sync SQLAlchemy URL; context: testcontainers 4.15.0, pytest, SQLAlchemy 2,
  psycopg2 installed, Docker running; checked: no [DER S-2ibe4s6m, S-pw5sn74s: PostgresContainer context manager and `get_connection_url()`; pytest fixture scopes in python/pytest.md]
```python
import pytest
import sqlalchemy
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_url() -> str:
    with PostgresContainer("postgres:16-alpine", dbname="app_test") as pg:
        yield pg.get_connection_url()  # postgresql+psycopg2://test:test@host:port/app_test


@pytest.fixture
def engine(pg_url):
    eng = sqlalchemy.create_engine(pg_url)
    yield eng
    eng.dispose()
```
- SNIPPET: the same container with an asyncpg URL for `create_async_engine`; context: testcontainers
  4.15.0, asyncpg installed; checked: no [DER S-2ibe4s6m: `driver` argument selects the URL scheme]
```python
with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
    url = pg.get_connection_url()  # postgresql+asyncpg://test:test@host:port/test
```
- SNIPPET: GitLab CI job variables for the TLS-less dind setup, then a test run; context: GitLab
  Docker executor, privileged runner, `docker:dind` service; checked: no [DER S-bb3uummy: variables from the dind page; job image must contain Python and pytest]
```yaml
pytest-integration:
  image: python:3.12
  services:
    - docker:24.0.5-dind
  variables:
    DOCKER_HOST: tcp://docker:2375
    DOCKER_TLS_CERTDIR: ""
  script:
    - pip install -e ".[test]"
    - pytest tests/integration
```
