"""Bounded, redacted native/CAPI diagnostics; never a connection admission receipt.

No network, provider, session or process is started by this module. The observer
is installed only by the already guarded hosted entry points. Fixture evidence
and real response-side reports remain distinct from independent attestation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

from ghcp_ahp_diagnostics import DiagnosticRedactor, NOT_REPORTED
from ghcp_ahp_probe import (DESIRED_MODEL, MAX_ARCHIVE_EXPANSION_BYTES, Refused,
                            digest, load_manifest, save_json, strict_json)

PRELOAD = Path(__file__).with_name("ghcp_ahp_wire_preload.cjs")
PIN = "2c33b50b16c472efe58357d1d2a8a5414bc23fbf"
MAX_BYTES = 16 * 1024 * 1024
FIELDS = ("model", "reasoning_effort", "context_window", "sandbox", "approval", "network", "web_search")
SOURCES = {
    "agent_fork": ("src/vs/platform/agentHost/node/nodeAgentHostStarter.ts", "VSCODE_ESM_ENTRYPOINT: 'vs/platform/agentHost/node/agentHostMain'"),
    "agent_module": ("src/vs/platform/agentHost/node/nodeAgentHostStarter.ts", "new Client(FileAccess.asFileUri('bootstrap-fork').fsPath, options)"),
    "agent_arguments": ("src/vs/platform/agentHost/node/nodeAgentHostStarter.ts", "'--logsPath', this._environmentService.logsHome"),
    "agent_ready": ("src/vs/platform/agentHost/node/agentHostMain.ts", "console.log(`Agent host server listening on ${listenTarget}`)"),
    "fork_sanitizer": ("src/vs/base/parts/ipc/node/ipc.cp.ts", "removeDangerousEnvVariables(forkOpts.env)"),
    "ipc_start": ("src/vs/platform/agentHost/node/codex/codexAgent.ts", "child = spawn(binaryPath, args"),
    "native_config": ("src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadSettings.ts", "export type ThreadSettings"),
    "native_thread": ("src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadStartResponse.ts", "export type ThreadStartResponse"),
    "context": ("src/vs/platform/agentHost/node/codex/protocol/generated/v2/ThreadTokenUsage.ts", "modelContextWindow"),
    "web_search_request": ("src/vs/platform/agentHost/node/codex/codexAgent.ts", "web_search: narrowWebSearchMode"),
    "fetch": ("src/vs/platform/agentHost/node/shared/copilotApiService.ts", "this._fetch = fetchFn ?? globalThis.fetch"),
    "capi_request": ("src/vs/platform/agentHost/node/shared/copilotApiService.ts", "async responses("),
    "capi_fetch": ("src/vs/platform/agentHost/node/shared/copilotApiService.ts", "fetch: (url, options) => fetch(url"),
    "capi_stream": ("src/vs/platform/agentHost/node/codex/codexProxyService.ts", "const reader = upstream.body.getReader()"),
    "model_echo": ("src/vs/platform/agentHost/node/codex/codexMapAppServerEvents.ts", "...(modelId ? { model: modelId }"),
}


def source_evidence(archive, manifest):
    """Quote exact lines from the already pinned source archive, not current main."""
    if manifest["vscode_commit"] != PIN or digest(archive) != manifest["artifacts"]["source"]["sha256"]:
        raise Refused("wire_source_identity_refused")
    result = []
    with tarfile.open(archive, "r:gz") as bundle:
        for label, (relative, anchor) in SOURCES.items():
            member = bundle.getmember(f"vscode-{PIN}/{relative}")
            if not member.isfile() or member.size > MAX_BYTES:
                raise Refused("wire_source_member_refused")
            with bundle.extractfile(member) as stream:
                content = stream.read()
            lines = content.decode().splitlines()
            matches = [i for i, line in enumerate(lines) if anchor in line]
            if not matches:
                raise Refused("wire_source_anchor_missing")
            line = matches[0] + 1
            result.append({"id": label, "path": relative, "line": line,
                "sha256": hashlib.sha256(content).hexdigest(), "anchor": anchor,
                "url": f"https://github.com/microsoft/vscode/blob/{PIN}/{relative}#L{line}"})
    return {"schema_version": "ghcp-ahp-wire-sources-v1", "vscode_commit": PIN,
            "codex_sdk_version": manifest["codex_sdk_version"], "citations": result}


def discover_native_binary(prepared, manifest):
    """Inspect installed package metadata/inventory; never execute a launcher.

    The wrapper's optionalDependencies identify bundled platform packages.
    Their verified os/cpu metadata select Linux x64; bin declarations and the
    native layout entrypoints and inventories identify candidates without a vendor-layout
    assumption. Exactly one executable, archive-identical native ELF is required.
    """
    sdk = prepared / "codex-sdk"
    report = {"schema_version": "ghcp-ahp-native-discovery-v1", "stage": "archive_identity",
              "sdk_version": manifest["codex_sdk_version"], "target": {"os": "linux", "cpu": "x64"},
              "packages": [], "package_layouts": [], "attempted_candidates": [],
              "search_complete": False, "selected": None}

    def refuse(code):
        error = Refused(code)
        error.native_binary_discovery = report
        raise error

    def safe_path(name):
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or len(name) > 4096:
            refuse("wire_sdk_path_refused")
        return str(relative)

    def linked(path):
        return any(part.is_symlink() for part in (path, *path.parents))

    def checksum(stream):
        total = hashlib.sha256()
        while part := stream.read(1024 * 1024):
            total.update(part)
        return total.hexdigest()

    archive = prepared / "downloads/codex_sdk.tgz"
    try:
        if not archive.is_file() or linked(archive):
            refuse("wire_sdk_archive_missing_or_unsafe")
        if digest(archive) != manifest["artifacts"]["codex_sdk"]["sha256"]:
            refuse("wire_sdk_archive_drift")
        with tarfile.open(archive, "r:gz") as bundle:
            members = {}
            inventory = bundle.getmembers()
            if len(inventory) > 100_000 or sum(item.size for item in inventory) > MAX_ARCHIVE_EXPANSION_BYTES:
                refuse("archive_expansion_limit")
            for member in inventory:
                name = safe_path(member.name)
                if name in members:
                    refuse("wire_sdk_archive_duplicate_member")
                members[name] = member

            def metadata(name):
                report["stage"] = "package_metadata"
                path, member = sdk / name, members.get(name)
                if (not path.is_file() or linked(path) or member is None or not member.isfile()
                        or not 0 < member.size <= 1024 * 1024 or path.stat().st_size != member.size):
                    refuse("wire_sdk_metadata_missing_or_unsafe")
                content = path.read_bytes()
                with bundle.extractfile(member) as source:
                    if hashlib.sha256(content).hexdigest() != checksum(source):
                        refuse("wire_sdk_metadata_drift")
                try:
                    value = strict_json(content.decode())
                except (UnicodeError, json.JSONDecodeError):
                    refuse("wire_sdk_metadata_invalid")
                if not isinstance(value, dict):
                    refuse("wire_sdk_metadata_invalid")
                return value

            wrapper = metadata("node_modules/@openai/codex/package.json")
            dependencies = wrapper.get("optionalDependencies")
            if (wrapper.get("name") != "@openai/codex" or wrapper.get("version") != manifest["codex_sdk_version"]
                    or not isinstance(dependencies, dict) or not 0 < len(dependencies) <= 64):
                refuse("wire_sdk_wrapper_identity_refused")
            candidates, declared_entrypoints = {}, set()
            for dependency, spec in sorted(dependencies.items()):
                if not re.fullmatch(r"@openai/codex-[a-z0-9-]+", dependency) or not isinstance(spec, str):
                    refuse("wire_sdk_dependency_refused")
                prefix = "node_modules/" + dependency
                name = prefix + "/package.json"
                package = {"dependency": dependency, "metadata_path": name, "status": "not_bundled"}
                report["packages"].append(package)
                if name not in members and not (sdk / name).exists():
                    continue
                package["status"] = "metadata_pending"
                value = metadata(name)
                if not isinstance(value.get("name"), str) or not isinstance(value.get("version"), str):
                    refuse("wire_sdk_metadata_invalid")
                package.update(name=value.get("name"), version=value.get("version"), os=value.get("os"), cpu=value.get("cpu"))
                if spec not in {value.get("version"), f"npm:{value.get('name')}@{value.get('version')}"}:
                    refuse("wire_sdk_dependency_identity_refused")
                if value.get("os") != ["linux"] or value.get("cpu") != ["x64"]:
                    package["status"] = "other_platform"
                    continue
                package["status"] = "compatible"
                report["stage"] = "candidate_inventory"

                def candidate(relative, source):
                    relative = safe_path(relative)
                    if not relative.startswith(prefix + "/"):
                        refuse("wire_sdk_path_refused")
                    if relative not in candidates:
                        candidates[relative] = {"path": relative, "sources": [], "status": "unexamined"}
                        report["attempted_candidates"].append(candidates[relative])
                    candidates[relative]["sources"].append(source)
                    if len(candidates) > 128:
                        refuse("wire_native_inventory_limit")

                declared = value.get("bin", {})
                if declared is not None and not isinstance(declared, (str, dict)):
                    refuse("wire_sdk_bin_metadata_invalid")
                declarations = [declared] if isinstance(declared, str) else list(declared.values()) if isinstance(declared, dict) else []
                for target in declarations:
                    if not isinstance(target, str):
                        refuse("wire_sdk_bin_metadata_invalid")
                    relative = str(PurePosixPath(prefix) / target)
                    candidate(relative, "package_bin")
                    declared_entrypoints.add(relative)
                for name in sorted(members):
                    if name.startswith(prefix + "/") and PurePosixPath(name).name == "codex-package.json":
                        layout = metadata(name)
                        report["stage"] = "native_entrypoint_metadata"
                        if (type(layout.get("layoutVersion")) is not int or layout["layoutVersion"] != 1
                                or layout.get("version") != manifest["codex_sdk_version"]
                                or layout.get("variant") != "codex" or not isinstance(layout.get("entrypoint"), str)
                                or not re.fullmatch(r"x86_64-[a-z0-9_]+-linux-(musl|gnu)", str(layout.get("target")))):
                            refuse("wire_sdk_native_layout_refused")
                        relative = str(PurePosixPath(name).parent / layout["entrypoint"])
                        candidate(relative, "native_package_entrypoint")
                        declared_entrypoints.add(relative)
                        report["package_layouts"].append({"path": name, "version": layout["version"],
                            "target": layout["target"], "entrypoint": layout["entrypoint"]})
                # Installed paths are inspected without following directory links.
                # Archive inventory also records paths whose extraction is missing.
                visited = 0
                for parent, directories, files in os.walk(sdk / prefix, followlinks=False):
                    directories.sort()
                    for filename in sorted(files):
                        visited += 1
                        if visited > 8192:
                            refuse("wire_native_inventory_limit")
                        if filename == "codex":
                            candidate((Path(parent) / filename).relative_to(sdk).as_posix(), "installed_inventory")
                for name in sorted(members):
                    if name.startswith(prefix + "/") and PurePosixPath(name).name == "codex":
                        candidate(name, "archive_inventory")

            report["stage"] = "candidate_validation"
            valid, fatal = [], False
            for name, item in sorted(candidates.items()):
                binary, member = sdk / name, members.get(name)
                if linked(binary):
                    item["status"], fatal = "unsafe_link", True
                elif not binary.is_file():
                    item["status"] = "missing"
                elif member is None or not member.isfile():
                    item["status"], fatal = "not_in_verified_archive", True
                # Compressed download size is not an unpacked executable bound:
                # the pinned 0.163.0 binary is 296,865,480 bytes. Its exact size
                # and hash come from the verified archive; retain the existing
                # 2 GiB whole-archive expansion limit above, unchanged.
                elif not _native_size_matches(member.size, binary.stat().st_size):
                    item["status"], fatal = "size_mismatch", True
                elif not member.mode & 0o111 or not os.access(binary, os.X_OK):
                    item["status"] = "not_executable"
                else:
                    with binary.open("rb") as stream:
                        magic = stream.read(4)
                    if magic != b"\x7fELF":
                        item["status"] = "not_native_elf"
                        continue
                    with bundle.extractfile(member) as source:
                        expected = checksum(source)
                    if digest(binary) != expected:
                        item["status"], fatal = "hash_mismatch", True
                    else:
                        item.update(status="verified_native", sha256=expected, size_bytes=member.size)
                        valid.append((binary, expected, name))
            report["search_complete"] = True
            if fatal:
                refuse("wire_native_binary_drift")
            if not valid:
                refuse("wire_native_binary_not_found")
            if len(valid) != 1:
                refuse("wire_native_binary_ambiguous")
            binary, expected, selected = valid[0]
            if declared_entrypoints and selected not in declared_entrypoints:
                refuse("wire_native_entrypoint_missing")
            report.update(stage="selected", selected=selected)
            return binary, expected, report
    except Refused as error:
        error.native_binary_discovery = report
        raise
    except (OSError, tarfile.TarError):
        refuse("wire_sdk_discovery_io_refused")


def _native_size_matches(archive_size, installed_size):
    return 0 < archive_size <= MAX_ARCHIVE_EXPANSION_BYTES and installed_size == archive_size


def agent_fork_contract(prepared, state, manifest):
    """Bind exactly one extensionless Node request to its pinned on-disk file.

    The supervisor's registry user-data-dir is NOT the server's data directory.
    The pinned CLI forwards only server-data-dir; server.main.ts appends /data.
    The single logs directory is resolved at fork time, not guessed from a clock.
    """
    archive_path = prepared / "downloads/server.tgz"
    if digest(archive_path) != manifest["artifacts"]["server"]["sha256"]:
        raise Refused("wire_server_archive_drift")
    server = prepared / "cli-data/servers" / ("Stable-" + PIN) / "server"
    files = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        for label, relative in (("node", "node"), ("module", "out/bootstrap-fork.js"), ("parent", "out/server-main.js")):
            path = server / relative
            if (not path.is_file() or any(parent.is_symlink() for parent in (path, *path.parents))):
                raise Refused("wire_agent_fork_file_refused")
            member = archive.getmember("vscode-server-linux-x64/" + relative)
            if not member.isfile() or not 0 < member.size <= MAX_ARCHIVE_EXPANSION_BYTES or member.size != path.stat().st_size:
                raise Refused("wire_agent_fork_file_refused")
            expected = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for part in iter(lambda: stream.read(1024 * 1024), b""):
                    expected.update(part)
            if digest(path) != expected.hexdigest():
                raise Refused("wire_agent_fork_file_drift")
            files[label] = {"path": str(path), "sha256": expected.hexdigest()}
    return {"schema_version": "ghcp-ahp-agent-fork-v1", "vscode_commit": PIN,
            "files": files, "module_request": str(server / "out/bootstrap-fork"),
            "state_root": str(state), "data_path": str(state / "server-data/data"),
            "logs_root": str(state / "server-data/data/logs"), "sdk_root": str(prepared / "codex-sdk"),
            "entrypoint": "vs/platform/agentHost/node/agentHostMain", "exec_argv": [], "telemetry": "off"}


def install(prepared, state, environment, *, model_free, credential=""):
    """Add a passive tee to the isolated host, never to the user's environment.

    Native binary and source stay byte-identical to their original archives.
    The seed travels only in the isolated process environment, is deleted by
    the preload, and is never placed in an argv, config file or artifact.
    """
    if type(model_free) is not bool:
        raise Refused("wire_mode_refused")
    manifest = load_manifest()
    binary, expected, discovery = discover_native_binary(prepared, manifest)
    directory = state / "wire"
    if (not directory.is_absolute() or directory.exists()
            or any(parent.is_symlink() for parent in (directory, *directory.parents))):
        raise Refused("wire_directory_refused")
    directory.mkdir(mode=0o700)
    sources = source_evidence(prepared / "downloads/source.tgz", manifest)
    save_json(directory / "sources.json", sources)
    fork_contract = agent_fork_contract(prepared, state, manifest)
    fork_encoded = json.dumps(fork_contract, sort_keys=True, separators=(",", ":"))
    bootstrap = {"schema_version": "ghcp-ahp-wire-bootstrap-v1", "model_free": model_free,
                 "observer_sha256": digest(PRELOAD), "native_binary_sha256": expected,
                 "vscode_commit": PIN, "sdk_version": manifest["codex_sdk_version"],
                 "native_binary_discovery": discovery, "agent_host_fork": fork_contract}
    save_json(directory / "bootstrap.json", bootstrap)
    if "NODE_OPTIONS" in environment:
        raise Refused("wire_inherited_node_options_refused")
    return {**environment, "NODE_OPTIONS": "--require=" + json.dumps(str(PRELOAD)),
            "GHCP_AHP_WIRE_DIR": str(directory), "GHCP_AHP_WIRE_MODE": "model-free" if model_free else "connection",
            "GHCP_AHP_WIRE_NATIVE": str(binary.resolve()), "GHCP_AHP_WIRE_NATIVE_SHA256": expected,
            "GHCP_AHP_WIRE_FORK_CONTRACT": fork_encoded,
            "GHCP_AHP_WIRE_FORK_SHA256": hashlib.sha256(fork_encoded.encode()).hexdigest(),
            "GHCP_AHP_WIRE_OBSERVER_SHA256": bootstrap["observer_sha256"],
            "GHCP_AHP_WIRE_SEEDS": json.dumps([credential] if credential else [])}


def _settings(value, source, scope, thread_id=NOT_REPORTED):
    result = dict.fromkeys(FIELDS, NOT_REPORTED)
    for key, names in {"model": ("model",), "reasoning_effort": ("effort", "reasoningEffort"),
                       "approval": ("approvalPolicy",)}.items():
        for name in names:
            if type(value.get(name)) is str:
                result[key] = value[name]
                break
    sandbox = value.get("sandboxPolicy", value.get("sandbox"))
    if isinstance(sandbox, dict):
        result["sandbox"] = sandbox.get("type", NOT_REPORTED)
        if type(sandbox.get("networkAccess")) is bool:
            result["network"] = sandbox["networkAccess"]
    # No native effective-thread web_search/context field is invented from the
    # thread/start request or the unrelated disk-level config/read response.
    return {"values": result, "source": source, "scope": scope, "thread_id": thread_id}


def analyze(records, *, synthetic):
    """Classify provenance; even an all-matching fixture cannot open admission."""
    result = {"schema_version": "ghcp-ahp-wire-capture-v1", "synthetic": synthetic,
        "admission_allowed": False, "connection_verified": False, "gate_ready": False,
        "requested": {"model": DESIRED_MODEL["id"], "reasoning_effort": "max", "context_window": 1_000_000,
                      "sandbox": "read-only", "approval": "untrusted", "network": False, "web_search": "disabled"},
        "native_requests": [], "native_applied_snapshots": [], "native_base_configuration": [],
        "native_context_reports": [], "capi_requests": [], "capi_response_reports": [],
        "capture_errors": [], "records": records,
        "limitations": ["diagnostic_only_not_admission", "response_report_not_independent_model_attestation",
                        "capi_field_availability_requires_real_response", "native_settings_are_not_served_settings",
                        "sdk_context_window_is_not_provider_capacity_proof"]}
    pending, capi, headers, ended = {}, set(), {}, set()
    for record in records:
        if record.get("synthetic") is True:
            result["synthetic"] = True
        stream = (record.get("process", "fixture"), record.get("stream"))
        kind, value = record.get("kind"), record.get("value")
        if kind in {"blocked", "wire_parse_error"}:
            result["capture_errors"].append(record.get("reason", "wire_boundary_refused"))
        if kind == "ipc_request" and isinstance(value, dict):
            if "id" in value:
                key = (*stream, type(value["id"]).__name__, str(value["id"]))
                if key in pending:
                    raise Refused("wire_duplicate_rpc_id")
                pending[key] = value
            if value.get("method") in {"thread/start", "thread/resume", "thread/fork", "turn/start"}:
                result["native_requests"].append({"source": "native_client_request_only", "request": value})
        if kind == "ipc_response" and isinstance(value, dict):
            if "id" in value:
                request = pending.pop((*stream, type(value["id"]).__name__, str(value["id"])), None)
                if request is None:
                    result["capture_errors"].append("wire_uncorrelated_native_reply")
                    continue
                response = value.get("result")
                if not isinstance(response, dict):
                    continue
                method = request.get("method")
                if method in {"thread/start", "thread/resume", "thread/fork"}:
                    result["native_applied_snapshots"].append(_settings(response,
                        f"native.{method}.result", "thread_start_not_final_turn",
                        (response.get("thread") or {}).get("id", NOT_REPORTED)))
                if method == "config/read":
                    result["native_base_configuration"].append({"scope": "disk_layers_not_thread_override", "value": response})
            params = value.get("params") or {}
            if value.get("method") == "thread/settings/updated" and isinstance(params.get("threadSettings"), dict):
                result["native_applied_snapshots"].append(_settings(params["threadSettings"],
                    "native.thread/settings/updated", "thread_event_not_per_turn_attestation", params.get("threadId", NOT_REPORTED)))
            if value.get("method") == "thread/tokenUsage/updated":
                context = (params.get("tokenUsage") or {}).get("modelContextWindow")
                result["native_context_reports"].append({"source": "native.SDK.tokenUsage.modelContextWindow",
                    "thread_id": params.get("threadId", NOT_REPORTED), "turn_id": params.get("turnId", NOT_REPORTED),
                    "context_window": context if type(context) is int and context > 0 else NOT_REPORTED})
        if kind == "capi_request":
            if stream in capi:
                raise Refused("wire_duplicate_http_request")
            capi.add(stream)
            result["capi_requests"].append({"source": "capi_request_only", "value": value, "stream": list(stream)})
        if kind == "capi_headers":
            if stream not in capi or stream in headers:
                raise Refused("wire_uncorrelated_capi_headers")
            headers[stream] = record.get("status")
            if type(headers[stream]) is not int or headers[stream] != 200:
                result["capture_errors"].append("wire_capi_non_success_status")
        if kind == "capi_end":
            ended.add(stream)
        if kind in {"capi_event", "capi_body"}:
            if stream not in headers:
                raise Refused("wire_uncorrelated_capi_response")
            response = value.get("response") if kind == "capi_event" and isinstance(value, dict) else value
            if kind == "capi_event" and record.get("event") not in {"response.created", "response.completed", "response.incomplete", "response.failed"}:
                continue
            if not isinstance(response, dict):
                continue
            reasoning = response.get("reasoning")
            effort = reasoning.get("effort") if isinstance(reasoning, dict) else None
            well_formed = (kind == "capi_body" or value.get("type") == record.get("event"))
            if not well_formed:
                result["capture_errors"].append("wire_capi_event_type_mismatch")
            result["capi_response_reports"].append({"stream": list(stream),
                "source": "capi_upstream_response_body_not_request_echo",
                "response_id": response.get("id", NOT_REPORTED), "event": record.get("event", "http_json"),
                "http_status": headers[stream],
                "well_formed": well_formed,
                "reported_model": response.get("model") if type(response.get("model")) is str else NOT_REPORTED,
                "reported_reasoning_effort": effort if type(effort) is str else NOT_REPORTED,
                "usage": response.get("usage", NOT_REPORTED), "independent_attestation": False})
    if any(stream not in ended for stream in capi):
        result["capture_errors"].append("wire_capi_stream_incomplete")
    reports = result["capi_response_reports"]
    result["field_verdicts"] = {}
    for key, reported, expected in (("served_model", "reported_model", "gpt-5.6-sol"),
                                    ("reasoning_effort", "reported_reasoning_effort", "max")):
        values = {row[reported] for row in reports if row[reported] != NOT_REPORTED}
        valid = not result["capture_errors"] and all(row["well_formed"] for row in reports)
        result["field_verdicts"][key] = {"response_reported": sorted(values),
            "classification": ("response_reported_candidate" if valid else "invalid_or_incomplete_response") if values else "request_only" if result["capi_requests"] else "not_reported",
            "matches_requested": values == {expected} if values and valid else None,
            "conflicting": len(values) > 1, "proven_for_live_gate": False}
    return result


def export(state, destination, *, credential=""):
    """Only export files owned by this invocation, after the host has stopped."""
    directory = state / "wire"
    if not directory.exists():
        report = analyze([], synthetic=False)
        report["capture_status"] = "observer_not_started"
    else:
        if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
            raise Refused("wire_export_path_refused")
        files = sorted(directory.glob("wire-*.jsonl"))
        if len(files) > 16:
            raise Refused("wire_process_limit")
        records, total = [], 0
        for file in files:
            if file.is_symlink() or not re.fullmatch(r"wire-[0-9]+\.jsonl", file.name):
                raise Refused("wire_export_file_refused")
            total += file.stat().st_size
            if total > MAX_BYTES:
                raise Refused("wire_export_size_limit")
            for sequence, line in enumerate(file.read_text().splitlines(), 1):
                row = strict_json(line)
                if not isinstance(row, dict) or type(row.get("sequence")) is not int or row["sequence"] != sequence:
                    raise Refused("wire_sequence_refused")
                records.append({**row, "process": file.name})
        report = analyze(records, synthetic=False)
        installed = [row for row in records if row.get("kind") == "observer_installed"
                     and row.get("entrypoint") == "vs/platform/agentHost/node/agentHostMain"]
        report["capture_status"] = "captured" if installed else "observer_not_started"
        for name in ("bootstrap", "sources"):
            file = directory / (name + ".json")
            if file.is_symlink() or file.stat().st_size > 512 * 1024:
                raise Refused("wire_metadata_refused")
            report[name] = strict_json(file.read_text())
        expected = report["bootstrap"]["observer_sha256"]
        if expected != digest(PRELOAD) or report["bootstrap"].get("vscode_commit") != PIN:
            raise Refused("wire_bootstrap_identity_refused")
        if any(row.get("kind") == "observer_installed" and row.get("observer_sha256") != expected for row in records):
            raise Refused("wire_observer_identity_refused")
    mask = DiagnosticRedactor(credential)
    # Learn later identifiers before cleaning earlier raw-text echoes.
    mask.clean(report)
    report = mask.clean(report)
    output = destination / "wire-capture.json"
    save_json(output, report)
    return {"path": output.name, "sha256": digest(output), "capture_status": report["capture_status"],
            "synthetic": report["synthetic"], "admission_allowed": False}
