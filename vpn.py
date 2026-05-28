"""
Raven VPN integration: opt-in layered egress controls on top of Tor.

This module provides thin, OS-portable wrappers around WireGuard and OpenVPN
so the user can route Raven's traffic through an additional tunnel without
leaving the app. It is opt-in — if nothing is connected, behaviour is
identical to upstream Robin.

Security note: WireGuard and OpenVPN config files allow directives that
execute arbitrary commands on tunnel up/down (PostUp, script-security 2,
etc.). A malicious uploaded config would otherwise be a code-exec vector,
so every config is parsed and rejected if it contains any dangerous
directive. The sanitized config that gets handed to the binary is rewritten
without those lines.
"""
from __future__ import annotations

import atexit
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import config as _cfg

_logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform.startswith("win")
IS_MACOS = sys.platform == "darwin"

# Directives forbidden inside an uploaded WireGuard .conf (would execute
# arbitrary shell commands as root). Case-insensitive key match.
_WG_FORBIDDEN_KEYS = {
    "preup", "postup", "predown", "postdown",
}

# OpenVPN directives that can execute arbitrary commands or load plugins.
_OVPN_FORBIDDEN_TOKENS = {
    "script-security", "up", "down", "route-up", "route-pre-down",
    "tls-verify", "ipchange", "client-connect", "client-disconnect",
    "learn-address", "auth-user-pass-verify", "plugin", "setenv",
}


class VPNConfigError(ValueError):
    """Raised when an uploaded VPN config contains forbidden directives."""


@dataclass
class TunnelState:
    kind: str                       # "wireguard" | "openvpn"
    iface: str                      # e.g. "raven-<uuid>" or service name
    sanitized_path: Path
    process: subprocess.Popen | None = None  # for openvpn
    peer_hint: str = ""             # display string for the UI

    def __repr__(self) -> str:
        return f"TunnelState(kind={self.kind!r}, iface={self.iface!r}, peer={self.peer_hint!r})"


# Module-level singleton — Streamlit reruns share this across reruns within
# the same process, which is what we want (one tunnel per app instance).
_active: TunnelState | None = None
_active_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def _strip_comment(line: str) -> str:
    # WG/OVPN both treat '#' as comment; OVPN also treats ';'
    for ch in ("#", ";"):
        idx = line.find(ch)
        if idx >= 0:
            line = line[:idx]
    return line.rstrip()


def sanitize_wireguard(text: str) -> str:
    """Parse a WireGuard .conf; raise VPNConfigError if any forbidden directive
    is present. Returns the (unchanged) text on success — WG configs are
    declarative and have no other code-exec surface beyond the forbidden keys.
    """
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if not line.strip() or line.strip().startswith("["):
            continue
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip().lower()
        if key in _WG_FORBIDDEN_KEYS:
            raise VPNConfigError(
                f"line {lineno}: directive '{key}' is not allowed "
                "(it would execute arbitrary commands on tunnel up/down)."
            )
    return text


def sanitize_openvpn(text: str) -> str:
    """Parse an OpenVPN .ovpn; raise VPNConfigError if any forbidden directive
    is present. Returns the input unchanged on success.
    """
    inside_inline_block = False
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).strip()
        if not line:
            continue
        # Skip inline cert/key blocks like <ca>...</ca>
        if line.startswith("<") and line.endswith(">"):
            inside_inline_block = not line.startswith("</")
            continue
        if inside_inline_block:
            continue
        first_token = line.split()[0].lower()
        if first_token in _OVPN_FORBIDDEN_TOKENS:
            raise VPNConfigError(
                f"line {lineno}: directive '{first_token}' is not allowed "
                "(it would execute arbitrary commands or load plugins)."
            )
    return text


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _tunnel_dir() -> Path:
    base = Path(_cfg.RAVEN_DATA_DIR) / "tunnels"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _save_config(content: str, suffix: str) -> Path:
    name = f"raven-{uuid.uuid4().hex[:8]}{suffix}"
    path = _tunnel_dir() / name
    path.write_text(content, encoding="utf-8")
    try:
        if not IS_WINDOWS:
            os.chmod(path, 0o600)
        else:
            # Best-effort lockdown — restrict to current user.
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r",
                 f"{os.environ.get('USERNAME', 'CurrentUser')}:F"],
                check=False,
                capture_output=True,
            )
    except OSError as e:
        _logger.warning("Could not tighten permissions on %s: %s", path, e)
    return path


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as e:
        _logger.debug("Could not delete %s: %s", path, e)


# ---------------------------------------------------------------------------
# WireGuard
# ---------------------------------------------------------------------------

def _wg_iface_name() -> str:
    # Linux interface names must be <= 15 chars
    return f"raven-{uuid.uuid4().hex[:6]}"


