#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional


HOME_DIR = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TARGETS = {
    "rescue-local": {
        "wrapper": os.path.join(SCRIPT_DIR, "rescue-openclaw.sh"),
        "state_env": "OPENCLAW_RESCUE_STATE_DIR",
        "config_env": "OPENCLAW_RESCUE_CONFIG_PATH",
        "default_state_dir": os.path.join(HOME_DIR, ".openclaw-rescue"),
        "default_config_path": os.path.join(HOME_DIR, ".openclaw-rescue", "openclaw.json"),
        "forbidden_path_fragment": ".openclaw/openclaw.json",
    },
    "principal-local": {
        "wrapper": os.path.join(SCRIPT_DIR, "principal-openclaw.sh"),
        "state_env": "OPENCLAW_PRINCIPAL_STATE_DIR",
        "config_env": None,
        "default_state_dir": os.path.join(HOME_DIR, ".openclaw"),
        "default_config_path": os.path.join(HOME_DIR, ".openclaw", "openclaw.json"),
        "forbidden_path_fragment": ".openclaw-rescue",
    },
}


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def resolve_sender(cli_value: str | None) -> str:
    sender = cli_value or os.environ.get("TELEGRAM_SENDER_ID")
    if not sender:
        fail("telegram sender id is required; pass --sender or set TELEGRAM_SENDER_ID")
    return str(sender)


def to_tilde(path: str) -> str:
    if path.startswith(HOME_DIR + os.sep):
        return path.replace(HOME_DIR, "~", 1)
    if path == HOME_DIR:
        return "~"
    return path


def markers_for_path(path: str) -> List[str]:
    markers = [path]
    tilde_path = to_tilde(path)
    if tilde_path != path:
        markers.append(tilde_path)
    return markers


def line_value(lines: Iterable[str], prefix_pattern: str) -> Optional[str]:
    regex = re.compile(prefix_pattern)
    for line in lines:
        match = regex.match(line)
        if match:
            return match.group(1).strip()
    return None


def allowlist_contains(entries: Iterable[Any], sender: str) -> bool:
    sender_str = str(sender)
    for entry in entries:
        entry_str = str(entry)
        if entry_str == sender_str:
            return True
        if entry_str == f"id:{sender_str}":
            return True
    return False


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        fail(f"config is not a JSON object: {path}")
    return data


