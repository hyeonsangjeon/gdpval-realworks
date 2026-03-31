# Experiment Report: GPT-5.4-Mini Reasoning NULL — Full Benchmark (Ablation 4/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp024_GPT54Mini_reasoning_null` |
| **Condition** | GPT-5.4-Mini reasoning=null (omitted) + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4-mini |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-30 |
| **Duration** | 97m 59s |
| **Generated At** | 2026-03-30T17:51:50.026439+00:00 |
| 🤗 HF Dataset | [exp024_GPT54Mini_reasoning_null](https://huggingface.co/datasets/HyeonSang/exp024_GPT54Mini_reasoning_null) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp024_GPT54Mini_reasoning_null/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This run evaluated gpt-5.4-mini under the GPT-5.4-Mini reasoning=null (omitted) condition, with the gpt-audio-1.5 preprocessor enabled, across the full 220-task benchmark in subprocess execution mode. Overall task completion was strong: 207 of 220 tasks completed successfully, for a 94.1% task completion rate, with 13 errors and 44 tasks requiring retry. Average end-to-end latency was 17,471 ms.

From an LLM-evaluated quality standpoint, the average Self-QA score was 6.74/10, with observed scores ranging from 2 to 9. This indicates that successful completions were generally assessed by the model as usable to solid rather than consistently high-confidence. The spread from low to high self-assessed confidence suggests uneven output quality across task types, even when execution completed successfully.

At the sector level, completion reliability was strongest in Government and Real Estate and Rental and Leasing, both at 25/25 successful tasks, and also strong in Wholesale Trade at 24/25. Retail Trade was notable for combining perfect completion (20/20) with the highest average Self-QA score among sectors. Lower completion counts appeared in Information and Professional, Scientific, and Technical Services, both at 22/25, with the latter also showing the weakest average self-assessed quality.

Deliverable file generation quality appears generally stable for completed tasks, with successful executions implying usable output artifacts in most cases. However, the 13 error cases represent direct deliverable-generation failures, and the 44 retries indicate some production instability or recoverable execution issues. In practical terms, the run shows strong output coverage, but with moderate confidence calibration and some inconsistency in final deliverable quality across sectors.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 207 (94.1%) |
| Errors | 13 |
| Retried Tasks | 44 |
| Avg QA Score | 6.74/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 17,471ms |
| Max Latency | 110,324ms |
| Total LLM Time | 3843s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 176 (95.1%) |
| Failed → dummy created | 9 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 26 | 26 | 0 |
| 2 | 18 | 5 | 13 |

## Quality Analysis

The Self-QA distribution centers in the mid-to-upper range rather than at the top end: the run averaged 6.74/10, with a minimum of 2 and a maximum of 9. That pattern suggests the model frequently judged its outputs as acceptable or good, but not uniformly strong. The low-end outliers matter because they indicate a subset of tasks where the model itself detected substantial weaknesses despite eventual completion in many cases.

Sector-level differences are meaningful. Retail Trade and Wholesale Trade posted the highest average Self-QA scores at 7.5/10, with Retail also achieving 20/20 completion, making it the strongest combined quality-and-reliability segment in this run. Government also performed well at 25/25 success and 7.0/10 average Self-QA. By contrast, Professional, Scientific, and Technical Services had the lowest average Self-QA score at 6.0/10 and only 22/25 successful tasks, indicating a comparatively harder domain for this configuration.

Some sectors showed strong completion without correspondingly high self-assessed confidence. Real Estate and Rental and Leasing completed all 25 tasks but averaged 6.5/10, and Manufacturing completed 23/25 at 6.5/10. Health Care and Social Assistance and Information both landed at 6.6/10, but Information was materially slower and had fewer successful tasks. No occupation-level breakdown is provided in the run summary, so observations are limited to sector-level behavior rather than role-specific patterns.

Latency does not show a positive correlation with LLM-evaluated quality in this run. Information had the highest average latency at 25,985 ms yet only a 6.6/10 average Self-QA, while Finance and Insurance was also slow at 24,906 ms with 6.7/10. In contrast, Retail Trade achieved the highest average Self-QA at a relatively low 13,765 ms, and Government combined solid quality with 14,422 ms latency. The main implication is that longer processing time in this configuration did not reliably translate into better self-assessed output quality or stronger deliverable outcomes.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 23 | 92.0% | 6.65/10 | 24,906ms |
| Government | 25 | 25 | 100.0% | 7.0/10 | 14,422ms |
| Health Care and Social Assistance | 25 | 23 | 92.0% | 6.57/10 | 14,043ms |
| Information | 25 | 22 | 88.0% | 6.59/10 | 25,985ms |
| Manufacturing | 25 | 23 | 92.0% | 6.48/10 | 17,370ms |
| Professional, Scientific, and Technical  | 25 | 22 | 88.0% | 5.95/10 | 15,389ms |
| Real Estate and Rental and Leasing | 25 | 25 | 100.0% | 6.48/10 | 14,665ms |
| Retail Trade | 20 | 20 | 100.0% | 7.45/10 | 13,765ms |
| Wholesale Trade | 25 | 24 | 96.0% | 7.5/10 | 15,953ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 4/10 | 16061ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 4/10 | 17601ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 9/10 | 16105ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 6/10 | 22844ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 13422ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 9436ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 9614ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 2 | 8/10 | 20935ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 9/10 | 12253ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | Yes | 3 | 6/10 | 22602ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 8/10 | 38457ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 3 | 5/10 | 24319ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 6 | 9/10 | 71774ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 2 | 7/10 | 39983ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | 9/10 | 21277ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 16072ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 6/10 | 19949ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 8/10 | 14711ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 8/10 | 14468ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 14707ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 9/10 | 15406ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 5 | 6/10 | 13500ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | Yes | 5 | 6/10 | 17271ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 2 | 4/10 | 17296ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | 9/10 | 14966ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 3/10 | 7774ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 7371ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 6108ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 7336ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 2 | 6/10 | 18538ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 6/10 | 16133ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 6/10 | 12397ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 6/10 | 17238ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 9/10 | 20138ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 4 | 6/10 | 18100ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 4/10 | 13298ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 19276ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 16347ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 6/10 | 19711ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 17848ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 13235ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 10383ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 3/10 | 11440ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 2/10 | 11385ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 17549ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 4/10 | 7615ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 6/10 | 18499ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 7/10 | 14040ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 1 | 4/10 | 16642ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 6/10 | 8876ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 4/10 | 8963ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 8/10 | 10655ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 6 | 6/10 | 21541ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | 8/10 | 12915ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 6/10 | 17604ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 9/10 | 8360ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 2 | 6/10 | 12061ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 5 | 4/10 | 110324ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 75308ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 39702ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 20203ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 2 | 8/10 | 28635ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 9/10 | 33317ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 6 | 8/10 | 27966ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 6/10 | 16672ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 8/10 | 23938ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 37183ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 9/10 | 33623ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 6/10 | 23708ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 6/10 | 42566ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 8/10 | 9599ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 10497ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 9/10 | 16462ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 1 | 4/10 | 12127ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 1 | 4/10 | 29455ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 6/10 | 14904ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 8/10 | 12438ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 4/10 | 12439ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 1 | 4/10 | 13544ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 6/10 | 17190ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 18561ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 15866ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 15296ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 19210ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | Yes | 2 | 8/10 | 19946ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 16001ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 6/10 | 25121ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 19729ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 9/10 | 18286ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 12806ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | 6/10 | 15826ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 6/10 | 9414ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 3 | 9/10 | 11690ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 8/10 | 17790ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | 7/10 | 18627ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 10522ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 11788ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 9/10 | 14999ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 6/10 | 17424ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 9732ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 9/10 | 17739ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 6/10 | 19765ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 3 | 4/10 | 18224ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 8/10 | 21553ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 4/10 | 29382ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 4/10 | 17195ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 2/10 | 11326ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | Yes | 1 | 7/10 | 9824ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 9/10 | 19280ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 17938ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 6/10 | 19473ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 6 | 4/10 | 19246ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 1 | 4/10 | 15262ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 6 | 8/10 | 24886ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 18626ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 17500ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 7855ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 16296ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 4/10 | 11600ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | 6/10 | 21893ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 6 | 4/10 | 15013ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 9/10 | 7646ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 11516ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 17851ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 8/10 | 14288ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 6141ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 7746ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | 8/10 | 9605ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | Yes | 1 | 4/10 | 11489ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 17410ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 19491ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 9/10 | 20925ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 9/10 | 8585ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 8142ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | 9/10 | 16273ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 13439ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 12788ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 15401ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 10534ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 13538ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 8/10 | 27392ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 7/10 | 34374ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 24122ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 8/10 | 43041ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 52463ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 9/10 | 11795ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 10 | 8/10 | 18151ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 8942ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 6/10 | 12275ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 8/10 | 13532ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | 4/10 | 15449ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 9/10 | 18086ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 24555ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 3/10 | 13388ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 12512ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | Yes | 2 | 3/10 | 14579ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 17118ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 1 | 9/10 | 14274ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 8/10 | 16634ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 4/10 | 18299ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | Yes | 1 | 8/10 | 10692ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 3/10 | 12593ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 9/10 | 9039ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 8/10 | 12640ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 9/10 | 15091ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 6 | 9/10 | 19586ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 7264ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 9062ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 13 | 4/10 | 19826ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 6/10 | 16016ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 4 | 8/10 | 17316ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 4/10 | 22302ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 10 | 4/10 | 18763ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 6/10 | 12600ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 6/10 | 13362ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 15422ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 4/10 | 13856ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 9/10 | 12388ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 13642ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 3 | 8/10 | 15952ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 13540ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 9286ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 8/10 | 21155ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 11334ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 3/10 | 10380ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 9/10 | 26341ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 4/10 | 10287ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 8/10 | 13946ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 9/10 | 7743ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 4/10 | 14471ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 11399ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 27979ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | Yes | 2 | 8/10 | 32410ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 8/10 | 20326ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 16356ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 8/10 | 15353ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 29074ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 14128ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 12836ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 12669ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 2/10 | 14809ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 10555ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 9605ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 8/10 | 15395ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 12097ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 6/10 | 14331ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 4 | 6/10 | 23048ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 1 | 3/10 | 14986ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 8/10 | 10883ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 8/10 | 24526ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 8/10 | 12428ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 8/10 | 11162ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 5 | 8/10 | 17029ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 1 | 4/10 | 7157ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 1 | 4/10 | 10464ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 13386ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 7394ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ✅ success | Yes | 2 | 6/10 | 5657ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 16842ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 6/10 | 14944ms |

## QA Issues

### ❌ `83d10b06…` — score 4/10
- Missing required separate 'Population' source tab in the final workbook.
- Sample sheet has only 10 columns; column K flagging is absent.
- Text mentions a Python script, but only the workbook was produced.
  > 💡 Add the Population tab, include column K flags, and remove unsupported script claims.

### ❌ `7b08cd4d…` — score 4/10
- Revenue withholding appears zero despite country-specific rates.
- Revenue detail lacks source separation by Tour Manager and production company.
- Text response is generic and does not confirm completed calculations.
  > 💡 Verify calculations, source breakdowns, and populate the workbook with finalized figures.

### ✅ `43dc9778…` — score 6/10
- No actual tax return calculations are shown.
- Text says files are saved in current directory, but paths differ.
- Potentially required forms may be incomplete or unverified.
  > 💡 Provide a fully calculated 1040 package with verified supporting forms and consistent file delivery.

### ❌ `f84ea6ac…` — score 3/10
- No actual research table content is shown in the document preview.
- The file appears to contain only a title and subtitle, not five studies.
- No evidence of required study details, findings, or government implications.
  > 💡 Populate the DOCX with a one-page five-row summary table and verify all required fields.

### ❌ `a328feea…` — score 3/10
- Document contains only a title and compliance note.
- Purpose, scope, definitions, and procedures are missing.
- No step-by-step phone-call reporting process is provided.
  > 💡 Expand the document with full policy sections and detailed reporting procedures.

### ✅ `27e8912c…` — score 8/10
- PDF is only 2 pages, not near the five-page maximum with appendix images.
- Checklist references images, but preview does not confirm actual embedded or appendix images.
- Text response is repetitive and slightly verbose.
  > 💡 Add verified reference images and expand the PDF to include a fuller appendix.

### ✅ `c44e9b62…` — score 6/10
- Briefing note preview is truncated; completeness cannot be verified.
- No evidence the Excel report includes required position-level reduction details.
- Text response is generic and does not confirm all task-specific requirements.
  > 💡 Verify all deliverables fully reflect the 4% reduction and required narratives.

### ✅ `f9a1c16c…` — score 5/10
- Missing professional visual clarity; PDF text appears garbled and overlapping.
- No evidence of sourced or crafted graphic icons as required.
- Companion DOCX was created, but the task requested only the stage plot PDF.
  > 💡 Rebuild the PDF with clean layout, clear icons, and accurate labeled stage positions.

### ✅ `ff85ee58…` — score 7/10
- Text says DOCX report was generated, which is extra and not requested.
- Loudness spec is misstated as -0.1 dB LUFS instead of peak limit.
- No verification that the WAV actually meets the loudness target.
  > 💡 Remove the extra report claim and verify the final audio meets all technical specs.

### ✅ `1b1ade2d…` — score 6/10
- No actual workflow details are provided in the text response.
- The response does not confirm the required approval and signoff structure.
- The document content appears truncated in the preview.
  > 💡 Include a complete workflow with approvals, change handling, and full signoff traceability.

### ✅ `93b336f3…` — score 6/10
- No evidence the Word document is 2–3 pages long.
- Cost assumptions appear inconsistent with the prompt's 1300 USD assembly figure.
- Text response mentions a PDF, but the task only required a Word document.
  > 💡 Revise the calculations to match the prompt and ensure the Word file is concise and complete.

### ✅ `05389f78…` — score 6/10
- Report content is truncated in the preview.
- No evidence of detailed INR calculations is shown.
- Recommendation may lack full quotation-based comparison.
  > 💡 Verify the report includes complete cost analysis and explicit vendor comparison.

### ✅ `a74ead3b…` — score 6/10
- Only a text response is shown; PPTX content cannot be verified.
- No evidence the presentations closely follow Sessions 13 and 14 manual content.
- Neutral images are produced, but slide completeness is unconfirmed.
  > 💡 Verify both PPTX files include all required slides and session-specific content.

### ✅ `bbe0a93b…` — score 6/10
- Spanish assessment is DOCX, not PDF.
- Resource guide preview appears truncated and may miss categories.
- Some resource guide text shows formatting errors.
  > 💡 Regenerate the Spanish PDF and verify all resource guide categories and formatting.

### ❌ `85d95ce5…` — score 4/10
- The report appears incomplete and still contains placeholder text.
- The file date and consent date are inconsistent with the task details.
- No evidence confirms the required 8-15 page polished final report content.
  > 💡 Verify the template was fully completed, remove placeholders, and align all dates with the task.

### ❌ `36d567ba…` — score 3/10
- Document preview shows only instructions, not the required 11 questions.
- Uniform Guidance references for topics 6 through 10 are missing.
- File appears too short for the requested 1-2 page questionnaire.
  > 💡 Revise the document to include all required two-part questions and cited Uniform Guidance references.

### ✅ `4c18ebae…` — score 6/10
- Text response claims DOCX and Excel creation, but SAR content is not verified.
- No explicit SAR narrative details or FinCEN-style findings are shown.
- Generated files may be incomplete despite valid filenames.
  > 💡 Provide the actual SAR narrative and confirm all deliverables fully match the task.

### ✅ `cebf301e…` — score 6/10
- Output is a design document, not a direct task completion artifact.
- Preview is truncated, so PDF export and extensibility details are unverified.
- No evidence the deliverable fully covers all required requirements.
  > 💡 Provide a complete deliverable with explicit coverage of every requirement and verifiable file contents.

### ✅ `c2e8f271…` — score 6/10
- Only 3 pages; the task requested no longer than 6 pages, but content may be incomplete.
- Preview is truncated, so full coverage of required standards cannot be verified.
- Text response mentions PDF generation, but the task only required a Word document.
  > 💡 Provide a complete DOCX-focused draft and ensure all required sections are fully visible and verifiable.

### ✅ `2ea2e5b5…` — score 6/10
- Strategic level mapping appears incomplete in the provided task text.
- No evidence the PPTX includes all required classification tables.
- Text response is generic and does not summarize findings.
  > 💡 Verify all category mappings and ensure the deck includes complete, accurate analysis.

### ✅ `a45bc83b…` — score 6/10
- Text response is generic and not a complete deliverable summary.
- POC plan preview is truncated, so completeness cannot be verified.
- Architecture summary content and diagram details are not visible in the preview.
  > 💡 Provide full deliverable content and verify the diagram and summary explicitly meet all requirements.

### ❌ `a10ec48c…` — score 4/10
- No restaurant tables or row details are visible in the document preview.
- Restaurant links, hours, descriptions, directions, and categories are missing from the preview.
- Cuisine sections appear only as headings, suggesting incomplete content.
  > 💡 Populate each cuisine table with verified restaurant entries and full concierge details.

### ✅ `fccaa4a1…` — score 6/10
- PDF has 3 pages, not the requested 2.
- Requirements section appears truncated in the preview.
- No clear evidence of all exclusions and age details.
  > 💡 Revise the PDF to exactly two pages and fully include all required inclusions, exclusions, and requirements.

### ✅ `f5d428fd…` — score 6/10
- PDF is four pages, not the requested two pages.
- No visible evidence of royalty-free photos in the PDF preview.
- Eleuthera day content appears truncated in the preview.
  > 💡 Condense to two pages and verify all images and destination sections are complete.

### ✅ `2fa8e956…` — score 6/10
- One winery has placeholder distance and drive time.
- Some winery details appear truncated in the preview.
- Need confirmation the document stays within four pages.
  > 💡 Verify all winery fields, complete missing data, and confirm final page count.

### ✅ `0e4fe8cd…` — score 6/10
- Task appears incomplete in the prompt preview.
- No evidence of factual link verification for all providers.
- Potentially missing full four-day detail in the workbook.
  > 💡 Verify all itinerary details and ensure each day is fully populated with sourced links.

### ❌ `aa071045…` — score 3/10
- Service form lacks customer, vehicle, damage, and charge details.
- Report contains nan categories instead of valid labels.
- Operational conclusions are generic and not data-specific.
  > 💡 Rebuild both files with complete task data and correct summary calculations.

### ❌ `476db143…` — score 2/10
- Tracking file is empty and missing resident data.
- Email PDF contains placeholder summary without actual recipients.
- Required move-out dates and inspection dates are not populated.
  > 💡 Populate both PDFs with the full September resident list and scheduled dates.

### ❌ `f3351922…` — score 4/10
- Output is a file summary, not the requested email content.
- The response does not directly answer the two requested topics.
- The preview appears truncated and may omit the full deliverable.
  > 💡 Provide the complete professional email text with all requested TSP details.

### ✅ `61717508…` — score 6/10
- Quick training PDF is only 3 pages, not about 10.
- Second deliverable is a PDF, but a DOCX was also produced.
- Text response promises two PDFs, but file set includes an extra non-PDF file.
  > 💡 Revise the deck to about 10 pages and remove the extra DOCX file.

### ✅ `0ed38524…` — score 7/10
- Summary is two pages, not one page as requested.
- District detail may be too long for a concise general summary.
- Talking points are present, but file content should be verified for board-ready brevity.
  > 💡 Condense the district summary to one page and keep both PDFs tightly focused.

### ❌ `87da214f…` — score 4/10
- No evidence the deck includes required financial impact figures.
- Policy review and claim analysis details are not verifiable from the preview.
- Text response is generic and does not confirm all required slide sections.
  > 💡 Verify the deck contains all required sections and explicit reimbursement calculations.

### ✅ `d025a41c…` — score 6/10
- Text response is generic and not a true deliverable summary.
- File content preview is truncated, so completeness cannot be verified.
- Likely missing direct confirmation of all case-specific requirements.
  > 💡 Verify the document fully addresses all three cases and required formatting.

### ❌ `401a07f1…` — score 4/10
- The DOCX appears truncated and ends mid-sentence.
- No actual reference links are visible in the preview.
- The task required a 500-word editorial, but length is unverified.
  > 💡 Provide a complete DOCX with visible source links and a fully finished 500-word editorial.

### ✅ `afe56d05…` — score 8/10
- Preview is truncated, so full word count cannot be verified.
- No obvious file-type or content errors were shown.
- Text response is professional but mentions validation without evidence.
  > 💡 Confirm the document length and hyperlink formatting before delivery.

### ✅ `9a8c8e28…` — score 6/10
- Guide preview is truncated, so completeness cannot be fully verified.
- No evidence the quiz includes answer key explanations and scoring guide.
- No confirmation all required PDFs contain final, polished content.
  > 💡 Verify the full PDFs include all required sections and complete quiz materials.

### ✅ `ec2fccc9…` — score 6/10
- Word count appears below the requested 1,500-word range.
- Reference artist links and news links are not verifiable from the preview.
- Secondary keyword list is mentioned, but SEO research evidence is not shown.
  > 💡 Expand the article, verify all required links, and include the four researched secondary keywords clearly.

### ✅ `e222075d…` — score 6/10
- No actual video file was produced.
- Media links are search URLs, not direct clip links.
- Production log appears incomplete and truncated.
  > 💡 Create the 30-second MP4 and provide exact source links with a complete edit log.

### ❌ `c94452e4…` — score 4/10
- Text admits placeholder content instead of final stock footage.
- No evidence of sourced royalty-free clips or licensed music.
- Deliverable may not match exact script and PSD requirements.
  > 💡 Verify the edit uses real licensed assets and matches the provided script exactly.

### ✅ `e21cd746…` — score 8/10
- No obvious content gaps in the 5-slide deliverable.
- Text response is professional and confirms PPTX and PDF outputs.
- Minor risk that valuation figures may be dated or approximate.
  > 💡 Verify all valuation and multiple figures against current market sources.

### ✅ `c7d83f01…` — score 8/10
- Notebook file was not produced; only a Python script is listed.
- Visualizations are mentioned but not shown in the delivered files.
- Monte Carlo results appear noisier than the summary implies.
  > 💡 Provide the notebook and generated plots, and clarify Monte Carlo limitations.

### ✅ `46b34f78…` — score 6/10
- Memo appears to use generic issuer analysis instead of specific issuer-level bond data.
- Reference data preview suggests missing oil and natural gas source extraction details.
- Text response promises validation but does not confirm document completeness or exact constraints.
  > 💡 Add named issuer bond analysis with live data and verify all required constraints are explicitly addressed.

### ✅ `a1963a68…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of appendix or Q&A page content.
- Text response is duplicated and slightly repetitive.
  > 💡 Verify the full PDF includes all required sections and remove duplicate wording.

### ✅ `b78fd844…` — score 6/10
- PDF is only one page and may not fully cover all required analysis.
- Generated text omits the detailed risk mitigation and contingency plans in the preview.
- The response does not confirm the Word/PDF content meets the fifteen-page limit with full task coverage.
  > 💡 Revise the report to include complete risk, contingency, and allocation details within the required length.

### ✅ `4520f882…` — score 6/10
- Workbook exists, but generated content may be incomplete.
- Text response promises a file, but no final confirmation is shown.
- No evidence of full CBA-driven validation across all payroll categories.
  > 💡 Verify the workbook formulas, compliance checks, and final deliverable completeness.

### ❌ `e996036e…` — score 4/10
- Shipments total 255,000 conflicts with task's 225,000 assumption.
- Only one workbook file is shown; scenario completeness is unclear.
- Text response does not confirm the required 5–6 sentence executive summary.
  > 💡 Revise the workbook to match the stated assumptions and include the full summary.

### ❌ `327fbc21…` — score 4/10
- No actual sales summary is provided in the text response.
- Workbook content may be incomplete or unverified from preview.
- No evidence of closed-store LY volume summary.
  > 💡 Add the required May summary and verify all store-level calculations and rollups.

### ✅ `6dcae3f5…` — score 6/10
- Text response promises a Word email, but task required only the Excel deliverable.
- The email content appears truncated and may be incomplete.
- No evidence the ACGME requirement link was incorporated into the workbook.
  > 💡 Verify workbook requirements and ensure all requested benchmark and graduation requirement data are fully included.

### ❌ `0353ee0c…` — score 4/10
- PDF appears incomplete and truncated.
- Content is mostly generic placeholders, not exhaustive source consolidation.
- No evidence of exact locations, dates, or conditions from all links.
  > 💡 Rebuild the PDF with fully extracted, source-specific PACT Act details from every reference link.

### ❌ `40a8c4b1…` — score 4/10
- Response is only a plan, not a completed deliverable.
- No evidence the schedule meets all required timing constraints.
- Text mentions current directory, not the attached final file.
  > 💡 Provide the finished workbook and confirm required events and dates were scheduled correctly.

### ✅ `4d1a8410…` — score 6/10
- Schedule content appears incomplete; only headings are visible, not the full timetable.
- No evidence the required applicant names, room assignments, and tour order are fully detailed.
- Sample itineraries seem generic and may lack the requested one-page personalized content.
  > 💡 Verify the DOCX files include the complete schedule, all applicant details, and personalized itineraries.

### ✅ `eb54f575…` — score 8/10
- PDF is only 3 pages and may be too brief for executive review.
- Ballistics section is somewhat general and lacks specific FBI data citations.
- The preview shows a truncated word, suggesting minor formatting issues.
  > 💡 Add concise FBI data references and proofread the PDF formatting before final submission.

### ✅ `22c0809b…` — score 8/10
- Form content appears complete, but the preview is truncated.
- No obvious formatting verification of the 2-4 page PDF is shown.
- Text response is professional but mentions an extra source document.
  > 💡 Confirm final PDF pagination and review the full form for layout accuracy.

### ✅ `efca245f…` — score 6/10
- Summary file is a DOCX, but the task requested an Excel spreadsheet deliverable.
- The output mentions a separate summary file instead of embedding scenario implications in the workbook.
- Truck Grill Guard production appears included in scenarios that should exclude it.
  > 💡 Revise the workbook to fully satisfy all three scenarios and include the required implications within Excel.

### ✅ `9e39df84…` — score 6/10
- Dashboard sheet appears incomplete or misaligned.
- Summary KPI values are not fully populated.
- Text response mentions validation, not verified in file.
  > 💡 Populate all dashboard elements and verify formulas, charts, and validations in the workbook.

### ✅ `bd72994f…` — score 6/10
- PDF has only 2 pages, not 4-6 slides.
- No clear evidence the looks came from the brand's official 2025 resort collection.
- Text response mentions unavailable assets instead of confirming task completion.
  > 💡 Regenerate with 4-6 slide PDF using official collection references and clearer deliverable language.

### ✅ `211d0093…` — score 6/10
- Task list content appears incomplete or truncated in the preview.
- No evidence the PDF includes all required employee name, initials, and notes fields for every task.
- Manager sign-off placement at the very end is not fully verified.
  > 💡 Verify the full PDF includes every task and all required sign-off fields.

### ✅ `cecac8f9…` — score 7/10
- Files are PDFs, but the preview shows only partial content.
- The plan preview is truncated, so completeness cannot be fully verified.
- The text response is generic and does not confirm key deliverable details.
  > 💡 Verify full content coverage and ensure the response summarizes the completed deliverables more specifically.

### ✅ `8f9e8bcd…` — score 6/10
- Types of objections lack descriptions and examples.
- Practice section appears missing the required objection-response table.
- Text response is generic and does not confirm completed content details.
  > 💡 Revise the document to include full type descriptions, examples, and a practice table.

### ✅ `4d61a19a…` — score 6/10
- Promotion dates appear inconsistent, with end date earlier than start date.
- Excel sheet columns are unclear and not properly labeled.
- No evidence the PowerPoint stays under eight slides.
  > 💡 Fix the date order, clarify the template fields, and verify slide count.

### ✅ `40a99a31…` — score 6/10
- Excel content was not verified from the preview.
- Report preview appears truncated before completion.
- No explicit evidence of all six cameras and seven LIDAR units in files.
  > 💡 Verify the spreadsheet columns and confirm all required devices are fully documented.

### ❌ `b9665ca1…` — score 4/10
- Missing required detailed wiring labels and button-box conventions.
- Output includes extra DOCX and PNG files not requested.
- Text response is generic and does not confirm all specified connections.
  > 💡 Revise the schematic to explicitly show every required wire label and connection.

### ❌ `be830ca0…` — score 4/10
- Cannot verify slide content from the preview.
- No evidence all required charts and A3 sections are included.
- Text response is only a delivery statement, not a completed analysis summary.
  > 💡 Inspect the PPTX to confirm every required slide, chart, and section is present.

### ❌ `cd9efc18…` — score 4/10
- PDF is only 4 pages, not the required 8 to 11 pages.
- The output omits the requested notary execution details in the preview.
- Trust and guardian provisions appear incomplete or truncated.
  > 💡 Revise the will to include all requested clauses and produce a full 8 to 11 page PDF.

### ❌ `a97369c7…` — score 2/10
- Output is not a JSON object and violates the required format.
- Response discusses producing files instead of delivering the memo analysis.
- No assessment of the legal issues or file content is provided.
  > 💡 Return only the required JSON with a concise quality assessment.

### ✅ `3f625cb2…` — score 7/10
- PDF is only two pages, but the task required no more than three.
- The memo appears complete, but the preview is truncated before confirming all recommendations.
- Text response promises validation steps, which are not part of the requested deliverable.
  > 💡 Confirm the PDF fully covers all required topics and remove unnecessary process commentary.

### ✅ `8314d1b1…` — score 6/10
- Text response promises a PDF, but the task only required a Word document.
- Memo content may be incomplete or truncated in the preview.
- Need confirmation the March 2025 DGCL amendments are accurately analyzed.
  > 💡 Verify the full memo covers all required authorities and remove unsupported deliverable claims.

### ✅ `5e2b6aab…` — score 6/10
- Only one sub-assembly drawing is shown; all required sub-assemblies may be missing.
- PDF content appears truncated and may not fully show title block or balloons.
- Text response is generic and does not confirm all task requirements were met.
  > 💡 Verify every required drawing and STEP deliverable is complete and clearly documented.

### ❌ `46fc494e…` — score 4/10
- Back-face temperature is reported as constant, suggesting a likely model error.
- Required 22-node transient calculation details are not shown in the report.
- The text response does not mention the mitigation threshold condition.
  > 💡 Verify the thermal model outputs and include the requested transient results explicitly.

### ❌ `3940b7e7…` — score 4/10
- Key numerical results are all zero, suggesting placeholder or incomplete data.
- The report omits a clear, complete conclusion in the preview.
- The text response does not confirm all required analysis details were actually included.
  > 💡 Populate the report with real CFD values and verify all required sections are complete.

### ✅ `74d6e8b0…` — score 6/10
- Text response promises a PDF, but the task required only a Word document.
- Preview shows the guideline content is truncated and may omit required citations.
- No clear evidence the document fully covers all requested prescribing details.
  > 💡 Verify the Word file includes complete, cited guidelines and remove unsupported deliverable claims.

### ✅ `61b0946a…` — score 6/10
- Task appears truncated before the full original prompt requirements are addressed.
- Proposal content preview is incomplete, so required sections cannot be fully verified.
- No evidence of the referenced Excel budget file being used directly.
  > 💡 Provide the complete proposal with all required sections and verify budget-based calculations.

### ❌ `61e7b9c6…` — score 4/10
- Spreadsheet contains blank and duplicate rows.
- No evidence of FDA-approved/off-label categorization completeness.
- Text response is generic and does not confirm actual data sourcing.
  > 💡 Verify the formulary is deduplicated, complete, and sourced before delivery.

### ✅ `c9bf9801…` — score 6/10
- Guide content is not verified in the preview.
- No evidence of 4-month and 8-month evaluation forms.
- Text response is a promise, not a completed deliverable.
  > 💡 Confirm the guide includes all required sections and evaluation forms.

### ❌ `f1be6436…` — score 4/10
- Task instructions were truncated before lodging and total calculations were fully verified.
- Registration cost is $0.00, which appears implausible and may be incorrect.
- The document preview shows only 13 paragraphs, suggesting incomplete content or missing screenshots.
  > 💡 Verify all conference costs, complete the missing sections, and ensure screenshots are embedded.

### ✅ `ef8719da…` — score 6/10
- No actual reported pitch was provided in the text response.
- The response describes a DOCX file instead of summarizing its contents.
- Required hyperlinks are not visible in the previewed content.
  > 💡 Provide the pitch text directly with explicit links and all required elements.

### ❌ `5d0feb24…` — score 4/10
- No actual review of the draft text is shown.
- Response promises a DOCX but only summarizes file creation.
- Missing specific edits, accuracy checks, and source-linked feedback.
  > 💡 Provide concrete, draft-specific editorial comments with cited science corrections.

### ✅ `6974adea…` — score 6/10
- The article file appears truncated in the preview.
- No evidence the Word document meets the 1,000-1,500 word requirement.
- The response text is generic and does not confirm the article content.
  > 💡 Verify the document length and completeness, then resubmit with a full article.

### ✅ `1a78e076…` — score 6/10
- Output is a brief status note, not the required 10-15 page manuscript.
- No evidence the document fully covers all required sections and subthemes.
- Reference count and content quality cannot be verified from the preview.
  > 💡 Provide the complete manuscript with all required sections and verified references.

### ✅ `772e7524…` — score 6/10
- Text response does not provide the requested SOAP note.
- Plan content is truncated in the preview.
- No verification of complete file content is shown.
  > 💡 Provide the full SOAP note directly and ensure the document content is complete.

### ✅ `664a42e5…` — score 7/10
- Some file content is truncated in the preview.
- The text response does not confirm all required presentation details are fully included.
- No explicit verification of side-by-side comparison content is shown.
  > 💡 Review the deck to confirm every required ILIT topic is fully covered.

### ✅ `feb5eefc…` — score 6/10
- PDF is only 3 pages, not the requested no more than 12 pages with full analysis.
- CRAT section appears truncated in the preview, suggesting incomplete content.
- Text response mentions DOCX conversion, but the task required a PDF deliverable.
  > 💡 Revise the PDF to fully cover both trusts and ensure the final deliverable is clearly complete.

### ✅ `c657103b…` — score 6/10
- Excel preview shows RMDs start too early, before age 72.
- No evidence the PowerPoint uses the required business digital tunnel template.
- Text response is generic and does not confirm all slide requirements.
  > 💡 Verify RMD timing, template usage, and slide content against the task requirements.

### ✅ `f9f82549…` — score 8/10
- PowerPoint content could not be fully verified from previews.
- The incident details appear summarized, not fully embedded in each PPTX.
- No explicit confirmation of one PPTX per flowchart header.
  > 💡 Verify each PPTX contains the matching incident details and flowchart section.

### ✅ `84322284…` — score 6/10
- Report content appears incomplete and truncated.
- Timeline has inconsistent cash-collection timestamps.
- Text response is generic and lacks substantive findings.
  > 💡 Revise the report to fully summarize observations, clarify the timeline, and strengthen the analysis.

### ❌ `6241e678…` — score 4/10
- Missing required file types/content alignment.
- Schedule omits several specified tasks and review windows.
- Text response is generic and not project-specific.
  > 💡 Rebuild the schedule to match all listed tasks, dates, and client review requirements.

### ❌ `e4f664ea…` — score 3/10
- Only a 3-page script was produced, not the required 8-12 pages.
- The screenplay appears too brief and underdeveloped for a production-ready short film.
- No evidence of the requested 10-15 concise scenes or fuller story breakdown.
  > 💡 Expand the screenplay to 8-12 pages with more scenes and stronger narrative development.

### ❌ `02aa1805…` — score 3/10
- All Wells sheet is empty, so required well data was not extracted.
- Potential Wells contains a placeholder row instead of actual qualifying wells.
- Email says no wells met criteria, but task required identifying and highlighting top options.
  > 💡 Populate both sheets with real well records and identify the best qualifying options.

### ✅ `58ac1cc5…` — score 8/10
- PDF preview is truncated, so full form completeness cannot be fully verified.
- No obvious content errors were visible in the provided document previews.
- The response is professional and addresses the requested deliverables.
  > 💡 Verify the full PDF form fields and final disposition language before release.

### ❌ `3c19c6d1…` — score 4/10
- Cannot verify slide content from the PPTX preview.
- Text response mentions source files not in the task.
- No evidence all required sections are correctly populated.
  > 💡 Verify the PPTX includes all required slides and exact requested content.

### ❌ `55ddb773…` — score 3/10
- Missing most violation types and qualifying questions from the source PDF.
- Y/N options are not shown with circle formatting in the text preview.
- Only architectural regulations are included; community-specific blank lines are limited.
  > 💡 Add all violation categories and details from the reference, then format the form with proper circle options and more fillable lines.

### ❌ `0818571f…` — score 4/10
- Report date says March 2026, not June 2025.
- Live listing data and photos were not independently verified.
- Key deal metrics remain TBD for all properties.
  > 💡 Verify current listings and replace TBD fields with sourced transaction data.

### ✅ `6074bba3…` — score 6/10
- Output is a DOCX and PDF, but the task requested a complete PDF using the template.
- The report appears to contain placeholder fields like $[_] in pricing statistics.
- Comparable sales and active listing details are not fully visible in the preview.
  > 💡 Replace placeholders, verify all comps and charts, and ensure the final PDF is complete and polished.

### ✅ `5ad0c554…` — score 8/10
- PDF text appears slightly broken across lines.
- Word document is very sparse with only three paragraphs.
- No evidence of specific referenced buyer tasks beyond milestone headings.
  > 💡 Add fuller brochure copy with clearer NAR explanation and more specific buyer-service details.

### ❌ `11593a50…` — score 4/10
- Tour PDF is 4 pages, not the required 2 pages.
- Listing map PDF content cannot be verified from the preview.
- List dates are N/A, so a required column is incomplete.
  > 💡 Regenerate the PDFs to fit two pages and populate missing listing dates if available.

### ❌ `94925f49…` — score 4/10
- Only four PDF reports were produced; one school report is missing.
- Reports use placeholder or unverified school metrics and listings.
- Text admits live web access was unavailable, weakening source compliance.
  > 💡 Produce all five verified PDFs with current sourced school and listing data.

### ✅ `90f37ff3…` — score 6/10
- PDF is only 2 pages, not the requested 4 pages.
- Market rent survey lacks 3-6 comps with clear source/date details.
- Text response is generic and does not confirm data-driven analysis.
  > 💡 Expand the report to four pages and add fully sourced comparable data with dates.

### ✅ `d3d255b2…` — score 6/10
- Report appears incomplete in the preview.
- Counteroffer amount is truncated and may contain a typo.
- Original task requested a PDF report; only text and file names are shown.
  > 💡 Verify the full report content and ensure the PDF is complete and professionally formatted.

### ❌ `1bff4551…` — score 4/10
- PDF text is garbled and partially unreadable.
- YouTube links appear malformed or corrupted.
- No evidence the collection search requirement was used.
  > 💡 Regenerate the PDF with clean text, valid links, and verified collection-based selections.

### ✅ `01d7e53e…` — score 6/10
- Primary contact details appear incomplete or placeholder.
- Federal, state, and city requirements are not clearly identified.
- Reference to standard City contract language may be incomplete.
  > 💡 Revise the draft to add complete contacts and explicit compliance clauses.

### ❌ `7151c60a…` — score 4/10
- Checklist lacks the required table format and patient fields.
- Fax cover sheet is missing sender and recipient information fields.
- Text response is incomplete and contains a truncated sentence.
  > 💡 Revise both documents to include all required fields, table structure, and complete wording.

### ❌ `90edba97…` — score 3/10
- Output is generic and does not show completed patient data entry.
- No evidence of monthly lab values or treatment changes populated in the workbook.
- Text response promises completion but lacks specific results or documentation.
  > 💡 Populate the spreadsheet with all patient labs and monthly protocol-based actions.

### ❌ `8384083a…` — score 4/10
- PDF content appears garbled and hard to read.
- Miebo days supply is incomplete and vague.
- Text response is generic, not a completed guide.
  > 💡 Provide a clean, accurate one-page guide with all required medication details.

### ❌ `ffed32d8…` — score 4/10
- Requested PDF report exists, but no evidence of one-to-two page formatting.
- Text response promises a spreadsheet, not a completed financial recommendation.
- Summary sheet preview is truncated, so final recommendation cannot be verified.
  > 💡 Verify the PDF includes the full comparison table, summary, and clear recommendation.

### ✅ `ab81b076…` — score 8/10
- Preview is truncated, so final page completeness cannot be fully verified.
- No obvious issues in the provided content preview.
  > 💡 Verify the full PDF includes the complete documentation and communication section.

### ✅ `19403010…` — score 6/10
- Recap sheet exists, but values appear rounded and may not fully match source totals.
- No evidence the workbook is truly one-page formatted as requested.
- Text response is generic and does not confirm completed analysis details.
  > 💡 Verify calculations, enforce one-page layout, and provide a concise completion summary.

### ✅ `105f8ad0…` — score 6/10
- Workbook appears incomplete; competitor research sources are not shown.
- Some recommended MSRPs seem inconsistent with stated competitor averages.
- Text response promises creation, but deliverable quality is not fully evidenced.
  > 💡 Verify source-backed competitor pricing and recalculate all MSRP recommendations.

### ❌ `b57efde3…` — score 2/10
- Workbook contains only a failed scrape placeholder, not actual prospects.
- Summary sheet is incomplete and missing populated counts.
- No exhibitor leads, contacts, or fit assessments were identified.
  > 💡 Manually review the exhibitor list and populate verified leads with contact details and fit notes.

### ❌ `15d37511…` — score 4/10
- Ceiling volume is 15, not the stated 2,000 year-one projection.
- Total row is blank and does not summarize Year 1 gross margin.
- No clear evidence the spreadsheet includes all requested revenue and margin calculations.
  > 💡 Correct the volume assumption and add a complete Year 1 totals summary.

### ✅ `bb863dd9…` — score 6/10
- Basic module quantity is incorrect; it should be 10 units, not 1.
- Other modules appear duplicated or misquantified in the quotation.
- The workbook content may not fully reflect all IEHK 2017 modules.
  > 💡 Verify module quantities against the task and regenerate the quotation.

### ✅ `fe0d3941…` — score 8/10
- Non-physician survey has only four questions, which meets the minimum but is sparse.
- Text response mentions a DOCX source file, which was not requested.
- No evidence the PPT includes the optional title-slide picture.
  > 💡 Add one more non-physician question and verify the title-slide graphic is included.

### ✅ `9efbcd35…` — score 6/10
- Document preview is truncated, so completeness cannot be fully verified.
- No evidence of actual MSCI or news-source citations in the provided content.
- Text response mentions a PNG, but task required a Word document only.
  > 💡 Add explicit source citations and ensure the deliverable stays within the requested Word-only format.

### ✅ `1d4672c8…` — score 6/10
- Excel workbook content is truncated, so required sheet details cannot be fully verified.
- Analysis is brief and may not fully cover all requested portfolio implications and next steps.
- No evidence the historical data source from MSCI was actually extracted and used.
  > 💡 Provide a fuller report and verify the workbook includes complete monthly data and correlation matrix.

### ❌ `4de6a529…` — score 3/10
- Response is only a status note, not the required deliverable content.
- No verification of PDF completeness or correctness is provided.
- The generated file may be incomplete or mismatched with the task requirements.
  > 💡 Review the PDF against all required sections, labels, and line items before resubmitting.

### ✅ `bb499d9c…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of the required 25-page limit.
- Text response is brief but professional.
  > 💡 Confirm full document length and inspect the missing sections for completeness.

### ✅ `a4a9195c…` — score 8/10
- PDF preview is truncated, so full content cannot be fully verified.
- No explicit confirmation that the Word file is under five pages.
- Text response mentions a PDF, but the task required Word format only.
  > 💡 Provide a complete DOCX under five pages and verify all required content.

### ❌ `11dcc268…` — score 4/10
- No evidence the workbook was actually populated with inventory data.
- Text response is generic and does not confirm task-specific cross-referencing.
- File content preview suggests the sheet may still be blank.
  > 💡 Verify the Excel file contains all received items, locations, and balances before delivery.

### ❌ `76418a2c…` — score 4/10
- Only three shipments were populated; most manifest rows are blank.
- No evidence of using the pick tickets or shipping-parameter source files.
- Tracking numbers remain placeholders, and the workbook lacks validation details.
  > 💡 Populate all required shipments from the source files and verify every field before delivery.

### ❌ `0e386e32…` — score 3/10
- No actual implementation details are verifiable from the ZIP preview.
- Privacy and withdrawal logic may be incomplete or placeholder.
- Output is a promise, not a confirmed deliverable summary.
  > 💡 Provide a verified file manifest and confirm implemented core components.

### ✅ `854f3814…` — score 6/10
- Query uses a bounding box, not the full ABQ-to-OKC corridor.
- Instructions mention files, but no actual downloadable file contents are shown.
- Output may miss exact interstate relation coverage and corridor precision.
  > 💡 Refine the query to follow the full route and include exact relation-based filtering.

### ✅ `2c249e0f…` — score 6/10
- Only a text summary is shown; actual YAML and data_flow contents are not verified.
- No evidence the data_flow.txt fully describes the end-to-end pipeline.
- Potentially incomplete handling of all required upload and resume scenarios.
  > 💡 Verify the full files include all required endpoints, resumable uploads, and pipeline details.

## Failure Analysis

The clearest failure mode was brittle handling of source files and templates rather than pure reasoning failure. Several hard errors came from exact-string or exact-layout assumptions: missing input file detection in ee09d943-5a11-430a-b7a2-971b4e9b01b5, column-name mismatch in 1752cb53-5983-46b6-92ee-58ac85a11283 ("Planned Hours Per Day "), unpacking assumptions in 5f6c57dd-feb6-4e70-b152-4969d92d1608, merged-cell writes in a0552909-bc66-4a3a-8970-ee0d17b49718, month-token parsing in 6d2c8e55-fe20-45c6-bdaf-93e676868503, row-label lookup failure in 6a900a40-8d2b-4064-a5b1-13a60bc173d8, and type-unsafe hyperlink assignment in 5a2d70da-0a42-4a6b-a3ca-763e03f070a5. This cluster explains why Professional, Scientific, and Technical Services and some spreadsheet-heavy Manufacturing/Health Care tasks underperformed even when the underlying task was straightforward. By contrast, strongly structured local-data spreadsheet jobs such as 7bbfcfe9-132d-4194-82bb-d6f29d001b01, ce864f41-8584-49ba-b24f-9c9104b47bf0, and b5d2e6f1-62a2-433a-bcdd-95b260cdd860 scored well, suggesting the model does better when the template structure is stable and fully inspectable.

A second cluster is modality and artifact complexity, especially in Information-sector media work. Film and Video Editors was the weakest occupation pattern: 75401f7c-396d-406d-b08e-938874ad1045 failed on binary/text decoding, a941b6d8-4289-4500-b45a-f8e4fc94a724 failed on OpenCV memory allocation, e222075d-5d62-4757-ae3c-e34b0846583b completed without producing the requested MP4, and c94452e4-39cd-4846-b73a-ab75933d1ad7 admitted placeholder footage. Software Developers showed a related packaging problem rather than domain reasoning weakness: 7de33b48-5163-4f50-b5f3-8deea8185e57 and 4122f866-01fa-400b-904d-fa171cdab7c7 both died on unterminated triple-quoted strings, and the remaining software tasks topped out at middling QA. Information was also the slowest sector overall, but its extra time did not buy reliability; the sector combined 22/25 completion with high-latency outliers and several artifact-generation failures.

A third pattern is "deliverable drift": many tasks executed successfully but produced a plan, shell, wrong format, or incomplete artifact rather than the requested final deliverable. Examples include title-only or nearly empty documents in f84ea6ac-8f9f-428c-b96c-d0884e30f7c7 and a328feea-47db-4856-b4be-2bdc63dd88fb, empty/placeholder tracking outputs in 476db143-163a-4537-9e21-fe46adad703b and b57efde3-26d6-4742-bbff-2b63c43b4baa, a missing required tab in 83d10b06-26d1-4636-a32c-23f92c57f30b, and a manuscript that was really just a status note in 1a78e076-445e-4c5d-b8ce-387d2fe5e715. Format drift was also common across otherwise successful runs: bbe0a93b-ebf0-40b0-98dc-8d9243099034 returned DOCX where PDF was required, f9a1c16c-53fd-4c8f-88cc-5c325ec2f0bb added extra files, efca245f-c24f-4f75-a9d5-59201330ab7a used DOCX instead of embedding summary content in Excel, and several tasks claimed PDFs or scripts that were not actually requested or not actually present. This means the 94.1% completion rate materially overstates production readiness, especially in Government and Real Estate where completion was perfect but some outputs still scored 3-4 because content was thin or incomplete.

Retries helped with transient execution more than with final fidelity. All 13 outright errors were already retried and still failed, so the current retry policy is not breaking the dominant failure modes. Some retries were valuable when the failure was recoverable, such as 7d7fc9a7-21a7-4b83-906f-416dea5ad04f (QA 9), bf68f2ad-eac5-490a-adec-d847eb45bd6f (QA 9), and a99d85fc-eff8-48d2-a7d4-42a75d62f18d (QA 8). But many retried successes remained weak, including aa071045-bcb0-4164-bb85-97245d56287e (QA 3), 476db143-163a-4537-9e21-fe46adad703b (QA 2), e996036e-8287-4e7f-8d0a-90a57cb53c45 (QA 4), and 40a8c4b1-b169-4f92-a38b-7f79685037ec (QA 4). Latency also did not correlate with quality: c94452e4-39cd-4846-b73a-ab75933d1ad7 took 110s for a QA 4 result, while 7bbfcfe9-132d-4194-82bb-d6f29d001b01 and 02314fc6-a24e-42f4-a8cd-362cae0f0ec1 delivered QA 9 in far less time. The higher-risk profile is therefore complexity of artifact manipulation, external dependency, and schema brittleness, not simply long reasoning time.

## Recommendations

First, harden the execution layer around template introspection and schema normalization before generation. The runtime should trim header whitespace, fuzzy-match near-identical column names, detect merged-cell regions before writes, validate required files up front, and fall back to pattern search when expected rows or tabs are missing. That directly addresses ee09d943-5a11-430a-b7a2-971b4e9b01b5, 1752cb53-5983-46b6-92ee-58ac85a11283, 5f6c57dd-feb6-4e70-b152-4969d92d1608, a0552909-bc66-4a3a-8970-ee0d17b49718, 6d2c8e55-fe20-45c6-bdaf-93e676868503, 6a900a40-8d2b-4064-a5b1-13a60bc173d8, and 5a2d70da-0a42-4a6b-a3ca-763e03f070a5. A simple preflight report that lists discovered files, worksheets, headers, merged ranges, and candidate anchors would likely convert several of these hard failures into successful repairs.

Second, route high-risk media and packaged-code tasks to a different tool profile. Film/video jobs need binary-safe I/O, larger memory allocation, and staged processing with ffmpeg/downsampling rather than all-in-memory OpenCV workflows; that would directly reduce failures like 75401f7c-396d-406d-b08e-938874ad1045 and a941b6d8-4289-4500-b45a-f8e4fc94a724 and improve weak media outputs like e222075d-5d62-4757-ae3c-e34b0846583b and c94452e4-39cd-4846-b73a-ab75933d1ad7. Software package tasks should be emitted through file-by-file templating or syntax-checked code generation rather than one giant raw string blob; both 7de33b48-5163-4f50-b5f3-8deea8185e57 and 4122f866-01fa-400b-904d-fa171cdab7c7 look like avoidable packaging failures that a local compile/lint step would catch before submission.

Third, tighten prompt and QA contracts around artifact completion, not just execution success. Many low-QA tasks need a validator that checks page count, word count, required tabs, required filenames, allowed file types, non-empty tables, absence of placeholders, and whether the response is a completed deliverable rather than a promise to create one. That would catch cases like f84ea6ac-8f9f-428c-b96c-d0884e30f7c7, a328feea-47db-4856-b4be-2bdc63dd88fb, 83d10b06-26d1-4636-a32c-23f92c57f30b, 476db143-163a-4537-9e21-fe46adad703b, 1a78e076-445e-4c5d-b8ce-387d2fe5e715, and b57efde3-26d6-4742-bbff-2b63c43b4baa before final delivery. For web-dependent tasks, either provide supported browsing/scraping access or replace live-data requirements with supplied snapshots; otherwise 8079e27d-b6f3-4f75-a9b5-db27903c798d, 94925f49-36bc-42da-b45b-61078d329300, 0818571f-5ff7-4d39-9d2c-ced5ae44299e, and 105f8ad0-8dd2-422f-9e88-2be5fbd2b215 will continue to fail or degrade into unsourced placeholders.

Fourth, retune retries to be quality-aware rather than merely crash-aware. The evidence shows that retries can recover some executions, but repeating the same strategy rarely fixes schema drift or thin content. A better policy is: auto-retry any run with validator failures or self-QA <= 4; switch strategy on retry (for example, preserve the input template exactly, reduce output scope, or regenerate only the missing artifact sections); and escalate risky occupations such as Film and Video Editors, Software Developers, Medical Secretaries, Accountants, and Technical Sales to a more robust reasoning/tool configuration. Meanwhile, low-risk deterministic task families such as Order Clerks, Compliance Officers, and many Retail/Government spreadsheet jobs can stay on the current profile because tasks like b5d2e6f1-62a2-433a-bcdd-95b260cdd860, 47ef842d-8eac-4b90-bda8-dd934c228c96, 7bbfcfe9-132d-4194-82bb-d6f29d001b01, and 02314fc6-a24e-42f4-a8cd-362cae0f0ec1 already show that the configuration is strong when the artifact contract is simple and local.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 2 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 2 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 3 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `38889c3b…` (Information): 6 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 3 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `24d1e93f…` (Manufacturing): 2 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 5 file(s)
- `bbe0a93b…` (Government): 5 file(s)
- `85d95ce5…` (Government): 2 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 1 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 4 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 2 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 3 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 2 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 3 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 1 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `61717508…` (Finance and Insurance): 3 file(s)
- `0ed38524…` (Finance and Insurance): 2 file(s)
- `87da214f…` (Finance and Insurance): 1 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 6 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e222075d…` (Information): 2 file(s)
- `c94452e4…` (Information): 5 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 5 file(s)
- `c7d83f01…` (Finance and Insurance): 6 file(s)
- `46b34f78…` (Finance and Insurance): 3 file(s)
- `a1963a68…` (Finance and Insurance): 2 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 3 file(s)
- `4520f882…` (Finance and Insurance): 1 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `e996036e…` (Wholesale Trade): 1 file(s)
- `327fbc21…` (Wholesale Trade): 1 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 1 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 2 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `bf68f2ad…` (Manufacturing): 2 file(s)
- `efca245f…` (Manufacturing): 2 file(s)
- `9e39df84…` (Manufacturing): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 4 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `d4525420…` (Retail Trade): 3 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 4 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 3 file(s)
- `c6269101…` (Manufacturing): 2 file(s)
- `be830ca0…` (Manufacturing): 1 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `5e2b6aab…` (Manufacturing): 6 file(s)
- `46fc494e…` (Manufacturing): 6 file(s)
- `3940b7e7…` (Manufacturing): 1 file(s)
- `8077e700…` (Manufacturing): 6 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 2 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 4 file(s)
- `f1be6436…` (Health Care and Social Assistance): 6 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 3 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 2 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 1 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 2 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 2 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 10 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `a46d5cd2…` (Retail Trade): 3 file(s)
- `6241e678…` (Information): 3 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 1 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 1 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 1 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 2 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 6 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 13 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 4 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 3 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 10 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 1 file(s)
- `a73fbc98…` (Government): 3 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 1 file(s)
- `91060ff0…` (Retail Trade): 3 file(s)
- `8384083a…` (Retail Trade): 3 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `ffed32d8…` (Retail Trade): 3 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 2 file(s)
- `788d2bc6…` (Wholesale Trade): 2 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 3 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 1 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 3 file(s)
- `9efbcd35…` (Finance and Insurance): 2 file(s)
- `1d4672c8…` (Finance and Insurance): 4 file(s)
- `4de6a529…` (Finance and Insurance): 1 file(s)
- `4c4dc603…` (Finance and Insurance): 1 file(s)
- `bb499d9c…` (Finance and Insurance): 3 file(s)
- `5349dd7b…` (Manufacturing): 2 file(s)
- `a4a9195c…` (Manufacturing): 2 file(s)
- `552b7dd0…` (Manufacturing): 5 file(s)
- `11dcc268…` (Manufacturing): 1 file(s)
- `76418a2c…` (Manufacturing): 1 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `854f3814…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
