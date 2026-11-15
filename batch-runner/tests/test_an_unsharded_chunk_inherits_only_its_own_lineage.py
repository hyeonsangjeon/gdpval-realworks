"""A resume chunk of an unsharded grade inherits its approval only from its own partial.

exp037's chunk 1 (run 43310879444) waited 47 hours at the grading gate because
"Resolve inherited paid approval" only ever looked for
``_shards/<stem>/shard-000-of-001.json``. step8 writes that path only when
shard_count > 1; an unsharded partial is the canonical
``data/grades/<stem>.json`` (step8_grade.resolve_grade_output_path), so every
approved Sol chunk after the first was sent back to the gate.

The canonical path is also where a finished grade lives, so finding a file
there proves nothing by itself. The step now also requires the stem to carry
this config's hash and the file's last commit to be the grading job's own
"partial chunk N-1" commit for this request. These tests run the workflow's
real step script with bash against a stub ``gh`` that serves a small repository
tree, and check what it decides. Model-free and offline.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
CONFIGS = REPO_ROOT / "batch-runner/grading_configs"
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
BOT = "41898282+github-actions[bot]@users.noreply.github.com"
EXPERIMENT = "exp039_sol_next98"
CONFIG = "exp039_v2_sol_max.yaml"
REVISION = "a" * 40
DISPATCHED_SHA = "c" * 40

STUB_GH = r'''#!/usr/bin/env python3
import base64, json, os, sys, urllib.parse
fixture = json.load(open(os.environ["GH_STUB_FIXTURE"]))
args = sys.argv[1:]
if fixture.get("outage"):
    sys.stderr.write("HTTP 502: Bad Gateway (stub)\n"); sys.exit(1)
if len(args) < 4 or args[0] != "api" or args[2] != "--jq":
    sys.stderr.write("stub: unexpected call %r\n" % (args,)); sys.exit(2)
endpoint, jq = args[1], args[3]
prefix = "repos/%s/" % os.environ["GITHUB_REPOSITORY"]
assert endpoint.startswith(prefix), endpoint
path, _, query = endpoint[len(prefix):].partition("?")
q = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
files = fixture["files"]          # path -> [author email, subject of its last commit]
def listing(directory):
    names = {}
    for p in files:
        if p.startswith(directory + "/"):
            head = p[len(directory) + 1:].split("/", 1)
            names[head[0]] = "dir" if len(head) == 2 else "file"
    return names
if path.startswith("contents/batch-runner/grading_configs/"):
    assert q.get("ref") == os.environ["GITHUB_SHA"], q
    assert jq == '.content // ""', jq
    config = os.path.join(fixture["configs"], path.rsplit("/", 1)[1])
    if not os.path.isfile(config):
        sys.exit(1)
    print(base64.b64encode(open(config, "rb").read()).decode())
elif path.startswith("contents/"):
    assert q.get("ref") == "main", q
    names = listing(path[len("contents/"):])
    if not names:
        sys.stderr.write("HTTP 404: Not Found (stub)\n"); sys.exit(1)
    if jq == '.[] | select(.type == "dir") | .name':
        out = [n for n, t in sorted(names.items()) if t == "dir"]
    elif jq == '.[] | select(.type == "file") | .name | select(endswith(".json")) | rtrimstr(".json")':
        out = [n[:-5] for n, t in sorted(names.items()) if t == "file" and n.endswith(".json")]
    else:
        sys.stderr.write("stub: unknown jq %r\n" % jq); sys.exit(2)
    print("\n".join(out))
elif path == "commits":
    assert q.get("sha") == "main" and q.get("per_page") == "1", q
    last = files.get(q["path"])
    if jq == '.[0] // empty | [.commit.author.email, (.commit.message | split("\\n")[0])] | @tsv':
        if last:
            print("%s\t%s" % (last[0], last[1]))
    elif jq == '.[0].commit.author.email // ""':
        print(last[0] if last else "")
    else:
        sys.stderr.write("stub: unknown jq %r\n" % jq); sys.exit(2)
else:
    sys.stderr.write("stub: unexpected endpoint %r\n" % endpoint); sys.exit(2)
'''


def _step_script() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["validate-request"]["steps"]
    (step,) = [s for s in steps if s.get("name") == "Resolve inherited paid approval"]
    assert step["id"] == "inherit" and step["shell"] == "bash"
    assert step["env"]["GRADE_BOT_EMAIL"] == BOT
    return step["run"]


def _cfg16(config: str = CONFIG) -> str:
    return hashlib.sha256((CONFIGS / config).read_bytes()).hexdigest()[:16]


def _stem(experiment: str = EXPERIMENT, config: str = CONFIG, revision: str = REVISION,
          cfg16: str | None = None) -> str:
    name = config.removesuffix(".yaml")
    return (f"{experiment}__judge_gpt-5_6-sol__{name}__cfg_{cfg16 or _cfg16(config)}"
            f"__rubric_{'1' * 40}__inference_{revision}__src_{'2' * 16}__v2.2")


def _partial(chunk: int, experiment: str = EXPERIMENT, config: str = CONFIG, shard: str = "") -> str:
    return f"chore(grades): partial chunk {chunk} for {experiment} via {config}{shard}"


def _decide(tmp_path: Path, files: dict[str, list[str]], *, outage: bool = False, **env: str) -> tuple[str, str]:
    if shutil.which("bash") is None or shutil.which("sha256sum") is None or shutil.which("base64") is None:
        pytest.fail("bash, sha256sum and base64 are on every hosted runner; this host lacks one")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n" + STUB_GH.split("\n", 1)[1], encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"files": files, "configs": str(CONFIGS), "outage": outage}), encoding="utf-8")
    script = tmp_path / "inherit.sh"
    script.write_text(_step_script(), encoding="utf-8")
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir(exist_ok=True)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    values = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "GH_STUB_FIXTURE": str(fixture), "GH_TOKEN": "stub", "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_SHA": DISPATCHED_SHA, "GITHUB_ACTOR": "github-actions[bot]",
        "GITHUB_TRIGGERING_ACTOR": "github-actions[bot]", "GITHUB_OUTPUT": str(output),
        "RUNNER_TEMP": str(runner_temp), "GRADE_BOT_EMAIL": BOT,
        "GRADE_EXPERIMENT_YAML": EXPERIMENT, "GRADE_CONFIG": CONFIG, "GRADE_INFERENCE_REVISION": REVISION,
        "GRADE_DRY_RUN": "false", "GRADE_PAID_APPROVAL": "true", "GRADE_RESUME": "true",
        "GRADE_RESUME_CHUNK": "1", "GRADE_TASKS_LIMIT": "0", "GRADE_TASKS": "",
        "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
    }
    values.update(env)
    values.setdefault("GRADE_EXPERIMENT_SLUG", values["GRADE_EXPERIMENT_YAML"].replace("/", "__"))
    done = subprocess.run(["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
                          env=values, capture_output=True, text=True, timeout=60)
    # The step must never fail the job: every doubt is a denial, not an error.
    assert done.returncode == 0, done.stdout + done.stderr
    decided = [line for line in output.read_text(encoding="utf-8").splitlines() if line.startswith("approval_inherited=")]
    assert len(decided) == 1, (decided, done.stdout)
    reason = [line for line in done.stdout.splitlines() if line.startswith("[inherit] ")][0]
    return decided[0].split("=", 1)[1], reason


def _grade(stem: str | None = None, root: str = "data/grades") -> str:
    return f"{root}/{stem or _stem()}.json"


def test_chunk_one_inherits_through_the_bots_partial_chunk_zero(tmp_path):
    files = {_grade(): [BOT, _partial(0)], "data/grades/_combined_usd/x/run-1-1.combined_usd.jsonl": [BOT, "j"]}
    decided, reason = _decide(tmp_path, files)
    assert decided == "true", reason
    assert reason == f"[inherit] continuing approved lineage via {_grade()}"


def test_chunk_two_needs_the_partial_of_chunk_one(tmp_path):
    assert _decide(tmp_path, {_grade(): [BOT, _partial(1)]}, GRADE_RESUME_CHUNK="2")[0] == "true"
    # A partial last written by chunk 0 is stale for chunk 2.
    decided, reason = _decide(tmp_path, {_grade(): [BOT, _partial(0)]}, GRADE_RESUME_CHUNK="2")
    assert decided == "false" and "partial chunk 1 for" in reason


@pytest.mark.parametrize("last_commit", [
    ["someone@example.com", _partial(0)],                              # a person wrote it
    [BOT, f"chore(grades): grade {EXPERIMENT} via {CONFIG}"],          # it is a finished grade
    [BOT, _partial(0, experiment="exp040_sol_last97", config="exp040_v2_sol_max.yaml")],
], ids=["human", "finished-grade", "another-lineage"])
def test_a_canonical_file_that_is_not_this_requests_partial_is_refused(tmp_path, last_commit):
    decided, reason = _decide(tmp_path, {_grade(): last_commit})
    assert decided == "false", reason


def test_a_stem_with_another_config_hash_or_revision_is_refused(tmp_path):
    for stem in (_stem(cfg16="0" * 16), _stem(revision="b" * 40),
                 _stem(experiment="exp040_sol_last97", config="exp040_v2_sol_max.yaml")):
        decided, reason = _decide(tmp_path, {_grade(stem): [BOT, _partial(0)]})
        assert decided == "false", reason


def test_nothing_committed_means_the_gate(tmp_path):
    decided, reason = _decide(tmp_path, {"data/grades/unrelated.json": [BOT, "x"]})
    assert decided == "false" and "whose last commit is the bot's" in reason


@pytest.mark.parametrize("env, why", [
    ({"GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0"}, "chunk 0 is the click"),
    ({"GRADE_RESUME_CHUNK": "0"}, "chunk 0 is the click"),
    ({"GITHUB_TRIGGERING_ACTOR": "hyeonsangjeon"}, "not the auto-retrigger"),
    ({"GITHUB_ACTOR": "hyeonsangjeon"}, "not the auto-retrigger"),
    ({"GRADE_DRY_RUN": "true", "GRADE_PAID_APPROVAL": "false"}, "not a paid request"),
    ({"GRADE_TASKS_LIMIT": "3"}, "narrowed scope"),
    ({"GRADE_TASKS": "0fad6023-767b-42c1-a1b3-027cd4f583cb"}, "narrowed scope"),
], ids=["chunk0-no-resume", "chunk0", "human-trigger", "human-actor", "dry-run", "limit", "tasks"])
def test_requests_that_cannot_inherit_are_sent_to_the_gate(tmp_path, env, why):
    decided, reason = _decide(tmp_path, {_grade(): [BOT, _partial(0)]}, **env)
    assert decided == "false" and why in reason


def test_a_repeat_reads_its_own_root(tmp_path):
    repeat = _grade(root="data/grades/_repeats/run-002")
    assert _decide(tmp_path, {repeat: [BOT, _partial(0)]}, GRADE_RUN_ORDINAL="2")[0] == "true"
    # Run 1's partial is not run 2's receipt.
    assert _decide(tmp_path, {_grade(): [BOT, _partial(0)]}, GRADE_RUN_ORDINAL="2")[0] == "false"


def test_a_sharded_chunk_still_inherits_through_its_shard_file(tmp_path):
    shard = f"data/grades/_shards/{_stem()}/shard-006-of-009.json"
    env = {"GRADE_SHARD_COUNT": "9", "GRADE_SHARD_INDEX": "6"}
    assert _decide(tmp_path, {shard: [BOT, _partial(0, shard=" [shard 6 of 9]")]}, **env)[0] == "true"
    assert _decide(tmp_path, {shard: [BOT, _partial(0)]}, **env)[0] == "false"
    # The unsharded file does not stand in for a shard's.
    assert _decide(tmp_path, {_grade(): [BOT, _partial(0)]}, **env)[0] == "false"


def test_an_api_outage_denies_instead_of_failing_the_job(tmp_path):
    decided, reason = _decide(tmp_path, {_grade(): [BOT, _partial(0)]}, outage=True)
    assert decided == "false", reason


def test_the_receipt_subject_is_the_one_the_commit_step_writes():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'MSG="chore(grades): partial chunk $GRADE_RESUME_CHUNK for $GRADE_EXPERIMENT_YAML via $GRADE_CONFIG"' in text
    assert 'MSG="$MSG [shard $GRADE_SHARD_INDEX of $GRADE_SHARD_COUNT]"' in text
    assert ('WANT_SUBJECT="chore(grades): partial chunk $((10#$GRADE_RESUME_CHUNK - 1)) for '
            '${GRADE_EXPERIMENT_YAML} via ${GRADE_CONFIG}"') in _step_script()