def run_wrapper(wrapper: str, *args: str) -> str:
    proc = subprocess.run([wrapper, *args], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        fail(f"wrapper command failed: {wrapper} {' '.join(args)}")
    return proc.stdout


def summarize_allowlist(entries: Iterable[Any]) -> str:
    values = [str(entry) for entry in entries]
    return ", ".join(values) if values else "none"


def inspect_target(target: str, sender: str) -> str:
    spec = TARGETS[target]
    wrapper = spec["wrapper"]
    if not os.path.exists(wrapper):
        fail(f"wrapper missing: {wrapper}")
    if not os.access(wrapper, os.X_OK):
        fail(f"wrapper not executable: {wrapper}")

    state_dir = os.path.abspath(os.environ.get(spec["state_env"], spec["default_state_dir"]))
    config_path = os.path.abspath(os.environ.get(spec["config_env"], spec["default_config_path"])) if spec["config_env"] else os.path.abspath(spec["default_config_path"])

    if target == "principal-local":
        if state_dir == os.path.join(HOME_DIR, ".openclaw-rescue") or ".openclaw-rescue" in state_dir:
            fail(f"principal target still points to rescue state dir: {state_dir}")
        if ".openclaw-rescue" in config_path:
            fail(f"principal target still points to rescue config: {config_path}")
    if target == "rescue-local":
        if state_dir == os.path.join(HOME_DIR, ".openclaw"):
            fail(f"rescue target still points to principal state dir: {state_dir}")
        if config_path == os.path.join(HOME_DIR, ".openclaw", "openclaw.json"):
            fail(f"rescue target still points to principal config: {config_path}")

    if not os.path.isfile(config_path):
        fail(f"config missing: {config_path}")

    config = load_json(config_path)
    gateway_output = run_wrapper(wrapper, "gateway", "status", "--require-rpc")
    lines = gateway_output.splitlines()

    cli_config = line_value(lines, r"^Config \(cli\):\s*(.+)$")
    service_config = line_value(lines, r"^Config \(service\):\s*(.+)$")
    probe_status = line_value(lines, r"^(?:RPC|Read|Connectivity) probe:\s*(.+)$")

    if not cli_config:
        fail("gateway status did not expose Config (cli)")
    if not service_config:
        fail("gateway status did not expose Config (service)")
    if not probe_status:
        fail("gateway status did not expose probe status")

    valid_config_markers = markers_for_path(config_path)
    if cli_config not in valid_config_markers:
        fail(f"gateway status CLI config does not match target config: {cli_config}")
    if service_config not in valid_config_markers:
        fail(f"gateway status service config does not match target config: {service_config}")
    if probe_status != "ok":
        fail(f"probe status is not ok: {probe_status}")

    forbidden_fragment = spec["forbidden_path_fragment"]
    if forbidden_fragment and forbidden_fragment in gateway_output and target == "principal-local":
        fail("principal gateway status still references rescue")

    tools = config.get("tools") or {}
    if not isinstance(tools, dict):
        tools = {}
    global_elevated = tools.get("elevated") or {}
    if not isinstance(global_elevated, dict):
        global_elevated = {}

    global_enabled = bool(global_elevated.get("enabled") is True)
    global_allow = ((global_elevated.get("allowFrom") or {}).get("telegram") or []) if isinstance(global_elevated.get("allowFrom") or {}, dict) else []
    global_sender_allowed = allowlist_contains(global_allow, sender)

    agents = ((config.get("agents") or {}).get("list") or []) if isinstance(config.get("agents") or {}, dict) else []
    if not isinstance(agents, list):
        agents = []

    out: List[str] = []
    out.append("Telegram elevated inspection (read-only)")
    out.append(f"Target              : {target}")
    out.append(f"Requested sender    : telegram:{sender}")
    out.append(f"Wrapper             : {wrapper}")
    out.append(f"Expected state dir  : {state_dir}")
    out.append(f"Expected config     : {config_path}")
    out.append(f"Config (cli)        : {cli_config}")
    out.append(f"Config (service)    : {service_config}")
    out.append(f"Probe               : {probe_status}")
    out.append("")
    out.append("Global elevated gate")
    out.append(f"- enabled           : {str(global_enabled).lower()}")
    out.append(f"- telegram allowlist: {summarize_allowlist(global_allow)}")
    out.append(f"- sender allowed    : {str(global_sender_allowed).lower()}")
    out.append("")
    out.append(f"Agents ({len(agents)})")
    if not agents:
        out.append("- none")
    else:
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            agent_id = str(agent.get("id") or "<missing-id>")
            agent_tools = agent.get("tools") or {}
            if not isinstance(agent_tools, dict):
                agent_tools = {}
            agent_elevated = agent_tools.get("elevated")
            if agent_elevated is None:
                override_enabled = "inherit"
                override_allow = []
                override_sender_allowed = "inherit"
                effective_enabled = global_enabled
                effective_sender_allowed = global_sender_allowed
            else:
                if not isinstance(agent_elevated, dict):
                    agent_elevated = {}
                if "enabled" in agent_elevated:
                    override_enabled_bool = bool(agent_elevated.get("enabled") is True)
                    override_enabled = str(override_enabled_bool).lower()
                    effective_enabled = global_enabled and override_enabled_bool
                else:
                    override_enabled = "inherit"
                    effective_enabled = global_enabled
                agent_allow_from = agent_elevated.get("allowFrom") or {}
                if not isinstance(agent_allow_from, dict):
                    agent_allow_from = {}
                if "telegram" in agent_allow_from:
                    override_allow = agent_allow_from.get("telegram") or []
                    override_sender_allowed_bool = allowlist_contains(override_allow, sender)
                    override_sender_allowed = str(override_sender_allowed_bool).lower()
                    effective_sender_allowed = global_sender_allowed and override_sender_allowed_bool
                else:
                    override_allow = []
                    override_sender_allowed = "inherit"
                    effective_sender_allowed = global_sender_allowed
            effective_available_for_sender = effective_enabled and effective_sender_allowed
            out.append(f"- {agent_id}")
            out.append(f"  - override.enabled          : {override_enabled}")
            out.append(f"  - override.telegram         : {summarize_allowlist(override_allow) if override_allow else 'inherit'}")
            out.append(f"  - override.senderAllowed    : {override_sender_allowed}")
            out.append(f"  - effective.enabled         : {str(effective_enabled).lower()}")
            out.append(f"  - effective.senderAllowed   : {str(effective_sender_allowed).lower()}")
            out.append(f"  - effective.availableSender : {str(effective_available_for_sender).lower()}")

    out.append("")
    out.append("Cross-checks")
    out.append(f"[OK] gateway context proved for target: {target}")
    out.append(f"[OK] requested sender inspected read-only: telegram:{sender}")
    if global_enabled:
        out.append("[OK] global elevated gate is enabled")
    else:
        out.append("[WARN] global elevated gate is disabled or absent")
    if global_sender_allowed:
        out.append(f"[OK] requested sender appears in global telegram allowlist: {sender}")
    else:
        out.append(f"[WARN] requested sender is absent from global telegram allowlist: {sender}")

    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Telegram elevated config and gateway context without mutating anything.")
    parser.add_argument("--target", required=True, choices=sorted(TARGETS.keys()))
    parser.add_argument("--sender", help="Telegram sender id to inspect against allowlists. Defaults to TELEGRAM_SENDER_ID when set.")
    args = parser.parse_args()
    sys.stdout.write(inspect_target(args.target, resolve_sender(args.sender)))


if __name__ == "__main__":
    main()
