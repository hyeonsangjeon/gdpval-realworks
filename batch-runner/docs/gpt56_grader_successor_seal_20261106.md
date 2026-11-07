# Reviewed successor grader seal — 2026-11-06 (selector fix)

Owner decision 1, recorded 2026-11-06 (Asia/Seoul), approves fixing the
deliverable selector inside the sealed grader closure and registering the fix
as a reviewed successor of the #794 seal, then regrading exp036 (all five
tasks, inside its existing USD 200) and the exp035 tasks whose selection
changes. This registration does not change the pilot's model settings, USD
ceilings, unknown-usage handling or launch rights, and it is not a model call.

The change is two sealed files, landed as their own commit (A) so that the
record can name it. The registration (this document, the record, its reader,
one more preflight chain link, the new source profile and two test files) is
the next commit (B). Nothing in B touches the closure.

**Merge rule.** Merge with "Create a merge commit" only. The record pins commit
A by SHA and the seal test runs `git archive` on it; a squash or rebase merge
drops A from main's history and the test fails on main. Update the branch only
by merging main into it.

## Identity and unchanged conditions

- Predecessor: `experiments/execution_envelope/gpt56_sol_grader_seal_20261030.json`,
  SHA256 `1a5841eed8f7acbdbfdc71d2810b5e6acc5d3b4f87edae8d88cb4bc420150915`,
  closure reviewed at `0140b4c125093dc04de9ca0814387c140a929a59`, grader hash
  `099755b009e7563e5b3824ac34c1ab2cf5c83b3cdf4aba7886b50e1c28003fd7`. Its bytes
  and its reader `gpt56_pilot_grader_seal.py` are unchanged.
- Commit A (the closure change): `788fdfcc51099d7082d79a0e86328a4bb3a6756c`.
- New record: `experiments/execution_envelope/gpt56_sol_grader_seal_20261106.json`,
  SHA256 `bf4b38105c6b9bb5deb380f0faf53cafa58efd9d58e3f08b43be55cd5c65b19c`.
  Its `previous.files` is exactly the 20261030 manifest (153 files), its
  `files` is commit A's closure (153 files), and `changes` holds exactly two
  `modified` rows. New grader hash of the exp035 template:
  `7a9aa01048b874c09642ee8cd73493cbe81065bb8d5c02ed52057c00ac78048c`.
- New reader: `gpt56_pilot_grader_reseal.py`, SHA256
  `1312ac36cb334fd44413ee024f98e89edf8d6316910795527f8c1ae4a830ad74`. It holds the
  20261030 record by SHA256, requires the preserved conditions to be equal and
  `launch_authority` false, admits exactly the two-file delta, rereads every
  byte, recomputes `compute_grader_source_hash`, and refuses everything else
  with one code, `grader_successor_seal_refused`.
- Preflight `gpt56_sol_codex_pilot_preflight.py`, SHA256
  `c4878e006fd6b5db01c5348717df4d3ee8aceb0b2cd7d4dc51e575b2c37a6023`: one more
  chain link. The 20261030 hash stays admissible only through its own verifier,
  which refuses on the resealed tree, so superseded profiles now report
  `grader_successor_seal_refused`.
- New active source profile:
  `experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261106_selector_reseal.yaml`,
  SHA256 `af5699e82f1d659e3778df376bcdc9dd8ee30b0b6090163accb6a4f21c40fc9b`. It is
  the 2026-11-05 batch-path profile (SHA256 `25d9a2de…059595`) with a new
  header, the new grader-template hash and the new preflight pin; the other 57
  of its 58 source pins are identical. Reason recorded:
  `owner_approved_selector_reseal_without_pilot_policy_change`.
- Unchanged: Sol (`gpt-5.6-sol`), Max, prompt v2.2, rubric revision
  `11e7900cdcac61bc4daf59e65feb238acda98fbf`, the ordered five-task selection and
  the USD 200 combined record
  `experiments/execution_envelope/gpt56_sol_native_usd_cap_20261027.yaml`. The
  native pilot stays paused; `launch_authority` is false.
