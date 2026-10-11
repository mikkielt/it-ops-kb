---
topic: arch/postgres-bundled-binaries
priority: P3
applies_to: "PostgreSQL 18 docs (initdb, pg_ctl, pg_upgrade, file layout) for binaries shipped inside a Python platform wheel; projects pixeltable-pgserver 0.6.0 (PG 16.14 and 18.4), postgresql-wheel 14.1.2, zonky embedded-postgres-binaries 18.6.0"
retrieved_utc: 2026-10-11
sources: [S-nmcdzdpf, S-rqvdmzku, S-zwrjh2bl, S-yz6be5ru, S-ltydjlxa, S-4o7okj5l, S-qudkq4hc, S-czyjfw3k, S-6kqqnivq, S-4dmek4hw, S-f3p4t6bi, S-bwd7sjme, S-cso734yx, S-piorrsz5, S-ewbubv2q, S-p3k7q3uv, S-pcnmerd5, S-shixdny6, S-nohekodh, S-clzjtcjg, S-c243glba, S-2nm5jzh5, S-uthirkoa, S-cpppwj2n, S-xuh26of4, S-mkyhrun3]
status: partial
---

# Bundling PostgreSQL binaries in a Python package: wheel shipping, initdb, pg_ctl, major upgrades

## Summary
A package that carries its own PostgreSQL has four jobs: ship the server executables in a platform-specific wheel, create a cluster with `initdb`, run it with `pg_ctl start -w` and stop it with `pg_ctl stop`, and deal with the fact that a data directory made by one major version cannot be started by another. PostgreSQL's licence allows redistribution; the upstream project itself distributes source plus third-party packages and installers, so a wheel is the packager's own build. The existing Python wheels (`pixeltable-pgserver`, `postgresql-wheel`) build PostgreSQL from the source tarball inside manylinux images, start it with `initdb` and `pg_ctl` over a Unix socket, and `pixeltable-pgserver` upgrades with `pg_upgrade` by shipping two majors side by side. The start-up sequence at the end is derived, not a vendor recipe. Dump determinism and S3 backups, and advisory locks, are out of scope here.

## Facts

### initdb (PostgreSQL 18)
- `initdb` creates the data directory, the shared catalogs and the `postgres`, `template1` and `template0` databases; `-D`/`--pgdata` (or `PGDATA`) is the only required input. [DOC S-nmcdzdpf]
- It must run as the user that will own the server process and refuses to run as root, because the server itself cannot run as root. [DOC S-nmcdzdpf]
- `initdb` creates the target directory when it can, and refuses to run when the directory exists and already contains files, to avoid overwriting an installation. [DOC S-4o7okj5l]
- The generated `pg_hba.conf` uses the method of `-A/--auth` (or `--auth-local` for Unix sockets, `--auth-host` for TCP); the default is `trust`, which lets any local user connect and become superuser, and the docs recommend a password (`--pwfile`) with `-A scram-sha-256`, or `peer`/file permissions, if local users are not trusted. [DOC S-4o7okj5l]
- In PostgreSQL 18 data checksums are on by default; `--no-data-checksums` turns them off. [DOC S-nmcdzdpf]
- `--locale` sets the cluster locale; without it the locale is inherited from the environment of `initdb`, and the encoding is derived from the locale unless `-E/--encoding` is given; `--no-locale` equals `--locale=C`, and with `C` the default encoding is `SQL_ASCII` for the libc provider and `UTF8` for ICU. [DOC S-nmcdzdpf]
- The sort order of the template databases cannot be changed without recreating them, and a cluster with a non-C locale cannot move to an incompatible collation library version (other OS, OS upgrade, snapshot restore, binary replication). [DOC S-4o7okj5l]
- `-U/--username` sets the bootstrap superuser (default: the OS user running `initdb`) and `--pwfile` reads its password from the first line of a file. [DOC S-nmcdzdpf]
- `--no-instructions` suppresses the "how to start" text and is documented for tools that wrap `initdb`; `-N/--no-sync` is faster but "should not be used" for a production installation because an OS crash can corrupt the directory. [DOC S-nmcdzdpf]
- `pg_ctl init` (or `initdb`) invokes `initdb` with options passed through `-o`, and `-p` gives the location of the `initdb` executable in that mode. [DOC S-rqvdmzku]

