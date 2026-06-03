# SELECTOR FIX - 99ac6944 PRINCIPLE-BASED CORRECTION

## One-line Conclusion
99ac6944 is now classified as `main_plus_support` by a general single-primary-format rule. The actual-rubric fixture is preserved, and the 28 focused cases pass: gold target selection 20/20, checked task classes 5/5, separate-equivalent controls 4/4, wrong-format controls 7/7, no regression in `no_generated_candidate` or hybrid routing. No pipeline wiring, regrade, Azure, or vision run was performed.

## Diagnostic Contradiction Resolved
The earlier contradiction was real: the refined separate regex still returned true for 99ac6944, but not because it matched `two separate mono mixes` directly.

The actual path was:

- `batch-runner/core/deliverable_selector.py:441` did not fire because support detection still depended on filename tokens.
- `batch-runner/core/deliverable_selector.py:444` then fired `_has_separate_deliverable_language`.
- The over-broad pattern crossed criterion sentence boundaries and matched `two xlr microphone inputs. the document`, treating the next criterion's `document` as the deliverable noun.
- If that path had not fired, the later doc extension branch at `batch-runner/core/deliverable_selector.py:465` could also have classified the mixed PDF/XLSX set as `separate_equivalent`.

The exact false-positive rubric neighborhood was task 99ac6944: content requirements about two XLR inputs and two independent IEM mixes were concatenated with the next criterion, creating a fake numeric deliverable phrase.

## Fix
Primary support selection is now format-based, not filename-token-based:

- `batch-runner/core/deliverable_selector.py:441` checks single-primary-with-support before separate-deliverable language.
- `batch-runner/core/deliverable_selector.py:472` returns `main_plus_support` when `required_exts` is a single format family and exactly one generated file matches it.
- All non-matching generated files are support by role. The selector no longer requires filename tokens such as `budget`, `breakdown`, or `signal` to identify support.

Content leakage is also narrowed:

- `batch-runner/core/deliverable_selector.py:507` keeps separate-deliverable regexes tied to deliverable/file nouns.
- Numeric phrases are constrained to a single sentence, so content text such as `two inputs. The document ...` cannot become a false multi-deliverable signal.
- Content nouns such as mixes, channels, outputs, tracks, tabs, sections, versions, and variants remain non-evidence for multi-deliverable classification on their own.

## Generalization Check
No task ID or specific filename is hardcoded. The rule is based on requested format and generated-file extensions:

- 99ac6944: required `.pdf`, exactly one generated PDF, remaining XLSX/PNG files become support.
- 27e8912c, a74ead3b, bbe0a93b, and 6dcae3f5 remain `separate_equivalent`.
- The seven wrong-format fixtures still return `wrong_format_primary`.

## Actual Rubric Fixture
`batch-runner/tests/test_deliverable_selector.py` now loads task prompt and `rubric_json` from `data/gdpval-local/data/train-00000-of-00001.parquet`. Fixture data only supplies file lists and owner-expected targets. Synthetic rubric criterion text was not restored.

## Verification
Command:

```bash
PYTHONPATH=batch-runner .venv/bin/python -m pytest batch-runner/tests/test_deliverable_selector.py -q
```

Result:

```text
7 passed in 1.42s
```

Explicit fixture counts:

- Gold owner-target files: 20/20.
- Checked gold task classes: 5/5, including 99ac6944 = `main_plus_support`.
- Separate-equivalent controls: 4/4.
- Positive controls: 3/3.
- Wrong-format controls: 7/7.
- Total focused fixture cases: 28.

## Next
Owner review, then pipeline integration, item-level audit fields, SP secret rotation, and one controlled regrade.
