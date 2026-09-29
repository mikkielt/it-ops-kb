# Hosting: the kb as a remote MCP endpoint

The runbook for serving the kb to a remote MCP client that connects by url, such as a Copilot Studio agent: `_tools/kb_http.py` from a clone, behind a front end that terminates TLS and authenticates the caller. Its flags, exit codes and guards are in `kb/_self/tools.md` and in the tool's docstring (`--help` prints it); why it is built this way is in `kb/_self/design.md` ("One server, two transports").

## 1. Pick a path

| the client | the path | runbook |
|---|---|---|
| connects to the kb itself by url (a Copilot Studio agent, another remote MCP client) | **direct**: `_tools/kb_http.py` behind an authenticating TLS front end | this file |
| already talks to a team's own MCP server, which should add the kb's lookups to its live tools | **host**: that server runs `_tools/kb_mcp.py` as a stdio child and re-exposes `kb_pack`, `kb_search` and `kb_show` | `kb/_self/embedding.md` |

The direct path adds one endpoint and needs no code; the host path adds no endpoint, and the host writes the kb's rules into its own tool descriptions (`kb/_self/embedding.md`, section 4), since its clients never see the kb's `instructions`.

## 2. What every deployment keeps

- **Authentication in front.** `_tools/kb_http.py` has none of its own and listens on loopback (`--bind 127.0.0.1`, the default); a non-loopback `--bind` needs `--bind-any` as well. Only the front end is reachable from outside, and it lets a request through to `/mcp` only after it has checked the caller: an API-key header for a proof of concept, an Entra ID access token in production.
- **The guards stay on.** The front end passes the `Origin` and `Content-Type` headers through unchanged and adds no CORS handling of its own; `--allow-origin` stays unset, so a browser page gets 403 and a server-to-server client (no `Origin`) passes. A request body over `--max-body` gets 413.
- **One instance per audience.** A root is a filter on what the tools read, not access control: the server serves `kb/public` unless its `--roots` names more, and nothing in a request widens that. An audience that may read an internal root gets its own instance (`--roots public,<root>`) with its own url and its own credential or token audience; everyone else gets an instance with the default root. A limited server names no local path or update command in its `kb copy:` line or `kb_status` (`kb/_self/embedding.md`, section 5).
- **`KB_INDEX`** names a writable directory for the pack index outside the clone; each root set gets its own index file, so instances can share the directory (`kb/_self/embedding.md`, section 1). The server starts building the index when it starts, and reuses a file already built for the same kb.
- **Census tags as releases.** The clone sits detached at a `census-YYYY-MM-DD` tag, a commit whose sources were all confirmed current that day (`kb/_self/git.md`); an update checks out the newest census tag and restarts every instance, since the server loads its code, `instructions` and tool list once at start. A clone made from one tag with `--single-branch` has no remote-tracking branch, so its packs carry no `kb copy: ... behind` line while it waits for the next tag.
- **No secret in the repository.** Keys, client secrets and certificates live in the host's or the platform's secret store; every value below is a placeholder.

## 3. On a VM

A Linux VM (`PL-SRV-0042`) with Python 3.11+, git, systemd and a reverse proxy; the public name `kb.corp.example.com` resolves to it.

**The clone**, owned by a service account `kb`, at the newest census tag:

```sh
sudo useradd --system --home-dir /srv/it-ops-kb --shell /usr/sbin/nologin kb
sudo -u kb git clone --branch census-YYYY-MM-DD --single-branch <kb remote url> /srv/it-ops-kb
sudo -u kb python3 /srv/it-ops-kb/_tools/kb_mcp.py --roots public --status   # commit, census tag, roots served
```

