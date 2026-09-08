"""References to steps and jobs that GitHub resolves to nothing.

`yaml.safe_load` accepts every workflow in this repository. That is the
problem: the mistakes this file looks for are all valid YAML, and several are
valid GitHub Actions *syntax* too. They fail by evaluating to null.

    - name: Confirm the record names no resource
      id: leak_check
      ...
    - name: Keep the record
      if: always() && steps.leak_check.conclusion == 'success'

Rename `leak_check` on the first step and leave the second alone. The file
still loads. The job still runs. `steps.leak_check` is now an unknown step, so
it resolves to null, `null.conclusion` resolves to the empty string, and the
condition is simply false — or, had it been written the other obvious way,
`!= 'failure'` would be *true* and the upload would happen unconditionally
again. A guard that was deleted by a rename, with nothing red anywhere.

The same null hides in two neighbouring shapes:

  * `steps.<id>` naming a step that exists but comes *later* in the job. The
    context only holds steps that have already run, so a forward reference is
    null every time, on every run, no matter what the later step does.
  * `needs.<job>` naming a job this job does not wait for. The `needs` context
    only carries the jobs listed in `needs:`; anything else is null, and an
    output read that way is the empty string rather than an error.

None of that is caught by loading the file, by `actionlint`-free CI, or by the
job-level context test in `test_step8_grade.py` — that one asks whether a
context may be *used in that position at all*, which is a different failure
(the workflow refuses to load) with a different symptom.
"""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

_TEMPLATED = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)
# The lookbehind excludes `-` and quotes as well as word characters, so that
# `my-steps.x` or `"steps.x"` inside a shell string is not read as a context.
_STEP_REF = re.compile(r"(?<![\w.\-'\"])steps\s*\.\s*([A-Za-z_][\w-]*)")
_STEP_INDEX = re.compile(r"""(?<![\w.\-'"])steps\s*\[\s*['"]([^'"]+)['"]\s*\]""")
_NEEDS_REF = re.compile(r"(?<![\w.\-'\"])needs\s*\.\s*([A-Za-z_][\w-]*)")

# Keys whose value GitHub evaluates as an expression even without `${{ }}`.
# An extractor that only reads inside the braces passes every bare `if:` —
# which is how the gate quoted above is written, so this is not a hypothetical.
_BARE_EXPRESSION_KEYS = frozenset({"if"})


def _expressions(value, bare):
    text = str(value)
    found = _TEMPLATED.findall(text)
    if bare and not found:
        found = [text]
    return found


