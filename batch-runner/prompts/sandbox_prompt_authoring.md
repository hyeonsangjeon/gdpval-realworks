# Authoring the sandbox prompt — one file, one place

The container-sandbox solving path (`execution.mode: sandbox`) builds its prompt
from a **single spec file**:

```
batch-runner/prompts/sandbox_occupation_codegen.yaml
```

A researcher or engineer edits *that file* to change how the model is briefed —
persona, rules, the order of the injected context blocks, the self-repair wording,
and where host audio/video perception is placed. The Python runner
(`core/sandbox_runner.py`) only assembles what the spec declares; it does not own
the wording or the section order. This guide is the map.

> Scope: this affects **sandbox mode only**. `subprocess`, `code_interpreter`, and
> `json_renderer` are untouched by anything here.

---

## 1. What the model actually receives

For each attempt the runner produces two messages:

- **system** — `system_message` from the spec, with `{occupation}` filled in.
- **user** — `user_prompt` from the spec, with `{task_prompt}` filled in, where
  `{task_prompt}` is the **assembled context** described below.

The assembled context is an ordered list of *sections*, joined by blank lines. Each
section is produced by a thin provider; empty sections are dropped automatically.

```
[ reflection ]            ← sandbox self-repair block (only on a repair attempt)
[ file_structure ]        ← tabular schema of reference files (columns/sheets)
[ skills_manual ]         ← "AVAILABLE SKILLS" — the selected Skills + their API
[ deps_hint ]             ← "Likely libraries" pre-installed for this task
[ contract ]              ← DELIVERABLE CONTRACT — the expected output type(s)
[ perception_analysis ]   ← host audio/video analysis block (when perception ran)
[ task ]                  ← the task instruction text
[ previews ]              ← reference-file content previews
[ available_files ]       ← "Files available in the sandbox working directory: [...]"
```

---

## 2. The knobs (all in the spec file)

### `system_message` / `user_prompt`
Persona, rules, output format, the worked example, and the `CONFIDENCE[XX]` tag.
Plain `str.format` templates — only `{occupation}` and `{task_prompt}` are
substituted, so keep other literal `{` / `}` out (the code examples already avoid
dict/set literals on purpose).

### `sections:` — order and presence of the context blocks
An ordered list. Each entry is either a bare id or `{id: ..., enabled: false}`.

```yaml
sections:
  - id: reflection
  - id: file_structure
  - id: skills_manual
  - id: deps_hint
  - id: contract
  - id: perception_analysis
  - id: task
  - id: previews
  - id: available_files
```

- **Reorder** by moving lines. **Drop** a block with `enabled: false` (keeps the
  line as documentation) or by deleting it.
- **Known ids** (and the existing builder each maps to):

  | id | source | omitted when |
  |---|---|---|
  | `reflection` | sandbox self-repair (`_build_reflection`) | not a repair attempt |
  | `file_structure` | `file_preview.build_file_structure_info` | no tabular refs |
  | `skills_manual` | `SkillsRegistry.render_manual` | no skills selected |
  | `deps_hint` | `DependencyManifest.to_prompt_hint` | nothing to install |
  | `contract` | `DeliverableContract.to_prompt_section` | no contract |
  | `perception_analysis` | host audio/video analysis | perception didn't run |
  | `task` | the task instruction | (always present) |
  | `previews` | `file_preview.generate_all_previews` | no reference files |
  | `available_files` | basenames of reference files | no reference files |

- An **unknown id fails loudly** at assembly time — a typo never silently drops a
  section.
- If you remove the whole `sections:` key, the runner falls back to
  `core.prompt_sections.DEFAULT_SECTIONS` (this same order).

### `reflection_strings:` — the self-repair wording (loop 2)
When an attempt fails the deliverable contract, the runner feeds a focused
`[REFLECTION] … [/REFLECTION]` block back to the model. The *wording* lives here;
the *layout* and safety limits (≤12 blocking errors, ≤6 warnings, prior code echoed
when ≤4000 chars, host paths redacted) stay in Python.

```yaml
reflection_strings:
  open: "[REFLECTION]"
  intro: >-
    Your previous attempt did NOT satisfy the deliverable contract. Regenerate
    the COMPLETE solution and fix every issue below.
  blocking_header: "Blocking problems to fix:"
  warnings_header: "Secondary warnings (address if relevant):"
  stdout_header: "Previous stdout (tail):"
  stderr_header: "Previous stderr/error (tail):"
  code_header: "Your previous code (fix and resend in full):"
  code_fence: "----"
  close: "[/REFLECTION]"
```

Any key you omit falls back to the built-in default
(`core.sandbox_runner._DEFAULT_REFLECTION_STRINGS`). **Quote** values that begin
with `[` or YAML will read them as a list.

### `perception_analysis` placement
Host audio/video analysis (the `[AUDIO ANALYSIS] … ` / `[VIDEO ANALYSIS] …` block
from the preprocessors) is injected as its own section. The analyzers own their
labels; the spec owns *where* the block sits. Move the `perception_analysis` line
to reposition it. It is dropped automatically when no perception ran.

---

## 3. A/B a whole prompt without touching Python

To try an alternative prompt design, copy the spec to a new name, edit it, and
point the experiment condition at it — no code change:

```bash
cp prompts/sandbox_occupation_codegen.yaml prompts/sandbox_codegen_variantB.yaml
# edit prompts/sandbox_codegen_variantB.yaml
```

```yaml
# in your experiment YAML, under the sandbox condition:
execution:
  mode: "sandbox"
  sandbox:
    prompt_name: "sandbox_codegen_variantB"   # selects the alternate spec
```

Selection order in `core/executor.py`: explicit `prompt_name` →
`execution.sandbox.prompt_name` → `SandboxRunner.DEFAULT_PROMPT`
(`sandbox_occupation_codegen`).

---

## 4. Safety net: the golden tests

`tests/test_sandbox_prompt_golden.py` freezes the exact assembled prompt for four
representative tasks (audio, 4K video, doc-only, spreadsheet), the repair
reflection, and a perception + repair combination. `tests/test_prompt_sections.py`
covers the section engine (ordering, toggles, unknown-id failure).

When you **intentionally** change the wording or order, regenerate the snapshots
and review the diff before committing:

```bash
cd batch-runner
REGEN_PROMPT_GOLDEN=1 python -m pytest tests/test_sandbox_prompt_golden.py
git diff -- tests/fixtures/prompt/golden/   # eyeball the wording/order change
```

If a diff appears that you did **not** intend, you changed the prompt by accident —
revert instead of regenerating.

---

## 5. What stays in Python (and why)

- **Section builders** (`file_preview`, `skills_registry`, `deliverable_contract`,
  `dependency_resolver`) — these compute content from the task/files; the spec only
  orders their output.
- **Reflection layout + limits** — bounded slicing keeps the repair prompt focused.
- **Path redaction** (`_sanitize_tail`) — stdout/stderr tails and paths are
  sanitized so the prompt never leaks host filesystem layout.

Everything else — the words the model reads and the order it reads them in — is in
the spec file. Edit there.
