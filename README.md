<div align="center">
   <img src=".github/assets/raven.png" alt="Raven" width="320" />
   <h1>R A V E N</h1>
   <p><em>an oracle for the unindexed deep — sees what others cannot</em></p>
   <p><strong>AI-powered dark web OSINT — a hardened fork of <a href="https://github.com/apurvsinghgautam/robin">Robin</a>.</strong></p>
   <p>
     <a href="#quick-start">Quick start</a> •
     <a href="#whats-different-from-robin">What's different</a> •
     <a href="#network-egress">Network egress</a> •
     <a href="#configuration">Configuration</a> •
     <a href="#acknowledgements">Acknowledgements</a>
   </p>
</div>

> Raven keeps Robin's pipeline (search → filter → scrape → summarize via an LLM) and adds five things:
> 1. **Stability fixes** for the LLM integration layer (bugs that broke custom providers, shared streaming state, stale model defaults).
> 2. **Opt-in egress security** — manual proxy + WireGuard / OpenVPN tunnel on top of Tor.
> 3. **Frictionless Windows startup** — a native PowerShell launcher. No WSL2, no `apt install tor`.
> 4. **Refined prompts** that demand concrete artifacts with dates, sources, and severity — no generic threat-landscape prose.
> 5. **EN / PT-BR** UI + LLM output, plus a **Dark Web + OSINT** search profile that adds Intelligence X / DDoSecrets / Wayback Machine alongside the .onion engines.

<div align="center">
   <img src=".github/assets/screen-ui.png" alt="Raven UI" width="850" />
   <br/>
   <sub><em>Threat-researcher terminal — Tor / VPN / Proxy HUD, console-style query form, archived runs sidebar.</em></sub>
</div>

---

## ⚠️ Disclaimer

This tool is intended for educational and lawful investigative purposes only. Accessing or interacting with certain dark web content may be illegal depending on your jurisdiction. The author is not responsible for any misuse of this tool or the data gathered using it.

Raven leverages third-party LLM APIs. Be cautious when sending potentially sensitive queries, and review the terms of service for any model provider you use.

---

## Quick start

### Windows (native, no WSL2)

```powershell
.\raven.ps1
```

The launcher takes care of everything:

1. Detects Python 3.10+ (offers to install via `winget` if missing).
2. Creates a local `.venv\`.
3. Installs dependencies.
4. Downloads a portable Tor Expert Bundle into `tools\tor\` (with SHA-256 verification once a hash is pinned).
5. Starts Tor on `127.0.0.1:9050`.
6. Launches the Streamlit UI on http://localhost:8501.

On shutdown (Ctrl+C), Tor and any active VPN tunnel are torn down automatically.

### Linux / macOS

```bash
./raven.sh
```

Uses system `tor` if installed (`apt install tor` / `brew install tor`); otherwise warns and continues with clearweb-only scraping.

### Docker (alternative)

```bash
docker build -t raven:latest .
docker run --rm \
   -v "$(pwd)/.env:/app/.env" \
   -v "$(pwd)/investigations:/app/investigations" \
   --add-host=host.docker.internal:host-gateway \
   -p 8501:8501 \
   raven:latest