### pg_ctl, the server process and the lock file
- `pg_ctl start` launches the server in the background with stdin on `/dev/null`; on Unix the server's stdout and stderr go to pg_ctl's stdout unless `-l filename` (appended to, owner-only readable) or a redirection is used, and the docs recommend one of the two. [DOC S-rqvdmzku]
- `-w/--wait` is the default for start, stop, restart, promote and register; startup counts as complete when the PID file says the server accepts connections, shutdown when the server removes the PID file. [DOC S-rqvdmzku]
- The wait limit is `-t`, else `PGCTLTIMEOUT`, else 60 seconds; on timeout pg_ctl exits nonzero although the operation may still finish in the background. [DOC S-rqvdmzku]
- `stop -m` takes `smart` (no new connections, waits for clients), `fast` (the default: rolls back active transactions and disconnects clients) or `immediate` (aborts all processes and forces crash recovery at the next start). [DOC S-rqvdmzku]
- `pg_ctl status` exits 3 when no server runs in the data directory and 4 when no accessible data directory is given. [DOC S-rqvdmzku]
- `-D` is required unless `PGDATA` is set; `-o` passes options straight to `postgres`; `-p path` names the `postgres` executable, which by default is taken from the same directory as `pg_ctl`. [DOC S-rqvdmzku]
- While the server runs its PID is in `postmaster.pid` in the data directory, which prevents several servers on one data directory. [DOC S-ltydjlxa]
- `postmaster.pid` records the postmaster PID, the data directory path, the start time, the port, the Unix-socket directory (possibly empty), the first valid listen address and the shared memory id, and is absent after shutdown. [DOC S-czyjfw3k]
- A start on a port that is taken fails with `could not bind IPv4 address ... Address already in use` and `could not create any TCP/IP sockets`. [DOC S-ltydjlxa]