def _walk(node, where="", bare=False):
    """Yield `(where, expression_text)` for every expression under `node`.

    Recursive because a reference can sit anywhere in a step: `if`, `env`,
    `with`, a `run` body, an action input three levels down a list.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(
                value, f"{where}.{key}", bare=str(key) in _BARE_EXPRESSION_KEYS
            )
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{where}[{index}]", bare=bare)
    elif node is not None:
        for expression in _expressions(node, bare):
            yield where, expression


def _steps_named(expression):
    return set(_STEP_REF.findall(expression)) | set(_STEP_INDEX.findall(expression))


def _needs_named(expression):
    return set(_NEEDS_REF.findall(expression))


def _declared_needs(job):
    declared = job.get("needs")
    if declared is None:
        return set()
    if isinstance(declared, str):
        return {declared}
    return {str(name) for name in declared}


def scan(parsed, filename="<workflow>"):
    """Every step and job reference in one workflow, and what is wrong with it.

    Returns `(violations, references)`. `references` holds every pair that
    *resolves*, so a caller can prove the scan read something real rather than
    passing because it found nothing to look at — and so that a count of them
    cannot be met by broken references.
    """
    violations = []
    references = []
    for job_name, job in (parsed.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        steps = [s for s in (job.get("steps") or []) if isinstance(s, dict)]
        ids_in_job = [s["id"] for s in steps if s.get("id")]

        duplicated = {i for i in ids_in_job if ids_in_job.count(i) > 1}
        for identifier in sorted(duplicated):
            violations.append(
                f"{filename}: jobs.{job_name} has {ids_in_job.count(identifier)} "
                f"steps with id `{identifier}`; a reference to it reads the "
                f"last one to run, not the one that was meant"
            )

        already_run = set()
        for index, step in enumerate(steps):
            label = f"{filename}: jobs.{job_name}.steps[{index}]"
            if step.get("id"):
                label += f" (id `{step['id']}`)"
            for where, expression in _walk(step):
                for named in sorted(_steps_named(expression)):
                    if named in already_run:
                        references.append((filename, job_name, named))
                        continue
                    if named == step.get("id"):
                        violations.append(
                            f"{label}{where} reads `steps.{named}`, which is "
                            f"itself; a step is not in the context while it runs"
                        )
                    elif named in ids_in_job:
                        violations.append(
                            f"{label}{where} reads `steps.{named}`, a step that "
                            f"has not run yet at that point, so it is null on "
                            f"every run"
                        )
                    else:
                        violations.append(
                            f"{label}{where} reads `steps.{named}`, and no step "
                            f"in jobs.{job_name} has that id"
                        )
                for named in sorted(_needs_named(expression)):
                    if named not in _declared_needs(job):
                        violations.append(
                            f"{label}{where} reads `needs.{named}`, which is not "
                            f"in jobs.{job_name}.needs, so it is null"
                        )
            if step.get("id"):
                already_run.add(step["id"])

        # `outputs` is evaluated after the job's steps, so it may read any of
        # them — but still only ones that exist.
        for where, expression in _walk(job.get("outputs") or {}):
            for named in sorted(_steps_named(expression)):
                if named in ids_in_job:
                    references.append((filename, job_name, named))
                else:
                    violations.append(
                        f"{filename}: jobs.{job_name}.outputs{where} reads "
                        f"`steps.{named}`, and no step in that job has that id"
                    )

        for key in ("if", "env", "outputs", "with"):
            for where, expression in _walk(
                {key: job[key]} if key in job else {}, bare=False
            ):
                for named in sorted(_needs_named(expression)):
                    if named not in _declared_needs(job):
                        violations.append(
                            f"{filename}: jobs.{job_name}{where} reads "
                            f"`needs.{named}`, which is not in "
                            f"jobs.{job_name}.needs, so it is null"
                        )
    return violations, references


def _every_workflow():
    paths = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    assert paths, f"no workflow files under {WORKFLOWS}; the scan would pass on nothing"
    return [(p.name, yaml.safe_load(p.read_text(encoding="utf-8"))) for p in paths]


def _scan_them_all():
    violations = []
    references = []
    for name, parsed in _every_workflow():
        found, read = scan(parsed, name)
        violations += found
        references += read
    return violations, references


def _load(text):
    return yaml.safe_load(text)


def test_every_step_reference_in_every_workflow_names_a_step_that_has_run():
    violations, references = _scan_them_all()
    assert not violations, (
        "a reference below resolves to null on every run. GitHub reports "
        "nothing: the file loads, the job runs, and the condition or value is "
        "simply empty.\n  " + "\n  ".join(sorted(set(violations)))
    )
    # Non-vacuity, three ways. A scan that read no files, or read them and
    # found nothing, or found only references that resolve to nothing, would
    # otherwise pass exactly as loudly as one that checked the whole repository.
    assert len(_every_workflow()) >= 15, "the workflow directory came back short"
    assert len(references) >= 20, f"only {len(references)} step references seen"
    assert len({f for f, _, _ in references}) >= 5


def test_the_gate_this_file_was_written_for_is_one_of_the_things_it_reads():
    """The concrete reference, named, and resolving.

    `references` only carries pairs that resolve, so this fails both if the
    scan stops covering that file and if the id it reads is renamed out from
    under the gate — which is the exact edit this whole file exists to catch.
    """
    _, references = _scan_them_all()
    assert (
        "codex-foundry-connection-diagnostic.yml",
        "diagnose",
        "leak_check",
    ) in references


def test_a_reference_to_a_step_that_does_not_exist_is_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - name: Check
                    id: leak_check
                    run: echo hi
                  - name: Keep
                    if: always() && steps.leek_check.conclusion == 'success'
                    run: echo keep
            """
        )
    )
    assert any("no step in jobs.diagnose has that id" in v for v in violations)


