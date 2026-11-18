# Public deployment preparation

This release adds an anonymous public deployment mode. Visitors can use the product without registering or signing in. The service gives each browser a private temporary workspace while sharing the operator's job catalogue and read-only research index. The repository contains deployment configuration; a cloud host, real domain, TLS certificate and deployment verification are still pending.

## Runtime and process model

The production entry is `jobcompass.wsgi:application`, served by Gunicorn 27.0.1 on Python 3.12. It refuses to start without `JOBCOMPASS_PUBLIC=1` and a valid public configuration; local personal use remains available through `main.py`. `requirements-server.txt` is separate from the desktop dependencies. The Docker command uses **one worker and eight HTTP threads**, and `--no-control-socket` avoids writing a control socket into an unavailable home directory. Background execution shares the application's bounded executor, with private task registries for visitors. Gunicorn's thread setting and worker behavior are described in its [official settings](https://gunicorn.org/reference/settings/).

The anonymous-session registry and AI admission counters are in one process. Do not increase workers or run multiple replicas against the same session directory: a file lock rejects another registry owner. Horizontal scaling requires moving session state, admission counters and task coordination to shared infrastructure first. No public login page or user account database is required.

## Anonymous data lifecycle

- A cryptographically random cookie identifies a visitor; unknown cookie values create a fresh session and cannot select a directory or database.
- The cookie is `HttpOnly`, `SameSite=Strict`, `Secure`, host-scoped, and renewed on requests. It is a bearer capability: copying the cookie gives access to that temporary workspace.
- Resume, preferences, AI output, imports, application notes/history, saved research cohorts, result files and task identifiers belong to that visitor. Shared catalogue application statuses and notes are stripped.
- Default capacity is 32 sessions, with a 3,600-second idle TTL. In-flight requests and background tasks prevent deletion. The gateway invokes cleanup every 30 seconds while running, and session access also checks expiry. A stopped server cannot perform scheduled deletion until it starts again.
- On process restart, old tokens are invalid. The registry removes only its own strictly named old session directories. Anonymous work is therefore temporary; users should export results they need to keep.
- The operator's job catalogue and configured research index are shared. Visitors cannot choose server database paths or rebuild the shared index. Their own imported/crawled jobs remain in their private workspace; the JobsDB refresh cooldown is shared across visitors.

New workspace creation has a separate allowance: **12 per source IP per hour and 120 globally per hour**, in addition to the 32 live-workspace capacity. Reusing a valid cookie does not spend that allowance. Unknown routes and health/static probes do not allocate workspaces. Failed creations release their concurrent slot but retain the admission count. Shared campus/company networks can share one public IP, so configure this value for the expected group size; it does not distinguish individual people behind a NAT.

POST requests and the heavier state, catalogue, export and research-status GET endpoints share a 120/IP/minute, 1,200/global/minute admission limit with 16 active slots. Lightweight status, task polling, health checks and static assets do not spend this work allowance.

The per-IP/global fixed-window AI budgets are independent of cookies, so deleting a browser cookie does not reset a source IP's allowance. An admission is counted before queueing; releasing its active slot does not refund the allowance. The global default is 100 admissions/hour, per-IP default 10/hour, and three concurrent admitted AI jobs. A multi-step AI research action may make multiple provider calls, so an admission count is **not** an exact token, request or currency budget. Set provider-side spending limits separately when provisioning the actual account.

## Configure a server

Copy `deploy/server.env.example` to a file outside the repository, for example `/etc/jobcompass/server.env`, then restrict access to the deployment operator. Fill in these values:

| Variable | Purpose |
|---|---|
| `JOBCOMPASS_PUBLIC_ORIGIN` | Exact HTTPS origin, e.g. `https://jobs.example.com` |
| `JOBCOMPASS_ALLOWED_HOSTS` | Comma-separated exact Host values, including the origin host; wildcards are rejected |
| `JOBCOMPASS_TRUSTED_PROXIES` | Exact source IP(s) of your own reverse proxy as seen by the application; leave blank until identified |
| `JOBCOMPASS_SESSION_TTL`, `JOBCOMPASS_MAX_SESSIONS` | Temporary workspace retention and capacity |
| `JOBCOMPASS_SESSION_PER_IP`, `JOBCOMPASS_SESSION_GLOBAL` | New-workspace creation allowances per hour; defaults 12 and 120 |
| `JOBCOMPASS_PAGE_HOSTS` | Optional comma-separated exact approved domains for public custom webpage collection; blank by default |
| `JOBCOMPASS_AI_PER_IP`, `JOBCOMPASS_AI_GLOBAL`, `JOBCOMPASS_AI_ACTIVE` | Admission and concurrency bounds |
| `JOBCOMPASS_RECOMMEND_ACTIVE` | Separate offline recommendation concurrency (default 3); 30 admissions/IP/hour, 300 globally/hour. No AI quota is consumed. |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | Runtime provider configuration; key is never baked into the image |

Host and write-origin checks use this explicit configuration. The application accepts `X-Real-IP` only when the network peer is an explicitly trusted proxy. It does not trust arbitrary client-supplied forwarded headers. Behind a Docker port mapping, the peer can be the Docker bridge address, not `127.0.0.1`; identify the actual deployment path before setting trusted proxies. Until then, callers behind one proxy share the proxy IP's allowance.

After DNS and the reverse proxy are configured:

```sh
docker compose --env-file /etc/jobcompass/server.env config --quiet
docker compose --env-file /etc/jobcompass/server.env up -d --build
docker compose --env-file /etc/jobcompass/server.env ps
```

These commands are deployment instructions, not a record that deployment has happened. The application port is bound to host `127.0.0.1:8765`, so clients reach it through the TLS reverse proxy. The container uses an unprivileged UID, read-only image filesystem, limited resources, and a writable `/app/data` volume. The image copies an explicit source/demo/selected-snapshot allowlist; workstation `.env`, raw research archives, visitor databases and model caches are excluded. See Docker's [image-build guidance](https://docs.docker.com/build/building/best-practices/) and [Compose service reference](https://docs.docker.com/reference/compose-file/services/).

The initial 2 CPU / 2 GiB container budget is a configuration starting point, not measured concurrency capacity. Tune only after exercising realistic concurrent visitor and research workloads on the supplied server. The volume preserves operator data across container recreation; anonymous session accessibility still ends on worker restart. Do not publish the volume or back up temporary visitor data into a public artifact.

## TLS reverse proxy

Choose one template:

- `deploy/Caddyfile.example`: replace the domain and use Caddy's certificate management. Its `X-Real-IP` value replaces any incoming client value. See the [official reverse-proxy directive](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
- `deploy/nginx.conf.example`: replace the domain and certificate paths, then validate the server's Nginx configuration before reload. It sets `Host`, `X-Real-IP` and HTTPS forwarding information explicitly; see [Nginx proxy header configuration](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header).

Keep the application listener private to the proxy. If another load balancer/CDN is introduced, update the trust configuration for the actual network topology rather than accepting all forwarded headers.

## Native Python 3.12 and systemd alternative

`deploy/jobcompass.service.example` provides a Linux deployment without Docker. It is also suitable as a starting point when an Aliyun Linux 3 host already serves another application through Nginx. This is a deployment template, not evidence that the service has been installed or reached through HTTPS. Use a distinct JobCompass hostname and a separate Nginx server block; preserve the existing site's files, default server and upstream process. Check that loopback port 8765 is unused before selecting it.

Use a dedicated Python 3.12 installation and virtual environment. Do not replace the operating system's `python3`, install into its site-packages, or reuse the other application's environment. If the configured distribution repositories supply Python 3.12, install that supported package. Otherwise obtain a chosen 3.12 patch release from the [official Python source releases](https://www.python.org/downloads/source/), verify the release's published provenance/checksum, and install the distribution's C compiler, make, OpenSSL, zlib, libffi, bzip2, xz, readline and SQLite development packages. Package names depend on the configured repository. From the verified extracted source directory:

```sh
./configure --prefix=/opt/python3.12 --with-ensurepip=install
make -j1
sudo make altinstall
/opt/python3.12/bin/python3.12 -c 'import ssl, sqlite3, bz2, lzma, ctypes, venv; print("Python runtime modules available")'
```

`altinstall` preserves the system interpreter name, as recommended by the [Python Unix installation documentation](https://docs.python.org/3.12/using/unix.html#building-python). A single build job reduces contention on a small shared host. Record the actual Python version and build result. Installing a template does not establish that these modules or its TLS trust store work.

The following paths are examples, not workstation paths to copy. Create a dedicated system account, keep source and virtual-environment files root-owned, and make only the application data directory writable by the service. Put a reviewed source release at `/opt/jobcompass/current`; it must contain the allowlisted benchmark and static assets, but no workstation `.env`, personal database, notes or raw archive. If this account or directory already exists, inspect and reuse it rather than changing another service's ownership.

```sh
sudo useradd --system --user-group --home-dir /nonexistent --shell /sbin/nologin jobcompass
sudo install -d -m 0755 /opt/jobcompass
sudo install -d -m 0700 /etc/jobcompass
sudo install -d -m 0700 -o jobcompass -g jobcompass /srv/jobcompass/data
sudo /opt/python3.12/bin/python3.12 -m venv /opt/jobcompass/venv
sudo /opt/jobcompass/venv/bin/python -m pip install -r /opt/jobcompass/current/requirements-server.txt
```

Create `/etc/jobcompass/server.env` from the example only if it does not already exist, and set mode 0600 with root ownership. Configure the actual HTTPS origin, exact hostname, provider key and quotas there. For this native topology, also set `JOBCOMPASS_DB=/srv/jobcompass/data/shared.sqlite`; do not retain Docker's `/app/data` path. The service already enables `JOBCOMPASS_PUBLIC=1`. With Nginx on this same host connecting explicitly to `127.0.0.1:8765`, the trusted proxy is `127.0.0.1`; its server block must overwrite `X-Real-IP` with `$remote_addr`. An external proxy/load balancer requires a separately verified trust configuration. Do not print the filled environment file, shell-trace it, commit it or place it in a public web directory.

The service uses one worker and eight HTTP threads. It runs with an empty capability set, a private temporary directory, a read-only system view and `/srv/jobcompass/data` as its only explicit persistent writable path. These restrictions use [systemd execution settings](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html); validate support on the installed systemd version. The initial 1 GiB memory ceiling and one-CPU quota leave some room for other services on a 2 CPU/2 GiB host, but are not a capacity guarantee. Measure the existing application's load and JobCompass query/index memory before opening broad access; a process that exceeds its memory ceiling can be stopped. Large research indexing should be scheduled separately with monitored resources.

```sh
sudo install -m 0644 /opt/jobcompass/current/deploy/jobcompass.service.example /etc/systemd/system/jobcompass.service
sudo systemd-analyze verify /etc/systemd/system/jobcompass.service
sudo systemctl daemon-reload
sudo systemctl enable --now jobcompass.service
sudo systemctl status jobcompass.service --no-pager
curl --fail --silent --show-error -H 'Host: jobs.example.com' http://127.0.0.1:8765/api/health
```

Replace the example Host with the configured hostname. The successful loopback check establishes only application readiness; it does not validate public TLS, reverse proxy headers or browser cookies. Inspect `journalctl -u jobcompass.service` for startup failures without dumping environment variables. Never use `main.py` as a publicly bound alternative.

For Nginx, adapt `deploy/nginx.conf.example` into a new site file included by the existing configuration. Supply a valid certificate and private-key path for the distinct JobCompass hostname. Do not overwrite `nginx.conf`, replace the other site's server block, add `default_server`, or stop its upstream. Run `nginx -t` before a graceful Nginx reload, then verify both the existing site and the new HTTPS site. Keep 8765 closed to external networks; external traffic goes through the TLS listener. If SELinux denies the Nginx loopback upstream, inspect its audit evidence and apply the distribution's appropriately scoped proxy policy rather than disabling SELinux.

Run the acceptance checks below through the real hostname before calling this deployed. Source updates should use a new reviewed release directory while retaining the old one. Restart only `jobcompass.service` after changing the release pointer; do not use Gunicorn reload or overlap workers because the anonymous registry allows one owner. A restart invalidates temporary visitor sessions. Roll back by stopping JobCompass, restoring the previous release pointer, then starting it with the same data directory; do not delete data volumes/directories or reset shared databases as part of a rollback. Database format changes require a separately planned consistent backup and migration.

The optional longitudinal source remains separate from source control. For a native installation set `JOBCOMPASS_RESEARCH_DB` to a provisioned read-only source readable by the service account and build its index using `deploy/build_research_index.py` under that same account and production paths. Do not substitute an operator's personal application database for a shared research source. The Docker-only `JOBCOMPASS_RESEARCH_SOURCE` variable is not the native runtime source setting.

## Outbound webpage collection

Public arbitrary webpage collection is disabled until the operator supplies `JOBCOMPASS_PAGE_HOSTS`. This restriction does not disable JobsDB updates, the fixed API sources, CSV/JSON/HTML file imports, matching, AI analysis or research features. A denied webpage request explains the available import alternatives instead of showing a login prompt.

Allowlist entries must be exact domains such as `careers.example.com`; wildcards, URL schemes and paths are rejected. The dedicated public collector accepts only HTTPS on port 443 without URL credentials. It checks the initial URL, robots request and **every redirect target** against the same allowlist and the existing public-DNS-address validation. It does not inherit HTTP proxy environment settings. Robots disallow rules stop collection before the advertisement request. All visitors share a 15-second attempt cooldown per approved hostname; imported rows and logs stay private to the requesting visitor.

Approve domains controlled by trusted site operators, including any separate redirect destinations they legitimately require. This is a domain-constrained collector, not a general public URL-fetch proxy or an IP-pinned DNS implementation. Desktop local mode retains its existing public-HTTPS collector.

## Optional longitudinal research database

The base image includes the already selected historical benchmark snapshot and synthetic demo fixtures. The large private longitudinal research database is not in the image. Without it, current-catalogue analysis can still work; historical study functions need the configured source and index.

To add a consistent, operator-provisioned SQLite snapshot, set `JOBCOMPASS_RESEARCH_SOURCE` to its host path. Ensure UID 10001 can read the file, and mount it read-only using the provided overlay:

```sh
docker compose --env-file /etc/jobcompass/server.env -f compose.yaml -f deploy/compose.research.yaml run --rm jobcompass python deploy/build_research_index.py
docker compose --env-file /etc/jobcompass/server.env -f compose.yaml -f deploy/compose.research.yaml up -d
```

Build the index inside the same container paths used by the running application; its source fingerprint includes path and file metadata. The operator script is an offline maintenance command, not an unauthenticated HTTP endpoint. The mount must reference an existing database; Compose is configured not to create a missing host path silently. The source remains read-only and the derived index lives in the application data volume.

## Acceptance before opening the real site

1. Check `/api/health` through the proxy and inspect the container health state. Health probing must not allocate a visitor workspace.
2. Open two separate browser profiles. Store distinct resumes/notes/results and verify neither profile can access the other profile's state, task ID or result ID.
3. Verify write requests from another origin and requests with an unlisted Host are rejected. Check cookie flags over real HTTPS.
4. Verify anonymous AI works with the configured provider and that per-IP/global admission limits remain effective after clearing cookies. Verify queued task slots release on success, error and cancellation.
5. Confirm shared research paths are absent from public status/error responses; repeat a read-only analysis and compare the source database checksum before/after.
6. Restart the worker and confirm old visitor cookies do not recover private data. Verify exports are usable before temporary data expires.
7. Record the real server's build logs, domain, TLS test, resource measurements and deployment version. Revert to the previous image if the smoke tests fail, retaining the operator data volume.

Local tests cover store isolation, legacy job IDs, private history/imports, shared cooldown, cookie rotation, expiry, active-work retention, capacity, creation/AI/work admission, cross-process locking, exact origins/proxies, path sanitization, allowed-host redirects and robots handling. The current computer did not expose Docker, Caddy or Nginx executables during this task, so no Docker image build, proxy syntax check, certificate issuance or cloud load test is claimed here. Local Gunicorn smoke-test results are recorded separately by the release verification process.