- Byte-identical as well: step 8, every other `core/**` file, the prompts, the
  grade schema, the requirements closure, the download script, every existing
  grading config (the exp035 template above all), `sol_batch_controls.py`,
  `step2_run_inference.py`, `batch-run.yml` and `backend-tests.yml`.

Names that move with the hash: `exp036_v2_sol_max.yaml` keeps
`cfg_1794403983325602` and its `src_` moves from `src_814d56797e9fc3dc` to
`src_6f8811acb9de0b81`, so its regrade is a new grade file and the published one
stays as the pre-fix record. All sixteen grading configs' hashes move.

## File-by-file classification

Both files change what is graded, so both are **impact**. Evidence lines are
in commit A.

| File | Class | Evidence | Effect |
| --- | --- | --- | --- |
| `core/deliverable_selector.py` | Impact | 323 | F1: `.eml` is a document (never a Word file) and email/memo/letter criteria route to it. F2: where cc256a50 refused `format_variant_no_match`, same-folder, same-name, same-family rendition copies are set aside and the rest is re-selected; otherwise the refusal is returned unchanged. The copy kept is the one whose format the task's prompt or rubric names outside a negation ("not PDF" names nothing), when exactly one member is named and the unchanged rules then grade it as a primary; otherwise a fixed format order decides: the formats the renderer draws, then the other formats the reader opens, then the legacy `.doc`, `.xls` and `.ppt`, then `.html`/`.htm` pages, then `.msg`. Formats the grader cannot open (`.msg`, `.doc`, `.xls`, `.ppt`) are never preferred by name. F3: an image the rubric asks for (2 of 220 tasks) becomes an extra primary beside the document, for VISUAL and manifest criteria only. F4: one document plus companions under other names, whose format the task never names, becomes `main_plus_support` instead of `ambiguous`. |
| `core/tools/read_deliverable.py` | Impact | 735 | F1b: an `.eml` is read as decoded headers, body (plain, or HTML with tags removed) and an attachment list; attachments open as members, and traversal or an unknown name is refused. The model-facing tool schema, the member refusal text for every other kind and `MAX_CONTENT_CHARS` are byte-identical. `.msg` stays support only (an OLE binary with no reader). |

Every rule reads only file names, folders and extensions plus the task's own
prompt and rubric; the same rules move gpt-5.4 (exp035) and Sol (exp036) tasks.
Stdlib `email` and `html.parser` only, so no requirements change.

## Offline evidence

Model-free replays of the real selector on four corpora (Docker
`gdpval-test:py310`, the openai/gdpval rubric at `11e7900c`):