def wg_up(config_text: str) -> TunnelState:
    """Bring up a WireGuard tunnel from an uploaded .conf text."""
    global _active
    sanitized = sanitize_wireguard(config_text)
    iface = _wg_iface_name()
    # wg-quick on POSIX uses the basename of the file as the interface name.
    path = _tunnel_dir() / f"{iface}.conf"
    path.write_text(sanitized, encoding="utf-8")
    try:
        if not IS_WINDOWS:
            os.chmod(path, 0o600)
    except OSError:
        pass

    peer = _peer_hint_from_wg(sanitized)

    with _active_lock:
        if _active is not None:
            raise RuntimeError(f"A tunnel is already active ({_active.kind}). Disconnect first.")
        try:
            if IS_WINDOWS:
                wireguard_exe = shutil.which("wireguard.exe") or r"C:\Program Files\WireGuard\wireguard.exe"
                if not Path(wireguard_exe).exists():
                    raise RuntimeError(
                        "WireGuard for Windows is not installed. "
                        "Install it via: winget install WireGuard.WireGuard"
                    )
                subprocess.run(
                    [wireguard_exe, "/installtunnelservice", str(path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            else:
                if shutil.which("wg-quick") is None:
                    raise RuntimeError(
                        "wg-quick not found. Install with: "
                        "sudo apt install wireguard  (Debian/Ubuntu) "
                        "or  brew install wireguard-tools  (macOS)"
                    )
                subprocess.run(
                    ["sudo", "wg-quick", "up", str(path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except subprocess.CalledProcessError as e:
            _safe_unlink(path)
            stderr = (e.stderr or "").strip() or (e.stdout or "").strip()
            raise RuntimeError(f"Failed to bring up WireGuard tunnel: {stderr or e}") from e

        _active = TunnelState(
            kind="wireguard",
            iface=iface,
            sanitized_path=path,
            peer_hint=peer,
        )
        return _active


def wg_down(state: TunnelState) -> None:
    if state.kind != "wireguard":
        return
    try:
        if IS_WINDOWS:
            wireguard_exe = shutil.which("wireguard.exe") or r"C:\Program Files\WireGuard\wireguard.exe"
            subprocess.run(
                [wireguard_exe, "/uninstalltunnelservice", state.iface],
                check=False,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["sudo", "wg-quick", "down", str(state.sanitized_path)],
                check=False,
                capture_output=True,
            )
    finally:
        _safe_unlink(state.sanitized_path)


def _peer_hint_from_wg(text: str) -> str:
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if line.lower().startswith("endpoint"):
            _, _, val = line.partition("=")
            return val.strip()
    return "unknown peer"


def _wg_is_alive(state: TunnelState) -> bool:
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ["sc", "query", f"WireGuardTunnel${state.iface}"],
                capture_output=True, text=True, timeout=5,
            )
            return "RUNNING" in (r.stdout or "")
        else:
            r = subprocess.run(
                ["wg", "show", state.iface],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# OpenVPN
# ---------------------------------------------------------------------------

def ovpn_up(config_text: str) -> TunnelState:
    """Start an OpenVPN tunnel from an uploaded .ovpn text."""
    global _active
    sanitized = sanitize_openvpn(config_text)
    path = _save_config(sanitized, ".ovpn")

    if shutil.which("openvpn") is None:
        _safe_unlink(path)
        raise RuntimeError(
            "openvpn binary not found in PATH. Install it: "
            "sudo apt install openvpn  /  brew install openvpn  /  winget install OpenVPNTechnologies.OpenVPN"
        )

    with _active_lock:
        if _active is not None:
            raise RuntimeError(f"A tunnel is already active ({_active.kind}). Disconnect first.")

        cmd = ["openvpn", "--config", str(path)]
        if not IS_WINDOWS:
            cmd = ["sudo"] + cmd
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
        except OSError as e:
            _safe_unlink(path)
            raise RuntimeError(f"Failed to start openvpn: {e}") from e

        _active = TunnelState(
            kind="openvpn",
            iface=path.stem,
            sanitized_path=path,
            process=proc,
            peer_hint=_peer_hint_from_ovpn(sanitized),
        )
        return _active


def ovpn_down(state: TunnelState) -> None:
    if state.kind != "openvpn":
        return
    proc = state.process
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        except OSError:
            pass
    _safe_unlink(state.sanitized_path)


def _peer_hint_from_ovpn(text: str) -> str:
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if line.lower().startswith("remote "):
            parts = line.split()
            if len(parts) >= 2:
                return " ".join(parts[1:3])  # host + optional port
    return "unknown remote"


def _ovpn_is_alive(state: TunnelState) -> bool:
    return state.process is not None and state.process.poll() is None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def status() -> dict:
    """Return a JSON-serializable status snapshot for the UI."""
    with _active_lock:
        if _active is None:
            return {"connected": False}
        alive = is_alive(_active)
        return {
            "connected": True,
            "kind": _active.kind,
            "iface": _active.iface,
            "peer": _active.peer_hint,
            "alive": alive,
        }


def is_alive(state: TunnelState | None = None) -> bool:
    state = state or _active
    if state is None:
        return False
    if state.kind == "wireguard":
        return _wg_is_alive(state)
    if state.kind == "openvpn":
        return _ovpn_is_alive(state)
    return False


def disconnect() -> None:
    """Tear down the currently active tunnel (if any)."""
    global _active
    with _active_lock:
        state = _active
        _active = None
    if state is None:
        return
    if state.kind == "wireguard":
        wg_down(state)
    elif state.kind == "openvpn":
        ovpn_down(state)


def disconnect_all() -> None:
    """Belt-and-suspenders teardown, safe to call from atexit."""
    try:
        disconnect()
    except Exception as e:
        _logger.warning("disconnect_all encountered: %s", e)


atexit.register(disconnect_all)
