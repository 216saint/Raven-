# Raven — Rebrand of Robin (Design Spec)

**Date:** 2026-05-28
**Status:** Approved
**Upstream:** [Robin](https://github.com/apurvsinghgautam/robin) by Apurv Singh Gautam

## 1. Goal

Fork Robin into a project named **Raven** with three concrete improvements:

1. **Stability** — fix LLM-integration bugs (subset already landed in master: shadowed `config` in `resolve_model_config`, shared streaming callback, uncached model fetchers, dead default model). Remaining items tracked separately.
2. **Egress security** — optional, layered network controls (manual proxy + WireGuard tunnel + OpenVPN tunnel) on top of the existing Tor circuit.
3. **Frictionless startup on Windows** — a native PowerShell launcher that removes the WSL2 + `apt install tor` dance.

Rebrand is intentionally **surface-only**: docs, UI, env vars, Docker tag. Python module names are unchanged so existing imports and entrypoints keep working.

## 2. Non-goals

- Renaming `.py` modules or restructuring into a package.
- Bundling a single-file `raven.exe` (PyInstaller path rejected — antivirus risk, build cost).
- System-wide firewall killswitch (only a pipeline-abort killswitch is in scope).
- Hosted/SaaS deployment.
- Removing attribution to Robin. Crédito explícito é parte do design.
- Other LLM items from the earlier review (#3, #4, #5, #6, #7, #10, #11) — separate spec.

## 3. Rebrand surface

| Surface | Change |
|---|---|
| `README.md` | Rewritten. New title, positioning, credit to Robin in header and Acknowledgements. |
| `ui.py` | `st.set_page_config(page_title="Raven", ...)`. Header text updated. |
| `.env` vars | New canonical names `RAVEN_DATA_DIR`, `RAVEN_PROXY_URL`. Legacy `ROBIN_*` and existing names continue to work as aliases — `config.py` reads new name first, falls back to legacy. |
| Docker | Local build tag `raven:latest`. `LABEL org.opencontainers.image.source` updated. Image content unchanged. |
| Logo | Text placeholder in README until a new asset exists. Old logo not copied/redistributed. |
| `.py` filenames | **Unchanged.** `ui.py`, `llm.py`, `llm_utils.py`, `scrape.py`, `search.py`, `health.py`, `config.py`. |
| LICENSE | Preserved verbatim with original copyright notice. |

## 4. Egress layers (opt-in)

All three layers are optional and independent. Empty config = no effect. Tor remains the default circuit.

### 4.1 Layer A — Manual proxy

- Sidebar expander **🌐 Network egress** with: proxy URL field (accepts `http://`, `https://`, `socks5://`, `socks5h://`), optional inline auth.
- `scrape.py` exposes `make_session(proxy_url: str | None) -> requests.Session`. When `proxy_url` is set, populates `session.proxies = {"http": proxy_url, "https": proxy_url}`.
- Proxy URL is stored only in `st.session_state["proxy_url"]`. Never written to disk by Raven.
- `RAVEN_PROXY_URL` env var seeds the field on first run for users who want it persisted via `.env`.

### 4.2 Layer B — WireGuard tunnel

- Sidebar: file uploader for a `.conf` (ProtonVPN distributes ready-to-use WG configs).
- **Connect** button calls `vpn.wg_up(conf_path)`:
  - Linux/macOS: `sudo wg-quick up <path>` (sudo prompt expected; documented).
  - Windows: `wireguard.exe /installtunnelservice <path>` (requires *WireGuard for Windows*; launcher detects, instructs install via `winget install WireGuard.WireGuard` if missing).
- **Disconnect** button calls the symmetric command. Auto-disconnect on app shutdown via `atexit` + Streamlit session end.
- Status badge in sidebar header: `🛡️ VPN: 🟢 wg-raven · peer 1.2.3.4` / `⚪ off`.
- Config storage:
  - Copied to `RAVEN_DATA_DIR/tunnels/<uuid>.conf`.
  - File permissions: `0o600` on POSIX; ACL restricted to current user on Windows (`icacls`).
  - Removed from disk on disconnect or app exit.

### 4.3 Layer C — OpenVPN

- Same UX as WG, but accepts `.ovpn` and runs `openvpn --config <path>` as a managed subprocess.
- Detects `openvpn` binary in PATH; instructs install if missing (`apt install openvpn` / `brew install openvpn` / `winget install OpenVPNTechnologies.OpenVPN`).
- Used primarily for IPVanish (no WG distribution) but works with any OpenVPN provider.

### 4.4 Killswitch (pipeline-level, opt-in)

- Checkbox: **Abort pipeline if VPN drops**.
- When checked AND a tunnel is active: background poller checks tunnel liveness every 3s during a scrape job. Liveness check is OS-portable:
  - Linux/macOS WG: `wg show <iface>` exit code.
  - Windows WG: query `wireguard.exe /servicemanager` or check the service state via `sc query WireGuardTunnel$<name>`.
  - OpenVPN (any OS): subprocess `poll()` against the managed openvpn process.
- On drop: pending HTTP/scrape work is cancelled cleanly via a `threading.Event`. UI surfaces a banner.
- **Does NOT touch system firewall.** Out of scope.

### 4.5 Config sanitization (security-critical)

Both `.conf` and `.ovpn` formats permit directives that execute arbitrary commands on tunnel up/down. A malicious config uploaded by a victim would otherwise be a code-execution vector.

`vpn.parse_and_validate(path)` enforces:

- **WireGuard reject list:** `PreUp`, `PostUp`, `PreDown`, `PostDown`, `Table = off` with `Allowed IPs = 0.0.0.0/0` combined with custom routes (manual review).
- **OpenVPN reject list:** `script-security 2|3`, `up`, `down`, `route-up`, `route-pre-down`, `tls-verify`, `ipchange`, `client-connect`, `client-disconnect`, `learn-address`, `auth-user-pass-verify`, `plugin`.
- Any rejected directive → upload refused with a precise error pointing at the line.
- Validator returns a normalized config rewritten without those lines (defensive — even if a directive is later allowed, the rewrite is what gets handed to the binary).

## 5. Startup (Windows-native)

### 5.1 `raven.ps1`

Single entry point at repo root. Idempotent.

```
1. Check Python ≥ 3.10. If absent: prompt → winget install Python.Python.3.12.
2. Ensure .venv\ exists; create + activate if not.
3. pip install -r requirements.txt (with --quiet, pip cache enabled).
4. Ensure tools\tor\tor.exe exists:
   - If absent: download Tor Expert Bundle from torproject.org,
     verify SHA-256 against a pinned value in raven.ps1,
     extract tor.exe into tools\tor\.
5. Start tor.exe as background job on 127.0.0.1:9050.
   - Write PID to .raven\tor.pid.
   - Wait for "Bootstrapped 100%" line on stdout (timeout 60s).
6. streamlit run ui.py --server.headless=true.
7. On Ctrl+C or exit: kill Tor PID, call vpn.disconnect_all().
```

Errors at each step surface a one-line message + the remediation command (no stack traces in the user-facing path).

### 5.2 `raven.sh`

POSIX equivalent. Uses system Tor if `which tor` succeeds; falls back to portable bundle for parity with Windows.

### 5.3 UI status block

Above the existing stat cards in `ui.py`:

```
🧅 Tor: 🟢 127.0.0.1:9050     🛡️ VPN: ⚪ off     🌐 Proxy: ⚪ off
```

Each badge clickable, scrolls/expands to the matching sidebar control. Visibility removes the implicit "you must run Tor yourself" knowledge.

### 5.4 Docker

Kept as a documented alternative ("for users who prefer container isolation"). No functional changes. README ordering: PowerShell launcher first, Docker second, Python-from-source third.

## 6. File-level change list

| File | Status | Change |
|---|---|---|
| `README.md` | rewrite | New positioning, launcher-first install path, credit section |
| `ui.py` | edit | Status block, sidebar **🌐 Network egress** + **🛡️ VPN tunnel** expanders, page title |
| `scrape.py` | edit | `make_session(proxy_url)`; thread through to existing call sites |
| `config.py` | edit | `RAVEN_DATA_DIR`, `RAVEN_PROXY_URL`; alias resolver for legacy vars |
| `vpn.py` | **new** | `wg_up/down`, `ovpn_up/down`, `status()`, `parse_and_validate()`, `disconnect_all()` |
| `raven.ps1` | **new** | Windows launcher (§5.1) |
| `raven.sh` | **new** | POSIX launcher (§5.2) |
| `.gitignore` | edit | `tools/`, `.raven/`, `.venv/`, `*.conf`, `*.ovpn` |
| `Dockerfile` | edit | Labels + tag; no functional change |
| `requirements.txt` | edit | Add `requests[socks]` for SOCKS proxy support if not already present |

## 7. Architecture sketch

```
        ┌────────────────────────────────────────────────────┐
        │ ui.py (Streamlit)                                  │
        │  ├─ status block (Tor/VPN/Proxy)                   │
        │  └─ sidebar:                                        │
        │      ├─ 🌐 Network egress (proxy URL)              │
        │      └─ 🛡️ VPN tunnel (WG/OVPN upload + connect)   │
        └────┬───────────────┬───────────────────┬───────────┘
             │               │                    │
             ▼               ▼                    ▼
         scrape.py       vpn.py            llm.py / llm_utils.py
       make_session(    wg_up/down         (existing pipeline)
       proxy_url)       ovpn_up/down
             │          parse_and_validate
             │          status / killswitch
             ▼
        requests ──► [proxy?] ──► [Tor 9050] ──► target
                          └─ optional layer
```

## 8. Testing & verification

- **Smoke test (Windows):** clean Win11 VM, no Python pre-installed → `.\raven.ps1` → UI loads, Tor green, scrape returns results.
- **Smoke test (Linux):** Ubuntu 22.04 container → `./raven.sh` → same.
- **Proxy:** point at local `mitmproxy --mode regular` → confirm scrape traffic shows up there.
- **WireGuard:** test peer (self-hosted wg server in VM) → connect/disconnect/status badges/auto-cleanup on exit.
- **OpenVPN:** local OpenVPN server → same.
- **Killswitch:** during a long scrape, `ifdown wg-raven` → pipeline aborts within ~3s, banner shown.
- **Config sanitization (unit):** craft `.conf` with `PostUp = curl evil.example`; assert validator rejects with the offending line cited.
- **Backward compat:** `.env` with `ROBIN_*` legacy vars only → app reads them via aliases, no warnings about missing config.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| Tor Expert Bundle URL/hash drift | Pinned SHA-256 in `raven.ps1`; launcher prints clear "update the pinned hash" message on mismatch. |
| `wireguard.exe` not installed on Windows | Detected; instructions printed; UI shows a clear "install required" state instead of crashing. |
| Sudo prompt UX on Linux (GUI users) | Document that `wg-quick` needs sudo; suggest configuring NOPASSWD entry for `wg-quick` if user wants headless. |
| Antivirus flagging `tor.exe` download | Use official torproject.org URL only; document expected AV behavior. |
| User uploads malicious config | §4.5 sanitization gate. |

## 10. Out of scope (deferred to follow-up specs)

- LLM review items #3 (structured output), #4 (token mgmt), #5 (retry/backoff), #6 (temperature/streaming overrides), #7 (streaming inconsistency on local models), #10 (prompt-injection defense in `generate_summary`), #11 (externalize model catalog).
- New logo asset (placeholder text until designed).
- Publishing `raven` image to a registry (purely local until decided).