### Sockets and ports
- `listen_addresses` defaults to `localhost`; an empty list means only Unix-domain sockets are used; `port` defaults to 5432 and both need a server start to change. [DOC S-qudkq4hc]
- `unix_socket_directories` normally defaults to `/tmp` (a build-time choice), is empty on Windows (no Unix socket by default), accepts several comma-separated directories, and creates `.s.PGSQL.<port>` plus a `.s.PGSQL.<port>.lock` file in each, neither of which may be removed by hand. [DOC S-qudkq4hc]
- `unix_socket_permissions` defaults to 0777 (anyone can connect); 0700 restricts to the server user. [DOC S-qudkq4hc]
- The socket path must fit in the `sun_path` field of `struct sockaddr_un`, which the source comment calls "usually only 100 or so bytes". [CODE S-f3p4t6bi: src/include/libpq/pqcomm.h#UNIXSOCK_PATH_BUFLEN]
- The PostgreSQL 18 pages read here state no numeric byte limit for the socket directory path; the limit is the platform's `sun_path` size. [UNK]

### Major and minor upgrades
- Minor releases never change the storage format; to move between them replace the executables while the server is down and restart on the same data directory. [DOC S-zwrjh2bl]
- A major release may change the internal storage format, so the options are dump and restore, `pg_upgrade`, or logical replication. [DOC S-zwrjh2bl]
- `PG_VERSION` in the data directory holds the major version number of the server that made it. [DOC S-czyjfw3k]
- A file-system level copy cannot cross a major version; use a logical tool such as `pg_dumpall`; checks make a server of the wrong major refuse the data directory, so trying causes no harm. [DOC S-zwrjh2bl]
- The docs advise taking the dump with the newer version's `pg_dump`/`pg_dumpall`, which can read servers back to 9.2. [DOC S-zwrjh2bl]
- The dump-and-restore recipe is: stop writes, `pg_dumpall > file`, stop the old server, install the new binaries, `initdb`, restore `pg_hba.conf` and `postgresql.conf` changes, start, then `psql -d postgres -f file`; for least downtime run old and new in parallel on different ports and pipe `pg_dumpall` into `psql`. [DOC S-zwrjh2bl]
- `pg_upgrade` migrates in place and needs both the old and new `bin` and data directories, with the new cluster already created by `initdb` using compatible flags and both servers stopped; the docs say always run the new server's `pg_upgrade`. [DOC S-yz6be5ru]
- `pg_upgrade --check` only checks; link, clone and swap modes need old and new data directories on one file system, and after the new cluster starts in link mode the old cluster is unsafe to use; it defaults to port 50432 and needs write permission in the current directory. [DOC S-yz6be5ru]
- Extension shared objects (for example `pgcrypto.so`) matching the new server must be installed before the upgrade, `CREATE EXTENSION` must not be repeated, and `pg_upgrade` cannot check external modules for binary compatibility. [DOC S-yz6be5ru]
- Upgrading makes the new server run arbitrary code chosen by the source cluster's superusers, so the source superusers must be trusted; afterwards statistics are regenerated with `vacuumdb` and generated scripts must be run. [DOC S-yz6be5ru]
- Contrib modules such as `pgcrypto` are not built unless the `world` target is built, pre-packaged distributions usually offer them as a separate subpackage, and each is registered per database with `CREATE EXTENSION` (superuser unless the extension is trusted). [DOC S-4dmek4hw]

### Distribution and licence
- PostgreSQL is released under the PostgreSQL License: use, copy, modify and distribute for any purpose without fee, provided the copyright notice and the two following paragraphs appear in all copies. [DOC S-6kqqnivq]
- The upstream download page offers ready-to-use packages or installers per OS family and a source archive, not a library for embedding. [DOC S-bwd7sjme]
- For Windows the EDB-hosted installer page also links a zip archive of the binaries without installer, "intended for users who wish to include Postgres as part of another application installer". [DOC S-cso734yx]

### Wheel tags for a package that carries executables
- A wheel file name ends in `{python tag}-{abi tag}-{platform tag}.whl`; `py27-none-any` means any implementation of that Python, no ABI requirement, any platform. [DOC S-piorrsz5]
- The simple platform tag is `sysconfig.get_platform()` with hyphens and periods replaced by underscores (`linux_x86_64`, `win32`); it is "insufficient" for public Linux wheels, for which `manylinux_{x}_{y}_{arch}` (glibc x.y or newer) and `musllinux_{x}_{y}_{arch}` exist. [DOC S-piorrsz5]
- The wheel spec unpacks the archive into `purelib` when `Root-Is-Purelib` is true and into `platlib` otherwise, and scripts go to `{distribution}-{version}.data/scripts/`. [DOC S-ewbubv2q]
- The wheel spec reads here says nothing about the executable permission bit of binaries inside the package tree (it mentions the `+x` bit only for `scripts/`). [UNK]
- A wheel holding `initdb`, `pg_ctl` and `postgres` should carry a platform tag (`py3-none-<platform>` if Python-independent, or a `cpXY` tag as below), because the `any` platform tag claims compatibility with every platform. [DER S-piorrsz5, S-ewbubv2q: `any` is defined as "any platform"; the specs have no rule specific to executables]

### Existing Python wheels that ship PostgreSQL
- `pixeltable-pgserver` is documented as an embedded Postgres server used by Pixeltable, a fork of `pgserver`, which is a fork of `postgresql-wheel`; it is Apache-2.0. [COMMUNITY S-2nm5jzh5]
- PyPI release 0.6.0 (uploaded 2026-07-14) has only wheels, no sdist: `cp310` to `cp314` for macOS (x86_64 `macosx_10_13`, or `10_15` for cp314; `macosx_11_0_arm64`), `manylinux_2_27`/`manylinux_2_28` on x86_64 and aarch64, and Windows `win_amd64` and `win_arm64`, with `requires_python >=3.10`. [COMMUNITY S-clzjtcjg]
- The v0.6.0 build compiles PostgreSQL 16.14 and 18.4 into two install directories (`pginstall`, `pginstall18`) shipped in one package. [DER S-shixdny6, S-pcnmerd5: the top-level `Makefile` at v0.6.0 runs the pgbuild step twice, with `POSTGRES_VERSION=16.14` into `pginstall` and `18.4` into `pginstall18`, and `utils.py` maps majors 16 and 18 to those directories]
- Each major is built from the `ftp.postgresql.org` source tarball with `configure --without-icu`, and pgvector v0.8.5 is built against that major's install. [CODE S-nohekodh: pgbuild/Makefile#pgvector]
- The wheel gets its platform and `cpXY` tags from a dummy cffi module in `setup.py`, commented "dummy but needed for the binaries to work", not from a Python extension of its own. [CODE S-uthirkoa: setup.py#setup]
- Wheels are built by `cibuildwheel` with `before-all = "make"`; on Linux the step first installs `flex bison readline-devel`, because the comment says the PG 18 tarball no longer ships pre-generated scanner and parser sources. [CODE S-c243glba: pyproject.toml#tool.cibuildwheel]
- The bundled directory layout is a version-to-bin-dir map (16 and 18), the target defaults to 18 and `PGSERVER_POSTGRES_VERSION` overrides it. [CODE S-pcnmerd5: src/pixeltable_pgserver/utils.py#POSTGRES_VERSIONS]
- When `PG_VERSION` is missing it runs `initdb --auth=trust --auth-local=trust --encoding=utf8 -U postgres -D <pgdata>`, after first killing any leftover `postgres` process whose command line names the same data directory; otherwise it logs that `PG_VERSION` exists and skips `initdb`. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#PostgresServer.ensure_pgdata_inited]
- On Unix it starts with `pg_ctl -w -o '-h "" -k <socket_dir>' -l <pgdata>/log -D <pgdata> start` (timeout 10 s), so no TCP listener; on Windows it picks a free port and passes `-h 127.0.0.1 -p <port>`; it then polls `postmaster.pid` until the status line is `ready`. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#PostgresServer.ensure_postgres_running]
- The socket directory is the data directory unless `<dir>/.s.PGSQL.5432` fails a trial `bind()` (path too long), then a hash-named directory under the user runtime path is used. [CODE S-pcnmerd5: src/pixeltable_pgserver/utils.py#find_suitable_socket_dir]
- Stop is `pg_ctl -w -D <pgdata> stop`; if that fails it terminates and then kills the postmaster process. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#PostgresServer._stop]
- When the effective user is root it creates the OS user `pgserver` and runs `initdb` and `pg_ctl` as that user. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#PostgresServer.__init__]
- `get_server` reads `PG_VERSION` and raises when it differs from the requested major. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#get_server]
- `upgrade_db` stops the old server, enables checksums on the old cluster with `pg_checksums --enable` when `pg_controldata` shows version 0 (16 had none, 18 defaults to on), `initdb`s a temporary cluster beside it, runs the new major's `pg_upgrade -b <old bin> -d <old> -D <new> -U postgres`, renames the old directory to `.old`, moves the new one in and runs `update_extensions.sql`. [CODE S-p3k7q3uv: src/pixeltable_pgserver/postgres_server.py#upgrade_db]
- `postgresql-wheel` 14.1.2 (Apache-2.0) describes itself as a Linux-only wheel with a self-contained server compiled in manylinux images by cibuildwheel and stored in the package data, running as the Python process user without root; it wraps `initdb` and `pg_ctl` and shows `pg_ctl -D db -o "-p 5678" -l log start` then a TCP connect. [COMMUNITY S-cpppwj2n]
- PyPI lists `postgresql-wheel` 14.1.2 (2021-12-29) as `cp37`-`cp39` and `pp37`-`pp38` wheels for manylinux and musllinux (i686 and x86_64), `requires_python >=3.7,<3.10`, Development Status Beta. [COMMUNITY S-xuh26of4]
- `zonkyio/embedded-postgres-binaries` ships PostgreSQL bundles per OS and architecture (Darwin, Windows, Linux, Alpine; amd64, i386, arm32, arm64v8, ppc64le), tag v18.6.0 builds PostgreSQL 18.6, and the README says they are "intended for testing purposes"; Java, Go, Rust and Node wrappers use them. [COMMUNITY S-mkyhrun3]

### Start-up sequence for a package that bundles PostgreSQL (derived)
- Step 1, decide by `PG_VERSION`: absent or empty directory means create; equal to the bundled major means use; lower means a major upgrade is needed; higher means refuse and keep the data untouched. [DER S-czyjfw3k, S-zwrjh2bl: PG_VERSION holds the major; a wrong-major server refuses the directory; pixeltable-pgserver compares the same file]
- Step 2, create: run the bundled `initdb` as an unprivileged user with explicit `-D`, `-U`, `--encoding=UTF8` and `--locale=C` (non-C locales depend on the OS collation library, which the cluster cannot outlive a change of), and a non-`trust` `--auth-local` or a `--pwfile`. [DER S-nmcdzdpf, S-4o7okj5l: documented defaults are an environment-derived locale and `trust`; non-C locales rely on the OS collation library]
- Step 3, start: `pg_ctl -D <pgdata> -l <log> -t <n> -w -o "-c listen_addresses= -c unix_socket_directories=<dir>" start` and treat a nonzero exit as failure, reading the log; check first that `<dir>/.s.PGSQL.<port>` fits `sun_path`. [DER S-rqvdmzku, S-qudkq4hc, S-f3p4t6bi: `-w` waits for readiness; empty `listen_addresses` means sockets only; socket path bounded by `sun_path`]
- Step 4, connect over the Unix socket at `<dir>/.s.PGSQL.<port>` and learn the socket directory and port from `postmaster.pid` when the server was started by an earlier process. [DER S-qudkq4hc, S-czyjfw3k: socket file name embeds the port; the PID file records socket directory and port]
- Step 5, stop with `pg_ctl -D <pgdata> -m fast -w stop` (the default mode), use `pg_ctl status` exit code 3 to detect "not running", and avoid `immediate`, which forces crash recovery on the next start. [DER S-rqvdmzku: documented stop modes and status exit codes]
- Major upgrade needs the old binaries: a dump needs a running old server and `pg_upgrade` needs the old `bin` directory, so a package that ships only the new major cannot upgrade an older cluster by itself and either ships both majors (as pixeltable-pgserver does) or requires the old server's dump beforehand. [DER S-yz6be5ru, S-zwrjh2bl, S-p3k7q3uv: pg_upgrade takes `-b` old bindir; dump and restore runs against a live old server; the project ships 16 and 18]
- Extension libraries such as pgvector are compiled against one server major, so each bundled major needs its own build of them and the upgrade step must install the new major's libraries before `pg_upgrade`. [DER S-yz6be5ru, S-nohekodh: shared objects must match the new server; the project builds pgvector per PostgreSQL version]
- Redistributing the binaries in a wheel is permitted by the licence if the licence text travels with them, so the wheel should include the PostgreSQL License notice. [DER S-6kqqnivq: the notice and two paragraphs must appear in all copies]

## Reference

| Item | Value | Source |
|---|---|---|
| `pg_ctl status` exit | 3 not running, 4 no accessible data dir | S-rqvdmzku |
| `pg_ctl` wait default | on (`-w`), 60 s or `PGCTLTIMEOUT` | S-rqvdmzku |
| stop mode default | `fast` | S-rqvdmzku |
| data checksums (PG 18 initdb) | on by default | S-nmcdzdpf |
| `unix_socket_directories` default | `/tmp` (build-time), empty on Windows | S-qudkq4hc |
| `listen_addresses` default | `localhost` | S-qudkq4hc |
| `port` default | 5432 | S-qudkq4hc |
| `pg_upgrade` default port | 50432 | S-yz6be5ru |
| data dir major marker | `PG_VERSION` | S-czyjfw3k |
| wheel root | purelib if `Root-Is-Purelib: true`, else platlib | S-ewbubv2q |

| Project | Version | Wheel platforms | PostgreSQL | Licence |
|---|---|---|---|---|
| pixeltable-pgserver | 0.6.0 | macOS x86_64/arm64, manylinux_2_28 x86_64/aarch64, win amd64/arm64, cp310-cp314 | 16.14 and 18.4 | Apache-2.0 |
| postgresql-wheel | 14.1.2 | manylinux and musllinux i686/x86_64, cp37-cp39, pp37-pp38 | version number 14.1 (README sample prints 13.4) | Apache-2.0 |
| zonky embedded-postgres-binaries | v18.6.0 | Maven artifacts per OS/arch, not wheels | 18.6 | Apache-2.0 |

## Examples
- SNIPPET: start a bundled cluster over a Unix socket and stop it; context: PostgreSQL 18 binaries in a package directory, Unix, placeholder paths; checked: no [DER S-nmcdzdpf, S-rqvdmzku, S-qudkq4hc: `initdb -D`, `pg_ctl -w -l -o start`, `stop -m fast`]

```python
import subprocess
from pathlib import Path

BIN = Path("/opt/example/pg18/bin")
PGDATA = Path("/var/lib/example/pgdata")
SOCKDIR = Path("/run/example/pg")
PORT = "54320"

def pg(tool, *args):
    subprocess.run([str(BIN / tool), *args], check=True, stdin=subprocess.DEVNULL)

if not (PGDATA / "PG_VERSION").exists():
    # bootstrap superuser defaults to the OS user running initdb, which peer auth needs
    pg("initdb", "-D", str(PGDATA), "--encoding=UTF8",
       "--locale=C", "--auth-local=peer", "--no-instructions")

pg("pg_ctl", "-D", str(PGDATA), "-l", str(PGDATA / "server.log"), "-t", "30", "-w",
   "-o", f'-c listen_addresses= -c unix_socket_directories={SOCKDIR} -p {PORT}', "start")
# connect with host=/run/example/pg port=54320 dbname=postgres (user = the OS user)
pg("pg_ctl", "-D", str(PGDATA), "-m", "fast", "-w", "stop")
```