def test_a_reference_to_a_later_step_is_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - name: Keep
                    if: steps.leak_check.conclusion == 'success'
                    run: echo keep
                  - name: Check
                    id: leak_check
                    run: echo hi
            """
        )
    )
    assert any("has not run yet at that point" in v for v in violations)


def test_a_step_that_reads_itself_is_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - name: Check
                    id: leak_check
                    if: steps.leak_check.conclusion != 'failure'
                    run: echo hi
            """
        )
    )
    assert any("which is itself" in v for v in violations)


def test_two_steps_with_one_id_are_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - id: leak_check
                    run: echo one
                  - id: leak_check
                    run: echo two
                  - if: steps.leak_check.conclusion == 'success'
                    run: echo keep
            """
        )
    )
    assert any("steps with id `leak_check`" in v for v in violations)


def test_an_if_written_without_braces_is_still_read_as_an_expression():
    """The shape the real gate uses. A `${{ }}`-only extractor sees nothing here."""
    bare, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - if: steps.absent.conclusion == 'success'
                    run: echo keep
            """
        )
    )
    wrapped, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - if: ${{ steps.absent.conclusion == 'success' }}
                    run: echo keep
            """
        )
    )
    assert bare and wrapped
    assert len(bare) == len(wrapped)


def test_the_word_steps_in_a_shell_line_is_not_a_reference():
    """`run:` is shell, not an expression. Only `${{ }}` is evaluated there."""
    violations, references = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - run: |
                      # the next steps.absent are documentation, not context
                      echo "see steps.absent in the notes"
                      echo "my-steps.absent"
            """
        )
    )
    assert violations == []
    assert references == []


def test_a_reference_inside_a_with_block_is_still_read():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                steps:
                  - uses: actions/upload-artifact@v7
                    with:
                      name: record
                      path: ${{ steps.absent.outputs.path }}
            """
        )
    )
    assert any("steps.absent" in v for v in violations)


def test_a_job_output_may_read_any_step_in_its_job():
    violations, references = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                outputs:
                  verdict: ${{ steps.late.outputs.verdict }}
                steps:
                  - id: early
                    run: echo one
                  - id: late
                    run: echo two
            """
        )
    )
    assert violations == []
    assert ("<workflow>", "diagnose", "late") in references


def test_a_job_output_naming_no_step_at_all_is_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              diagnose:
                runs-on: ubuntu-22.04
                outputs:
                  verdict: ${{ steps.absent.outputs.verdict }}
                steps:
                  - id: early
                    run: echo one
            """
        )
    )
    assert any("no step in that job has that id" in v for v in violations)


def test_every_needs_reference_names_a_job_the_reader_waits_for():
    violations, _ = _scan_them_all()
    assert not [v for v in violations if "needs." in v], "\n  ".join(violations)


def test_reading_a_job_this_one_does_not_wait_for_is_reported():
    violations, _ = scan(
        _load(
            """
            jobs:
              first:
                runs-on: ubuntu-22.04
                steps:
                  - run: echo one
              second:
                runs-on: ubuntu-22.04
                steps:
                  - run: echo ${{ needs.first.outputs.verdict }}
            """
        )
    )
    assert any("not in jobs.second.needs" in v for v in violations)


def test_reading_a_job_this_one_does_wait_for_is_fine():
    violations, _ = scan(
        _load(
            """
            jobs:
              first:
                runs-on: ubuntu-22.04
                steps:
                  - run: echo one
              second:
                needs: first
                runs-on: ubuntu-22.04
                if: needs.first.result == 'success'
                steps:
                  - run: echo ${{ needs.first.outputs.verdict }}
            """
        )
    )
    assert violations == []


@pytest.mark.parametrize("filename", [p.name for p in sorted(WORKFLOWS.glob("*.yml"))])
def test_each_workflow_on_its_own(filename):
    """One case per file, so a failure names the file in its own test id."""
    parsed = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
    violations, _ = scan(parsed, filename)
    assert not violations, "\n  ".join(violations)
