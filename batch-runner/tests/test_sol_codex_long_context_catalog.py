"""Owner decision 2026-10-30 (item 3): the Sol pilot's 1,000,000 window reaches Codex.

Codex 0.147.0's bundled models.json gives gpt-5.6-sol 272,000 tokens and clamps
``model_context_window`` to it (258,400 usable at 95%). The wire observer that
already rewrites the pilot's Codex overrides now adds a held catalog: the
bundled bytes except Sol's window fields. Model-free; no provider is called.
"""
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt56_pilot_wire_receipt as wire
import gpt56_sol_codex_pilot_preflight as pilot
from core.codex_runtime_config import _toml_literal
from .test_gpt56_pilot_provider_observation import UPSTREAM, _upstream
from .test_gpt56_pilot_wire_receipt import REQUESTED

#: SHA256 of codex-rs/models-manager/models.json at rust-v0.147.0, the file the
#: pinned CLI compiles in. The held catalog differs from it in three values only.
BUNDLED_MODELS_JSON_SHA256 = "384ff2e0ca67f65d2866e422e2ec7dfa5ed9e3fec7a84fe14005247a7087a302"
KEY = "model_providers.gdpval-foundry.base_url="
CATALOG = pilot.ROOT / pilot.CODEX_LONG_CONTEXT_CATALOG
SOL_FIELDS = {"context_window", "max_context_window", "effective_context_window_percent"}


def _replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def _bundled_bytes():
    text = CATALOG.read_text(encoding="utf-8")
    text = _replace_once(text, '      "context_window": 1050000,\n      "max_context_window": 1050000,\n',
                         '      "context_window": 272000,\n      "max_context_window": 272000,\n')
    text = _replace_once(text, '      "supports_reasoning_summaries": true,\n'
                               '      "effective_context_window_percent": 100\n    },\n',
                         '      "supports_reasoning_summaries": true\n    },\n')
    return text.encode("utf-8")


def _configure(monkeypatch, *extra):
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    overrides = (KEY + _toml_literal(UPSTREAM), *extra)
    with _upstream(monkeypatch, []):
        try:
            return observer, observer.configure_provider_observer(provider, overrides, timeout=60)
        finally:
            observer.close_provider_observer()


def test_held_catalog_is_the_bundled_catalog_except_sol_window():
    data = CATALOG.read_bytes()
    assert hashlib.sha256(data).hexdigest() == pilot.SOURCE_PROFILE_AUXILIARY[pilot.CODEX_LONG_CONTEXT_CATALOG]
    assert hashlib.sha256(_bundled_bytes()).hexdigest() == BUNDLED_MODELS_JSON_SHA256

    held = json.loads(data)["models"]
    bundled = json.loads(_bundled_bytes())["models"]
    assert [model["slug"] for model in held] == [model["slug"] for model in bundled]
    for mine, theirs in zip(held, bundled):
        if mine["slug"] != "gpt-5.6-sol":
            assert mine == theirs
            continue
        assert {k: v for k, v in mine.items() if k not in SOL_FIELDS} == {
            k: v for k, v in theirs.items() if k not in SOL_FIELDS}
        assert theirs["context_window"] == theirs["max_context_window"] == pilot.CODEX_BUNDLED_SOL_CONTEXT_WINDOW
        assert "effective_context_window_percent" not in theirs  # Codex default: 95%
        assert mine["context_window"] == mine["max_context_window"] == 1_050_000
        assert mine["effective_context_window_percent"] == 100


def test_catalog_name_matches_the_pinned_codex_release():
    release = re.fullmatch(r"codex-([0-9.]+)-models-gpt56-sol-1m\.json", CATALOG.name).group(1)
    requirements = (pilot.ROOT / "batch-runner/requirements.txt").read_text(encoding="utf-8")
    assert f"openai-codex=={release}\n" in requirements
    assert f"openai-codex-cli-bin=={release}\n" in requirements


def test_pinned_codex_binary_compiles_in_the_bundled_catalog():
    cli = pytest.importorskip("codex_cli_bin")
    binary = Path(cli.bundled_codex_path())
    assert _bundled_bytes() in binary.read_bytes()


def test_window_above_bundled_maximum_adds_the_held_catalog_once(monkeypatch):
    rest = ("model_context_window=1000000", 'model_reasoning_effort="max"')
    observer, changed = _configure(monkeypatch, *rest)
    assert changed[0] != KEY + _toml_literal(UPSTREAM) and changed[0].startswith(KEY)
    assert changed[1:] == (*rest, "model_catalog_json=" + _toml_literal(str(CATALOG)))
    assert observer.provider_capture is not None


@pytest.mark.parametrize("extra", [(), ("model_context_window=272000",), ("model_context_window=258400",)])
def test_window_within_bundled_maximum_changes_nothing_else(monkeypatch, extra):
    _, changed = _configure(monkeypatch, *extra)
    assert changed[1:] == extra


@pytest.mark.parametrize("extra", [
    ("model_context_window=1000000", "model_context_window=1000000"),
    ("model_context_window=1000000", 'model_catalog_json="/elsewhere/models.json"'),
    ('model_catalog_json="/elsewhere/models.json"',),
    ("model_context_window=01000000",),
    ('model_context_window="1000000"',),
    ("model_context_window=-1",),
])
def test_duplicate_foreign_or_malformed_window_settings_refuse(monkeypatch, extra):
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    with pytest.raises(wire.PilotWireReceiptRefused):
        observer.configure_provider_observer(provider, (KEY + _toml_literal(UPSTREAM), *extra), timeout=60)
    assert observer.provider_capture is None


def test_changed_catalog_bytes_refuse_before_any_listener(monkeypatch):
    held = dict(pilot.SOURCE_PROFILE_AUXILIARY)
    held[pilot.CODEX_LONG_CONTEXT_CATALOG] = "0" * 64
    monkeypatch.setattr(pilot, "SOURCE_PROFILE_AUXILIARY", held)
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    with pytest.raises(wire.PilotWireReceiptRefused):
        observer.configure_provider_observer(
            provider, (KEY + _toml_literal(UPSTREAM), "model_context_window=1000000"), timeout=60)
    assert observer.provider_capture is None