| Corpus | Refused before → after | Items in refused tasks | Predicted render-unavailable items | Selections changed |
| --- | --- | --- | --- | --- |
| gold-185 | 0 → 0 | 0 → 0 | 5 → 5 | 1 (3baa0009, + JPG) |
| exp003 (219) | 0 → 0 | 0 → 0 | 8 → 8 | 1 (3baa0009) |
| exp035 (150 with files) | 7 → 2 | 388 → 94 | 15 (20 pts) → 6 (9 pts) | 7 (8 against the published grade, + 15ddd28d from #649) |
| exp036 (4 with files) | 2 → 0 | 126 → 0 | 9 → 0 | 3 (02aa1805 F1, 0112fc9b F2, 3baa0009 F3) |

The two exp035 refusals left (0e386e32, 7de33b48) are code packages and stay
`format_variant_no_match` by design. 0818571f stays `no_deliverables`
(content filter, a real failure).

- 02aa1805 (Sol's `.eml` + `.xlsx`): 21 email items (23 points) all see the
  `.eml`, 0 blind; saving the same email as `.docx` routes 0 of the 71 items
  differently.
- The `.eml` read: 26,449 characters of raw MIME (about 78% base64, 50 soft line
  breaks splitting words and IDs, attachment unopenable) become 2,431 clean
  characters plus an openable attachment (2,795 characters as a member).
- The three `test_old_and_successor_requests_verdict_denominator_scores_summary_equal`
  cases (pass, fail, partial) compare the complete serialized judge request,
  verdict, denominator, five aggregation rows and summary of `8ac891e3` with
  the resealed source: equal. F1b did not move the judge-facing request.
- `tests/test_gpt56_grader_successor_seal.py` (41 cases) and
  `tests/test_sol_source_registration.py` (1 case): 42 passed on this branch
  with HEAD at the registration commit and a clean tree. The model-free
  preflight CLI on the new profile exits 2 with `configuration_valid` true,
  `source_verified` and `reviewed_successor_seal_verified`.

Not more lenient than a careful reader. Copies are set aside only when they are
same-folder, same-name, same-family renditions. The kept file is the rendition
the task names, or else the first in a fixed order; it is never chosen by
quality, and the model's own summary is never read. A set-aside copy is not
shown to the judge, which reads only the selected files: manifest criteria
record every set-aside file in their audit (`support_paths_visible`), not in
the judge's request. The email is read as a mail client shows it. F3 turns 9
excluded items per run into judged items and ends a leniency on b1a79ce1, where
chart items had been passed from drawing code. F4 companions become support
exactly as images already do. F2's re-selection makes build scripts
co-primaries on 15d37511 (`.xlsx` + `.py`), aad21e4c (`.docx` + `.py` + `.txt`)
and cebf301e (`.docx` + `.py`); that is cc256a50's existing rule, under which
49 of the 142 `ok` tasks in the published exp035 grade already pair code with a
document.

Neither the named-format rule, its negation guard nor the order of the
legacy binaries and pages moves a recorded selection: replayed on all 558
recorded deliveries, every selection and every item's plan is byte-identical
with or without them. They matter for twins no model has delivered yet:
2c249e0f ("include a text file called data_flow.txt", one of exp037's first 25)
answered with a same-name `.docx` beside the `.txt` keeps the `.txt`; 62f04c2f
with a same-name PDF of each file keeps the `.xlsx` and `.docx` its rubric asks
for ("in .xlsx or .xls format (not CSV/Google Sheet/PDF …)"); a `.doc` or `.xls`
beside a plain-text, Markdown, `.eml` or CSV copy keeps the copy the judge can
read. With a same-name twin in each of nine formats added to every recorded
delivery (5,580 shapes), 8 selections move against the same rules without the
guard and the order: the three 62f04c2f PDF-twin shapes, three lone `.txt` +
`.html` twins that now keep the `.txt`, 4b894ae3's edit report (graded as the
`.txt`, where neither rendition was), and one change in support order only.

## Limits

This is not a replay of real task scores, and the judge is not deterministic.
The renderer (`PyMuPDF>=1.21.0`, unpinned) is not in the grader hash. The
gold_ceiling_185 row for 3baa0009 becomes semantically stale (F3 would now add
its JPG); regrading it is not approved.

Three shapes still grade less than a careful reader would open. A legacy
`.doc` beside a same-name `.html` page keeps the `.doc`, which the judge cannot
read; ranking the page first would instead let F4 make it the companion of any
other document and drop the document altogether. A negation counts only before
the format word, within 40 characters and up to a clause break: one after the
word is missed, a format written with its own dot ends it ("not .pdf" still
names PDF, as in 6974adea's "(not .pdf, .txt, …)"), and in a list the formats
after a comma count as named ("no PDFs, CSVs" names CSV; on f841ddcf a required
format decides first). None of the 558 recorded deliveries (gold-185, exp003,
exp035, exp036) has the first shape, and the second moves none of them.
cc256a50's own single-PDF answer to format variants is unchanged: it grades
only the PDF, even where the task names another rendition, and it sets distinct
files aside too (22 exp035 tasks take it; on a73fbc98 the assigned-vendors
`.xlsx`, on 0ec25916 the references `.md`).

Any later change to step 8, `core/**`, the prompts, the schema, the
requirements, the download script or a grading config in use must refuse until
it is reviewed and resealed again. The Sol 220 must be graded under one grader
hash from its first paid grading chunk to its last. If commit A has to change
before merge, regenerate the registration from the new A and rewrite the
digests in this document; never edit a digest by hand.
