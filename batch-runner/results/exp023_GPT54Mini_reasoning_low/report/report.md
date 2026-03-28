# Experiment Report: GPT-5.4-Mini Reasoning LOW — Full Benchmark (Ablation 3/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp023_GPT54Mini_reasoning_low` |
| **Condition** | GPT-5.4-Mini reasoning=low + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4-mini |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-26 |
| **Duration** | 115m 16s |
| **Generated At** | 2026-03-26T16:55:08.264350+00:00 |
| 🤗 HF Dataset | [exp023_GPT54Mini_reasoning_low](https://huggingface.co/datasets/HyeonSang/exp023_GPT54Mini_reasoning_low) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp023_GPT54Mini_reasoning_low/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated gpt-5.4-mini in subprocess execution mode with reasoning set to low and a gpt-audio-1.5 preprocessing stage. Across 220 benchmark tasks, the run completed 204 successfully, for a 92.7% task completion rate, with 16 errors and 41 retried tasks. Average end-to-end latency was 19,923 ms.

From an LLM-evaluated quality perspective, the average Self-QA score was 6.75/10, with a wide range from 1 to 10. That pattern indicates generally usable outputs with moderate self-assessed confidence, but also nontrivial variance across individual tasks. The run therefore looks operationally strong on completion, while quality consistency is more mixed than the completion rate alone suggests.

At the sector level, completion was strongest in Government at 25/25 and very high in Real Estate and Rental and Leasing at 24/25. Information was the slowest sector at 28,676 ms average latency and also one of the lower-completion groups at 22/25, while Wholesale Trade had the highest average Self-QA score at 7.7/10 with 23/25 successful tasks. Deliverable file generation quality appears broadly reliable when tasks complete, but the 41 retries and 16 terminal errors indicate some instability in producing final artifacts without re-execution.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 204 (92.7%) |
| Errors | 16 |
| Retried Tasks | 41 |
| Avg QA Score | 6.75/10 |
| Min QA Score | 1/10 |
| Max QA Score | 10/10 |
| Avg Latency | 19,923ms |
| Max Latency | 172,906ms |
| Total LLM Time | 4383s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 173 (93.5%) |
| Failed → dummy created | 12 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 17 | 17 | 0 |
| 2 | 24 | 8 | 16 |

## Quality Analysis

The Self-QA distribution suggests a mid-to-upper quality center with meaningful spread. An average of 6.75/10 implies moderate self-assessed confidence overall, but the minimum of 1 shows that some outputs were judged by the model itself as poor or incomplete. The maximum of 10 confirms that the stack can produce high-confidence deliverables on some tasks, so the main issue is variability rather than an absolute quality ceiling.

Sector-level differences are noticeable. Wholesale Trade stands out with the best LLM-evaluated quality at 7.7/10 and relatively low latency at 16,832 ms, suggesting that this domain is well matched to the current configuration. Real Estate and Rental and Leasing also performed well, combining 24/25 completion with 7.1/10 average Self-QA and low latency. By contrast, Health Care and Social Assistance had one of the weaker quality profiles at 6.3/10 despite relatively fast latency, indicating that speed alone did not translate into stronger self-assessed confidence.

Latency does not show a simple positive relationship with quality. Information had the highest average latency by a large margin at 28,676 ms, but only 6.5/10 average Self-QA and 22/25 completion, which points to more difficult or less stable task handling rather than deeper processing yielding better deliverables. Government completed all 25 tasks with 6.7/10 Self-QA at 17,952 ms, a better operational balance than Information. Wholesale Trade further supports the weak latency-quality correlation by achieving the best quality score with one of the fastest average runtimes.

Occupation-specific observations are not directly exposed in the provided summary, so evaluation is limited to sector aggregates. Within that constraint, the data suggests the model generates acceptable deliverable files in most domains, but with uneven confidence across task types and some artifact-generation instability reflected in the retry count. In practical terms, the run shows strong task completion and generally serviceable output quality, while domain-specific tuning would likely be most useful for lower-confidence sectors such as Health Care and the slower, less efficient Information workload.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 23 | 92.0% | 6.48/10 | 22,229ms |
| Government | 25 | 25 | 100.0% | 6.72/10 | 17,952ms |
| Health Care and Social Assistance | 25 | 23 | 92.0% | 6.35/10 | 16,977ms |
| Information | 25 | 22 | 88.0% | 6.55/10 | 28,676ms |
| Manufacturing | 25 | 23 | 92.0% | 6.48/10 | 19,971ms |
| Professional, Scientific, and Technical  | 25 | 23 | 92.0% | 6.52/10 | 20,786ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 7.08/10 | 16,937ms |
| Retail Trade | 20 | 18 | 90.0% | 6.89/10 | 18,702ms |
| Wholesale Trade | 25 | 23 | 92.0% | 7.7/10 | 16,832ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 6/10 | 14430ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 9/10 | 18707ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 9/10 | 17538ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 3 | 4/10 | 24739ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 4/10 | 18244ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 18779ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 2 | 9/10 | 16469ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 2 | 9/10 | 26897ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 9/10 | 35783ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 3 | 4/10 | 24759ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 8/10 | 24834ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 5 | 9/10 | 24490ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | Yes | 7 | 9/10 | 43181ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 9/10 | 27088ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | 4/10 | 18811ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 12306ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 4 | 6/10 | 17940ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 18306ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 14928ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 13868ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 9/10 | 14433ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 4 | 4/10 | 19561ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | 7/10 | 16927ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 2 | 4/10 | 21346ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | 4/10 | 19882ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 6/10 | 11805ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 10011ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 10705ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 11753ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | Yes | 3 | 6/10 | 29632ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 8/10 | 23593ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 7/10 | 16335ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 6/10 | 20124ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 9/10 | 22928ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 4 | 8/10 | 24481ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 13511ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 9/10 | 19672ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 4/10 | 22579ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 8/10 | 13958ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 15784ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 14528ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 1 | 9/10 | 21866ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 14667ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 10/10 | 11788ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 9/10 | 12662ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 6/10 | 8580ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 4/10 | 19408ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 2 | 8/10 | 16999ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 17800ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 6/10 | 9035ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 2 | 6/10 | 12053ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 2 | 6/10 | 17104ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | 6/10 | 20891ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | 6/10 | 15041ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 4/10 | 19411ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 9/10 | 8288ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 19354ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 16836ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | Yes | 2 | 4/10 | 98609ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 172906ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 4/10 | 15682ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 8/10 | 20653ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 8/10 | 46537ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 8 | 8/10 | 25000ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 4 | 8/10 | 23688ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 6/10 | 31657ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 1 | 6/10 | 33750ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 8/10 | 25127ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 8/10 | 20825ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 8/10 | 35714ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 4/10 | 15764ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 15516ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 21745ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 9/10 | 14969ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 18600ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 6/10 | 17365ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 9/10 | 11801ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 4/10 | 15252ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 8/10 | 17221ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 4/10 | 25072ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 6/10 | 21330ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 1 | 6/10 | 25137ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 6/10 | 10935ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 16569ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 1 | 6/10 | 15693ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 8/10 | 12622ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 6/10 | 18767ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 17832ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 8/10 | 14629ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 12056ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 0 | 1/10 | 20942ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 4/10 | 16828ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 19310ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 22373ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | 9/10 | 37436ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 19143ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 21750ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 9/10 | 18221ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 2 | 9/10 | 21121ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 13254ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 9/10 | 23622ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 6/10 | 35145ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 4/10 | 27999ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 4/10 | 35311ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 10 | 7/10 | 53558ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 16346ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 4/10 | 14710ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 11811ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 9/10 | 19974ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 19030ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 5 | 7/10 | 20269ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 9/10 | 20797ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 4/10 | 21474ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 5 | 6/10 | 24798ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 2 | 8/10 | 21218ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 20411ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 8325ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 14041ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 4/10 | 9019ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 6 | 9/10 | 20968ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 6/10 | 21962ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 6/10 | 14060ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 18484ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 25713ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 6/10 | 16294ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 9/10 | 8398ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 11746ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 6/10 | 9638ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | 4/10 | 14198ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 16378ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 27613ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | 9/10 | 33146ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 8814ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 11560ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 4 | 8/10 | 16707ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 15765ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 8/10 | 14725ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 10316ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 11824ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 16034ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 21922ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 25592ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | Yes | 1 | 4/10 | 17291ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | Yes | 2 | 4/10 | 21959ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 9/10 | 25257ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 6/10 | 16685ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 6/10 | 22594ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 4/10 | 14108ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 15650ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 14844ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | 6/10 | 25606ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 22746ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 26753ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 4/10 | 26224ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 9/10 | 16313ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | Yes | 2 | 2/10 | 23299ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 28483ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 1 | 6/10 | 24127ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 7/10 | 32606ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 1 | 4/10 | 26918ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 6/10 | 27575ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 6/10 | 16844ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 4/10 | 9321ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 7/10 | 18181ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 9/10 | 16933ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 2 | 8/10 | 23748ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 11754ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 8508ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 3/10 | 22803ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 3/10 | 17150ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 9/10 | 17530ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 6/10 | 18908ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 6 | 4/10 | 19059ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 8/10 | 19116ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 9/10 | 14971ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 2 | 8/10 | 11954ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 12924ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 12822ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 1 | 6/10 | 15960ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 16734ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 12803ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 8/10 | 12345ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 20555ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 16242ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 8639ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 5 | 9/10 | 27147ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 4/10 | 11628ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 7/10 | 16259ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 3/10 | 6488ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 18257ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 6/10 | 7838ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 19179ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 17 | 9/10 | 35060ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 6/10 | 21970ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 8/10 | 10699ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 8/10 | 21528ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 22591ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 17481ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 21316ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 6/10 | 20549ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 8299ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 13091ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 11498ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 9/10 | 18264ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 4/10 | 16193ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 15224ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 18693ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 8/10 | 23363ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 6/10 | 12106ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 8/10 | 23854ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 4/10 | 12148ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 9/10 | 10354ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | 8/10 | 17529ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 10117ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | 2/10 | 11675ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 6/10 | 27414ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 9414ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 8/10 | 10074ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 26953ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 8/10 | 27382ms |

## QA Issues

### ✅ `83d10b06…` — score 6/10
- Variance column appears duplicated instead of a single J calculation.
- Sample selection criteria coverage is not verifiable from the preview.
- Text response promises validation but gives no audit-specific results.
  > 💡 Verify the workbook structure and confirm sampled rows satisfy every required criterion.

### ❌ `43dc9778…` — score 4/10
- Only a draft summary is provided; no actual completed Form 1040 data is shown.
- The package appears to contain implausible tax amounts and likely invalid calculations.
- Required e-file forms may be listed, but final IRS-ready validation is not demonstrated.
  > 💡 Provide a fully completed, validated 1040 package with accurate calculations and supporting forms.

### ❌ `ee09d943…` — score 4/10
- Response is generic and does not verify workbook contents.
- No evidence all April source files were incorporated.
- Potential mismatch between promised and actual tab updates.
  > 💡 Confirm each required schedule and source file is reflected in the workbook.

### ❌ `f84ea6ac…` — score 3/10
- DOCX lacks the required five-study summary table.
- No article details, findings, or government implications are included.
- Output is only a brief note, not the requested research summary.
  > 💡 Provide a one-page table with five post-2020 public academic articles and concise findings.

### ❌ `c44e9b62…` — score 4/10
- Reduction is 3.8%, below the required 4%.
- Briefing note omits the incomplete resignation detail handling.
- Organizational chart preview appears garbled and hard to verify.
  > 💡 Recalculate reductions to meet 4% and verify all deliverables are complete and legible.

### ❌ `4b894ae3…` — score 4/10
- Edit log times do not match the provided reference spots.
- Text response mentions a DOCX log, but the task only required the final mix.
- Bass fixes appear incomplete versus the five referenced edit spots.
  > 💡 Align all edits to the reference times and ensure the final mix fully reflects every required bass correction.

### ✅ `93b336f3…` — score 6/10
- Only assembly savings are analyzed; broader partnership economics are missing.
- The document is 2 pages, but the task requested 2–3 pages and a CPO-focused proposal.
- Text response mentions extra files, but no explicit validation of content quality is shown.
  > 💡 Revise the proposal to include a fuller CPO-ready business case and verify all calculations.

### ✅ `15ddd28d…` — score 6/10
- Output is incomplete; the document preview is truncated.
- Original task asks to outline a preferred path, but the preview cuts off mid-section.
- No evidence the full 2–3 page strategy is complete and polished.
  > 💡 Provide the full document content and verify all required sections are present.

### ✅ `05389f78…` — score 6/10
- Report preview is truncated, so completeness cannot be verified.
- No evidence the INR calculations and quote comparison are fully shown.
- Text response is generic and does not confirm validation of content accuracy.
  > 💡 Verify the full report includes complete calculations, comparisons, and a clear replacement recommendation.

### ❌ `a74ead3b…` — score 4/10
- No evidence the slides closely follow the manual content.
- Text response is generic and does not confirm session-specific coverage.
- No verification of accessible language or neutral image use in the PPTX files.
  > 💡 Review both presentations against the manual and add session-specific content details.

### ✅ `bbe0a93b…` — score 7/10
- Resource guide preview is truncated, so completeness cannot be verified.
- Needs assessment uses 'Questions related to areas of needs' instead of a cleaner table header.
- Spanish follow-up table label appears awkward and may need proofreading.
  > 💡 Verify the full resource guide and polish table labels for consistency.

### ❌ `85d95ce5…` — score 4/10
- PDF is only 4 pages, not the required 8-15 pages.
- A DOCX was produced, but the task required a PDF final deliverable.
- The text response is generic and does not confirm completion of all report sections.
  > 💡 Revise the report to fully complete the template and ensure the PDF meets the page and content requirements.

### ❌ `76d10872…` — score 4/10
- Text response does not include the actual report content.
- Case details appear incomplete or truncated in the preview.
- Custodial parent fields are blank in the generated file.
  > 💡 Provide a fully populated report with all required case data and verified fields.

### ✅ `36d567ba…` — score 6/10
- Preview is truncated, so full compliance cannot be verified.
- Topic 10 content is incomplete in the preview.
- No evidence of a 1-2 page length check.
  > 💡 Provide the complete document text and confirm page length.

### ✅ `4c18ebae…` — score 6/10
- Text response is generic and not a completed SAR narrative.
- Preview shows truncated content, so completeness cannot be verified.
- No evidence the Excel and image contents match required analysis fields.
  > 💡 Provide the finalized SAR narrative and verify all file contents against the task requirements.

### ✅ `cebf301e…` — score 8/10
- Output is a design brief, not an implementation deliverable.
- The preview is truncated, so completeness cannot be fully verified.
- No explicit mention of the six-week delivery plan in the response.
  > 💡 Add a concise implementation plan and ensure all required requirements are explicitly covered.

### ✅ `c2e8f271…` — score 7/10
- PDF is only 3 pages, but the task allows up to 6 pages and expects a fuller draft.
- Preview is truncated, so completeness of testing, documentation, and commit guidelines cannot be fully verified.
- Text response promises validation, but no evidence of content review or source-of-truth structure is shown.
  > 💡 Expand the document to cover all required guidelines and verify the full file contents.

### ✅ `2ea2e5b5…` — score 6/10
- Strategic level section appears truncated in the prompt.
- No evidence the PPTX includes all required classifications from the source data.
- Text response is generic and lacks specific results or validation.
  > 💡 Verify the deck covers every category and includes complete, accurate classifications.

### ✅ `a45bc83b…` — score 8/10
- POC guide preview is truncated, so completeness cannot be fully verified.
- No direct evidence of the diagram's visual style or official icon usage.
- Text response is professional but generic and adds no solution specifics.
  > 💡 Verify the full documents include all required architecture details and official GCP iconography.

### ✅ `a10ec48c…` — score 6/10
- No actual restaurant table content is visible in the preview.
- Cuisine subtables are present, but restaurant entries cannot be verified.
- The response text does not confirm exclusion of permanently closed restaurants.
  > 💡 Verify the document contains complete restaurant rows with sourced details and working links.

### ❌ `f5d428fd…` — score 4/10
- PDF is three pages, not two.
- The text response is only a process note, not a complete itinerary.
- The preview is truncated, so required photo sourcing cannot be verified.
  > 💡 Provide a complete two-page itinerary with verified royalty-free images and full destination details.

### ✅ `2fa8e956…` — score 8/10
- Document preview is truncated, so completeness cannot be fully verified.
- Need confirmation that all wineries are within one hour by Google Maps.
- Formatting requirements cannot be fully checked from preview.
  > 💡 Verify the full document meets all content and formatting requirements.

### ✅ `0e4fe8cd…` — score 6/10
- Task text was cut off, so completeness is uncertain.
- Links and factual research are not visible in the preview.
- No evidence of all four day tabs being fully populated.
  > 💡 Verify each sheet includes complete researched links, timings, and all four days.

### ✅ `f3351922…` — score 6/10
- Text response is not an email and omits a proper closing.
- The preview shows truncated content, suggesting the response may be incomplete.
- No evidence the exact requested subject line was used in the deliverable.
  > 💡 Revise the document into a complete email with the exact subject line and full closing.

### ❌ `61717508…` — score 4/10
- Training deck is only 2 pages, not the requested ~10 pages.
- Second PDF content is not shown, so required mock accounts cannot be verified.
- An extra PNG file was produced instead of only the two requested PDFs.
  > 💡 Regenerate the deliverables with a full 10-page deck and verified three-account scenario PDF.

### ✅ `d025a41c…` — score 6/10
- Case Three content appears truncated in the preview.
- No evidence the full document stays under five pages.
- Text response is generic and not fully complete.
  > 💡 Verify the full document content and formatting against all task requirements.

### ✅ `401a07f1…` — score 6/10
- No actual links are visible in the provided text preview.
- The editorial appears truncated before the call to action finishes.
- The response is a promise, not the editorial content itself.
  > 💡 Provide the full editorial text with explicit source links and complete ending.

### ✅ `afe56d05…` — score 6/10
- Only a PDF and DOCX were produced; the task required a Word document.
- The document appears truncated in preview, so completeness and word count are unverified.
- The response promises a PDF version, which was not requested.
  > 💡 Ensure the DOCX is complete, within the required word count, and avoid adding unrequested deliverables.

### ✅ `9a8c8e28…` — score 6/10
- Quiz content appears truncated in the preview.
- No evidence the guide includes the required bibliography links.
- Cannot verify all three PDFs fully satisfy the task from the provided output.
  > 💡 Provide complete file previews or summaries confirming every required section is present.

### ✅ `3a4c347c…` — score 6/10
- File content preview is truncated, so completeness cannot be fully verified.
- No detailed story ideas or named contributors are visible in the preview.
- Broadcast schedule and VT/radio re-versioning details appear incomplete.
  > 💡 Verify the full document includes all required sections and specific story planning details.

### ❌ `ec2fccc9…` — score 4/10
- Response is duplicated and not a complete professional deliverable.
- No actual article text or keyword list is provided in the response.
- File content may be incomplete or truncated, with missing required details.
  > 💡 Provide a single complete DOCX-ready article with all required SEO elements and keyword list.

### ❌ `75401f7c…` — score 4/10
- Duration is only 46.5 seconds, not near the 1:20 maximum.
- Required sound effects and embedded audio usage are not documented.
- The text response promises an edit log, which is unnecessary and incomplete.
  > 💡 Extend the reel and verify all required audio placements and shot order.

### ❌ `8079e27d…` — score 4/10
- Workbook appears incomplete; preview shows truncated data and only partial company coverage.
- PDF was produced instead of a fully validated Excel-only deliverable.
- No evidence of all required columns, sheets, or complete S&P 500 coverage.
  > 💡 Regenerate a complete Excel workbook with all 500 companies, all required columns, and no placeholders.

### ✅ `9e8607e7…` — score 8/10
- PDF has 27 pages, slightly below the requested roughly 30 slides.
- Text preview shows minor formatting corruption in one line.
- No obvious placeholder content, but file content was not fully inspectable.
  > 💡 Consider adding a few slides to reach the target length and recheck formatting.

### ✅ `c7d83f01…` — score 8/10
- Notebook artifact itself is not shown in the preview.
- Monte Carlo is less suitable for vanilla American production pricing.
- Summary text preview is truncated, limiting verification.
  > 💡 Include the notebook file and ensure the summary is fully accessible.

### ✅ `46b34f78…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No obvious evidence of missing required file types.
- Text response is professional but brief.
  > 💡 Confirm the full memo includes both issuer analyses and strategy recommendations.

### ✅ `a1963a68…` — score 6/10
- PDF has 9 pages, exceeding the requested 5-6 core slides.
- Text response is a plan, not a completed strategy presentation summary.
- No clear evidence of detailed public-source analysis or appendix content.
  > 💡 Trim the deck to the requested structure and add explicit data-backed recommendations.

### ✅ `5f6c57dd…` — score 6/10
- Workbook appears incomplete; only a few sheets are visible in the preview.
- Dropdown functionality and branch selection are not verifiable from the provided content.
- Several requested metrics and regional comparisons are not confirmed in the preview.
  > 💡 Verify all five worksheets, formulas, and dropdown controls are fully implemented and populated.

### ✅ `b78fd844…` — score 8/10
- Report is only 4 pages, not near the 15-page limit.
- Directional analysis is present, but exact project details are not fully visible in preview.
- No obvious content gaps, but full file review is limited by truncated preview.
  > 💡 Verify the full report includes all required analysis, risks, and allocation details.

### ✅ `4520f882…` — score 8/10
- Workbook appears to cover the required payroll logic and conflict checks.
- Guide and Excel files are both produced with appropriate file types.
- No obvious placeholder content is visible in the preview.
  > 💡 Verify all CBA edge cases and rate formulas against the source excerpt.

### ❌ `ec591973…` — score 4/10
- No evidence the slide includes the required strategy content.
- Text response is generic and not a concise executive-level pitch.
- File content cannot be verified from the preview.
  > 💡 Provide a verified slide summary showing channel-specific strategy and business rationale.

### ✅ `3f821c2d…` — score 6/10
- No evidence the workbook meets the inventory and turn targets.
- Text response claims completion but omits validation of formulas and constraints.
- LY comparison appears incomplete or inconsistently formatted.
  > 💡 Verify formulas, targets, and side-by-side formatting before final delivery.

### ✅ `6dcae3f5…` — score 6/10
- Task appears incomplete; the prompt was truncated mid-instruction.
- Email draft is included, but the requested workbook details are not fully verifiable.
- No evidence the ACGME requirement-year mapping was fully completed.
  > 💡 Verify the workbook contains all requested benchmarks, PGY mappings, and complete resident analyses.

### ❌ `0353ee0c…` — score 4/10
- Content appears generic and may omit exhaustive PACT Act details.
- No evidence the source links from Document B were individually reviewed.
- Preview shows truncated and possibly incomplete condition/location lists.
  > 💡 Rebuild the guide using all source links and verify every presumptive exposure, condition, location, and date.

### ❌ `4d1a8410…` — score 4/10
- Schedule content appears generic and may omit required timing details.
- Itineraries seem minimal and may lack the requested one-page schedule specifics.
- No evidence of the required table with room numbers, breaks, lunch, and applicant names.
  > 💡 Verify the documents include all timing, room, and applicant details exactly as requested.

### ✅ `8c823e32…` — score 6/10
- Output is text, not a standalone PDF deliverable.
- Policy content appears incomplete in the preview.
- No evidence of final internal-review-ready formatting or full compliance language.
  > 💡 Provide the complete finalized PDF with all required sections and verified formatting.

### ✅ `eb54f575…` — score 6/10
- PDF is only 2 pages and appears truncated.
- Quantity table contains formatting errors and a typo.
- Ballistics section is brief and lacks detailed comparison.
  > 💡 Revise the PDF with complete, polished content and clearer analysis.

### ✅ `11e1b169…` — score 6/10
- PDF is only one page, not the required two pages.
- KRS 503.090 content appears incomplete in the preview.
- The response says a source document was generated, but the task required a PDF deliverable.
  > 💡 Revise the PDF to two pages and ensure all required legal topics are fully covered.

### ✅ `22c0809b…` — score 6/10
- PDF is only 2 pages, below the requested 2-4 page range.
- Preview shows truncated and malformed text, suggesting formatting issues.
- Required sections may be incomplete or not fully verifiable from the preview.
  > 💡 Verify the PDF includes all required fields and clean, readable formatting across 2-4 pages.

### ✅ `efca245f…` — score 6/10
- Executive summary appears truncated in the preview.
- Scenario 1 may not fully address the May 1 catch-up requirement.
- Text response is generic and does not summarize scenario implications clearly.
  > 💡 Verify the workbook includes complete scenario outcomes and a full executive summary.

### ✅ `9e39df84…` — score 6/10
- Week 1 row appears incomplete or missing values in the first operator record.
- Dashboard preview does not confirm required PivotTables or data validation lists.
- Text response says "will create" instead of confirming completed deliverable.
  > 💡 Verify all Week 1 data, required dashboard objects, and provide a completion-confirming summary.

### ✅ `68d8d901…` — score 8/10
- Workbook content appears complete but not fully verifiable from preview.
- No obvious formatting or placeholder issues are shown.
- Text response is professional but generic.
  > 💡 Confirm all sheet details match the reference files exactly.

### ❌ `bd72994f…` — score 1/10
- No PDF presentation was produced.
- No email or text template was provided.
- No collection was selected or sourced from an official website.
  > 💡 Create the PDF slides and outreach template using a specific 2025 resort collection.

### ❌ `211d0093…` — score 4/10
- PDF exists, but content appears incomplete and lacks task details.
- Employee assignment, initials, and notes fields are not visible in the DOCX preview.
- Manager sign-off details are present, but task sections are missing required entries.
  > 💡 Regenerate the document with all tasks and fillable fields clearly included.

### ✅ `40a99a31…` — score 6/10
- Report preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of exact required table columns or sheet names.
- Text response claims validation, but no validation details are shown.
  > 💡 Provide full file contents and confirm exact table structure, sheet names, and validation results.

### ❌ `b9665ca1…` — score 4/10
- Text response mentions start/enable signals not requested.
- Preview shows garbled labels and unclear wiring details.
- Task-specific button-box wiring appears incomplete.
  > 💡 Revise the schematic to match all specified labels and connections exactly.

### ❌ `c6269101…` — score 4/10
- No evidence the deck includes actual capability or stability analysis.
- Supporting PNG charts were promised but not produced.
- Cannot verify summary findings, recommendations, or trend review from the preview.
  > 💡 Include explicit analysis results and all requested supporting files in the deliverable.

### ✅ `be830ca0…` — score 7/10
- Final timeline may not clearly show completed tollgates and in-progress phases.
- Text response omits explicit confirmation of all required chart contents.
- Project schedule appears incomplete with Improve and Control marked TBD.
  > 💡 Revise the timeline and slide content to explicitly show tollgate status and all required analysis elements.

### ✅ `cd9efc18…` — score 6/10
- PDF is only 5 pages, not the requested 8 to 11 pages.
- Execution date in the file appears inconsistent with the April 2023 matter date.
- Trust and fiduciary provisions may be incomplete or truncated in the preview.
  > 💡 Revise the document to match the requested length and verify all Texas will provisions.

### ❌ `a97369c7…` — score 4/10
- Output claims file creation instead of providing the requested memo.
- Memo content appears truncated and incomplete.
- No clear analysis of Marcus's fiduciary duty exposure is shown.
  > 💡 Provide the full legal memo text and ensure all three issues are addressed.

### ✅ `3f625cb2…` — score 6/10
- The memo content appears truncated in the preview.
- No clear confirmation the PDF is under three pages.
- The text response is generic and lacks specific legal findings.
  > 💡 Provide the full three-page memo with concrete legal analysis and verify the PDF length.

### ✅ `8314d1b1…` — score 6/10
- The memo content is truncated, so completeness cannot be verified.
- No evidence confirms the March 2025 DGCL amendments were accurately researched.
- The file may lack the required Word-document depth and cited authorities.
  > 💡 Verify the full memo includes accurate citations, complete analysis, and all required sections.

### ✅ `5e2b6aab…` — score 7/10
- No individual STEP files are visible in the package preview.
- PDF content appears duplicated across assembly and sub-assembly pages.
- Text response mentions source DOCX and image/PDF set beyond requested deliverables.
  > 💡 Verify the ZIP contents include all STEP models and remove any duplicate or extra deliverables.

### ❌ `3940b7e7…` — score 4/10
- PDF text shows many N/A values instead of required numerical results.
- Field-variable min/max table is incomplete and lacks actual CFD values.
- Discussion appears truncated and may miss required recommendations.
  > 💡 Populate all tables with real CFD data and ensure the full report text is complete.

### ✅ `8077e700…` — score 6/10
- Only AISI 1018 data appear analyzed; AISI 1045 is not evidenced.
- Direct microstructure observations are missing despite being requested.
- The report text may be incomplete or truncated in the preview.
  > 💡 Verify both steels are covered and include complete, non-placeholder report content.

### ✅ `74d6e8b0…` — score 6/10
- No evidence the document includes actual literature citations.
- PDF preview appears truncated and may omit required guideline details.
- Text response promises a PDF, but task only required a Word document.
  > 💡 Add full cited guideline content and ensure the Word file contains complete, reviewable prescribing guidance.

### ✅ `61b0946a…` — score 6/10
- Task appears incomplete; preview text is truncated mid-sentence.
- No evidence of the required detailed procedure-range calculations.
- Text mentions a workbook, but workbook file is not produced.
  > 💡 Provide the full proposal with complete calculations and include the workbook file.

### ❌ `61e7b9c6…` — score 4/10
- No evidence of source citations or price methodology.
- Spreadsheet may omit some FDA-approved or commonly used off-label options.
- Text response is generic and does not confirm template-specific completion.
  > 💡 Verify completeness against the template and add cited cash-price sources for each medication.

### ✅ `f1be6436…` — score 6/10
- Missing explicit dates in section headers.
- No evidence screenshots are embedded in the document.
- Original task text is truncated before all logistics requirements.
  > 💡 Verify the document includes dated headers, embedded screenshots, and all remaining travel details.

### ✅ `41f6ef59…` — score 6/10
- Spreadsheet has an extra blank column and instruction column.
- Date format in example row is not MM/DD/YYYY.
- Text response is generic and omits specific deliverable details.
  > 💡 Align the spreadsheet exactly to required fields and format dates consistently.

### ✅ `4b98ccce…` — score 6/10
- Workbook sheet preview is truncated, so deceased-tab compliance is unverified.
- No evidence the employee-sheet name and ID were inserted beneath both tables.
- Letter formatting may be incomplete without visible template-specific elements.
  > 💡 Verify the deceased worksheet, signatures, and template fields against the source sheets.

### ✅ `ef8719da…` — score 6/10
- The pitch is not included in the text response.
- The response only summarizes the file instead of delivering the requested content.
- The file preview appears truncated, so completeness cannot be verified.
  > 💡 Provide the full pitch text with all required elements and verify the document is complete.

### ✅ `3baa0009…` — score 6/10
- Article is under 300 words and may miss required depth.
- No evidence the article includes Reuters and AP source attribution in final publication form.
- Text response mentions DOCX, not the requested article deliverable details.
  > 💡 Revise the article to 300-500 words with explicit source attribution and publication-ready formatting.

### ❌ `5d0feb24…` — score 4/10
- No actual editorial feedback or proposed edits were provided.
- The response promises files instead of reviewing the draft content.
- Science accuracy, clarity, and source links were not addressed.
  > 💡 Provide concise, draft-specific editorial comments with verified science corrections and source links.

### ✅ `6974adea…` — score 6/10
- Preview is truncated, so full article compliance cannot be verified.
- No evidence the Word file meets the 1,000-1,500 word requirement.
- Text response is generic and does not confirm key reporting elements.
  > 💡 Provide the full article text and verify length, structure and source use before submission.

### ✅ `1a78e076…` — score 6/10
- Only 8 pages; task required 10 to 15 pages.
- PDF content preview is truncated, so completeness cannot be verified.
- No evidence the references stay within the 30-item limit.
  > 💡 Revise the document to meet page length and verify all required sections and reference count.

### ✅ `0112fc9b…` — score 8/10
- Plan content is truncated in the preview.
- No obvious documentation of follow-up timeframe.
- Assessment could better distinguish concussion from minor head injury.
  > 💡 Ensure the full SOAP note includes complete plan and explicit follow-up instructions.

### ✅ `e6429658…` — score 8/10
- Appeal letter content appears truncated in preview.
- AbbVie application file type may not match requested form format.
- No evidence of manufacturer form fields being fully completed.
  > 💡 Verify the full letter and ensure the assistance application is correctly completed and formatted.

### ❌ `9a0d8d36…` — score 4/10
- No evidence the deck includes the required calculations or tax comparisons.
- Text response promises a script, but only the PPTX file is listed.
- Cannot verify the presentation content from the provided preview.
  > 💡 Provide a content summary or slide outline confirming all required topics are covered.

### ❌ `664a42e5…` — score 4/10
- No evidence the PPTX covers all required ILIT topics.
- Text response is a creation promise, not a completed content summary.
- No verification of slide quality, completeness, or file validity.
  > 💡 Provide a slide-by-slide content summary confirming every required topic is included.

### ❌ `feb5eefc…` — score 4/10
- PDF is only 2 pages, not within the requested analysis depth.
- The deliverable appears to omit a clear, explicit recommendation.
- CRAT discussion seems incomplete in the preview.
  > 💡 Expand the PDF to fully cover both trusts and state a direct recommendation.

### ❌ `3600de06…` — score 4/10
- No slide content was verified from the PPTX.
- Text response promises validation, but no evidence is shown.
- Source citations and required comparisons may be incomplete.
  > 💡 Verify the deck contains all ten required slides with cited FINRA and NAIC content.

### ✅ `ae0c1093…` — score 6/10
- Observation form text appears garbled in the header.
- Required three solid note lines are not clearly evident.
- Guide content is truncated in preview, so completeness is uncertain.
  > 💡 Fix the form layout and verify the full guide content renders correctly.

### ✅ `f9f82549…` — score 6/10
- PDF content is truncated in the preview, so completeness is uncertain.
- The PPTX content cannot be verified from the provided preview.
- The text response is generic and does not confirm all required deliverables.
  > 💡 Verify the full PDF and PPTX contents against every flowchart header and incident detail.

### ❌ `57b2cdf2…` — score 4/10
- PDF is four pages, exceeding the two-page limit.
- Response is a placeholder, not a finalized report.
- No actual photo review is demonstrated in the text.
  > 💡 Revise the report to a concise two-page final version and verify photo alignment.

### ✅ `6241e678…` — score 6/10
- No evidence the PDF is a visual calendar-style schedule.
- Client tasks and review windows may be incomplete or mislabeled.
- Text response mentions holidays and weekends not requested in the task.
  > 💡 Verify the PDF visually shows all tasks, color-coding, and required review periods.

### ✅ `e14e32ba…` — score 6/10
- Only a summary response is provided, not the researched content.
- Image availability is missing for the establishments.
- Some required media links and details may be incomplete.
  > 💡 Provide the full researched one-sheet with complete entries and verified links.

### ❌ `e4f664ea…` — score 4/10
- PDF is only 6 pages, below the required 8-12 pages.
- Output text promises file generation, but no screenplay content is shown.
- Potentially incomplete story; preview is truncated before the ending.
  > 💡 Provide a complete 8-12 page screenplay with full ending and verified formatting.

### ❌ `02aa1805…` — score 2/10
- Workbook sheets are empty, so no wells were actually extracted.
- No evidence of the required water systems or screening results is shown.
- Email content cannot be verified from the preview.
  > 💡 Populate the workbook with sourced well data and verify the email recommends qualifying wells.

### ✅ `fd6129bd…` — score 8/10
- SOP preview is truncated, so completeness cannot be fully verified.
- No obvious placeholder content is shown, but full file content was not reviewed.
- Text response is professional but does not confirm final validation results.
  > 💡 Verify the full SOP and form contents against the source requirements before release.

### ✅ `ce864f41…` — score 6/10
- No brief responses to the three questions were provided.
- Workbook content cannot be fully verified from the preview.
- Text response is generic and lacks specific analysis results.
  > 💡 Include concise answers with department, individual, and project findings.

### ✅ `58ac1cc5…` — score 7/10
- Duplicate PDF/DOCX change control files were produced.
- The text response repeats itself unnecessarily.
- Risk assessment content may not fully reflect the vendor memo timing issue.
  > 💡 Remove duplicate files and ensure all deliverables explicitly address the late vendor notification breakdown.

### ❌ `3c19c6d1…` — score 4/10
- Only a text response is shown; slide content cannot be verified.
- Required slide details may be incomplete or missing.
- No evidence the presentation matches the specified report structure.
  > 💡 Verify the PPTX contains all required slides and exact requested content.

### ✅ `a99d85fc…` — score 6/10
- Annual and monthly matrix formulas are not verified in the preview.
- ChartData sheet appears empty, suggesting incomplete supporting data.
- PDF summary is present, but DOCX is unnecessary and not requested.
  > 💡 Verify all formulas populate correctly and remove unneeded deliverables.

### ✅ `55ddb773…` — score 6/10
- No evidence the attached PDF content was fully incorporated.
- The form may omit some qualifying questions from the source document.
- Text response is repetitive and not fully polished.
  > 💡 Verify all source violations are included and remove duplicated wording.

### ❌ `1e5a1d7f…` — score 4/10
- Missing the required table format and four columns.
- Docx content appears to contain only title and notes, not the schedule.
- Week-of-month task breakdown is not shown.
  > 💡 Rebuild the document as a populated table with all required columns and weekly tasks.

### ✅ `0419f1c3…` — score 7/10
- File preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of the required training module recommendations.
- Potentially missing full signature section and consequences text.
  > 💡 Verify the document includes all required sections and complete, untruncated content.

### ✅ `46bc7238…` — score 8/10
- Preview is truncated, so full page count and visuals cannot be fully verified.
- No explicit confirmation that free stock photos appear on every page.
- One-page flyer template content is not fully visible in the preview.
  > 💡 Verify the PDF includes all required sections and page-level images throughout.

### ❌ `0818571f…` — score 3/10
- Listings are placeholders, not verified public Crexi or LoopNet properties.
- Required photos and surrounding-area maps are not actually included.
- Internet sourcing limitation conflicts with the task's active-listing requirement.
  > 💡 Replace placeholders with verified June 2025 public listings and include real visuals and maps.

### ❌ `6074bba3…` — score 3/10
- PDF contains placeholder fields instead of completed CMA data.
- Required 5–10 sold comps and 3–5 active/pending listings are not shown.
- Text response is generic and does not provide a pricing recommendation.
  > 💡 Populate the template with actual comp data, pricing analysis, and finalized charts.

### ✅ `11593a50…` — score 6/10
- Buyer tour PDF has 3 pages, not 2.
- Photos are placeholders, not actual home photos.
- Text says current folder, but files are in a deliverable_files subfolder.
  > 💡 Regenerate the tour as exactly two pages with real photos and clearer file delivery details.

### ❌ `94925f49…` — score 4/10
- Reports are only one page each, not up to 10 pages.
- Key school metrics are placeholders marked 'To verify' instead of actual data.
- Nearby homes are example entries, not real listings from accessible platforms.
  > 💡 Replace placeholders with sourced school and listing data, and expand each PDF with verified details.

### ✅ `90f37ff3…` — score 8/10
- Text response is duplicated.
- Comparable addresses and rents are not visible in the preview.
- No evidence of source citations or dates for comps.
  > 💡 Include clearly labeled comp details and source dates in the report.

### ✅ `d3d255b2…` — score 9/10
- Preview is truncated, so full report completeness cannot be fully verified.
- Text response is generic and does not summarize the actual recommendation.
- No obvious formatting or file-type errors were detected.
  > 💡 Ensure the final report fully states the counteroffer and seller guidance in the PDF.

### ✅ `1bff4551…` — score 6/10
- Requested PDF exists, but a DOCX was also produced.
- Preview is truncated, so completeness cannot be fully verified.
- Text response is generic and does not summarize the actual set list.
  > 💡 Provide a complete PDF-only deliverable with a concise summary of the included songs.

### ✅ `01d7e53e…` — score 6/10
- Missing visible primary contact details in the preview.
- Attached standard contract language is not verifiable from the preview.
- Output text promises validation, but no validation evidence is shown.
  > 💡 Review the document against all source attachments and confirm required contact and contract language are included.

### ✅ `a73fbc98…` — score 6/10
- No actual layout plan is provided in the summary document.
- The spreadsheet may contain UNASSIGNED entries needing follow-up.
- The text response is generic and omits key assignment details.
  > 💡 Include a specific table-by-table assignment summary and resolve any unassigned vendors.

### ❌ `0ec25916…` — score 4/10
- PDF is 2 pages, not the required 1 page.
- Table layout is not clearly 2 columns by 4 rows.
- Missing explicit lined space for nurse name and department at the top.
  > 💡 Revise the PDF to a single-page 2x4 table with top caller details and lined prompts.

### ✅ `116e791e…` — score 8/10
- File preview is truncated, but core requirements appear met.
- Text response is brief and does not summarize the care plan content.
- No obvious formatting or content errors are visible in the PDF preview.
  > 💡 Provide a fuller text summary of the completed care plan.

### ❌ `dd724c67…` — score 4/10
- Output is generic and does not verify completed research or spreadsheet content.
- TFU guide details and condition timeframes are not shown or confirmed.
- Facility list may be incomplete or contain duplicates without validation.
  > 💡 Provide the completed workbook content with verified facilities and TFU timeframes.

### ❌ `7151c60a…` — score 4/10
- Checklist preview shows only contact text, not the required table content.
- Fax cover sheet content is not verifiably complete from the preview.
- No evidence of page numbers or patient name/DOB fields in the checklist.
  > 💡 Verify both documents include all required fields, tables, and formatting elements.

### ❌ `90edba97…` — score 4/10
- No evidence the Excel tracker was actually populated with patient lab data.
- Text response is repetitive and does not confirm completed monthly clinical changes.
- Potential mismatch with task requirements for exact file content verification.
  > 💡 Provide the completed workbook with verified patient entries and a concise, non-repetitive summary.

### ❌ `8384083a…` — score 4/10
- Text response is incomplete and not the actual guide content.
- PDF contains unclear or inconsistent days-supply calculations.
- Some medication details may be inaccurate or insufficiently standardized.
  > 💡 Provide a fully detailed, audit-ready guide with verified calculations for each medication.

### ✅ `045aba2e…` — score 7/10
- Daily PDF preview is truncated, so completeness cannot be fully verified.
- No evidence the checklists were validated against the cited California resources.
- Text response is generic and does not mention specific compliance content.
  > 💡 Provide full, source-aligned checklist content and verify all three PDFs are complete.

### ❌ `f2986c1f…` — score 3/10
- Only one unknown medication was listed.
- Required image-based identification was not completed.
- MedlinePlus counseling links are missing.
  > 💡 Identify each pill from the image and populate all required fields with verified data.

### ✅ `b3573f20…` — score 6/10
- PDF has 4 pages, not the required 3.
- Content appears incomplete in the preview and may be truncated.
- Text response is generic and does not confirm all required details.
  > 💡 Revise the PDF to exactly 3 pages and verify all required prompts are fully included.

### ✅ `74ed1dc7…` — score 6/10
- File content appears truncated in the preview.
- Proposal may not fully address all required order type changes.
- No evidence the document uses the reference file details comprehensively.
  > 💡 Verify the full Word proposal includes complete recommendations and rationale from the source material.

### ✅ `69a8ef86…` — score 8/10
- Internal preview is truncated, so full step compliance cannot be fully verified.
- No explicit evidence of the 90-day manual closure and account notification step.
- Text response is generic and does not confirm document-specific completion details.
  > 💡 Verify the internal document includes every deadline and closure requirement explicitly.

### ✅ `105f8ad0…` — score 6/10
- No evidence of live September 2025 web research.
- Competitor set includes brand-site entries outside requested retailer-only sourcing.
- Output may not fully verify all SKU recommendations and rationales.
  > 💡 Add source citations and verify every SKU against retailer-specific current MSRPs.

### ❌ `b57efde3…` — score 4/10
- Workbook contains placeholder data instead of exhibitor findings.
- No actual companies, contacts, or product research were provided.
- Text admits inability to access the source list, leaving task incomplete.
  > 💡 Populate the spreadsheet with verified Aqua Nor exhibitors and their product details.

### ❌ `6a900a40…` — score 4/10
- Transport options and remarks are not visible in the preview.
- Red-font general freight disclaimer cannot be verified from the preview.
- Only a text confirmation is shown, not the actual updated content.
  > 💡 Verify the spreadsheet contains all required transport lines, totals, and formatted disclaimer.

### ✅ `9efbcd35…` — score 6/10
- Missing detailed summary sections for China, India, Brazil, technology, and CEEMEA.
- Document is only a brief text summary, not a fully developed four-page outlook.
- No explicit MSCI performance figures or cited news sources are included.
  > 💡 Add specific Q1 2025 performance data, fuller regional sections, and source citations.

### ✅ `4de6a529…` — score 8/10
- PDF appears complete, but preview is truncated.
- Working XLSX and DOCX were produced, though only PDF was requested.
- No obvious content errors are visible from the preview.
  > 💡 Verify the full PDF includes all 26 rows and correct formatting.

### ✅ `4c4dc603…` — score 6/10
- PDF content appears truncated in preview.
- Team member profiles are generic, not specific individuals.
- No evidence the one-page summary includes all required economics details.
  > 💡 Verify the PDF includes all requested sections with specific team names and fund terms.

### ✅ `bb499d9c…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit validation of page count under 25 pages is shown.
- Text response is duplicated, though still professional.
  > 💡 Confirm final page count and provide a non-truncated content check.

### ❌ `5349dd7b…` — score 4/10
- Historical rate increase data is missing in the workbook.
- UPS and FedEx flat-rate options are marked not offered without analysis.
- The text response does not summarize findings or recommendations.
  > 💡 Populate the missing rate research and provide carrier-specific cost comparisons for all eligible package sizes.

### ❌ `76418a2c…` — score 2/10
- Workbook is blank with no shipment data populated.
- Summary shows shipment count zero, indicating no processing occurred.
- Text response promises a PDF summary but does not mention completed results.
  > 💡 Populate the manifest with all orders and verify shipment calculations before delivery.

### ✅ `0e386e32…` — score 6/10
- Privacy logic is incomplete; zkSNARK unlinking is truncated.
- No evidence of actual implementation beyond scaffolds and summaries.
- Cross-chain and Aave integration details are only described, not delivered.
  > 💡 Provide complete, working code and finish the missing privacy specification.

## Failure Analysis

Across the full 220-task run, the dominant hard-failure pattern was deterministic code brittleness rather than model refusal or timeout. Most terminal errors came from fragile spreadsheet/document automation and generated Python defects: openpyxl style mutation in aa071045-bcb0-4164-bb85-97245d56287e, hard-coded column expectations in 87da214f-fd92-4c58-9854-f4d0d10adce0 and a0552909-bc66-4a3a-8970-ee0d17b49718, type-unsafe header parsing in 327fbc21-7d26-4964-bf7c-f4f41e55c54d, missing-column/None handling in 1752cb53-5983-46b6-92ee-58ac85a11283 and 6d2c8e55-fe20-45c6-bdaf-93e676868503, and read-only array mutation in 1d4672c8-b0a7-488f-905f-9ab4e25a19f7. A second sub-pattern was pure code-generation syntax failure, which should have been catchable before execution: 7ed932dd-244f-4d61-bf02-1bc3bab1af14, 11dcc268-cb07-4d3a-a184-c6d7a19349bc, 7de33b48-5163-4f50-b5f3-8deea8185e57, and 4122f866-01fa-400b-904d-fa171cdab7c7. These failures cluster around spreadsheet-heavy operational occupations and software bundle tasks, indicating weak robustness to real-world schema variance and multi-file code assembly.

A distinct sector/occupation cluster appears in Information, especially Film and Video Editors. Three of the five film/video tasks failed outright: e222075d-5d62-4757-ae3c-e34b0846583b and c94452e4-39cd-4846-b73a-ab75933d1ad7 died on a missing moviepy dependency, while a941b6d8-4289-4500-b45a-f8e4fc94a724 hit an OpenCV memory fault after 172,906 ms. The remaining successful reel task, 75401f7c-396d-406d-b08e-938874ad1045, still scored only 4 after 98,609 ms. This is the clearest complexity-to-failure correlation in the set: heavy media transforms produce either environment failures or low-quality partials, whereas lighter specification/document tasks in the same run often succeed at much lower latency. The same pattern shows up more mildly in software tasks: text/spec outputs succeeded (854f3814-681c-4950-91ac-55b0db0e3781, 2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f), while full implementation bundles failed on syntax/assembly errors.

The larger risk, however, is soft failure hidden inside nominal success. Many low-QA tasks completed operationally but produced the wrong artifact, placeholder content, or a promise instead of the deliverable. Examples include f84ea6ac-8f9f-428c-b96c-d0884e30f7c7 and 85d95ce5-b20c-41e2-834e-e788ce9622b6 in Government, 401a07f1-d57e-4bb0-889b-22de8c900f0e and ec2fccc9-b7f6-4c73-bf51-896fdb433cec in Information editorial work, 02aa1805-c658-4069-8a6a-02dec146063a and 76418a2c-a3c0-4894-b89d-2493369135d9 with blank/empty workbooks, bd72994f-5659-4084-9fab-fc547d1efe3b with no usable files despite success status, and web-research-heavy real estate tasks 0818571f-5ff7-4d39-9d2c-ced5ae44299e and 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b that relied on placeholders instead of verified live listings. This means completion rate materially overstates business utility for tasks requiring exact file type, page count, template fidelity, or current-source research.

Retry behavior also reveals a sharp split between transient and deterministic issues. All 16 terminal errors were already retried, so the current retry policy did not repair a single hard failure. Retries did help some transient or artifact-generation cases, producing strong outputs on 7b08cd4d-df60-41ae-9102-8aaa49306ba2, 38889c3b-e3d4-49c8-816a-3cc8e5313aba, b7a5912e-0e63-41f5-8c22-9cdb8f46ab01, and 46b34f78-6c06-4416-87e2-77b6d8b20ce9, but they did not reliably improve quality: 02aa1805-c658-4069-8a6a-02dec146063a, 3c19c6d1-672c-467a-8437-6fe21afb8eae, feb5eefc-39f1-4451-9ef9-bffe011b71dd, and 3600de06-3f71-4e48-9480-e4828c579924 were retried yet still low confidence. Latency also did not buy quality; the slowest jobs were often the least stable, while high-quality spreadsheet and policy work in Wholesale or Government frequently landed in the 10-18 second range.

## Recommendations

First, separate media-intensive tasks from standard document/spreadsheet execution and harden the runtime before generation. The environment needs a verified ffmpeg/moviepy/OpenCV toolchain and more memory for video compositing; otherwise tasks like e222075d-5d62-4757-ae3c-e34b0846583b, c94452e4-39cd-4846-b73a-ab75933d1ad7, and a941b6d8-4289-4500-b45a-f8e4fc94a724 will continue to fail deterministically. Add a preflight capability check that routes media jobs to a higher-memory worker or degrades to a lower-resolution/chunked pipeline instead of attempting full-resolution processing. For long-form multimedia and code-heavy creative tasks, raising reasoning from low to medium is justified; the current low-reasoning setup appears adequate for routine docs but underpowered for multi-asset editing and VFX assembly.

Second, add a schema-discovery layer and static code validation before execution. Spreadsheet-heavy failures show the generator is assuming exact column names, row locations, and types. Use a first-pass workbook profiler that enumerates sheet names, candidate headers, column synonyms, merged cells, and date formats before writing task-specific logic. That would directly address 87da214f-fd92-4c58-9854-f4d0d10adce0, 327fbc21-7d26-4964-bf7c-f4f41e55c54d, 1752cb53-5983-46b6-92ee-58ac85a11283, a0552909-bc66-4a3a-8970-ee0d17b49718, 6d2c8e55-fe20-45c6-bdaf-93e676868503, and ffed32d8-d192-4e3f-8cd4-eda5a730aec3. In parallel, run py_compile or equivalent linting on generated Python before execution to catch the preventable syntax faults seen in 7ed932dd-244f-4d61-bf02-1bc3bab1af14, 11dcc268-cb07-4d3a-a184-c6d7a19349bc, 7de33b48-5163-4f50-b5f3-8deea8185e57, and 4122f866-01fa-400b-904d-fa171cdab7c7. This is a high-leverage fix because these failures do not require better reasoning, only safer code assembly.

Third, tighten the output contract and quality gates so that intent statements do not count as success. Many low-QA tasks passed operationally while delivering meta-text, wrong file types, blank sheets, or placeholders, as seen in bd72994f-5659-4084-9fab-fc547d1efe3b, 02aa1805-c658-4069-8a6a-02dec146063a, 76418a2c-a3c0-4894-b89d-2493369135d9, f84ea6ac-8f9f-428c-b96c-d0884e30f7c7, 85d95ce5-b20c-41e2-834e-e788ce9622b6, 0818571f-5ff7-4d39-9d2c-ced5ae44299e, and 6074bba3-7e3a-4b1c-b8c6-a15bb6695c3b. Require every run to emit a machine-checkable completion manifest: requested files created, actual file types, page/sheet counts, non-empty row counts, and confirmation that placeholders such as TBD, To verify, sample, or will create are absent from final artifacts. A rule-based gate should automatically downgrade or reopen any job with files_count = 0, blank worksheets, wrong deliverable type, or Self-QA <= 4 even if execution technically succeeded.

Fourth, replace blind retries with error-aware recovery. The current system retried every terminal failure and fixed none of them, so the retry budget is being spent on deterministic bugs. Retries should branch by failure class: dependency errors trigger library-free fallback or rerouting; syntax errors trigger regeneration from the last prompt plus compiler feedback; schema errors trigger exploratory parsing; memory faults trigger downsampling or task splitting. This would preserve the real value of retries already demonstrated by transient recoveries such as 7b08cd4d-df60-41ae-9102-8aaa49306ba2 and 38889c3b-e3d4-49c8-816a-3cc8e5313aba, while reducing wasted reruns on repeatable defects. I would also add domain-specific prompt checklists for sectors with strong completion but uneven quality, especially Government document fidelity and Health Care template adherence, because those sectors are failing more on exactness than on raw completion.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 2 file(s)
- `27e8912c…` (Government): 2 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 3 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 5 file(s)
- `38889c3b…` (Information): 7 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 4 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 4 file(s)
- `bbe0a93b…` (Government): 3 file(s)
- `85d95ce5…` (Government): 2 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 1 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 4 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 3 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 2 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 2 file(s)
- `f3351922…` (Finance and Insurance): 2 file(s)
- `61717508…` (Finance and Insurance): 3 file(s)
- `0ed38524…` (Finance and Insurance): 2 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 2 file(s)
- `afe56d05…` (Information): 2 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `75401f7c…` (Information): 2 file(s)
- `8079e27d…` (Finance and Insurance): 2 file(s)
- `e21cd746…` (Finance and Insurance): 3 file(s)
- `9e8607e7…` (Finance and Insurance): 3 file(s)
- `c7d83f01…` (Finance and Insurance): 8 file(s)
- `46b34f78…` (Finance and Insurance): 4 file(s)
- `a1963a68…` (Finance and Insurance): 2 file(s)
- `5f6c57dd…` (Finance and Insurance): 1 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 2 file(s)
- `4520f882…` (Finance and Insurance): 2 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `e996036e…` (Wholesale Trade): 1 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 1 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 1 file(s)
- `bf68f2ad…` (Manufacturing): 2 file(s)
- `efca245f…` (Manufacturing): 1 file(s)
- `9e39df84…` (Manufacturing): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 4 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 3 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `c6269101…` (Manufacturing): 1 file(s)
- `be830ca0…` (Manufacturing): 10 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 5 file(s)
- `46fc494e…` (Manufacturing): 6 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `8077e700…` (Manufacturing): 5 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 2 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 6 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 3 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 2 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 2 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 3 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 4 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 1 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 1 file(s)
- `3600de06…` (Finance and Insurance): 2 file(s)
- `c657103b…` (Finance and Insurance): 2 file(s)
- `ae0c1093…` (Retail Trade): 2 file(s)
- `f9f82549…` (Retail Trade): 3 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `a46d5cd2…` (Retail Trade): 2 file(s)
- `6241e678…` (Information): 3 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 1 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 1 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 3 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 2 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 2 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 4 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 3 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 3 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 6 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 2 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 1 file(s)
- `a73fbc98…` (Government): 2 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 1 file(s)
- `dd724c67…` (Health Care and Social Assistance): 2 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 2 file(s)
- `91060ff0…` (Retail Trade): 5 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `b3573f20…` (Wholesale Trade): 1 file(s)
- `a69be28f…` (Wholesale Trade): 2 file(s)
- `788d2bc6…` (Wholesale Trade): 17 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 1 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 3 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `4de6a529…` (Finance and Insurance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `bb499d9c…` (Finance and Insurance): 3 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 3 file(s)
- `76418a2c…` (Manufacturing): 3 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 2 file(s)
- `854f3814…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
