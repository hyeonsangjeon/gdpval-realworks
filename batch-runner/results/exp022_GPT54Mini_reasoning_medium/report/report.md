# Experiment Report: GPT-5.4-Mini Reasoning MEDIUM — Full Benchmark (Ablation 2/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp022_GPT54Mini_reasoning_medium` |
| **Condition** | GPT-5.4-Mini reasoning=medium + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4-mini |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-25 |
| **Duration** | 94m 33s |
| **Generated At** | 2026-03-25T21:23:04.013992+00:00 |
| 🤗 HF Dataset | [exp022_GPT54Mini_reasoning_medium](https://huggingface.co/datasets/HyeonSang/exp022_GPT54Mini_reasoning_medium) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp022_GPT54Mini_reasoning_medium/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This run evaluated gpt-5.4-mini in subprocess mode under the condition "reasoning=medium + gpt-audio-1.5 preprocessor" across 220 benchmark tasks dated 2026-03-25. Overall task completion rate was 205/220 (93.2%), with 15 execution errors and 56 retried tasks. Average end-to-end latency was 16,354 ms, indicating a moderate response-time profile for a medium-reasoning configuration.

From an LLM-evaluated quality perspective, the average self-assessed confidence score was 6.8/10, with a broad range from 2 to 9. That pattern suggests the system usually produced usable outputs when it completed tasks, but quality consistency was uneven across the benchmark. The retry count is also material: many tasks ultimately completed, but a nontrivial subset required additional attempts, which matters for operational stability even when final completion was successful.

At the sector level, completion was strongest in Retail Trade (20/20), and near-ceiling in Finance and Insurance, Government, and Manufacturing (24/25 each). Quality signals were strongest in Retail Trade (7.7/10) and Wholesale Trade (7.6/10), while Professional, Scientific, and Technical Services had the lowest average self-assessed confidence (5.9/10). Deliverable file generation quality appears operationally solid on completed tasks, but the combination of 15 failures, 56 retries, and variable self-assessed confidence indicates that successful file generation did not always correspond to uniformly high-confidence outputs.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 205 (93.2%) |
| Errors | 15 |
| Retried Tasks | 56 |
| Avg QA Score | 6.8/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 16,354ms |
| Max Latency | 39,730ms |
| Total LLM Time | 3597s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 172 (93.0%) |
| Failed → dummy created | 13 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 30 | 30 | 0 |
| 2 | 26 | 11 | 15 |

## Quality Analysis

The QA score distribution indicates a mid-to-upper performance band with noticeable variance. An average self-assessed confidence of 6.8/10 is acceptable for broad task execution, but the 2-9 range shows that some deliverables were assessed by the model as substantially weaker than others. This suggests that while the run was effective at producing outputs, the reliability of answer quality was not uniform across task types.

Sector-level differences were meaningful. Retail Trade combined perfect task completion (20/20) with the highest LLM-evaluated quality (7.7/10), making it the clearest strong segment in this run. Wholesale Trade also scored well on quality (7.6/10) with 23/25 completion. Finance and Insurance showed strong completion (24/25) and solid confidence (7.2/10), but at the highest average latency (20,059 ms). In contrast, Professional, Scientific, and Technical Services matched Information at 22/25 completion but had the lowest quality signal (5.9/10), implying that these tasks were completed at a reasonable rate yet with weaker self-assessed confidence.

Latency did not show a simple linear relationship with quality. Finance and Insurance was the slowest sector but still produced relatively strong LLM-evaluated quality, while Retail Trade achieved both comparatively low latency (14,808 ms) and the best quality. Government was one of the faster sectors (13,983 ms) with above-average confidence (6.9/10). This pattern suggests that longer runtimes were not consistently buying higher-quality outputs; instead, task/domain characteristics appear to have mattered more.

No occupation-level breakdown was provided, so observations are limited to sector-level execution behavior rather than role-specific patterns. Based on the available data, deliverable generation quality was best characterized as high completion with moderate confidence spread: many files were produced successfully, but confidence scores and retry dependence indicate uneven robustness across domains. The most favorable balance of completion, quality, and latency appeared in Retail and Wholesale contexts, while technical/professional domains showed the clearest quality drag.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 24 | 96.0% | 7.17/10 | 20,059ms |
| Government | 25 | 24 | 96.0% | 6.88/10 | 13,983ms |
| Health Care and Social Assistance | 25 | 23 | 92.0% | 6.7/10 | 14,775ms |
| Information | 25 | 22 | 88.0% | 6.45/10 | 16,808ms |
| Manufacturing | 25 | 24 | 96.0% | 6.42/10 | 17,339ms |
| Professional, Scientific, and Technical  | 25 | 22 | 88.0% | 5.91/10 | 17,051ms |
| Real Estate and Rental and Leasing | 25 | 23 | 92.0% | 6.52/10 | 16,287ms |
| Retail Trade | 20 | 20 | 100.0% | 7.7/10 | 14,808ms |
| Wholesale Trade | 25 | 23 | 92.0% | 7.57/10 | 15,766ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 8/10 | 17038ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 14705ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 2/10 | 17694ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 4/10 | 15412ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 6/10 | 11700ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 2/10 | 10358ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | Yes | 1 | 9/10 | 5930ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 3 | 8/10 | 18539ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 9/10 | 13611ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 4 | 6/10 | 17383ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ❌ error | Yes | 0 | - | 22885ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 4 | 6/10 | 17183ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | Yes | 6 | 6/10 | 25251ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 2 | 8/10 | 11368ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 3 | 6/10 | 15158ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 18686ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 20358ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 8/10 | 14113ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 20170ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 23253ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 16352ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 4 | 6/10 | 17536ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 6 | 6/10 | 13746ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 2 | 4/10 | 19053ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | Yes | 2 | 8/10 | 14800ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 4/10 | 9772ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 7635ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 8/10 | 7570ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 8591ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 6/10 | 23991ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 6/10 | 14016ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 14083ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 4/10 | 16951ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 1 | 9/10 | 21128ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 4 | 8/10 | 15616ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | Yes | 1 | 3/10 | 14058ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 6/10 | 16179ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 15043ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 18732ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 12902ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 11594ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 15300ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 11147ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 9/10 | 9963ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 16283ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 8/10 | 8104ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 8/10 | 16772ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 8/10 | 14518ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 2 | 8/10 | 17364ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 6/10 | 9064ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 13196ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 8/10 | 21578ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | Yes | 3 | 7/10 | 39155ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | Yes | 1 | 8/10 | 19810ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 4/10 | 22629ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 7/10 | 7512ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | Yes | 4 | 6/10 | 22640ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 2 | 2/10 | 4272ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 13913ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 32900ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 1 | 6/10 | 24346ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 8/10 | 22291ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 8/10 | 26150ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 7 | 4/10 | 39730ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 3 | 8/10 | 16649ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 5 | 3/10 | 25151ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 1 | 8/10 | 25492ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 1 | 8/10 | 18414ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 6/10 | 18201ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 9/10 | 19542ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 8/10 | 9025ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 11629ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 26625ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 12400ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 1 | 9/10 | 17097ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 4/10 | 15095ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 8/10 | 10027ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 3 | 6/10 | 17339ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 4/10 | 12722ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 6/10 | 14930ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 16030ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 1 | 6/10 | 11348ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 13546ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 14353ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 6/10 | 13597ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 9/10 | 10650ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 8/10 | 18703ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 4/10 | 15359ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 8/10 | 14753ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 11376ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 3 | 9/10 | 22368ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 1 | 9/10 | 12919ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 4/10 | 13155ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 26819ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 5 | 6/10 | 26297ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 10764ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 2 | 6/10 | 13344ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 9/10 | 11529ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 9/10 | 18723ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 9489ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 9/10 | 15234ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | 9/10 | 20263ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 4/10 | 16506ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 5 | 8/10 | 27193ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 7 | 6/10 | 27358ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 5/10 | 23269ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 4/10 | 19739ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 13473ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 9/10 | 29137ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 20479ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 13 | 6/10 | 19528ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 10 | 4/10 | 19922ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 4/10 | 16298ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 1 | 6/10 | 27114ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 2 | 6/10 | 19890ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 14706ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 8381ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 14687ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 4/10 | 7550ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | Yes | 6 | 9/10 | 19135ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 4/10 | 22247ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 9/10 | 9461ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 15767ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 21885ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 6/10 | 19064ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 9/10 | 6554ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 11384ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 4/10 | 7880ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | 8/10 | 13153ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 15225ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 20299ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 20482ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 7822ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 4/10 | 7825ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | 9/10 | 14206ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 11474ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 1 | 8/10 | 21694ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 14996ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 8613ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 2 | 9/10 | 12547ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 17351ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 13309ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 8/10 | 14789ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 8/10 | 17117ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 4 | 8/10 | 29730ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 6/10 | 9597ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 8/10 | 11109ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 9257ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 8/10 | 26401ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 12934ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | 6/10 | 19109ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 6 | 6/10 | 10715ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 14970ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 4/10 | 17481ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 9/10 | 14269ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 22008ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 18390ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | Yes | 2 | 9/10 | 23231ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 4 | 8/10 | 16436ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 1 | 4/10 | 19877ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 15776ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 15861ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 3/10 | 9833ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 8/10 | 17412ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 20335ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 7 | 9/10 | 20545ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 8/10 | 11323ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 8106ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 16 | 6/10 | 24109ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 4 | 9/10 | 24639ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 5/10 | 20333ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 4/10 | 23480ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 6 | 4/10 | 20678ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 6/10 | 18288ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 4/10 | 15248ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 12525ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 4/10 | 14012ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 11659ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 23774ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 13874ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 9/10 | 11974ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 8868ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 8/10 | 15618ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 8/10 | 13499ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 4/10 | 25795ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 7 | 8/10 | 19874ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 4/10 | 10080ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 8/10 | 9452ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 9/10 | 5236ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | Yes | 3 | 9/10 | 16819ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 10394ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 25180ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | Yes | 5 | 9/10 | 31524ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 6/10 | 12257ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 15497ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 9/10 | 17379ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 9/10 | 17267ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 9/10 | 19625ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 16056ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 18483ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 3/10 | 14180ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 4/10 | 12522ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 10422ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 8/10 | 15973ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 8/10 | 11297ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 6/10 | 21420ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 3 | 6/10 | 23134ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 9/10 | 18357ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 9/10 | 15396ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 8/10 | 29078ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 11878ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 8/10 | 12865ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 4 | 8/10 | 15704ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 4/10 | 7562ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 3/10 | 8744ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 13656ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 9190ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ✅ success | Yes | 2 | 6/10 | 5403ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 16619ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 4/10 | 17013ms |

## QA Issues

### ❌ `7d7fc9a7…` — score 2/10
- Workbook totals are all zero and do not reconcile to provided GL balances.
- Detailed schedules appear to contain placeholder zero amounts instead of invoice data.
- No evidence of required monthly activity summaries or accurate amortization calculations.
  > 💡 Rebuild the workbook using the source invoices and verify all balances tie to the GL.

### ❌ `43dc9778…` — score 4/10
- Only a draft package was produced, not a final e-file-ready return.
- Required schedules/forms are summarized, not clearly included as separate filed forms.
- Source documents were not fully reconciled, leaving potential missing or inaccurate items.
  > 💡 Prepare a complete final 1040 package with all required forms and verify all source documents.

### ✅ `ee09d943…` — score 6/10
- Workbook appears created, but content accuracy is not fully verified.
- No evidence of updated April data across all required schedules.
- Potential missing validation of excluded CFO tabs and new April tabs.
  > 💡 Verify each tab against source files and confirm all required April schedules are updated.

### ❌ `f84ea6ac…` — score 2/10
- No research table or five studies are included.
- The document lacks required article details, findings, and implications.
- It explicitly notes no internet research was performed.
  > 💡 Provide a one-page table summarizing five post-2020 public academic articles with findings and implications.

### ✅ `27e8912c…` — score 8/10
- PDF and DOCX were produced, but the checklist is only four pages.
- The text response mentions a PDF and Word document, but both files are DOCX/PDF only.
- Image appendix content is present, but public-domain source details are not visible.
  > 💡 Verify file formats, page count, and source citations before final delivery.

### ✅ `c44e9b62…` — score 6/10
- Briefing note file is PDF, not Word as required.
- Text response does not mention all deliverables were completed.
- Preview suggests some content may be truncated or incomplete.
  > 💡 Provide a Word briefing note and verify all deliverables are complete.

### ✅ `f9a1c16c…` — score 6/10
- No evidence the PDF is actually landscape or visually verified.
- Output numbering may not match the requested counterclockwise stage-right convention.
- Text response mentions extra DOCX/XLSX files not requested.
  > 💡 Verify the plot orientation and numbering, then trim the package to the required deliverables.

### ✅ `38889c3b…` — score 6/10
- No evidence the audio matches 140 bpm or required key changes.
- Stem set includes Bridge but may not isolate all required instrumentation cleanly.
- Text response promises validation, but file contents are not verified.
  > 💡 Verify tempo, key sections, and stem separation before delivery.

### ✅ `ff85ee58…` — score 8/10
- No explicit verification of loudness compliance is shown.
- The text response promises a TXT summary, which is acceptable but not required.
- Mix quality cannot be fully confirmed from the preview alone.
  > 💡 Confirm final LUFS and peak measurements before delivery.

### ✅ `4b894ae3…` — score 6/10
- No evidence the specified bass edit timecodes were actually applied.
- The response mentions creating a DOCX summary, which was not requested as a deliverable.
- File naming is inconsistent with the required exact output name format.
  > 💡 Verify the bass edits against the reference spots and deliver only the required final mix.

### ✅ `1b1ade2d…` — score 6/10
- Output is generic and repeats the same sentence.
- File preview is truncated, so completeness cannot be verified.
- No explicit evidence of the required detailed workflow content.
  > 💡 Provide a complete, concise workflow document with all required approvals, change controls, and traceability details.

### ✅ `93b336f3…` — score 6/10
- Text response is incomplete and ends mid-sentence.
- Cost figures appear inconsistent with the stated USD-to-INR conversion.
- No explicit confirmation of all required calculations and recommendations in the preview.
  > 💡 Verify the cost math, complete the document content, and ensure all task requirements are explicitly covered.

### ✅ `15ddd28d…` — score 8/10
- Document preview is truncated, so completeness cannot be fully verified.
- No obvious formatting or file-type issues were detected.
- The response is professional but brief on negotiation specifics.
  > 💡 Verify the full document includes a clear 2–3 page strategy with timelines and contingencies.

### ✅ `24d1e93f…` — score 6/10
- NPV values appear blank in the summary sheet.
- Vendor quotations and volume projections are not visible in the preview.
- Recommendation field is present but may not be populated.
  > 💡 Populate all vendor inputs, calculated NPVs, and a clear nomination recommendation.

### ✅ `05389f78…` — score 6/10
- Report content is truncated, so completeness cannot be verified.
- Quotation-based cost comparison and calculations are not visible.
- Text response is generic and does not confirm key deliverable details.
  > 💡 Verify both Word files include full comparative analysis, calculations, and final recommendation.

### ✅ `a74ead3b…` — score 6/10
- No evidence the slides closely follow the manual content.
- Only a text promise is shown; presentation content is unverified.
- Validation check is mentioned but not demonstrated.
  > 💡 Verify slide content against the manual and confirm both PPTX files open correctly.

### ✅ `bbe0a93b…` — score 6/10
- Resource guide lacks verified live web search evidence.
- Assessment PDFs appear to be missing some requested bilingual table formatting.
- Spanish form includes untranslated English text.
  > 💡 Verify resources with current web sources and fully localize both assessment PDFs.

### ❌ `85d95ce5…` — score 4/10
- Only a brief text response was provided, not the completed report content.
- File content may contain placeholder or incomplete sections.
- No verification of 8-15 page length or required narrative sections.
  > 💡 Review the document against the template and complete all required sections before resubmitting.

### ❌ `36d567ba…` — score 4/10
- File preview shows only title and instructions, not the required question set.
- Topics 1-11 are not addressed in the document content.
- Required 2 CFR Part 200 references and two-part questions are missing.
  > 💡 Add all eleven topic questions with required Yes/No and detail prompts, including cited regulations for topics 6-10.

### ✅ `4c18ebae…` — score 6/10
- Text response is duplicated.
- No evidence the SAR narrative is complete.
- Output mentions current directory, not the actual saved path.
  > 💡 Provide one concise, complete deliverable summary with accurate file locations.

### ✅ `cebf301e…` — score 6/10
- Output is a design document, not a concise deliverable summary.
- The preview is truncated, so completeness cannot be fully verified.
- No explicit validation of all required requirements is shown.
  > 💡 Provide a complete, concise summary confirming each requirement and produced file.

### ❌ `2ea2e5b5…` — score 4/10
- Strategic Level classification is incomplete in the response.
- No evidence the source workbook was actually used.
- Output description is generic and may not match the required analysis.
  > 💡 Verify all three classification segments and confirm source-data-driven slide content.

### ❌ `a10ec48c…` — score 3/10
- Document lacks the required restaurant tables and columns.
- Only a generic placeholder cuisine section appears.
- Restaurant links, hours, directions, and categories are missing.
  > 💡 Rebuild the Word document with complete restaurant tables and sourced details.

### ✅ `fccaa4a1…` — score 6/10
- Age requirement text is incomplete and unclear.
- TakeWalks details may be too generic and not fully sourced.
- The PDF layout cannot be verified from the preview.
  > 💡 Confirm all requirements are fully stated and verify the PDF formatting visually.

### ✅ `f5d428fd…` — score 6/10
- PDF is 9 pages, not the requested concise two pages.
- The preview is truncated, so completeness cannot be verified.
- Some image sources appear to be search or destination pages, not direct royalty-free photos.
  > 💡 Condense to two pages and use direct royalty-free image URLs for each destination.

### ✅ `2fa8e956…` — score 6/10
- Document content appears truncated in preview, so completeness is uncertain.
- No verification of four-page limit, footer formatting, or purple grape text.
- Photo is a placeholder filename, not confirmed as a relevant royalty-free image.
  > 💡 Verify the DOCX formatting, page count, and replace any placeholder image with a sourced royalty-free photo.

### ✅ `0e4fe8cd…` — score 6/10
- Workbook preview is truncated, so completeness cannot be fully verified.
- Original task requested factual links and high-value connections; output evidence is unclear.
- Text response is generic and does not confirm all four day tabs are populated.
  > 💡 Verify all four sheets contain complete, linked, day-specific itinerary content.

### ✅ `87da214f…` — score 8/10
- Text response promises a validation-ready file, but no validation details are shown.
- Summary document lacks explicit next steps and financial impact narrative.
- Policy update recommendation is present, but remediation options are limited.
  > 💡 Add clearer next steps and a brief financial impact explanation in the deck.

### ✅ `d025a41c…` — score 6/10
- File content appears truncated in preview.
- Case Three content may be incomplete.
- Text response is not a full deliverable.
  > 💡 Verify the document includes all three complete cases and no missing sections.

### ✅ `401a07f1…` — score 6/10
- Text response is not a complete editorial.
- Reference links are not visible in the preview.
- Word count and Guardian style compliance are unverified.
  > 💡 Provide the full editorial with visible source links and verify length and style.

### ✅ `afe56d05…` — score 8/10
- Preview is truncated, so full word count cannot be verified.
- No explicit confirmation of hyperlink formatting in the document.
- File content appears complete, but exact section coverage cannot be fully checked.
  > 💡 Verify the final document length and hyperlink formatting before delivery.

### ✅ `9a8c8e28…` — score 7/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of the quiz answer key and scoring guide.
- The final text response is generic and does not confirm all requirements were met.
  > 💡 Provide full file content confirmation, especially the quiz key, scoring, and bibliography.

### ✅ `3a4c347c…` — score 8/10
- File preview is truncated, so full content cannot be fully verified.
- No explicit validation evidence is shown for the DOCX opening correctly.
  > 💡 Confirm the full document includes all schedule, KPI, and contributor details.

### ❌ `ec2fccc9…` — score 4/10
- No actual SEO keyword list is shown in the response.
- Reference artist links and news links are not verifiable from the preview.
- Word count and pull quote requirements cannot be confirmed.
  > 💡 Provide the full article content with visible links, keywords, and formatting details.

### ✅ `8c8fc328…` — score 7/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit confirmation of under-5-page length in the file.
- Text response is generic and does not mention key reference alignment.
  > 💡 Verify the full DOCX includes the complete script, timestamps, and reference-based narration.

### ✅ `e222075d…` — score 6/10
- No direct stock footage or music links are provided.
- Reference log lacks specific source details and clip selections.
- Video content cannot be verified from the preview alone.
  > 💡 Add exact source URLs and confirm the edit matches all script and timing requirements.

### ❌ `c94452e4…` — score 2/10
- No actual 15-second MP4 was produced.
- Required stock footage and music were not sourced or edited.
- Only a production summary was delivered, not the broadcast spot.
  > 💡 Produce the exact 15-second H.264 video with sourced media and supers.

### ✅ `8079e27d…` — score 6/10
- Workbook has 503 companies, not exactly 500.
- Company rows appear misaligned with extra sector/sub-sector values.
- No separate sub-sector summary sheet is shown.
  > 💡 Verify constituent count, fix column alignment, and add a sub-sector summary tab.

### ✅ `e21cd746…` — score 8/10
- Some private valuations are described as estimated or undisclosed.
- The preview suggests one slide may be truncated in the excerpt.
- No obvious content gaps in the required deliverables.
  > 💡 Confirm all target valuations and ensure the final PDF renders every slide cleanly.

### ❌ `c7d83f01…` — score 4/10
- FD Explicit results contain divergence and missing values.
- No actual notebook file is shown, only a .py script.
- Monte Carlo and FD methods appear less complete than requested.
  > 💡 Provide a true notebook and fix unstable finite-difference outputs.

### ✅ `46b34f78…` — score 8/10
- Memo preview is truncated, so completeness cannot be fully verified.
- No explicit confirmation of issuer names or source-data quality in the summary.
- Appendix and chart content are mentioned but not fully inspectable.
  > 💡 Verify the full memo includes all required sections, issuer analyses, and cited public sources.

### ❌ `a1963a68…` — score 3/10
- PDF is only a one-page text fallback, not a 5-6 slide presentation.
- Required formal strategy deck content is not verifiable from the PDF output.
- Deliverables include extra files, but the main PDF format and depth are insufficient.
  > 💡 Regenerate a proper multi-slide PDF with full strategy content and verified formatting.

### ✅ `5f6c57dd…` — score 8/10
- Workbook content appears mostly complete, but formulas and dropdown functionality were not verified.
- Text response is generic and does not confirm all five worksheets were fully built.
- No explicit validation of file opening or calculation accuracy is shown.
  > 💡 Verify formulas, dropdowns, and sheet outputs against the source data before final delivery.

### ✅ `b78fd844…` — score 6/10
- Report is only 4 pages, but the task required up to 15 pages.
- Preview is truncated, so completeness of risks, allocation, and justification cannot be verified.
- Text response is generic and does not confirm all required analysis was fully delivered.
  > 💡 Expand the report to include all required analyses and verify the full PDF content.

### ✅ `3f821c2d…` — score 6/10
- No evidence the workbook meets all receipt minimums and target constraints.
- Preview is truncated, so formulas and full table completeness cannot be verified.
- Text response is generic and does not confirm actual optimization results.
  > 💡 Verify formulas, constraints, and final omni metrics directly in the workbook.

### ✅ `e996036e…` — score 6/10
- Shipment total in reference file is 255,000, not the stated 225,000.
- Only one workbook was produced; file content may not fully verify the required summary and visual.
- Scenario details are present, but the selected preferred scenario is not clearly confirmed.
  > 💡 Revise the workbook to match the stated assumptions and clearly highlight the preferred scenario with the executive summary.

### ❌ `6dcae3f5…` — score 4/10
- Email mentions only a draft, not the required detailed analysis results.
- Original task appears incomplete in the response and may omit required PGY requirement mapping.
- No evidence the Excel workbook contains all requested benchmark calculations and resident-year entries.
  > 💡 Verify the workbook and email include all required calculations, mappings, and complete resident data.

### ✅ `1aecc095…` — score 8/10
- Email content is truncated in preview, so completeness cannot be fully verified.
- No obvious formatting or file-type issues are shown.
- Workflow appears to cover the required telehealth steps and handoff.
  > 💡 Verify the email word count and final formatting in the DOCX files.

### ✅ `0353ee0c…` — score 6/10
- PDF preview is truncated, so completeness cannot be verified.
- Some location entries are vague and may omit exact eligibility details.
- No evidence the document exhaustively consolidates all 19 source links.
  > 💡 Verify every source link and ensure the PDF fully lists all exact presumptive criteria.

### ❌ `40a8c4b1…` — score 4/10
- Response is only a plan, not a completed deliverable.
- No evidence the required file content was verified.
- No confirmation of the February In-Service Study Session placement.
  > 💡 Provide the finished workbook details and verify all required scheduling constraints.

### ✅ `4d1a8410…` — score 6/10
- Itinerary files appear too sparse for one-page personal schedules.
- Schedule content may omit detailed room-by-room timing and applicant assignments.
- Tour site list is not explicitly shown in the preview.
  > 💡 Expand the Word documents with full tables, timings, and complete itinerary details.

### ✅ `8c823e32…` — score 7/10
- No evidence the PDF was actually reviewed for formatting quality.
- Policy may lack explicit legal review and approval authority details.
- Output is descriptive, not a direct deliverable confirmation.
  > 💡 Verify the PDF content and include explicit approval and compliance language.

### ✅ `eb54f575…` — score 6/10
- PDF is only 3 pages and may omit required depth.
- Ballistics section appears truncated in the preview.
- Text response is generic and does not summarize the actual recommendation.
  > 💡 Provide a complete, fully detailed PDF with all five sections and explicit final recommendations.

### ✅ `22c0809b…` — score 6/10
- Required identification and background check fields are not visible in the preview.
- Pathways to Violence sections lack 2–3 indicators with guidance and detail space.
- PDF content appears truncated and may omit required form elements.
  > 💡 Verify the PDF includes all required fields and fully expanded pathway indicators.

### ✅ `efca245f…` — score 8/10
- No obvious missing files or wrong file type.
- Text response is professional but brief.
- Scenario details appear consistent with the task.
  > 💡 Add a concise note on how each scenario meets the May 1 target.

### ❌ `9e39df84…` — score 4/10
- Dashboard sheet appears incomplete; KPI and pivot values are blank.
- Week selection controls may not be fully functional or populated.
- Text response claims completion but does not verify chart and pivot content.
  > 💡 Populate all dashboard formulas, pivots, and charts, then verify outputs before delivery.

### ✅ `68d8d901…` — score 8/10
- Output is mostly a plan summary, not a substantive text deliverable.
- No obvious validation of the 250,000-pound target or full-batch logic.
- File content appears present, but sequence details are only partially shown.
  > 💡 Verify the workbook fully documents target math, batch sizing, and complete sequencing.

### ❌ `d4525420…` — score 4/10
- Text is incomplete and cuts off mid-sentence.
- Only two paragraphs were produced, not a 5–7 sentence paragraph.
- The response describes file creation instead of directly answering the selection task.
  > 💡 Provide a complete 5–7 sentence recommendation paragraph naming the selected employee and rationale.

### ✅ `cecac8f9…` — score 6/10
- Plan uses dollar targets, not UK-localized currency.
- Preparation plan preview appears truncated, risking missing weekly actions.
- No evidence the plan includes all eight weekly sections clearly.
  > 💡 Verify the PDF content is complete and localize all targets to GBP.

### ✅ `0fad6023…` — score 6/10
- Workbook has only one sheet; instruction tab is missing.
- PDF shows 22 pan rows, not every pan in a 24-foot case.
- Text response claims conditional cues, but file preview does not confirm them.
  > 💡 Add a separate instructions sheet and ensure the full 24-foot pan layout is represented.

### ✅ `02314fc6…` — score 9/10
- PDF content preview is truncated, so completeness cannot be fully verified.
- Companion DOCX is extra, but the PDF deliverable appears present.
- No obvious content errors were visible in the provided preview.
  > 💡 Confirm the full PDF includes all checklist sections, scoring, and follow-up instructions.

### ✅ `6436ff9e…` — score 6/10
- Missing visible content for class and instructor evaluation sections.
- Form preview appears truncated, so completeness cannot be confirmed.
- No evidence of fully structured digital-form-ready question formatting.
  > 💡 Add the missing section details and verify the full document content.

### ❌ `b9665ca1…` — score 4/10
- Missing several required wiring details and exact labels.
- Includes extra DOCX deliverable not requested.
- Text response is repetitive and omits confirmation of all specified connections.
  > 💡 Revise the schematic to match every specified connection and deliver only the required PDF.

### ✅ `be830ca0…` — score 6/10
- PPTX content could not be verified from the preview.
- No evidence confirms all required slide sections and timeline details.
- Text response is generic and omits analysis findings.
  > 💡 Verify the presentation includes every required section and documented chart results.

### ✅ `cd9efc18…` — score 5/10
- PDF is only 4 pages, not the requested 8 to 11 pages.
- Trust and guardianship provisions appear truncated in the preview.
- Text response promises DOCX/PDF but does not confirm full legal completeness.
  > 💡 Regenerate a complete 8 to 11 page will with all trust and execution provisions fully included.

### ❌ `a97369c7…` — score 4/10
- Output is not a brief memo; it only describes future work.
- No actual legal analysis is provided in the text response.
- The response mentions DOCX/PDF, but the deliverable content is incomplete.
  > 💡 Provide the full memo text directly and ensure it addresses all three Delaware law issues.

### ✅ `3f625cb2…` — score 6/10
- Output is not a PDF-only deliverable response.
- Memo content may exceed the three-page limit.
- No clear verification of final PDF content or completeness.
  > 💡 Provide a concise three-page PDF memo and confirm all required legal points are covered.

### ✅ `8314d1b1…` — score 6/10
- Text response is only a status note, not the requested memo content.
- File content preview is truncated, so completeness cannot be verified.
- No confirmation that citations and all required sections are fully included.
  > 💡 Provide the full memo text and verify the DOCX includes all required sections and citations.

### ✅ `5e2b6aab…` — score 6/10
- Missing a PDF drawing for the battery tube sub-assembly.
- No separate STEP for the full assembly ZIP contents is verified.
- Concept files do not confirm overheating mitigation details.
  > 💡 Add the missing sub-assembly drawing and verify all required deliverables.

### ❌ `46fc494e…` — score 4/10
- Missing 20-minute node profile plot file.
- No 0.5, 5, 10, and 20 minute profile data shown in text response.
- Text response does not include the required concise report or assessment details.
  > 💡 Provide all required plots, summarize results clearly, and state the pass/fail assessment.

### ❌ `3940b7e7…` — score 4/10
- PDF appears truncated and incomplete.
- Tables contain placeholder values instead of numeric results.
- No evidence of a fully polished, complete report.
  > 💡 Regenerate the PDF with complete numeric tables and full discussion.

### ✅ `8077e700…` — score 6/10
- Only 3 pages; required figures and tables are not clearly included.
- AISI 1045 results are discussed generally, but not clearly analyzed from data.
- The report preview is truncated, so completeness cannot be fully verified.
  > 💡 Include explicit AISI 1045 data analysis and ensure all required figures, tables, and sections are fully present.

### ✅ `5a2d70da…` — score 6/10
- Missing the required email draft if budget could not be met.
- Files may lack verified subtotal and grand total calculations.
- Text response omits key manufacturing and tooling specifics.
  > 💡 Add the missing contingency email and verify all totals and tool selections.

### ✅ `74d6e8b0…` — score 6/10
- PDF content appears truncated in the preview.
- No evidence the Word document contains the full guideline and citations.
- Text response promises a PDF, but the task required Word format only.
  > 💡 Provide a complete Word guideline with full citations and ensure all required content is included.

### ✅ `61b0946a…` — score 6/10
- Output is truncated, so completeness cannot be verified.
- No evidence the procedure-count estimates are fully included.
- The text mentions a chart, but file content is not fully confirmable.
  > 💡 Provide the full document content and verify all required sections and calculations are present.

### ❌ `61e7b9c6…` — score 4/10
- Workbook has duplicate Bijuva row.
- No evidence of complete FDA-approved and off-label coverage.
- Text response repeats itself and lacks specific sourcing.
  > 💡 Verify completeness, remove duplicates, and document pricing sources clearly.

### ❌ `f1be6436…` — score 4/10
- Missing required April 18 timing detail for Dr. Doe.
- Document lacks explicit screenshot date handling language.
- Text response mentions extra files not requested.
  > 💡 Revise the document to include all timing details and clearer date notes.

### ✅ `4b98ccce…` — score 6/10
- No evidence the letters include the full required template content.
- Employee name and ID are not verifiable from the preview.
- Workbook content cannot be fully confirmed from the truncated preview.
  > 💡 Verify the letters and workbook against the provided sheets before delivery.

### ✅ `ef8719da…` — score 8/10
- Word document content appears complete, but PDF conversion success is uncertain.
- Text response is professional, though it does not explicitly mention the draft timeline in the summary.
- No obvious placeholder content, but the preview is truncated for full verification.
  > 💡 Verify the PDF opens correctly and confirm the timeline is clearly stated in the final pitch.

### ❌ `3baa0009…` — score 4/10
- Text response is not the requested article.
- Word count and title requirements are not clearly met in the response.
- Chart file exists, but article content is only a summary of deliverables.
  > 💡 Provide the full 300-500 word article with a clear title and concise chart caption.

### ✅ `6974adea…` — score 6/10
- No evidence the article was actually written in the response.
- Word count and Guardian-style compliance cannot be verified from the preview.
- Source attribution and UK English consistency are not fully demonstrated.
  > 💡 Provide the finished article text and confirm it meets length, style, and sourcing requirements.

### ✅ `0112fc9b…` — score 6/10
- Response promises files but does not provide the SOAP note text.
- Plan content may be incomplete in the preview.
- No clear confirmation of all required SOAP sections in the text response.
  > 💡 Provide the full SOAP note directly and ensure all sections are complete.

### ❌ `772e7524…` — score 4/10
- No actual SOAP note text is provided in the response.
- The response promises files instead of answering the task directly.
- Plan details may be incomplete or hidden in truncated file content.
  > 💡 Provide the full SOAP note in the response and ensure all required clinical sections are complete.

### ❌ `9a0d8d36…` — score 4/10
- No actual presentation content is shown for verification.
- Text response only promises creation, not completed deliverable details.
- Cannot confirm required calculations, tax comparisons, or net proceeds are included.
  > 💡 Provide the finished slide content and verify all required tax examples are present.

### ✅ `feb5eefc…` — score 8/10
- CRAT is correctly framed as charity-focused, but heirs do not benefit from the remainder.
- The recommendation favors GRAT, but could better address marital planning and estate-tax timing.
- The preview is truncated, so full page limit and completeness cannot be fully verified.
  > 💡 Clarify the CRAT’s charitable remainder and strengthen the client-specific recommendation with marital estate-planning context.

### ✅ `ae0c1093…` — score 6/10
- PDF title file names omit the required hyphenated wording.
- Observation form appears to repeat note sections instead of a clean single template.
- Text response is acceptable but slightly generic for the requested deliverables.
  > 💡 Revise the PDFs to match the exact titles and streamline the observation form layout.

### ✅ `f9f82549…` — score 8/10
- PDF title differs from the requested flowchart title.
- Text response mentions a private detective role, which is unnecessary.
- No explicit confirmation that the PPTX has one slide per flowchart header.
  > 💡 Align titles exactly and confirm the slide structure in the deliverable description.

### ✅ `84322284…` — score 8/10
- PDF preview is truncated, so full content cannot be fully verified.
- No DOCX content preview was provided for quality review.
- Text response mentions a DOCX source report, which was not required.
  > 💡 Verify the full PDF and DOCX content against the timeline before final submission.

### ✅ `6241e678…` — score 6/10
- Task list appears incomplete in the provided preview.
- Client review timing may not fully match all required two-day review windows.
- Text response is generic and does not confirm all schedule requirements.
  > 💡 Verify every required task, review window, and final delivery date in the schedule.

### ✅ `e14e32ba…` — score 6/10
- Document preview is truncated, so completeness cannot be fully verified.
- Placeholder image files suggest non-final visual assets.
- One required deli entry may be incomplete in the preview.
  > 💡 Verify all 4-6 entries and replace placeholders with final photos.

### ❌ `e4f664ea…` — score 4/10
- Text response promises deliverables but not the screenplay itself.
- No evidence the script meets 8-12 pages or 10-15 scenes.
- File content appears truncated and may be incomplete.
  > 💡 Provide the full formatted screenplay and verify page count, scene count, and completeness.

### ❌ `02aa1805…` — score 3/10
- No actual well data was extracted for the required water systems.
- Second tab contains a placeholder row instead of potential wells.
- Email lacks identified top options and recommendations.
  > 💡 Extract and verify the source water factsheet data, then populate both tabs with real screened candidates.

### ✅ `fd6129bd…` — score 8/10
- SOP preview is truncated, so completeness cannot be fully verified.
- Text response mentions DOCX and XLSX, but content quality is not directly shown.
- No obvious placeholders, but form field completeness is not fully confirmable.
  > 💡 Verify the full SOP and form against the source summary before final release.

### ✅ `58ac1cc5…` — score 8/10
- Missing explicit internal summary note deliverable.
- Risk assessment appears in PDF, not separate Word document.
- Text response mentions three deliverables but task required four.
  > 💡 Add the missing Teams summary and ensure the risk assessment is a separate Word file.

### ❌ `3c19c6d1…` — score 4/10
- Slide 4 content cannot be verified from the preview.
- Required file content may be incomplete or unverified.
- Text response is generic and lacks deliverable-specific confirmation.
  > 💡 Verify all slides and required sections are present and accurately populated.

### ✅ `55ddb773…` — score 6/10
- Some content may be truncated in the preview.
- No evidence the PDF includes every attached violation question.
- Text response is generic and not fully verifiable.
  > 💡 Verify the PDF against the source violations list and confirm all required items are included.

### ❌ `1e5a1d7f…` — score 3/10
- DOCX preview shows only title and source, not the required table.
- Required columns and task details are missing from the file.
- Text response repeats itself and does not confirm completed content.
  > 💡 Create a populated table in the DOCX with all four required columns and task rows.

### ✅ `0419f1c3…` — score 8/10
- File preview is truncated, so full compliance cannot be fully verified.
- No obvious evidence of missing required sections in the generated document.
- Training recommendations appear aligned with the stated performance gaps.
  > 💡 Confirm the full DOCX includes all signature and consequence sections without truncation.

### ✅ `ed2bc14c…` — score 6/10
- File preview is truncated, so completeness cannot be fully verified.
- Top departure reasons are identified, but exact categorization details are limited.
- No evidence the Word memo fully covers all renewal offer specifics.
  > 💡 Verify the full document includes all four required sections with clear, specific recommendations.

### ✅ `2d06bc0a…` — score 8/10
- Minor truncation in preview, but file appears complete.
- Purchase price rounding is not explicitly shown in the prompt response.
- No obvious formatting issues were verifiable from the preview.
  > 💡 Confirm the final Word file includes all terms and clean formatting throughout.

### ✅ `0818571f…` — score 6/10
- Only six properties were sourced, not 5-10 with full detail.
- Listing sources are generic, not verifiable Crexi or LoopNet citations.
- The text response promises DOCX/PDF/XLSX but omits acquisition criteria analysis.
  > 💡 Add verifiable public listing sources and complete all property pages with full underwriting details.

### ✅ `5ad0c554…` — score 5/10
- Missing most required milestones: consultation, search, pre-offer, and offer process.
- Reference PDF was not found, so adaptation from the source is incomplete.
- Brochure content appears sparse and only partially covers the buyer journey.
  > 💡 Expand the brochure to cover all five milestones and verify source-based details.

### ❌ `11593a50…` — score 4/10
- PDF is only one page, not the required two pages.
- Home photos are missing or not embedded in the PDF.
- Location data appears incorrect: city/state/zip show Massabama, NY 11009.
  > 💡 Regenerate the PDFs with two pages, embedded photos, and corrected property location data.

### ❌ `94925f49…` — score 4/10
- Only four school PDFs were produced; one required report is missing.
- Reports are one page and contain many 'To verify' placeholders.
- No evidence of reputable source data or current home listing verification.
  > 💡 Produce all five complete PDFs with verified school metrics and current nearby listings.

### ✅ `90f37ff3…` — score 6/10
- PDF is only 2 pages, not the required 4 pages.
- Comparable details appear incomplete and may lack source verification.
- The report may not fully match the reference template structure.
  > 💡 Revise the report to four pages and add fully sourced, verified comparable data.

### ❌ `d3d255b2…` — score 4/10
- Text response is duplicated and not a complete report summary.
- Original task requested a PDF report; only file creation is described.
- Market analysis support is present, but the final recommendation is truncated.
  > 💡 Provide a complete, non-duplicated seller-facing report summary and confirm the PDF content is fully finished.

### ❌ `1bff4551…` — score 4/10
- PDF content is truncated and may omit required songs and links.
- No evidence the set list was researched against the Institute collection.
- The original song 'Fistful of Flyers' is not clearly included in the preview.
  > 💡 Provide a complete PDF with verified song choices, collection relevance, and full YouTube links.

### ✅ `01d7e53e…` — score 6/10
- Preview is truncated, so completeness cannot be verified.
- Referenced attached contract language may be missing or unconfirmed.
- No evidence the Word draft fully matches all required terms.
  > 💡 Verify the full document includes all required clauses and attachments.

### ❌ `90edba97…` — score 4/10
- Response is generic and does not confirm completed data entry.
- No patient-specific results or monthly changes are summarized.
- Text repeats and omits the required final deliverable details.
  > 💡 Provide a concise completion summary with patient-specific workbook confirmation.

### ❌ `8384083a…` — score 4/10
- Missing Miebo and some package details in the text response.
- Claims a PDF and Excel file, but content accuracy appears questionable.
- Several days' supply values look inconsistent with standard package calculations.
  > 💡 Verify all medication calculations and ensure the guide fully matches the requested audit reference details.

### ✅ `a69be28f…` — score 6/10
- Text response says it will create the deck, not that it is complete.
- Preview shows only Midwest slides, missing other required regions.
- Some fit names appear truncated or misspelled in the PDF.
  > 💡 Add all regional slides and verify labels, then regenerate the PDF.

### ✅ `74ed1dc7…` — score 6/10
- Document content is truncated in the preview, so completeness cannot be fully verified.
- No explicit confirmation that all required order-type rationale and reporting impacts are included.
- The text response is generic and does not summarize the actual proposal details.
  > 💡 Provide a complete, concise proposal summary and ensure the document fully covers all required order types.

### ✅ `69a8ef86…` — score 6/10
- Internal file preview is truncated, so required steps cannot be fully verified.
- No evidence the 90-day manual closure and account notification are included.
- Text response is generic and does not summarize the deliverables professionally.
  > 💡 Provide complete step-by-step content and explicitly include all deadline and closure requirements.

### ✅ `105f8ad0…` — score 6/10
- Workbook preview is truncated, so completeness cannot be fully verified.
- No evidence of the required online competitor research or source citations.
- Rationale appears generic and may not fully address all pricing relationships.
  > 💡 Add sourced competitor data and verify every SKU, size bucket, and rationale in the workbook.

### ❌ `b57efde3…` — score 3/10
- Only one placeholder record was extracted.
- No actual prospect leads were identified.
- Contact and fit details are not actionable.
  > 💡 Manually review the exhibitor list and populate verified AUV, ROV, and camera leads.

### ❌ `15d37511…` — score 4/10
- Workbook uses assumed pricing, not exact email values.
- Requested spreadsheet is not clearly simple or fully labeled.
- Summary document is extra and may not match the requested deliverable.
  > 💡 Replace assumptions with exact pricing email data and verify all required columns and totals.

### ✅ `9efbcd35…` — score 6/10
- PDF is only 2 pages, not the required four-page maximum summary.
- Preview shows truncated content, so completeness cannot be fully verified.
- Text response is a plan, not a completed deliverable summary.
  > 💡 Provide a fully completed, concise four-page document with all required sections and verified source-based content.

### ✅ `1d4672c8…` — score 6/10
- Excel preview is truncated, so required correlation matrix content cannot be verified.
- The workbook sheet names and exact column headers are not fully confirmed.
- The response promises a PDF, but content quality and completeness are only partially evidenced.
  > 💡 Verify the Excel sheets and PDF contain the full requested data, matrix, and analysis.

### ✅ `bb499d9c…` — score 8/10
- Preview is truncated, so full completeness cannot be fully verified.
- No explicit confirmation of the 25-page limit in the provided content.
- Text response mentions PDF generation, which was not required.
  > 💡 Verify the full document length and final section completeness before approval.

### ✅ `a4a9195c…` — score 8/10
- Text response mentions PDF generation, which was not requested.
- Preview is truncated, so full SOP completeness cannot be fully verified.
- No obvious formatting confirmation for the five-page limit is shown.
  > 💡 Confirm the SOP is complete, under five pages, and remove unnecessary PDF mention.

### ❌ `11dcc268…` — score 4/10
- Only three items appear populated; likely incomplete receipt coverage.
- No evidence the half-quantity P11-P09457-01 was handled correctly.
- Text response is generic and does not confirm workbook contents.
  > 💡 Verify all receipts against both source sheets and confirm every required line is populated.

### ❌ `76418a2c…` — score 3/10
- Spreadsheet appears blank and unpopulated.
- No evidence of shipping method calculations or savings.
- Text response promises completion without verifying required data.
  > 💡 Populate the manifest with all shipment details and validate calculations.

### ❌ `0e386e32…` — score 3/10
- Privacy logic description is truncated and incomplete.
- No evidence of full implementation or tested cross-chain withdrawal flow.
- Output is only a high-level promise, not a verified deliverable summary.
  > 💡 Provide a complete, verified codebase summary with all required components and no truncation.

### ✅ `854f3814…` — score 6/10
- Query uses a broad bounding box, not a precise ABQ-to-OKC corridor filter.
- Instructions are truncated and may be incomplete.
- Text response promises files but does not summarize the actual deliverables.
  > 💡 Tighten the corridor query and provide complete, untruncated Markdown instructions.

### ❌ `2c249e0f…` — score 4/10
- Output is only a narrative, not the required YAML and text file contents.
- The response does not include the actual data_flow.txt content.
- The OpenAPI deliverable may be incomplete or truncated.
  > 💡 Provide the full OpenAPI YAML and the complete data_flow.txt content.

## Failure Analysis

The clearest hard-failure pattern was deterministic schema brittleness in structured data tasks, especially spreadsheets. Errors on 7b08cd4d-df60-41ae-9102-8aaa49306ba2, 99ac6944-4ec6-4848-959c-a460ac705c6f, aa071045-bcb0-4164-bb85-97245d56287e, 1752cb53-5983-46b6-92ee-58ac85a11283, 47ef842d-8eac-4b90-bda8-dd934c228c96, and 6d2c8e55-fe20-45c6-bdaf-93e676868503 were all caused by rigid assumptions about headers, sheet layout, or table structure rather than deep reasoning failure. The same weakness showed up in low-QA successes: 24d1e93f-9018-45d4-b522-ad89dfd78079 had blank NPVs, 9e39df84-ac57-4c9b-a2e3-12b8abf2c797 had blank dashboard pivots, 76418a2c-a3c0-4894-b89d-2493369135d9 produced an unpopulated manifest, 8079e27d-b6f3-4f75-a9b5-db27903c798d misaligned S&P rows, and 02aa1805-c658-4069-8a6a-02dec146063a extracted placeholder well data. By contrast, template-preserving workbook tasks with simpler schemas, such as dfb4e0cd-a0b7-454e-b943-0dd586c2764c, 327fbc21-7d26-4964-bf7c-f4f41e55c54d, and 4520f882-715a-482d-8e87-1cb3cbdfe975, scored 9 and show the model can execute well when the input structure is stable.

A second pattern was deliverable substitution: many low-QA tasks technically completed but returned a plan, status note, or thin fallback artifact instead of the requested final product. Examples include f84ea6ac-8f9f-428c-b96c-d0884e30f7c7 with no actual research table, 36d567ba-e205-4313-9756-931c6e4691fe with only title/instructions for a compliance tool, a1963a68-1bea-4bb1-b7e0-145c92a57449 collapsing a strategy deck into a one-page fallback PDF, c94452e4-39cd-4846-b73a-ab75933d1ad7 delivering a production summary instead of a 15-second MP4, a97369c7-e5cf-40ca-99e8-d06f81c57d53 describing future legal work instead of a memo, and 0112fc9b-c3b2-4084-8993-5a4abb1f54f1 plus 772e7524-174e-4c88-957e-6e510b61ea69 promising SOAP-note files without substantive note content. This same issue also appeared as wrong format or incomplete format compliance, such as c44e9b62-7cd8-4f72-8ad9-f8fbddb94083 producing PDF instead of Word and 11593a50-734d-4449-b5b4-f8986a133fd8 missing the required two-page, photo-embedded layout.

Task complexity mattered most when it combined media processing, code packaging, or external research. Information-sector occupations were the strongest cluster for media/runtime failures: 75401f7c-396d-406d-b08e-938874ad1045 failed on missing moviepy, a941b6d8-4289-4500-b45a-f8e4fc94a724 hit OpenCV memory exhaustion, c94452e4-39cd-4846-b73a-ab75933d1ad7 never produced the video, and e222075d-5d62-4757-ae3c-e34b0846583b still lacked verifiable stock/music sourcing even when it succeeded. Professional, Scientific, and Technical Services showed a parallel pattern in code and analytic work: 7de33b48-5163-4f50-b5f3-8deea8185e57 and 4122f866-01fa-400b-904d-fa171cdab7c7 failed on unterminated strings, while 0e386e32-df20-4d1f-b536-7159bc409ad5 and 2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f produced high-level narratives instead of verifiable code/spec artifacts. Research-heavy tasks that depended on current sourcing also dragged quality down: f84ea6ac-8f9f-428c-b96c-d0884e30f7c7 explicitly noted no internet research, a10ec48c-168e-476c-8fe3-23b2a5f616ac lacked sourced restaurant detail, 94925f49-36bc-42da-b45b-61078d329300 contained To verify placeholders, and b57efde3-26d6-4742-bbff-2b63c43b4baa extracted only a placeholder prospect record.

Retries helped recover some borderline tasks but did not fix structural bugs. All 15 hard failures were already retried, so the current retry loop did not resolve deterministic issues such as 7b08cd4d-df60-41ae-9102-8aaa49306ba2, 75401f7c-396d-406d-b08e-938874ad1045, a0552909-bc66-4a3a-8970-ee0d17b49718, b5d2e6f1-62a2-433a-bcdd-95b260cdd860, 7de33b48-5163-4f50-b5f3-8deea8185e57, and 4122f866-01fa-400b-904d-fa171cdab7c7. Retries were effective when the first pass was close enough for repair, as seen in a328feea-47db-4856-b4be-2bdc63dd88fb, c357f0e2-963d-4eb7-a6fa-3078fe55b3ba, 327fbc21-7d26-4964-bf7c-f4f41e55c54d, ffed32d8-d192-4e3f-8cd4-eda5a730aec3, and 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b, all of which ended at QA 9 after retry. But retried tasks also often remained weak, such as 7d7fc9a7-21a7-4b83-906f-416dea5ad04f at QA 2, a10ec48c-168e-476c-8fe3-23b2a5f616ac at QA 3, and 9e39df84-ac57-4c9b-a2e3-12b8abf2c797 at QA 4. Latency was not a quality proxy: short runs often produced placeholder outputs like c94452e4-39cd-4846-b73a-ab75933d1ad7 and f84ea6ac-8f9f-428c-b96c-d0884e30f7c7, while long runs sometimes ended in partial artifacts or resource failures, such as c7d83f01-2874-4876-b7fd-52582ec99e1a and a941b6d8-4289-4500-b45a-f8e4fc94a724.

## Recommendations

Add a mandatory schema-introspection and normalization stage before any transformation code runs. For workbook and table tasks, the agent should first list sheet names, trim and case-normalize headers, map aliases and near-matches, and explicitly confirm required columns before writing outputs. That would directly reduce the KeyError/ValueError class seen in 99ac6944-4ec6-4848-959c-a460ac705c6f, aa071045-bcb0-4164-bb85-97245d56287e, 1752cb53-5983-46b6-92ee-58ac85a11283, 47ef842d-8eac-4b90-bda8-dd934c228c96, 7b08cd4d-df60-41ae-9102-8aaa49306ba2, and 6d2c8e55-fe20-45c6-bdaf-93e676868503, and it would also catch silent weak-success cases like 24d1e93f-9018-45d4-b522-ad89dfd78079, 9e39df84-ac57-4c9b-a2e3-12b8abf2c797, 76418a2c-a3c0-4894-b89d-2493369135d9, and 02aa1805-c658-4069-8a6a-02dec146063a before a low-value artifact is saved. Prompt-wise, require the agent to show the discovered mappings in its working notes so it cannot proceed with hidden schema assumptions.

Use differentiated execution environments by deliverable type instead of a single generic subprocess profile. Media tasks need dependency checks for ffmpeg/moviepy and memory-aware processing with downsampling, chunking, or proxy generation to avoid failures like 75401f7c-396d-406d-b08e-938874ad1045 and a941b6d8-4289-4500-b45a-f8e4fc94a724. Code-packaging tasks should run compile/lint/smoke-test steps before finalization; that would have caught the triple-quote failures in 7de33b48-5163-4f50-b5f3-8deea8185e57 and 4122f866-01fa-400b-904d-fa171cdab7c7 and the API-signature mismatch in 664a42e5-3240-413a-9a57-ea93c6303269. Spreadsheet-writing code should include safe merged-cell handling to prevent the openpyxl crashes seen in a0552909-bc66-4a3a-8970-ee0d17b49718 and a99d85fc-eff8-48d2-a7d4-42a75d62f18d.

Tighten completion gating so the system does not count plan-like or format-mismatched outputs as acceptable successes. A simple rule-based QA layer should flag final responses that still read like intent statements rather than proof of completion, especially in tasks like f84ea6ac-8f9f-428c-b96c-d0884e30f7c7, c94452e4-39cd-4846-b73a-ab75933d1ad7, a97369c7-e5cf-40ca-99e8-d06f81c57d53, 0112fc9b-c3b2-4084-8993-5a4abb1f54f1, and 772e7524-174e-4c88-957e-6e510b61ea69. Add cheap artifact checks matched to the task: page/slide counts for decks and reports (a1963a68-1bea-4bb1-b7e0-145c92a57449, 11593a50-734d-4449-b5b4-f8986a133fd8, 90f37ff3-e4ed-4a0b-94bb-bed0f7def1ef), required tab counts and non-zero formulas for workbooks (24d1e93f-9018-45d4-b522-ad89dfd78079, 9e39df84-ac57-4c9b-a2e3-12b8abf2c797, 76418a2c-a3c0-4894-b89d-2493369135d9), citation/source checks for research deliverables (a10ec48c-168e-476c-8fe3-23b2a5f616ac, 94925f49-36bc-42da-b45b-61078d329300, b57efde3-26d6-4742-bbff-2b63c43b4baa), and exact file-type validation for tasks with strict format requirements (c44e9b62-7cd8-4f72-8ad9-f8fbddb94083, 74d6e8b0-f334-4e7e-af55-c095d5d4d1a6).

Replace generic retries with adaptive, traceback-aware repair and domain routing. Since every hard failure already had retried=true, the first retry should ingest the exception, inspect the input files, and regenerate with a safer strategy rather than rerunning the same plan. If the failure is dependency- or memory-related, route to a media-capable worker; if it is schema-related, route to a data-normalization template; if it is syntax-related, force compile-before-package. Also tune model configuration by domain: keep medium reasoning for sectors already strong on routine office artifacts, such as Retail and many Wholesale/Government tasks, but raise reasoning and QA strictness for Information and Professional/Scientific/Technical tasks where confidence spread is widest and failures cluster around media, code, law, accounting, and research extraction. That should improve both the 15 execution errors and the larger pool of low-confidence successes without paying a universal latency penalty.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 3 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 4 file(s)
- `f9a1c16c…` (Information): 4 file(s)
- `38889c3b…` (Information): 6 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 3 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 4 file(s)
- `bbe0a93b…` (Government): 6 file(s)
- `85d95ce5…` (Government): 2 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 4 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 3 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 2 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 2 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 1 file(s)
- `f3351922…` (Finance and Insurance): 2 file(s)
- `61717508…` (Finance and Insurance): 2 file(s)
- `0ed38524…` (Finance and Insurance): 3 file(s)
- `87da214f…` (Finance and Insurance): 2 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e222075d…` (Information): 4 file(s)
- `c94452e4…` (Information): 2 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 3 file(s)
- `9e8607e7…` (Finance and Insurance): 3 file(s)
- `c7d83f01…` (Finance and Insurance): 7 file(s)
- `46b34f78…` (Finance and Insurance): 3 file(s)
- `a1963a68…` (Finance and Insurance): 5 file(s)
- `5f6c57dd…` (Finance and Insurance): 1 file(s)
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
- `0353ee0c…` (Health Care and Social Assistance): 3 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 1 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `bf68f2ad…` (Manufacturing): 1 file(s)
- `efca245f…` (Manufacturing): 1 file(s)
- `9e39df84…` (Manufacturing): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 1 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 5 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 2 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 3 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 7 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 2 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 13 file(s)
- `46fc494e…` (Manufacturing): 10 file(s)
- `3940b7e7…` (Manufacturing): 2 file(s)
- `8077e700…` (Manufacturing): 1 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 2 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 6 file(s)
- `f1be6436…` (Health Care and Social Assistance): 7 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 2 file(s)
- `3baa0009…` (Information): 2 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 2 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 2 file(s)
- `c657103b…` (Finance and Insurance): 4 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 3 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 3 file(s)
- `a46d5cd2…` (Retail Trade): 2 file(s)
- `6241e678…` (Information): 3 file(s)
- `e14e32ba…` (Information): 6 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 2 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 4 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 1 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 1 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 7 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 16 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 3 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 5 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 6 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 1 file(s)
- `0ec25916…` (Health Care and Social Assistance): 5 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 1 file(s)
- `91060ff0…` (Retail Trade): 7 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `ffed32d8…` (Retail Trade): 3 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 2 file(s)
- `788d2bc6…` (Wholesale Trade): 5 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 3 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 4 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `9efbcd35…` (Finance and Insurance): 3 file(s)
- `1d4672c8…` (Finance and Insurance): 3 file(s)
- `4de6a529…` (Finance and Insurance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 1 file(s)
- `bb499d9c…` (Finance and Insurance): 4 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 2 file(s)
- `552b7dd0…` (Manufacturing): 4 file(s)
- `11dcc268…` (Manufacturing): 1 file(s)
- `76418a2c…` (Manufacturing): 1 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `854f3814…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
