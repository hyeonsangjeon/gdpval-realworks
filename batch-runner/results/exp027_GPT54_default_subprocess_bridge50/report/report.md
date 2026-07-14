# Experiment Report: GPT-5.4 Default Reasoning - Subprocess Bridge 50

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp027_GPT54_default_subprocess_bridge50` |
| **Condition** | GPT-5.4 server-default + subprocess + audio/video perception |
| **Model** | gpt-5.4 |
| **Execution Mode** | subprocess |
| **Date** | 2026-07-14 |
| **Duration** | 157m 27s |
| **Generated At** | 2026-07-14T12:53:06.725612+00:00 |
| 🤗 HF Dataset | [exp027_GPT54_default_subprocess_bridge50](https://huggingface.co/datasets/HyeonSang/exp027_GPT54_default_subprocess_bridge50) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp027_GPT54_default_subprocess_bridge50/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated GPT-5.4 in server-default reasoning mode using a subprocess execution bridge with audio/video perception enabled across 50 tasks. Overall task completion was 23/50 (46.0%), with 13 recorded errors and 37 tasks requiring retries. End-to-end latency averaged 76.8s, indicating a relatively heavy execution profile under this setup.

From an LLM-evaluated quality perspective, the run was mixed. The average self-assessed confidence score was 5.08/10, with a wide spread from 2 to 9, which suggests substantial variance in answer quality and deliverable robustness across tasks. In practical terms, the model often produced usable outputs, but consistency was limited and a large share of tasks either failed outright or required recovery through retry behavior.

The strongest execution outcomes appeared in Real Estate and Rental and Leasing (6/8 success) and Information (6/10 success), while Government stood out for the best self-assessed confidence at 7.7/10 and the lowest average latency among multi-task sectors at 49.9s. Weaker areas included Professional, Scientific, and Technical Services (1/6 success), Health Care and Social Assistance (2/6), and Wholesale Trade (2/7), with Retail Trade also unsuccessful in its single task.

Deliverable file generation quality appears uneven rather than uniformly poor. Completed tasks in stronger sectors likely produced acceptable artifacts, but the combination of low overall completion, high retry volume, and mid-range self-assessed confidence indicates that artifact generation was not reliably stable. The subprocess bridge completed a meaningful share of jobs, but operational resilience and output consistency remain the main limitations in this run.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 50 |
| Success | 23 (46.0%) |
| Errors | 13 |
| Retried Tasks | 37 |
| Avg QA Score | 5.08/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 76,780ms |
| Max Latency | 192,825ms |
| Total LLM Time | 3839s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 42 |
| Successfully generated | 30 (71.4%) |
| Failed → dummy created | 12 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 6 | 6 | 0 |
| 2 | 31 | 4 | 27 |

## Quality Analysis

The QA distribution centers in the mid-range rather than at either extreme. An average self-assessed confidence of 5.08/10, with observed scores spanning 2 to 9, indicates that the model frequently judged its own outputs as partially adequate but not strongly reliable. This pattern is consistent with a run where some deliverables were complete and coherent, while others were incomplete, error-prone, or only minimally satisfactory despite eventual task completion.

Sector-level differences are material. Government had the highest LLM-evaluated quality at 7.7/10 with strong completion (3/4), making it the clearest positive outlier in both quality and efficiency. Information combined moderate-to-good quality (6.0/10) with the largest volume of successful tasks (6/10), suggesting the model could sustain acceptable performance there despite long runtimes. Real Estate and Rental and Leasing also delivered high completion (6/8), but its average QA was more modest at 5.4/10, implying that many outputs were completed successfully without being especially strong in self-assessed quality.

Lower-performing sectors show two different failure modes. Health Care and Social Assistance had both low completion (2/6) and low QA (3.7/10), pointing to substantive difficulty producing high-confidence outputs. Professional, Scientific, and Technical Services had very poor completion (1/6) but a middling QA average (5.0/10), which suggests that when outputs were produced they were not necessarily low-quality, but the execution path was fragile. Wholesale Trade and Manufacturing also remained below the overall benchmark on both completion and self-assessed confidence.

Latency does not show a simple linear relationship with quality. Government achieved the best quality with relatively low latency, which is favorable. However, Information posted one of the highest average latencies (97.9s) while still maintaining above-average QA, and Real Estate had high latency (83.9s) with only moderate QA. Conversely, Manufacturing and Professional, Scientific, and Technical Services had lower-than-average latencies but weak completion outcomes. The main pattern is that longer runtime sometimes supported acceptable results, but high latency alone did not guarantee stronger deliverables; execution stability and sector-specific task fit appear more predictive than raw time spent.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 3 | 1 | 33.3% | 4.5/10 | 78,907ms |
| Government | 4 | 3 | 75.0% | 7.67/10 | 49,862ms |
| Health Care and Social Assistance | 6 | 2 | 33.3% | 3.67/10 | 81,721ms |
| Information | 10 | 6 | 60.0% | 6.0/10 | 97,908ms |
| Manufacturing | 5 | 2 | 40.0% | 4.25/10 | 57,490ms |
| Professional, Scientific, and Technical  | 6 | 1 | 16.7% | 5.0/10 | 59,756ms |
| Real Estate and Rental and Leasing | 8 | 6 | 75.0% | 5.38/10 | 83,882ms |
| Retail Trade | 1 | 0 | 0.0% | 3.0/10 | 16,584ms |
| Wholesale Trade | 7 | 2 | 28.6% | 4.5/10 | 85,687ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 56971ms |
| 2 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ⚠️ qa_failed | Yes | 2 | 2/10 | 52464ms |
| 3 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ⚠️ qa_failed | Yes | 4 | 3/10 | 132723ms |
| 4 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 137712ms |
| 5 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 4 | 5/10 | 91503ms |
| 6 | `11dcc268…` | Manufacturing | Shipping, Receivin | ⚠️ qa_failed | Yes | 1 | 3/10 | 31027ms |
| 7 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 5/10 | 39635ms |
| 8 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 67604ms |
| 9 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 95889ms |
| 10 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ⚠️ qa_failed | Yes | 2 | 3/10 | 73134ms |
| 11 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 3 | 5/10 | 100831ms |
| 12 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 7 | 6/10 | 84023ms |
| 13 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 3 | 5/10 | 64658ms |
| 14 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 2 | 5/10 | 82336ms |
| 15 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ⚠️ qa_failed | Yes | 1 | 4/10 | 110510ms |
| 16 | `403b9234…` | Government | Recreation Workers | ✅ success | Yes | 2 | 8/10 | 68697ms |
| 17 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 5/10 | 83579ms |
| 18 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 72390ms |
| 19 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 7/10 | 41301ms |
| 20 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 5/10 | 63657ms |
| 21 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ⚠️ qa_failed | Yes | 3 | 4/10 | 72025ms |
| 22 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 51026ms |
| 23 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ⚠️ qa_failed | Yes | 3 | 4/10 | 92159ms |
| 24 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 5/10 | 63657ms |
| 25 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 7/10 | 56699ms |
| 26 | `6a900a40…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 45041ms |
| 27 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 11 | 5/10 | 97380ms |
| 28 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 87695ms |
| 29 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 83437ms |
| 30 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 38309ms |
| 31 | `8079e27d…` | Finance and Insurance | Financial and Inve | ⚠️ qa_failed | Yes | 2 | 3/10 | 75906ms |
| 32 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 25094ms |
| 33 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 64926ms |
| 34 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 7/10 | 41237ms |
| 35 | `90edba97…` | Health Care and Social | Registered Nurses | ⚠️ qa_failed | Yes | 2 | 2/10 | 107162ms |
| 36 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 14 | 6/10 | 122742ms |
| 37 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 7/10 | 98287ms |
| 38 | `a73fbc98…` | Government | Recreation Workers | ✅ success | - | 3 | 6/10 | 63936ms |
| 39 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 76905ms |
| 40 | `b57efde3…` | Wholesale Trade | Sales Representati | ⚠️ qa_failed | Yes | 2 | 4/10 | 78909ms |
| 41 | `c94452e4…` | Information | Film and Video Edi | ⚠️ qa_failed | Yes | 2 | 4/10 | 192825ms |
| 42 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 24981ms |
| 43 | `e222075d…` | Information | Film and Video Edi | ⚠️ qa_failed | Yes | 17 | 4/10 | 184883ms |
| 44 | `e996036e…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 87173ms |
| 45 | `f1be6436…` | Health Care and Social | Medical Secretarie | ⚠️ qa_failed | Yes | 5 | 4/10 | 77714ms |
| 46 | `f2986c1f…` | Retail Trade | Pharmacists | ⚠️ qa_failed | Yes | 1 | 3/10 | 16584ms |
| 47 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 70272ms |
| 48 | `f84ea6ac…` | Government | Administrative Ser | ❌ error | Yes | 0 | - | 41835ms |
| 49 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 3 | 6/10 | 72706ms |
| 50 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 3 | 9/10 | 76859ms |

## QA Issues

### ❌ `0353ee0c…` — score 2/10
- Core presumptive eligibility content is missing and replaced with placeholders.
- PDF/DOCX are templates, not the requested exhaustive consolidated guide.
- Output admits source links were not reviewed, violating task requirements.
  > 💡 Provide a completed PDF populated from all 19 source links with exhaustive eligibility details.

### ❌ `0818571f…` — score 3/10
- Listings are representative placeholders, not verified active June 2025 opportunities.
- Photos and maps are illustrative placeholders, not actual property materials.
- Output promised a PDF report but primarily delivered a DOCX template.
  > 💡 Provide verified active listings with real photos, maps, and complete transaction data in final files.

### ✅ `11593a50…` — score 5/10
- Shortlist PDF is 3 pages, not the required 2 pages.
- Map PDF content was not previewed, so pinned map requirement is unverified.
- Listings appear synthetic and not clearly sourced from MLSLI.com.
  > 💡 Provide a verified 2-page shortlist and a visible one-page pinned map using real MLS-sourced listings.

### ❌ `11dcc268…` — score 3/10
- Moved To uses NOT FOUND instead of assigned line locations.
- Report includes only three receipts without proving all daily receipts.
- Special handling for P11-P09457-01 is missing.
  > 💡 Cross-reference all receipts with Inv on line and populate correct destinations and partial move balance.

### ✅ `15d37511…` — score 5/10
- Year 1 total gross margin value is missing from the summary row.
- Client estimate was misread as 2,000 each product, not combined total.
- Text claims revenue projection, but workbook shows only gross margin figures.
  > 💡 Add the missing total, correct combined volume allocation, and include revenue totals in the spreadsheet.

### ❌ `24d1e93f…` — score 3/10
- Workbook uses assumed prices instead of quoted vendor values.
- Summary sheet lacks populated NPV comparison and recommendation fields.
- Extra DOCX file was produced beyond requested deliverable.
  > 💡 Rebuild the workbook using actual quotation data and complete the summary recommendation.

### ✅ `327fbc21…` — score 5/10
- Text response promises workbook creation instead of reporting completed results.
- Unexpected PNG file produced; not requested in original task.
- Total Stores plan misses comparable target of about -15% to LY.
  > 💡 Report actual completed outputs and align topline totals more closely to the stated planning target.

### ✅ `38889c3b…` — score 6/10
- Exports are 32-bit float, not requested 24-bit float WAV.
- Duration appears about 1:56, not approximately 2:17.
- No evidence the provided drum reference track was actually used.
  > 💡 Export correct specs, match target length, and document verified drum-track synchronization.

### ✅ `3940b7e7…` — score 5/10
- Report contains inferred placeholders instead of extracted CFD details.
- Simulation environment and boundary conditions are incomplete or speculative.
- Extra XLSX and PNG files were produced beyond the requested PDF deliverable.
  > 💡 Provide a fully data-backed PDF with explicit CFD parameters and no speculative placeholders.

### ✅ `3c19c6d1…` — score 5/10
- PPTX content was not verified against required slide details.
- Output mentions reference files not provided in evidence.
- Extra PNG file was produced without explicit requirement.
  > 💡 Verify the PPTX slide-by-slide and align outputs strictly to stated requirements.

### ❌ `3f821c2d…` — score 4/10
- Workbook lacks visible side-by-side Stores, E-commerce, Omni flow tables.
- Last-year comparison tables are not evident in the previewed sheet.
- Preview does not confirm required monthly and seasonal turn formulas.
  > 💡 Include clearly labeled channel tables with LY comparisons and visible working formulas on dedicated sheets.

### ✅ `403b9234…` — score 8/10
- PPTX content cannot be verified from the provided preview.
- Text response promises creation rather than summarizing completed deliverable.
  > 💡 Provide slide titles or a brief content summary to verify all required topics are covered.

### ✅ `40a8c4b1…` — score 5/10
- Workbook content cannot be verified against source scheduling priorities.
- One topic cell contains nan, indicating incomplete population.
- Text claims notes or alternate dates without confirming required source alignment.
  > 💡 Verify all scheduled topics against the source documents and replace incomplete cells.

### ✅ `476db143…` — score 7/10
- Email PDF is generic and not addressed to specific residents.
- Tracking PDF includes only five residents; source completeness is unverified.
- Email says residents may request changes, conflicting with existing noted responses.
  > 💡 Personalize resident notices and verify every September move-out from source files is included.

### ✅ `4b894ae3…` — score 5/10
- Report cites impossible 65-second duration despite later 1:45 edit spot.
- Response promises defensive inspection due to missing analysis, indicating workflow confusion.
- Extra DOCX report was delivered though not requested.
  > 💡 Verify source timing and deliver only the required WAV with accurate supporting details.

### ❌ `4d1a8410…` — score 4/10
- Master schedule preview lacks the required detailed timing table.
- Applicant itineraries omit visible personalized times and schedule details.
- Response says three deliverables, but task requested two deliverables.
  > 💡 Include full timed tables and personalized one-page itineraries with explicit interview and tour schedules.

### ✅ `5349dd7b…` — score 6/10
- Historical rates were not researched via search engines as required.
- Workbook relies on offline assumptions instead of verified published sources.
- Extra large flat-rate analysis appears incomplete or unsupported across carriers.
  > 💡 Add cited web-sourced rates and fully validate each carrier-size recommendation in the workbook.

### ❌ `5ad0c554…` — score 4/10
- DOCX preview shows only cover text, not brochure body content.
- Output admits it did not use the referenced source items.
- NAR agreement details appear insufficiently documented in the file.
  > 💡 Include complete double-sided brochure content tied to the referenced buyer-service milestones.

### ✅ `6074bba3…` — score 5/10
- DOCX still contains [Insert Graph] placeholders.
- Response admits illustrative comps due to missing dataset.
- Required 5–10 sold and 3–5 active counts aren't verified.
  > 💡 Populate the template fully with verified comps and embedded graphs before delivery.

### ✅ `61f546a8…` — score 7/10
- Report omits vendor availability source details and scheduling rationale.
- DOCX preview lacks populated tables, suggesting inconsistent file content.
- Text response promises creation but doesn't summarize actual scheduled results.
  > 💡 Ensure both files fully present the completed schedule and briefly summarize key outcomes in the response.

### ✅ `6d2c8e55…` — score 5/10
- No evidence dates avoid holidays or conferences.
- Article PDFs are citation handouts, not accessible full articles or link PDFs.
- Draft email is DOCX, not an email-ready message with attachments.
  > 💡 Provide verified schedule details and compliant article files, then draft the review email in email format.

### ❌ `8079e27d…` — score 3/10
- Workbook uses placeholder companies instead of real S&P 500 constituents.
- Public web data requirement was not fulfilled due to no live retrieval.
- Sub-sector and company outputs contain fabricated values and notes.
  > 💡 Rebuild the workbook with real S&P 500 data from public sources and verified constituent names.

### ✅ `87da214f…` — score 6/10
- Text response promises deliverables but omits actual findings and financial figures.
- PPTX content cannot be verified from preview for required slides and policy update option.
- No evidence claims were assessed against attached policy parameters.
  > 💡 Verify the slide deck includes quantified results, reimbursement percentages, and explicit policy-based claim determinations.

### ✅ `8c8fc328…` — score 7/10
- Text response promises a DOCX rather than presenting completed work.
- File preview is truncated, limiting verification against reference voiceover.
- No evidence it specifically used the attached reference document content.
  > 💡 Ensure the response confirms completion and the script clearly reflects the provided reference material.

### ❌ `90edba97…` — score 2/10
- Workbook lacks required monthly numeric lab entries.
- Output adds an unrequested summary document.
- Medication changes are placeholder notes, not protocol-based actions.
  > 💡 Populate all tracker sheets with exact monthly values and protocol-driven treatment changes only.

### ✅ `94925f49…` — score 6/10
- Reports appear to use fallback data instead of verified online sources.
- Required school metrics may be incomplete or inconsistently documented.
- No evidence all nearby homes were sourced from active public listings.
  > 💡 Verify every PDF with cited live sources and complete all requested school metrics.

### ✅ `99ac6944…` — score 7/10
- PDF preview shows only four pages; required last-page spreadsheet image is unclear.
- Proposal references one dual IEM system, not clearly two independent RF mixes.
- Text response promises creation, not a completed summary of actual selections.
  > 💡 Verify the PDF includes all required pages and clearly documents two separate singer mixes.

### ✅ `a73fbc98…` — score 6/10
- No evidence assignments honor specific adjacency requests.
- Electricity placements rely on assumptions, not confirmed layout outlets.
- Original layout update itself is not clearly provided.
  > 💡 Include verified layout-based assignments and explicitly document how each vendor request was satisfied.

### ❌ `b57efde3…` — score 4/10
- Workbook uses sample leads, not reviewed official exhibitor list.
- Deliverable admits inability to verify exhibitor status and product fit.
- Task required completed prospecting findings, not a template.
  > 💡 Review the official exhibitor list and populate verified company-specific leads and findings.

### ❌ `c94452e4…` — score 4/10
- Used mock visuals instead of required publicly available stock footage.
- Used original generated music instead of sourced stock music.
- Added storyboard PDF, but required deliverable was only final MP4.
  > 💡 Provide the exact 15-second MP4 using sourced stock footage and stock music matching the script.

### ❌ `e222075d…` — score 4/10
- Used placeholder local visuals instead of stock footage previews.
- Direct stock and music links log is missing.
- PDF packet is incomplete and only one page.
  > 💡 Provide actual watermarked stock preview clips, direct source links, and a complete review packet.

### ❌ `f1be6436…` — score 4/10
- Used generated placeholder evidence instead of live screenshots.
- Lodging used July proxy dates, not conference dates.
- Travel section omits specific airline and flight times.
  > 💡 Use live dated sources and include exact conference-date bookings with full itemized details.

### ❌ `f2986c1f…` — score 3/10
- Medications were not identified using Drugs.com as required.
- Spreadsheet contains only NA instead of each medication shown.
- Workbook structure includes extra notes instead of a complete medication list.
  > 💡 Identify each visible pill from the image and populate one row per medication with required fields.

### ✅ `f5d428fd…` — score 6/10
- Text response promises creation instead of summarizing completed deliverable.
- Photo credits list platforms, not specific royalty-free image sources or links.
- Source research citations from requested travel references are not shown.
  > 💡 Include explicit source citations and specific image attributions within the PDF and response.

### ✅ `f9a1c16c…` — score 6/10
- No evidence the PDF includes required input and output lists.
- Text response promises work instead of describing completed deliverable.
- File preview cannot verify labels, numbering, or stage orientation.
  > 💡 Provide a verifiable PDF with visible lists, labels, numbering, and a completion-focused summary.

### ✅ `ff85ee58…` — score 9/10
- Peak limit uses dBFS, not LUFS, in report.
- Timing correction evidence is summarized, not demonstrated.
  > 💡 Include measured true peak and clearer sync/timing verification details in the report.

## Failure Analysis

Execution errors were dominated by brittle code-generation and environment assumptions rather than ambiguous task intent. Several failures came from library/API misuse or version drift: invalid python-docx XML attribute handling in 02aa1805, merged-cell writes in openpyxl in 1752cb53, deprecated pandas frequency alias use in 1d4672c8, and wrong enum assignment in python-docx in f84ea6ac. A second execution subgroup was schema brittleness in spreadsheet-heavy tasks, where code assumed exact headers that were absent or differently named, producing shape or KeyError failures in 105f8ad0, 6a900a40, 7d7fc9a7, and e996036e. Compared with successful workbook/report tasks such as dfb4e0cd, a73fbc98, and 40a8c4b1, the weaker runs tended to skip dataset introspection and move straight into hard-coded transformations.

Among completed but low-scoring tasks, the dominant pattern was structurally correct artifacts with unverifiable, placeholder, or partially fabricated content. Real-estate work often completed file generation but relied on synthetic listings, illustrative photos/maps, missing graphs, or unverified MLS/public data: 0818571f, 5ad0c554, 6074bba3, 94925f49, and even the successful 11593a50 all show this behavior. The same pattern appeared in finance and healthcare research tasks where public-web evidence or exact schedule/eligibility details mattered: 8079e27d used placeholder S&P 500 data, 0353ee0c left PACT Act placeholders, 90edba97 omitted required monthly lab values, and f1be6436 used proxy travel dates. These contrast with stronger internally grounded tasks such as dfb4e0cd and 327fbc21, where the requested output could be built from local structured inputs without broad external verification.

Sector and occupation clustering was strong. Professional, Scientific, and Technical Services was the clearest execution hotspot: only 3c19c6d1 succeeded, while all three Software Developer tasks (4122f866, 7de33b48, 854f3814) failed at code generation time and the accounting task 7d7fc9a7 failed on column assumptions. Information split sharply by occupation: Audio and Video Technicians were consistently strong (38889c3b, 4b894ae3, 99ac6944, f9a1c16c, ff85ee58 all succeeded with qa_score 5-9), while Film and Video Editors went 1/5 with resource, encoding, and sourcing problems (75401f7c, a941b6d8, c94452e4, e222075d). Government remained the most stable multi-task sector, with high-confidence successes in 403b9234 and dfb4e0cd, suggesting that concise presentation/reporting tasks over bounded inputs were a better fit than open-ended package generation or media compositing.

Retries were a weak recovery mechanism in this run. All 13 non-retried tasks succeeded, while only 10 of 37 retried tasks ended in success; every qa_failed task and every error task had already been retried, so retries usually did not change the underlying failure mode. Latency also did not rescue difficult jobs: some of the longest runs still failed or had low self-QA, including 0818571f (132.7s, qa_failed), 105f8ad0 (137.7s, error), c94452e4 (192.8s, qa_failed), and e222075d (184.9s, qa_failed), whereas high-confidence successes like dfb4e0cd (25.0s, qa_score 9) and 8c8fc328 (41.2s, qa_score 7) were much faster. Complexity mattered most when tasks combined multi-file generation, live/source verification, and precise media specs, which explains why audio mixing was relatively robust but video compositing, stock-footage assembly, and externally verified market research were not.

## Recommendations

Harden execution with a mandatory preflight and compatibility layer before any file writing. Generated code should first parse/lint itself, inspect workbook sheets and column names, detect merged cells, and verify library enums/APIs before mutation. That would likely have prevented syntax-package failures in 4122f866, 7de33b48, and 854f3814, spreadsheet/header crashes in 6a900a40 and 7d7fc9a7, and library misuse in 02aa1805, 1752cb53, 1d4672c8, and f84ea6ac. A simple rule of "probe input schema, then transform" would reduce a large share of hard execution failures seen in spreadsheet and document tasks.

Route evidence-bound tasks through a stricter research-and-citation prompt, and do not let placeholder fallbacks count as completion. For real-estate, finance, healthcare, and wholesale research tasks, require an intermediate manifest listing every external source actually used, every required field populated, and every unresolved field flagged for regeneration. This directly targets the recurring synthetic-data pattern in 0818571f, 0353ee0c, 8079e27d, b57efde3, 90edba97, and f1be6436, while preserving the stronger behavior seen on bounded-input tasks like dfb4e0cd and a73fbc98. If live verification is unavailable, the system should switch to a clearly limited source-summary mode rather than fabricating representative data.

Use task-family-specific execution profiles instead of a mostly uniform subprocess strategy. Audio tasks already show that the environment can succeed when the pipeline is narrow and spec-driven, so keep that profile for jobs like ff85ee58 and 99ac6944, but give video-editing tasks a different sandbox with chunked frame processing, ffmpeg-first workflows, binary-safe subprocess capture, and explicit memory ceilings. That would address the OpenCV memory failure in a941b6d8 and the stderr decoding failure in 75401f7c, and it should reduce the long, low-yield render loops seen in c94452e4 and e222075d. Similarly, Software Developer tasks should be routed through a compile/test/package workflow before zipping outputs, because all three developer errors were code-validity failures rather than content-understanding failures.

Retune QA gates and retry policy so retries are conditional on a changed strategy, not just another pass. Since 27 of 37 retried tasks still ended non-success, the second attempt should automatically branch into schema-inspection mode for workbook errors, evidence-collection mode for public-data tasks, or simplified deliverable mode when file-count/format drift is detected. Add acceptance checks for exact file types and counts, no future-tense "I will create" language, no placeholder strings such as template markers, and sector-specific minima such as citation completeness for 0818571f and 94925f49, schedule completeness for 4d1a8410 and 90edba97, and media-spec compliance for 38889c3b and 4b894ae3. Self-QA can be used as a trigger here: outputs below roughly 5 on evidence-heavy tasks should be automatically revised or flagged instead of being treated as finished.

## Deliverable Files

- `0353ee0c…` (Health Care and Social Assistance): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 4 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 4 file(s)
- `11dcc268…` (Manufacturing): 1 file(s)
- `15d37511…` (Wholesale Trade): 1 file(s)
- `24d1e93f…` (Manufacturing): 2 file(s)
- `327fbc21…` (Wholesale Trade): 3 file(s)
- `38889c3b…` (Information): 7 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `403b9234…` (Government): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 3 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 11 file(s)
- `8079e27d…` (Finance and Insurance): 2 file(s)
- `87da214f…` (Finance and Insurance): 4 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `90edba97…` (Health Care and Social Assistance): 2 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 14 file(s)
- `99ac6944…` (Information): 5 file(s)
- `a73fbc98…` (Government): 3 file(s)
- `b57efde3…` (Wholesale Trade): 2 file(s)
- `c94452e4…` (Information): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `e222075d…` (Information): 17 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `ff85ee58…` (Information): 3 file(s)