```

Then open http://localhost:8501.

---

## What's different from Robin

### Stability (LLM integration)

| Fix | Why it mattered |
|---|---|
| `resolve_model_config` no longer shadows the `config` module | Resolving a custom API model raised `AttributeError` instead of returning a config. |
| Streaming callbacks are now created per-LLM-instance | The original shared a single `BufferedStreamingHandler`, so parallel or successive LLMs interleaved output. |
| `fetch_*_models()` results are TTL-cached (30s) | Streamlit reruns no longer pay 3× HTTP roundtrips of up to 3s each on every interaction. |
| Default model selection points to existing entries | The previous default looked for `"gpt4o"` (removed from the catalog) and silently fell back to index 0. |

The remaining items from the original review (structured output for `filter_results`, token-budget handling in `generate_summary`, unified retry/backoff, prompt-injection defense against scraped content, externalized model catalog) are tracked in [docs/superpowers/specs](docs/superpowers/specs/).

### Network egress

All three layers are **opt-in**. Empty config = identical behaviour to upstream Robin.

#### Layer A — Manual proxy (always available)

Sidebar **🌐 Network egress** accepts an HTTP or SOCKS5 URL:

```
socks5h://user:pass@host:1080
http://10.0.0.1:8080
```

Applied to **clearweb** scraping only — `.onion` targets continue to use Tor. The proxy URL is held in Streamlit session state, never written to disk by Raven.

#### Layer B — WireGuard tunnel (opt-in)

Sidebar **🛡️ VPN tunnel** accepts a WireGuard `.conf` (ProtonVPN distributes ready-to-use configs).

- **Linux / macOS:** Raven runs `sudo wg-quick up <config>`. Install with `apt install wireguard` or `brew install wireguard-tools`.
- **Windows:** Raven calls `wireguard.exe /installtunnelservice`. Install with `winget install WireGuard.WireGuard`.

The tunnel is brought up only when you click connect, and torn down on disconnect or app exit. Configs are stored under `RAVEN_DATA_DIR/tunnels/` with restricted permissions and deleted at teardown.

#### Layer C — OpenVPN (opt-in)

Same UX as WireGuard but takes `.ovpn`. Primarily for IPVanish-style providers without WG support. Requires `openvpn` on PATH (`winget install OpenVPNTechnologies.OpenVPN`, `apt install openvpn`, `brew install openvpn`).

#### Security: config sanitization

WireGuard and OpenVPN configs allow directives that execute arbitrary commands on tunnel up/down (`PostUp`, `script-security 2`, `client-connect`, ...). A malicious uploaded config would otherwise be a code-execution vector.

Raven parses every upload before launching the binary and **rejects** any of the following:

- WireGuard: `PreUp`, `PostUp`, `PreDown`, `PostDown`.
- OpenVPN: `script-security`, `up`, `down`, `route-up`, `route-pre-down`, `tls-verify`, `ipchange`, `client-connect`, `client-disconnect`, `learn-address`, `auth-user-pass-verify`, `plugin`, `setenv`.

The validator points at the offending line. If you legitimately need one of these, run the tunnel outside Raven and use the manual-proxy field (Layer A) instead.

#### Killswitch (pipeline-level, opt-in)

Checkbox **Abort pipeline if VPN drops** under the VPN expander. During an active scrape, Raven polls the tunnel interface every 3s; if it dies, in-flight work is cancelled. This **does not** touch system firewall — it is scoped to Raven's own pipeline.

---

## Configuration

Environment variables (via `.env` or shell). Existing `ROBIN_*` names continue to work as aliases.

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY` | LLM provider credentials. |
| `OPENROUTER_BASE_URL` | Defaults to `https://openrouter.ai/api/v1`. |
| `OLLAMA_BASE_URL` | e.g. `http://127.0.0.1:11434` (or `http://host.docker.internal:11434` from Docker). |
| `LLAMA_CPP_BASE_URL`, `CUSTOM_API_BASE_URL`, `CUSTOM_API_KEY`, `CUSTOM_API_MODEL` | Any OpenAI-compatible endpoint. The sidebar **🔌 Custom API Provider** expander writes these for the current session without touching `.env`. |
| `RAVEN_DATA_DIR` | Where Raven keeps runtime state (default `.raven`). |
| `RAVEN_PROXY_URL` | Pre-fills the manual-proxy field on startup. |

---

## Acknowledgements

- Original project: **[Robin](https://github.com/apurvsinghgautam/robin)** by [Apurv Singh Gautam](https://www.linkedin.com/in/apurvsinghgautam/). Raven is a fork — pipeline architecture, prompt presets, and the Streamlit UX all originate there. License preserved.
- Idea inspiration upstream: [Thomas Roccia](https://x.com/fr0gger_) and his [Perplexity of the Dark Web](https://x.com/fr0gger_/status/1908051083068645558) demo.
- LLM prompt inspiration upstream: [OSINT-Assistant](https://github.com/AXRoux/OSINT-Assistant).
- Robin logo by [Tanishq Rupaal](https://github.com/Tanq16/). Raven currently uses Robin's logo placeholder pending a new asset.

---

## Contributing

Contributions are welcome. The fork keeps Robin's contribution model:

- Fork, branch, commit, PR.
- Open an issue for bug reports, feature requests, or design questions.
- Larger refactors (e.g. the deferred LLM items) should land via the spec process under `docs/superpowers/specs/`.