**One systemd unit per audience**, each with its own environment file (public.env in /etc/kb-http holds `SERVE_PORT=8081` and `SERVE_ROOTS=public`; an internal audience's copy of the unit reads a file that names another port and `public,<root>`):

```ini
# /etc/systemd/system/kb-http-public.service
[Unit]
Description=it-ops-kb over Streamable HTTP (public audience)
After=network-online.target
Wants=network-online.target

[Service]
User=kb
Group=kb
EnvironmentFile=/etc/kb-http/public.env
Environment=KB_INDEX=/var/lib/kb-http
StateDirectory=kb-http
ExecStart=/usr/bin/python3 /srv/it-ops-kb/_tools/kb_http.py --port ${SERVE_PORT} --roots ${SERVE_ROOTS}
# the server exits 0 on an interrupt
KillSignal=SIGINT
Restart=on-failure
NoNewPrivileges=yes
ProtectSystem=full
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now kb-http-public.service`; `journalctl -u kb-http-public` shows the startup line with the port and the roots served. Exit 1 means the port is taken, exit 2 a bad option or an unknown root.

**The update timer** moves the clone to the newest census tag and restarts the instances (a restart with no new tag reuses the index):

```ini
# /etc/systemd/system/kb-update.service
[Unit]
Description=Move the it-ops-kb clone to the newest census tag

[Service]
Type=oneshot
User=kb
WorkingDirectory=/srv/it-ops-kb
ExecStart=/usr/bin/git fetch --quiet origin "refs/tags/census-*:refs/tags/census-*"
ExecStart=/bin/sh -c 't=$$(git tag --list "census-*" --sort=-v:refname | head -n 1); [ -n "$$t" ] && git checkout --quiet --detach "$$t"'
ExecStartPost=+/usr/bin/systemctl try-restart kb-http-public.service

# /etc/systemd/system/kb-update.timer
[Timer]
OnCalendar=daily
RandomizedDelaySec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

`sudo systemctl enable --now kb-update.timer`; list every audience's unit on the `try-restart` line.

**The reverse proxy** terminates TLS with a publicly trusted certificate served with its full chain, forwards only `POST /mcp` of an authenticated caller to `127.0.0.1:<port>`, and answers everything else itself. Per audience, one site block with its own name, key or token audience, and port.

Proof of concept, Caddy with an API-key header (Caddy obtains and renews a publicly trusted certificate for the name and serves the full chain). The key comes from an environment file readable only by Caddy's service account, filled from the vault:

```caddyfile
# /etc/caddy/Caddyfile; KB_API_KEY=<api-key from the vault> in the caddy service's environment file
kb.corp.example.com {
	@caller {
		method POST
		path /mcp
		header X-Api-Key {$KB_API_KEY}
	}
	handle @caller {
		reverse_proxy 127.0.0.1:8081
	}
	handle {
		respond 401
	}
}
```

Production, an Entra ID access token. The proxy (nginx here, with its `auth_request` module) asks a token validator on loopback about each request and forwards only on a 2xx:

```nginx
server {
    listen 443 ssl;
    server_name kb.corp.example.com;
    ssl_certificate     /etc/ssl/kb/fullchain.pem;   # leaf plus intermediates
    ssl_certificate_key /etc/ssl/kb/privkey.pem;

    location = /mcp {
        auth_request /_token;
        proxy_pass http://127.0.0.1:8081;
    }
    location = /_token {
        internal;
        proxy_pass http://127.0.0.1:9000/;           # the token validator
        proxy_pass_request_body off;
        proxy_set_header Content-Length "";
    }
    location / {
        return 404;
    }
}
```

The validator accepts a bearer token only when its signature checks against the tenant's published signing keys (`https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0/.well-known/openid-configuration`), its `iss` is that tenant's v2.0 issuer, its `aud` is the kb app registration's client id or Application ID URI, it has not expired, and, for an instance that serves an internal root, it carries the app role that audience is given. Entra ID as an MCP server's authorization server: `kb/public/auth/delegation-kcd-obo.md`.

## 4. On Azure: Container Apps or App Service

Azure Container Apps or Azure App Service (Linux, custom container) runs the same image; the platform's ingress terminates TLS and its built-in authentication with Microsoft Entra ID checks every request before it reaches the container. The setting names below are the Azure CLI's; the portal has the same ones under Ingress (or TLS/SSL) and Authentication.

**The image**, built from a clone made with `--single-branch` at a census tag, as on the VM (a fresh clone holds no `_cache/` or `_private/`). The Dockerfile lives with the build pipeline, not in the kb:

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* && useradd --system --create-home kb
COPY --chown=kb:kb . /srv/it-ops-kb
USER kb
ENV KB_INDEX=/tmp/kb-index
EXPOSE 8080
ENTRYPOINT ["sh", "-c", "exec python3 /srv/it-ops-kb/_tools/kb_http.py --bind 0.0.0.0 --bind-any --port 8080 --roots \"${SERVE_ROOTS:-public}\""]
```

Any Python 3.11+ base image does; git stays in the image so `kb_status` reports the census tag. `KB_INDEX` points into the container's own file system: each replica builds its index when it starts, so keep at least one replica running (Container Apps `--min-replicas 1`; App Service Always On). The image tag names the census tag (`<registry>/kb-http:census-YYYY-MM-DD`), and the app pulls it with its managed identity, not a registry password.

**Keeping the guards meaningful.** Inside a container the platform's ingress reaches the server over the container's network, not loopback, so the image binds `0.0.0.0` with `--bind-any`. That is safe only while the platform is the one way in:
- ingress on HTTPS only: Container Apps HTTP ingress with `allowInsecure` false (the default), App Service with HTTPS Only on, and no second port or path exposed;
- built-in authentication set to require authentication and answer 401 to an unauthenticated request, with no excluded paths, so nothing reaches `/mcp` without a valid token;
- in Container Apps, other apps of the same environment can call an app by name: give the kb apps an environment of their own;
- platform CORS stays off and the image passes no `--allow-origin`, so a browser's `Origin` still reaches the server and gets 403.

**Container Apps**, one app per audience (`kb-public` here; an internal audience's app sets `SERVE_ROOTS=public,<root>` and has its own token audience):

```sh
az containerapp create --name kb-public --resource-group <rg> --environment <kb environment> \
  --image <registry>/kb-http:census-YYYY-MM-DD --registry-server <registry> --registry-identity system \
  --ingress external --target-port 8080 --min-replicas 1 --env-vars SERVE_ROOTS=public
az containerapp auth microsoft update --name kb-public --resource-group <rg> \
  --client-id <kb app client id> --tenant-id 00000000-0000-0000-0000-000000000000 \
  --issuer https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0 \
  --allowed-token-audiences api://<kb app client id>
az containerapp auth update --name kb-public --resource-group <rg> \
  --enabled true --unauthenticated-client-action Return401 --require-https true
```

**App Service**, one web app per audience on a Linux plan:

```sh
az webapp create --name kb-public --resource-group <rg> --plan <linux plan> \
  --container-image-name <registry>/kb-http:census-YYYY-MM-DD \
  --assign-identity [system] --acr-use-identity --acr-identity [system] --https-only true
az webapp config appsettings set --name kb-public --resource-group <rg> --settings WEBSITES_PORT=8080 SERVE_ROOTS=public
az webapp config set --name kb-public --resource-group <rg> --always-on true
az webapp auth microsoft update --name kb-public --resource-group <rg> \
  --client-id <kb app client id> --tenant-id 00000000-0000-0000-0000-000000000000 \
  --issuer https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0 \
  --allowed-token-audiences api://<kb app client id>
az webapp auth update --name kb-public --resource-group <rg> \
  --enabled true --unauthenticated-client-action Return401 --require-https true
```

The app's identity needs pull rights on the registry (AcrPull) in both. A client secret, if the identity provider setup asks for one, is a platform secret or app setting reference, never a value in a script in the repository. The token checks are those of the VM section: the tenant's v2.0 issuer, the kb app registration as audience, and for an internal audience the app role it requires (App Service and Container Apps can also restrict the calling client applications and identities). Entra ID in front of an MCP server on App Service: `kb/public/auth/delegation-kcd-obo.md`.

**The census-tag update** is a scheduled pipeline job, the Azure form of the VM's timer: it lists the census tags, and when the newest is not the deployed image's tag it clones at that tag, builds and pushes `kb-http:<tag>`, and points each app at it (`az containerapp update --image`, `az webapp config container set --container-image-name`), which restarts it on the new kb.
