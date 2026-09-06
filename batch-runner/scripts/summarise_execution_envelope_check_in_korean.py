#!/usr/bin/env python3
"""Turn the free run-place check's JSON into a short Korean summary.

The check itself prints English, and its JSON is written for a program. The
owner of this comparison reads Korean and is learning the system, so the run
that produces the report also produces this: the same findings, in plain words,
with the English name kept beside every translated one so nothing here is a
name that exists only in this file.

This refuses rather than guesses. A file that is not there, is not JSON, or is
JSON without the keys this reads is reported as a failure and exits non-zero —
never as an empty summary, which on a build page is indistinguishable from a
summary saying everything was fine. That is the whole reason this is a program
with tests rather than a few lines of shell inside a workflow.

Usage:

    cd batch-runner
    python scripts/summarise_execution_envelope_check_in_korean.py report.json
    python scripts/summarise_execution_envelope_check_in_korean.py report.json \
        --commit "$GITHUB_SHA" --out summary.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

#: Plain-Korean names for the run places. The English name is printed beside
#: every one of these, and a place missing from here is printed under its
#: English name rather than dropped — a run place nobody translated is still a
#: run place the reader is entitled to see.
RUN_PLACE_NAMES = {
    "host_python_process": "내 컴퓨터에서 그냥 실행",
    "docker_container": "도커 상자 안에서 실행",
    "azure_code_interpreter": "Azure 클라우드에서 실행",
    "agentic_sandbox_v2": "에이전트 샌드박스 V2",
    "codex_built_in_agent": "Codex 내장 에이전트",
    "codex_command_line_tool_foundry": "Codex 명령줄 도구 (Foundry)",
    "copilot_command_line_tool_foundry": "Copilot 명령줄 도구 (Foundry)",
    "copilot_command_line_tool_github_served": "Copilot 명령줄 도구 (GitHub 제공)",
}

#: Plain-Korean readings of the five states a run place can be graded.
STATE_NAMES = {
    "can_run_real_experiment": "지금 실제로 돌릴 수 있음",
    "evidence_insufficient": "확인하지 않음 — 근거가 없어서 된다 안 된다 말할 수 없음",
    "blocked_requirement_unmet": "실행 준비 미완료 — 필요한 것이 빠져 있어 시작하면 안 됨",
    "structure_check_only": "모양만 볼 수 있음 — 모델을 부르지 않음",
    "not_implemented_in_this_repository": "이 저장소에 이 방식으로 돌리는 코드가 없음",
}

#: Plain-Korean readings of how thoroughly one written fingerprint was checked.
FINGERPRINT_STATE_NAMES = {
    "read the file": "파일을 실제로 읽어서 대조함",
    "folder name only": "폴더 이름만 봄 — 파일 내용은 대조하지 못함",
    "not checked": "확인하지 않음",
}


class CannotSummarise(Exception):
    """The report could not be read, so no summary may be printed."""


def _load(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CannotSummarise(f"보고서 파일을 열 수 없습니다: {path} ({error})")
    if not raw.strip():
        raise CannotSummarise(f"보고서 파일이 비어 있습니다: {path}")
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CannotSummarise(
            f"보고서가 올바른 JSON이 아닙니다: {path} ({error})"
        )
    if not isinstance(loaded, dict):
        raise CannotSummarise(
            f"보고서의 맨 바깥이 딕셔너리가 아닙니다: {type(loaded).__name__}"
        )
    return loaded


def _need(report: dict, key: str, kind: type) -> Any:
    """Read one key, and refuse if it is absent or the wrong shape.

    A missing key is not an empty value. Treating it as one would let a report
    that lost half its contents render as a clean summary.
    """
    if key not in report:
        raise CannotSummarise(f"보고서에 '{key}' 항목이 없습니다")
    value = report[key]
    if not isinstance(value, kind):
        raise CannotSummarise(
            f"보고서의 '{key}' 항목이 {kind.__name__}이 아니라 "
            f"{type(value).__name__}입니다"
        )
    return value


def _run_place(name: str) -> str:
    korean = RUN_PLACE_NAMES.get(name)
    return f"{korean} (`{name}`)" if korean else f"`{name}` (한국어 이름 없음)"


def _state(name: str) -> str:
    return STATE_NAMES.get(name, f"{name} (한국어 설명 없음)")


def _yes_no(value: bool) -> str:
    return f"{'예' if value else '아니오'}({value})"


def _group_notes_by_run_place(notes: list[str]) -> list[str]:
    """Collapse lines that say the same thing once per run place.

    The check reports missing evidence per run place, so one absent file
    becomes three near-identical paragraphs. Nothing is dropped: the shared
    sentence is printed once with every run place it came from named in front
    of it. A line whose prefix is not a run place this file knows is passed
    through untouched rather than guessed at.
    """
    order: list[str] = []
    places: dict[str, list[str]] = {}
    for note in notes:
        head, sep, tail = note.partition(": ")
        if sep and head in RUN_PLACE_NAMES:
            key, place = tail, head
        else:
            key, place = note, ""
        if key not in places:
            places[key] = []
            order.append(key)
        if place:
            places[key].append(place)

    grouped: list[str] = []
    for key in order:
        found_in = places[key]
        if not found_in:
            grouped.append(key)
        elif len(found_in) == 1:
            grouped.append(f"[{found_in[0]}] {key}")
        else:
            grouped.append(f"[실행 장소 {len(found_in)}곳 모두: "
                           f"{', '.join(found_in)}] {key}")
    return grouped


def summarise(report: dict, *, commit: str | None = None) -> str:
    verdict = _need(report, "offline_verdict", dict)
    problems = _need(verdict, "problems", list)
    not_checked = _need(verdict, "not_checked_here", list)
    readiness = _need(report, "readiness", dict)
    compared = _need(readiness, "compared_environments", list)
    environments = _need(readiness, "environments", list)
    differences = _need(report, "uncontrolled_differences", list)
    measurable = _need(report, "pure_run_place_effect_is_measurable", bool)
    may_start = _need(report, "may_start", bool)

    out: list[str] = []
    add = out.append

    add("## 실행 환경 비교 — 무료 사전검사 결과")
    add("")
    add("돈을 쓰지 않았습니다. 모델을 부르지 않았고, 클라우드에 로그인하지 "
        "않았고, 도커를 켜지 않았습니다. 이 저장소의 코드와 설정 파일만 읽었습니다.")
    add("")

    if problems:
        add(f"**결과: 실패.** 코드나 계획서 자체의 잘못이 {len(problems)}개 "
            "있습니다. 이건 어느 컴퓨터에서 봐도 똑같이 잘못인 것들이라 "
            "검사를 빨간불로 세웁니다.")
        add("")
        for problem in problems:
            add(f"- {problem}")
    else:
        add("**결과: 통과.** 코드나 계획서 자체의 잘못은 0개입니다.")
    add("")

    add("### 이 초록불이 뜻하지 않는 것")
    add("")
    add("- 유료 실험을 돌려도 된다는 허가가 **아닙니다**.")
    add("- 실행 환경이 다 준비됐다는 뜻도 **아닙니다**.")
    add(f"- 같은 도구의 기본 정책(진짜 실행 전에 통과해야 하는 그것)으로 보면 "
        f"지금 상태는 `실행 가능 = {_yes_no(may_start)}` 입니다. "
        "그 정책은 지금도 막혀 있고, 앞으로도 계속 막혀 있게 둡니다.")
    add("")

    add(f"### 비교할 실행 장소 {len(compared)}곳, 각각의 상태")
    add("")
    graded = {
        entry.get("environment"): entry
        for entry in environments
        if isinstance(entry, dict)
    }
    for name in compared:
        entry = graded.get(name)
        if entry is None:
            raise CannotSummarise(
                f"비교 대상 '{name}'의 상태가 보고서에 없습니다"
            )
        add(f"- **{_run_place(str(name))}** — {_state(str(entry.get('status')))}")
        for blocker in entry.get("blockers") or []:
            add(f"    - 막고 있는 것: {blocker}")
    add("")

    others = [
        entry
        for entry in environments
        if isinstance(entry, dict) and entry.get("environment") not in compared
    ]
    if others:
        add("### 비교에 넣지 않은 나머지 실행 장소")
        add("")
        add("아래는 이번 비교 대상이 아닙니다. 상태를 그대로 적어 둡니다.")
        add("")
        for entry in others:
            add(
                f"- {_run_place(str(entry.get('environment')))} — "
                f"{_state(str(entry.get('status')))}"
            )
        add("")

    add("### 여기서 확인하지 않은 것 (＝ 확인해서 통과한 것이 아님)")
    add("")
    for entry in not_checked:
        if not isinstance(entry, dict):
            raise CannotSummarise("확인하지 않은 항목의 모양이 딕셔너리가 아닙니다")
        add(f"- **{entry.get('what')}** — 확인하지 않음")
        add(f"    - 왜 못 하나: {entry.get('why_this_machine_cannot_say')}")
        add(f"    - 무엇이 있어야 알 수 있나: {entry.get('what_would_settle_it')}")
        notes = _group_notes_by_run_place(
            [str(note) for note in entry.get("notes") or []]
        )
        if notes:
            add(f"    - 아래 {len(notes)}줄은 검사 도구가 낸 영어 원문입니다. "
                "말을 바꾸면 도구와 어긋나므로 그대로 붙입니다.")
            for note in notes:
                add(f"        - {note}")
        else:
            add("    - (이번 실행에서 따로 적힌 내용은 없습니다)")
    add("")

    add("### 없앨 수 없는 차이")
    add("")
    add(f"실행 장소 사이에 끝까지 남는 차이가 {len(differences)}개 있습니다. "
        "잘못이 아니라, 이 비교로는 없앨 수 없는 것들입니다.")
    add("")
    for entry in differences:
        if not isinstance(entry, dict):
            raise CannotSummarise("남는 차이 항목의 모양이 딕셔너리가 아닙니다")
        places = ", ".join(str(p) for p in entry.get("run_places") or [])
        add(f"- **{entry.get('what')}** ({places})")
        add(f"    - 왜 남나: {entry.get('why_it_stays')}")
        add(f"    - 결과를 어떻게 흔들 수 있나: "
            f"{entry.get('what_it_could_do_to_a_result')}")
    add("")
    add(f"그래서 **`실행 장소만의 효과를 잴 수 있는가 = {_yes_no(measurable)}`** "
        "입니다. 결과에 차이가 나와도 그게 순전히 '어디서 돌렸는지' 때문이라고 "
        "말할 수 없다는 뜻입니다.")
    add("")

    add("### 이번 검사가 무엇을 보고 판단했는지 (증거 연결용)")
    add("")
    if commit:
        add(f"- 검사한 커밋: `{commit}`")
    else:
        add("- 검사한 커밋: (전달받지 못함)")
    every_read = report.get("every_input_file_was_read")
    add(
        "- 입력 파일 지문을 전부 실제 파일과 대조했는가: "
        + ("예" if every_read is True else f"아니오 (`{every_read}`)")
    )
    input_files = _need(report, "input_files", dict)
    seen: dict[str, str] = {}
    for place, verification in sorted(input_files.items()):
        if not isinstance(verification, dict):
            raise CannotSummarise(f"'{place}'의 입력 파일 기록이 딕셔너리가 아닙니다")
        for check in verification.get("checks") or []:
            written = str(check.get("written"))
            state = str(check.get("state"))
            path = str(check.get("path"))
            previous = seen.get(f"{path}|{written}")
            if previous is None:
                seen[f"{path}|{written}"] = state
                add(f"- `{written}` — {path}")
                add(
                    "    - 대조 상태: "
                    + FINGERPRINT_STATE_NAMES.get(state, f"{state} (한국어 설명 없음)")
                )
            elif previous != state:
                raise CannotSummarise(
                    f"같은 파일 {path}의 대조 상태가 실행 장소마다 다릅니다: "
                    f"{previous} vs {state}"
                )
    if not seen:
        raise CannotSummarise(
            "입력 파일 지문이 하나도 없습니다. 이 비교는 다섯 과제의 입력을 "
            "못 박는 것이 전제라, 빈 목록은 통과가 아니라 읽기 실패입니다"
        )
    add("")

    cost_findings = [str(f) for f in report.get("cost_findings") or []]
    grading_ceiling = [
        str(f)
        for f in report.get("grading_ceiling_problems") or []
        if str(f) not in cost_findings
    ]
    if cost_findings or grading_ceiling:
        add("### 비용 쪽에 적어 둔 것 (이번 검사를 막지는 않음)")
        add("")
        add("아래는 '얼마가 들지 아직 모른다'는 기록입니다. 0원이라는 뜻이 "
            "아니라, 재 본 적이 없어 계산이 안 된다는 뜻입니다.")
        add("")
        for finding in cost_findings:
            add(f"- {finding}")
        for finding in grading_ceiling:
            add(f"- (채점 한도) {finding}")
        add("")

    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render the free run-place check's JSON report as a short Korean "
            "summary."
        )
    )
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--commit",
        default=None,
        help="The commit the report was produced from, printed as evidence.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Also write the summary here. It always goes to standard output.",
    )
    args = parser.parse_args(argv)

    try:
        text = summarise(_load(args.report), commit=args.commit)
    except CannotSummarise as error:
        # Loud, and on stderr, and non-zero. An unreadable report must not be
        # able to look like a report that said nothing was wrong.
        print(f"요약을 만들 수 없습니다: {error}", file=sys.stderr)
        return 1

    print(text, end="")
    if args.out is not None:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
