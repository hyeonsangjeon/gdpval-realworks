# Experiment Report: GPT-5.2 Reasoning LOW — Full Benchmark (Ablation 3/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp019_GPT52_reasoning_low` |
| **Condition** | GPT-5.2 reasoning=low + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-26 |
| **Duration** | 123m 48s |
| **Generated At** | 2026-03-26T17:03:20.285486+00:00 |
| 🤗 HF Dataset | [exp019_GPT52_reasoning_low](https://huggingface.co/datasets/HyeonSang/exp019_GPT52_reasoning_low) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp019_GPT52_reasoning_low/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated GPT-5.2-chat with reasoning set to low and a gpt-audio-1.5 preprocessor across a 220-task benchmark. The run achieved a 95.5% task completion rate (210/220), with 10 errors and 34 retried tasks, indicating generally stable execution under the selected configuration. Average end-to-end latency was 23.1s, consistent with subprocess execution and audio preprocessing overhead.

Self-assessed QA confidence averaged 6.2/10, with a wide range (2–9), suggesting uneven task-level quality despite high completion. Sector-level completion was strong across most domains, with multiple sectors reaching full success, while confidence scores varied more meaningfully by domain than completion rate. These QA values reflect the model’s internal assessment during execution rather than external validation.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 210 (95.5%) |
| Errors | 10 |
| Retried Tasks | 34 |
| Avg QA Score | 6.2/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 23,062ms |
| Max Latency | 111,446ms |
| Total LLM Time | 5073s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 177 (95.7%) |
| Failed → dummy created | 8 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 22 | 22 | 0 |
| 2 | 12 | 2 | 10 |

## Quality Analysis

Self-assessed QA confidence clustered in the mid-range (5.5–6.8) across most sectors, indicating adequate but not robust answer quality under low-reasoning constraints. Government tasks showed the highest average confidence (7.2/10), while Health Care and Manufacturing were lower (5.5–5.8/10), suggesting reduced reliability on domain-specific or safety-sensitive reasoning.

Latency was relatively uniform across sectors, with Information tasks notably slower (~28.9s avg), likely reflecting heavier input or output generation. Retail Trade exhibited both lower completion (18/20) and relatively higher QA confidence (6.8/10), implying selective failures rather than uniformly degraded responses. Deliverable file generation quality appeared sufficient for task completion but likely contributed to lower QA confidence in technically dense sectors.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 24 | 96.0% | 6.58/10 | 23,514ms |
| Government | 25 | 24 | 96.0% | 7.17/10 | 22,831ms |
| Health Care and Social Assistance | 25 | 24 | 96.0% | 5.54/10 | 22,524ms |
| Information | 25 | 25 | 100.0% | 6.28/10 | 28,863ms |
| Manufacturing | 25 | 24 | 96.0% | 5.83/10 | 22,365ms |
| Professional, Scientific, and Technical  | 25 | 24 | 96.0% | 5.71/10 | 23,913ms |
| Real Estate and Rental and Leasing | 25 | 25 | 100.0% | 5.92/10 | 21,430ms |
| Retail Trade | 20 | 18 | 90.0% | 6.83/10 | 20,605ms |
| Wholesale Trade | 25 | 22 | 88.0% | 6.05/10 | 21,023ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 5/10 | 29007ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 3/10 | 18449ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 4/10 | 17782ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 3/10 | 23950ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 3/10 | 24401ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 2/10 | 18493ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 14418ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 7/10 | 26748ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 8/10 | 29113ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 4 | 6/10 | 30934ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 6/10 | 33628ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 7/10 | 23535ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 6 | 7/10 | 31680ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 2 | 8/10 | 27302ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 1 | 8/10 | 19728ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 27338ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 24703ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 9/10 | 27166ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 3/10 | 20915ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 5/10 | 29263ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 23018ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | Yes | 2 | 5/10 | 15104ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 6 | 7/10 | 23016ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 2 | 3/10 | 34184ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | 8/10 | 18094ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 20969ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 17764ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 19806ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 13908ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 2 | 8/10 | 23948ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 28634ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 20440ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 6/10 | 19936ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 5/10 | 19473ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 4 | 6/10 | 27000ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 2/10 | 22333ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 6/10 | 21059ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 9 | 6/10 | 21882ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 4/10 | 18153ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 20655ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 23165ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 1 | 6/10 | 15311ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 4/10 | 15447ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 4 | 7/10 | 17643ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 7/10 | 16202ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 8/10 | 14104ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 8/10 | 26001ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 7/10 | 14187ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 2 | 6/10 | 22623ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 8/10 | 17920ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 23800ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 8/10 | 26643ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 6 | 7/10 | 33567ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | 6/10 | 20208ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 5/10 | 35920ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 8/10 | 17144ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | Yes | 7 | 6/10 | 30735ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 2 | 4/10 | 26289ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | Yes | 2 | 3/10 | 27237ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | Yes | 6 | 4/10 | 111446ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 3/10 | 20925ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 8/10 | 24151ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 9/10 | 40467ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 7/10 | 35342ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 6/10 | 23505ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 22324ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 22334ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 1 | 6/10 | 23915ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 8/10 | 33654ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 6/10 | 19275ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 16448ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 18046ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 3/10 | 22926ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 6/10 | 20702ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 3/10 | 24542ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 2 | 3/10 | 21939ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 6/10 | 29369ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 3/10 | 20425ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 4/10 | 16570ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 3/10 | 16920ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 23398ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 23408ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 21986ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 21274ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 20934ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 4/10 | 22034ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 4/10 | 22338ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 4/10 | 20496ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 7/10 | 18754ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 19016ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 7/10 | 23204ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 18855ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 1 | 8/10 | 12696ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 22638ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 5 | 7/10 | 26632ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 22481ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 7/10 | 17685ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 19123ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 8/10 | 24575ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 19607ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 7/10 | 19135ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | 6/10 | 26089ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 7/10 | 21251ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 5 | 6/10 | 19863ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 6 | 7/10 | 34344ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 28995ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 35728ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 8/10 | 19069ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 20129ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 9/10 | 31964ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 10 | 4/10 | 23422ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 5 | 3/10 | 28590ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 7/10 | 24994ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 6/10 | 24750ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 6/10 | 27192ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 28164ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 6/10 | 13593ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 3 | 8/10 | 33000ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 6/10 | 13308ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 3 | 6/10 | 28856ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 3/10 | 21307ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 2 | 8/10 | 14568ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 22343ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 20 | 3/10 | 36224ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 6/10 | 27926ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 5/10 | 17954ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 7/10 | 17500ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 20771ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 24117ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 8/10 | 36529ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 40073ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 22673ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 19523ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 17116ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 24446ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 4/10 | 18493ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 8/10 | 20628ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 8/10 | 20152ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 22578ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 6/10 | 25624ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 22427ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 19119ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 8/10 | 26230ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 7/10 | 19746ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 24539ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 9/10 | 16274ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 8 | 8/10 | 22970ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 8/10 | 22514ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 8/10 | 22578ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 15905ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 23089ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 1 | 6/10 | 24521ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 24472ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 4/10 | 25600ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 4/10 | 18166ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 19424ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 5/10 | 26908ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 8/10 | 24231ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 8/10 | 28693ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 1 | 6/10 | 22702ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 4/10 | 15846ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 4/10 | 23321ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 3/10 | 13844ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 8/10 | 24650ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 21154ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 8 | 8/10 | 20627ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 8/10 | 21642ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 16908ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 12 | 6/10 | 27905ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 3/10 | 24430ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 7/10 | 24266ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 20 | 5/10 | 26555ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 11 | 7/10 | 32572ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 5/10 | 25839ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 8/10 | 24355ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 17866ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 37491ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 5/10 | 28839ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 1 | 6/10 | 20083ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 25990ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 7/10 | 18061ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 7/10 | 16900ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 4/10 | 23395ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 15256ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 3/10 | 21139ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 8/10 | 27927ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 3/10 | 19500ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 6 | 6/10 | 18309ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 3/10 | 12016ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 3/10 | 26615ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 7/10 | 20476ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 8/10 | 28703ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 24232ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 8/10 | 19877ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 21953ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 8/10 | 25116ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 22673ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 21197ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 6/10 | 16523ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 20957ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 17651ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 14463ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 23989ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 8/10 | 21550ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 16064ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 7/10 | 25426ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 3 | 7/10 | 18690ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 3/10 | 23337ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 5/10 | 19085ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 7/10 | 28532ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 16684ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 17657ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | 5/10 | 16889ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 14405ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 1 | 4/10 | 11825ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 19543ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | Yes | 1 | 3/10 | 21477ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 18552ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 6 | 5/10 | 23817ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 8/10 | 27527ms |

## QA Issues

### ✅ `83d10b06…` — score 5/10
- Selected sample far exceeds calculated sample size of 68.
- QoQ variance missing for rows with zero prior quarter values.
- Sample tab includes many non-justified selections beyond stated criteria.
  > 💡 Limit sampled rows to calculated size and fully compute variance with defined zero-handling.

### ❌ `7b08cd4d…` — score 3/10
- Excel file contains only headers with no revenue, expense, or net income data.
- Missing breakdown by source, tax calculations, currency conversions, and net revenue totals.
- Expenses are not categorized as required and no combined totals are shown.
  > 💡 Populate the Excel with complete revenue, tax, expense, and net income data per specifications.

### ❌ `7d7fc9a7…` — score 4/10
- Prepaid Summary lacks required YTD prepaid expenses and YTD amortization figures.
- Schedules do not reconcile to provided GL ending balances for April 2025.
- BCBS prepaid insurance invoices and monthly billing are entirely missing.
  > 💡 Rebuild schedules to include BCBS, monthly summaries, and ensure all balances reconcile to GL.

### ❌ `43dc9778…` — score 3/10
- The files are summaries, not completed IRS Form 1040 and schedules.
- Key amounts are placeholders like "as reported" with no calculations.
- Required e-file forms and schedules are not actually included in the PDF.
  > 💡 Prepare a fully completed IRS Form 1040 with all required schedules populated and calculated.

### ❌ `ee09d943…` — score 3/10
- Multiple schedules still reference March dates instead of April.
- April source files are not reflected in updated data.
- Cash Availability and TB tabs were carried forward without April updates.
  > 💡 Update all schedules with April data, dates, and reconciliations using the provided April source files.

### ❌ `f84ea6ac…` — score 2/10
- No research summary table or five studies included in the document.
- Academic articles are not identified, cited, or verified as post-2020 and public.
- File content is minimal paragraphs, not a one-page comparative table.
  > 💡 Include a one-page table summarizing five specific post-2020 public academic articles with findings and implications.

### ✅ `a328feea…` — score 9/10
- Scope extends beyond Administrative Support Teams without explicit justification.
- No alternate contact identified if Supervisor or Team Lead is unavailable.
  > 💡 Clarify scope alignment and add a backup contact procedure for unavailable supervisors.

### ✅ `27e8912c…` — score 7/10
- Ergonomic images lack cited credible public-domain sources or attribution.
- Organizational Action Items document shows no completed table with required tracking columns.
- NIH source is referenced but not linked or formally cited in documents.
  > 💡 Add proper source citations, complete the action-tracking table, and attribute all images to public-domain sources.

### ✅ `17111c03…` — score 8/10
- Cleanup schedule dates are in 2025 despite memo dated March 26, 2026.
- Memo lists role only, not an individual manager’s name.
  > 💡 Update the schedule to current or future dates and include the manager’s full name.

### ✅ `c44e9b62…` — score 6/10
- Revised organizational chart is not a visual chart and lacks clear position hierarchy.
- Regional Support Services Supervisor headcount not reduced despite office count reduction.
- Briefing note lacks quantified confirmation that total reductions meet the 4% target.
  > 💡 Provide a true visual org chart, adjust all required regional roles, and explicitly confirm total FTE reduction percentage.

### ✅ `99ac6944…` — score 6/10
- Mixer lacks true onboard compression despite stated requirement.
- Mixer cannot provide two fully independent vocal mixes for singers.
- Document lacks actual clickable web links to retailers.
  > 💡 Select an analog mixer with per-channel compression and two pre-fade aux sends, and add real purchase links.

### ✅ `f9a1c16c…` — score 7/10
- Output numbering does not follow counterclockwise order from stage right.
- IEM split sends and wedge mixes are ambiguously combined in the output list.
- Singer wedge vocal requirements are not explicitly identified in the outputs.
  > 💡 Separate IEM and wedge outputs clearly and renumber wedges counterclockwise starting from stage right.

### ✅ `38889c3b…` — score 7/10
- No proof of 140 BPM, key signatures, or drum-track synchronization.
- Master and stem durations and bridge timestamps not verified as specified.
- ZIP contents not itemized to confirm included stems and specs.
  > 💡 Include session notes confirming BPM, keys, sync, durations, and a ZIP manifest.

### ✅ `ff85ee58…` — score 8/10
- Timing tightening to ±1/16 note is implied but not explicitly confirmed.
- No objective loudness measurement report is provided to verify LUFS compliance.
  > 💡 Include a brief loudness and timing verification report with measured values for clarity.

### ✅ `4b894ae3…` — score 8/10
- Text response lacks explicit confirmation of copying replacement notes from other song sections.
  > 💡 Explicitly confirm how replacement bass notes were sourced and edited at each provided timecode.

### ✅ `1b1ade2d…` — score 8/10
- Minor typographical error observed in modular quotation section.
- Explicit approval timelines and SLAs are not clearly defined.
  > 💡 Add a clear approval matrix with SLAs and correct minor typos for executive readiness.

### ✅ `93b336f3…` — score 8/10
- Introduces a 49:51 JV ownership split not specified in the original task.
- Assumes EvTronics Delhi facility without source confirmation.
- Text response summarizes intent but omits explicit cost figures.
  > 💡 Explicitly flag all added assumptions and align them with stakeholder validation.

### ❌ `24d1e93f…` — score 3/10
- Analysis uses five years instead of required four-year product lifecycle.
- Variant split, tooling amortization, and R&D cost allocation are not reflected.
- Recommendation selects highest-cost NPV without justification against results.
  > 💡 Rebuild the Excel with correct lifecycle, cost logic, and a recommendation aligned to calculated NPVs.

### ✅ `05389f78…` — score 5/10
- Report lacks required quantitative cost comparison and INR calculations.
- Attached quotation data was not used despite explicit requirement.
- Financial section admits missing pricing, violating task instructions.
  > 💡 Incorporate provided quotation data and present full INR cost comparisons and calculations.

### ✅ `575f8679…` — score 8/10
- Appendix instrument descriptions appear brief and may lack full sample items or links.
- Data analysis section lacks detail on statistical tests beyond pre-post comparisons.
- Limited discussion of language access and cultural adaptation procedures.
  > 💡 Expand the appendix and analysis sections with more detail and explicit cultural and linguistic considerations.

### ✅ `a74ead3b…` — score 5/10
- Content not confirmed to closely follow the required manual for Sessions 13 and 14.
- Response admits inability to access required source materials.
- Slide content details cannot be verified for required elements.
  > 💡 Revise presentations using the official manual content to ensure full alignment and document specific session topics.

### ✅ `bbe0a93b…` — score 7/10
- Spanish assessment includes untranslated English column headers.
- Resource guide omits several requested categories like transportation, clothing, and counseling.
- Needs assessment DOCX files lack full screening table content.
  > 💡 Translate all headers, add missing resource categories, and ensure DOCX versions mirror the PDF content.

### ❌ `85d95ce5…` — score 3/10
- PDF is only 5 pages, not the required 8–15 pages.
- Required placeholders were not followed; school name and social worker fields are filled.
- File naming and deliverables are incorrect, including extra DOCX and double-dot PDF name.
  > 💡 Revise the report to meet length, placeholder, and file submission requirements exactly.

### ✅ `76d10872…` — score 8/10
- An additional DOCX file was produced though only a PDF was requested.
  > 💡 Confirm deliverable file types strictly match the task requirements.

### ✅ `36d567ba…` — score 8/10
- Timekeeping Uniform Guidance citation not visible in preview.
- High-risk status question not visible in preview.
  > 💡 Verify all topics are present and include required Uniform Guidance citations, especially timekeeping.

### ✅ `dfb4e0cd…` — score 9/10
- Text response includes an unnecessary confidence tag not requested by instructions.
  > 💡 Remove extraneous confidence indicators to align strictly with professional deliverable norms.

### ✅ `4c18ebae…` — score 8/10
- SAR narrative lacks specific transaction dates and dollar amounts.
- Excel transaction breakdown content is not fully evidenced in preview.
  > 💡 Add concrete transaction examples with dates and amounts to strengthen regulatory defensibility.

### ✅ `cebf301e…` — score 8/10
- Social login extensibility lacks concrete interface or migration details.
  > 💡 Add a brief auth abstraction section describing future provider integration steps.

### ✅ `c2e8f271…` — score 8/10
- Backend testing tools and standards are not explicitly defined.
- Prettier configuration and enforcement process are not documented.
  > 💡 Add a brief appendix defining backend testing tools and Prettier enforcement details.

### ✅ `2ea2e5b5…` — score 6/10
- Original task required explicit activity classification, not just summarized charts.
- No visible evidence of using the provided Excel source data.
- Strategic level mapping per category is not explicitly documented.
  > 💡 Include a clear table mapping each activity to margin impact, time sensitivity, and strategic level using source data.

### ✅ `c357f0e2…` — score 5/10
- Test cases count is only 60, below the required 80–100 range.
- Column headers do not match the required UAT template fields.
- Viewer role is incorrectly allowed to create ideas, proposals, and projects.
  > 💡 Expand to 80–100 cases, fix role permissions, and correct column headers to match the template.

### ✅ `a45bc83b…` — score 6/10
- Architecture diagram does not use official GCP icons as explicitly required.
- Cloud Armor is incorrectly described as providing Layer 3 and 4 DDoS protection.
- POC steps lack explicit purpose statements for every step.
  > 💡 Update the diagram with official GCP icons and correct security descriptions, clarifying purposes per POC step.

### ❌ `a10ec48c…` — score 2/10
- Required tables with five columns and restaurant rows are missing.
- No restaurant details, links, hours, directions, or categories are provided.
- Sources were not used and permanently closed restaurants were not addressed.
  > 💡 Populate categorized tables with verified downtown Sarasota restaurants and all required column details.

### ✅ `fccaa4a1…` — score 6/10
- Age requirement excludes the 16-year-old participant.
- Icons and visual organization are not evident in the document preview.
- Explicit citation or link to the TakeWalks source page is missing.
  > 💡 Update age requirements, add visible icons, and include a clear TakeWalks source citation.

### ✅ `f5d428fd…` — score 6/10
- PDF is five pages instead of the required two pages.
- Royalty-free image sources are not cited or documented.
- Research sources are not referenced in the itinerary.
  > 💡 Condense the PDF to two pages and add clear citations for images and research sources.

### ❌ `2fa8e956…` — score 4/10
- Document lacks required footer, fonts, and purple grape-variety formatting.
- Image is not embedded or sourced as royalty-free within the Word document.
- List is incomplete and not sourced; does not cover all wineries within one hour.
  > 💡 Revise the Word document to include proper formatting, embedded sourced image, citations, and a more complete winery list.

### ✅ `0e4fe8cd…` — score 6/10
- Missing fourth-day tab and return-home logistics for June 4.
- Airport code listed as ISL instead of standard IST.
- Several car services and transfers lack provider details or links.
  > 💡 Add a complete June 4 return itinerary, correct airport codes, and fully specify all transport providers.

### ✅ `b7a5912e…` — score 6/10
- Booking source revenue does not reconcile with total reported revenue.
- Payment method totals cover only half of total revenue.
- Category utilization percentages are shown as decimals, not formatted percentages.
  > 💡 Reconcile all revenue summaries to totals and format utilization clearly as percentages.

### ❌ `aa071045…` — score 4/10
- Service Request Form lacks required fields like customer, vehicle details, damage description, request type, and status.
- Damage revenue totals are inconsistent; category and damage-type sums equal 15170, not 30340.
- Service Request Form content is minimal and incomplete for maintenance processing.
  > 💡 Complete the service form with all specified fields and correct revenue calculations to ensure consistency.

### ✅ `476db143…` — score 7/10
- Tracking DOCX lacks the inspection table and contains only a title.
- One inspection date differs from the stated tentative date without explanation.
- Email notice lacks specific contact information or phone number.
  > 💡 Ensure all produced file formats contain complete, consistent content and clearer contact details.

### ✅ `61f546a8…` — score 7/10
- Make-ready date changes are noted but revised dates are not specified per unit.
- Appliance installation extra day is not explicitly scheduled as a separate workday.
- An unrequested DOCX file was produced in addition to the required PDF.
  > 💡 Add explicit revised make-ready dates and clearly schedule appliance installation days.

### ✅ `f3351922…` — score 8/10
- Text response summarizes delivery instead of including the drafted email body.
- Transition benefits section omits civilian agency matching contribution details.
- Email preview appears truncated without a complete closing.
  > 💡 Include the full email text in the response and expand transition-specific benefits.

### ✅ `61717508…` — score 8/10
- Second PDF preview does not confirm three distinct mutual fund scenarios.
- No explicit links or citations included for Senior Safe Act and FINRA Rule 2165.
- Escalation guidance may be overly firm without noting firm-specific policy variations.
  > 💡 Add explicit regulatory links and briefly label each role-play scenario for clarity.

### ✅ `0ed38524…` — score 7/10
- District 1 lists the category "General" twice, indicating a categorization error.
- The response does not explicitly confirm use of the provided Excel tracking log.
- The text response describes intent rather than summarizing completed analytical work.
  > 💡 Remove duplicate categories and explicitly reference the Excel log as the data source.

### ✅ `87da214f…` — score 6/10
- Text response is generic and does not summarize findings or financial impact.
- No confirmation that PPTX includes required agenda, figures, and recommendations.
- Review of attached policy and claims is not explicitly evidenced.
  > 💡 Include a concise executive summary with key numbers and explicitly confirm slide contents.

### ✅ `d025a41c…` — score 8/10
- Document does not explicitly confirm bold formatting for case titles.
- 1.5 line spacing cannot be verified from the content preview.
  > 💡 Explicitly confirm formatting requirements in the document or submission notes.

### ✅ `401a07f1…` — score 6/10
- Editorial lacks explicit hyperlinks to referenced news stories.
- Text response describes intent instead of summarising delivered content.
- Evidence of fact-checkable sourcing is implied but not directly linked.
  > 💡 Add clear hyperlinks to specific Nature, Science, Scientific American, and Guardian articles.

### ✅ `afe56d05…` — score 8/10
- Minor typo observed in previewed text near end of a sentence.
- Exact word count compliance with 2,200–2,300 range not explicitly verified.
- Hyperlinks and references not visible in provided preview excerpt.
  > 💡 Proofread the document, confirm word count, and verify all required hyperlinks are included.

### ✅ `9a8c8e28…` — score 7/10
- Bibliography with linked further reading is not evident in the framework guide.
- Framework guide is very brief and may lack sufficient depth for training.
- Quiz content, explanations, and scoring guide were not previewed for verification.
  > 💡 Expand the guide and clearly include a linked bibliography and verified quiz explanations.

### ✅ `3a4c347c…` — score 6/10
- Story ideas lack specific proposed contributors and expert names.
- Draft schedule does not map stories and countries to specific weeks.
- Reference boilerplate context is not explicitly incorporated.
  > 💡 Add week-by-week story assignments with named contributors and align explicitly to the boilerplate.

### ✅ `ec2fccc9…` — score 5/10
- Secondary keywords list is missing at the end of the document.
- There is a visible typo in a section heading ('How NFT Photographers Make Mone').
- Artist links and referenced collections are incomplete or unclear.
  > 💡 Add the missing keyword list, fix typos, and verify all required artist and collection links.

### ✅ `8c8fc328…` — score 8/10
- Script does not explicitly reference or adapt the provided voiceover text.
- Alignment to the reference document’s sequence breakdown is implicit, not explicit.
  > 💡 Briefly note how each section aligns with the provided voiceover and reference sequences.

### ✅ `e222075d…` — score 6/10
- No exported 30-second H.264 MP4 file was delivered.
- Stock footage log uses search pages, not direct clip preview links.
- Music selection is a search result, not a specific track.
  > 💡 Deliver the actual 30-second MP4 and replace searches with direct clip and music URLs.

### ❌ `c94452e4…` — score 4/10
- No actual stock footage was sourced or incorporated.
- Background music was omitted despite being required.
- Supers from the provided PSD were not demonstrated in the video.
  > 💡 Produce a true 15-second cut using real stock footage, PSD supers, and dramatic music.

### ❌ `75401f7c…` — score 3/10
- No actual showreel video file was produced.
- Required .mp4 deliverable with specified resolution and codec is missing.
- Task requested editing execution, not planning documents only.
  > 💡 Produce and deliver the final edited MP4 showreel meeting all technical and creative specifications.

### ❌ `a941b6d8…` — score 4/10
- Stabilization, masking with alpha, and motion tracking are explicitly noted as approximated.
- No actual smoke stock footage was added, only described in documentation.
- Final composite does not demonstrate verified color matching to base clip.
  > 💡 Provide a fully realized final composite implementing all required VFX steps without approximations.

### ❌ `8079e27d…` — score 3/10
- No S&P 500 company-level data populated; Companies sheet is empty.
- Sub-sector summary lacks calculated values and company counts.
- Publicly sourced valuation metrics were not retrieved or included.
  > 💡 Populate all sheets with real S&P 500 data sourced from public markets and complete required calculations.

### ✅ `e21cd746…` — score 8/10
- Some private targets lack complete investor and funding details.
- Valuation figures lack explicit sourcing or date assumptions.
- OnTrac valuation description is imprecise post-merger.
  > 💡 Add concise sources and complete missing private company data for stronger client credibility.

### ✅ `9e8607e7…` — score 9/10
- Slide count is slightly below the requested ~30-slide target.
  > 💡 Consider adding one to two slides on regulatory and structuring considerations by key LatAm country.

### ✅ `c7d83f01…` — score 7/10
- Notebook file size suggests insufficient code depth for multiple full methodologies.
- Monte Carlo American option methodology details are not explicitly evidenced.
- Visualizations are external PNGs rather than integrated notebook outputs.
  > 💡 Expand the notebook with detailed, well-documented implementations and embedded analysis cells.

### ✅ `46b34f78…` — score 6/10
- No explicit use or citation of provided public energy market data.
- Bond analyses lack specific issuer names and quantitative metrics.
- Diversification across fixed income products is not clearly addressed.
  > 💡 Incorporate cited data, name real issuers with metrics, and explicitly address portfolio diversification.

### ✅ `a1963a68…` — score 6/10
- Missing explicit Korean user experience and future-proofing slides.
- Limited use of robust data, metrics, and cited public sources.
- Actionability lacks timelines, owners, and quantified targets.
  > 💡 Add data-backed metrics, explicit UX and innovation slides, and a phased execution roadmap.

### ✅ `b39a5aa7…` — score 6/10
- Projected quarterly results for the next two years are not clearly calculated or displayed.
- Year-over-year growth rates by quarter are missing from the projections.
- Inputs & Projections sheet lacks clear output columns and populated results.
  > 💡 Add explicit quarterly projections for two future years with calculated Y/Y growth tied to editable inputs.

### ✅ `b78fd844…` — score 8/10
- Text response is a meta-summary rather than substantive analysis.
- Page count compliance with 15-page limit is not explicitly stated.
  > 💡 Include a brief executive summary in the text response and confirm final PDF page count.

### ✅ `4520f882…` — score 6/10
- CBA excerpt rules are not fully implemented or referenced in calculations.
- Payroll model lacks detailed per-category totals required by the contract.
- Validation logic for CBA conflicts is minimal and not clearly defined.
  > 💡 Incorporate full CBA rules with explicit formulas, validations, and detailed category summaries.

### ✅ `ec591973…` — score 6/10
- Text response is meta and does not summarize slide content.
- Slide content cannot be verified from provided preview.
- Confidence tag is irrelevant to professional deliverable.
  > 💡 Include a concise textual summary of slide content and key takeaways for verification.

### ❌ `3f821c2d…` — score 3/10
- EOM Inventory, Turn, and Omni sections are blank with no working formulas.
- LY comparison tables are missing despite being required.
- Seasonal turn, inventory constraints, and receipt budget validation are not shown.
  > 💡 Complete all calculations with formulas, add LY tables, and validate constraints before resubmission.

### ✅ `e996036e…` — score 6/10
- Projected shipment total conflicts with stated $225,000 assumption.
- Wholesale revenue calculations appear inconsistent with retailer margin and shipment values.
- Cash flow timing by quarter is not modeled despite payment term differences.
  > 💡 Recalculate using correct shipment totals and explicitly model quarterly cash flow timing by payment terms.

### ❌ `327fbc21…` — score 3/10
- Topline summary misses -15% comp target and shows implausible -99.9% decline.
- Active versus closed store flags are not shown or clearly applied.
- Required 1–2 sentence May sales plan summary with dollars and LY is missing.
  > 💡 Recalculate comp plan to -15% LY, clearly apply active/closed flags, and add a concise numeric summary.

### ❌ `6dcae3f5…` — score 3/10
- ACGME requirement thresholds and PGY attainment were not determined as required.
- Benchmarks sheet lacks calculated averages and standard deviations.
- Excel data structure contains inconsistent years and unclear resident identifiers.
  > 💡 Complete benchmark calculations and ACGME requirement mapping using the provided reference to fulfill all task requirements.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a Visio-style visual workflow with steps and decision points.
- Telehealth Roadmap content does not clearly start from MA placing the patient call.
- Email content length and adherence to 100–150 words cannot be verified.
  > 💡 Revise the roadmap into a true visual flow and confirm the email meets length and content requirements.

### ❌ `0353ee0c…` — score 3/10
- Document lacks exhaustive lists of presumptive conditions, locations, and dates.
- Content uses section headers instead of consolidating required details from references.
- Claims inability to access links, violating task requirements.
  > 💡 Fully extract and list all presumptive exposures, conditions, locations, and dates from Document B sources.

### ❌ `40a8c4b1…` — score 4/10
- Schedule content does not clearly reflect required priorities and conditions from the instructions.
- In-Service Study Session placement in late February is not clearly verified.
- Optional unused topics highlighting is not demonstrated or documented.
  > 💡 Review priorities document carefully and explicitly verify required placements and highlighting in the schedule.

### ❌ `4d1a8410…` — score 3/10
- Interview schedule document lacks required table with detailed timings, rooms, applicants, breaks, and lunch.
- Mandatory constraints missing, including specific breaks, buffers, tour timing, and physician availability requirements.
- Sample itineraries omit timing details and the Simulation Learning Center tour location.
  > 💡 Rebuild documents with a complete timed table schedule and fully compliant, detailed applicant itineraries.

### ✅ `8c823e32…` — score 8/10
- Prohibited Uses section appears truncated with an incomplete sentence.
- Privacy, data retention, and records management provisions are not clearly previewed.
- Community transparency or public notification guidance is not evident.
  > 💡 Review the final document to complete truncated sections and add explicit privacy and data governance language.

### ✅ `eb54f575…` — score 9/10
- Minor inconsistency between calculated total (431) and rounded recommendation (430).
  > 💡 Align the final recommended quantity exactly with the calculated total or clearly justify rounding.

### ✅ `11e1b169…` — score 7/10
- PDF is three pages instead of the required two pages.
- Length control does not meet the specified page limit.
  > 💡 Condense content or adjust formatting to ensure the PDF is exactly two pages.

### ✅ `a95a5829…` — score 9/10
- Effective date is listed as 'Upon Issuance' rather than a specific date.
  > 💡 Specify a concrete effective date and add signature blocks for each approving authority.

### ✅ `22c0809b…` — score 8/10
- Minor typographical truncation observed in Preparation section text.
- Text response describes process rather than summarizing delivered form content.
  > 💡 Proofread the form and add brief Midwest-specific examples or guidance.

### ❌ `bf68f2ad…` — score 4/10
- Weekly demand values appear fabricated and not sourced from the provided Excel data.
- Overtime hours are incorrect; 60 hours shown instead of 20 above regular time.
- Cumulative backlog/buffer calculation starts from an incorrect initial balance.
  > 💡 Rebuild the plan using the provided demand data, correct overtime logic, and initialize backlog at 438.81 hours.

### ❌ `efca245f…` — score 4/10
- No open PO quantities or cumulative backlog tracking shown.
- Scenario 2 still schedules Grill Guard production despite exclusion requirement.
- Expanded capacity scenario ignores 135/day upgrade and 10-hour shift output.
  > 💡 Add PO demand data, cumulative balances, correct capacities, and fully align each scenario to stated constraints.

### ❌ `9e39df84…` — score 4/10
- Average Output and Total Output formulas are missing or not calculated.
- Operator Output Data only includes Week 1 instead of Weeks 1–48.
- Dashboard lacks required PivotTables, charts, and complete KPI calculations.
  > 💡 Complete formulas, expand data to all weeks, and fully implement dashboard pivots, charts, and KPIs.

### ✅ `68d8d901…` — score 7/10
- Work Schedule lacks calculated throughput proving 250,000 lbs in four weeks.
- Production Sequences do not clearly show staggered dryer end times.
- Equipment capacity assumptions are not explicitly tied to batch frequency.
  > 💡 Add a throughput calculation summary linking batch size, cycles per day, and four-week output.

### ✅ `1752cb53…` — score 6/10
- No daily breakdown to verify 450-minute per-press limit.
- Team member weekly hour limits are not demonstrated or summarized.
- Changeover minimum per press is not explicitly validated.
  > 💡 Add summary checks proving labor hours, daily press minutes, and changeover rules are met.

### ✅ `bd72994f…` — score 7/10
- PDF contains no visual imagery from the actual 2025 resort collection.
- Brand and collection source are not explicitly cited within the slides.
- An extra PPTX file was produced without being requested.
  > 💡 Add official look images and clear collection attribution, and remove unrequested file formats.

### ✅ `211d0093…` — score 7/10
- DOCX file lacks full task tables and content.
- PDF lacks a clear employee name field per task.
- Extra DOCX file produced despite PDF-only requirement.
  > 💡 Revise the PDF to add employee name fields and remove or complete the DOCX file.

### ✅ `d4525420…` — score 8/10
- Text response describes deliverable instead of providing the required evaluation paragraph.
  > 💡 Include the actual 5–7 sentence evaluation paragraph directly in the text response.

### ✅ `cecac8f9…` — score 7/10
- Currency uses dollars despite UK store context.
- Preparation plan lacks sufficient operational detail for leadership use.
- Reference materials are not explicitly reflected in targets or offers.
  > 💡 Localise metrics to UK context and expand weekly actions with clearer, actionable detail.

### ✅ `8f9e8bcd…` — score 6/10
- The Let's Practice section lacks examples, objection types, and suggested responses.
- Training document does not explicitly reference conversion rate decline context.
- Core strategies section lacks a named or structured framework.
  > 💡 Add a filled-out practice section with objections, types, and responses, and tie strategies to conversion improvement.

### ✅ `0fad6023…` — score 7/10
- Total FSC Inches Used does not appear to calculate automatically.
- Visual Representation column lacks an actual scaled visual of pan widths.
- POG Builder column headers include blank columns, reducing clarity.
  > 💡 Add formulas for total inches, implement a simple scaled visual bar per pan, and clean up headers.

### ✅ `02314fc6…` — score 8/10
- No explicit overall pass/fail score threshold is defined.
- Corrective action follow-up timeline and responsible owner are not specified.
- Checklist lacks version control, revision date, or document owner.
  > 💡 Add a scoring summary with pass criteria, assigned owner, deadlines, and document version control.

### ✅ `4d61a19a…` — score 8/10
- Excel template does not indicate locked or protected non-store fields.
- PowerPoint content cannot be verified for slide count and included sample visuals.
  > 💡 Add sheet protection to restrict edits and confirm the deck shows a filled sample within eight slides.

### ✅ `8a7b6fca…` — score 7/10
- PDF text formatting is broken, with split words and poor spacing.
- Decision logic for automation compatibility is unclear and weakly labeled.
- Start/end symbols and handoffs are not clearly distinguished visually.
  > 💡 Refine layout, labeling, and standard symbols to improve clarity and executive-ready presentation.

### ✅ `40a99a31…` — score 6/10
- Hardware table lists only one camera, not minimum six required.
- Hardware table contains only five items, missing required quantity detail.
- PDF report is overly brief and lacks detailed justification sections.
  > 💡 Expand hardware table with quantities and detail camera deployment, and deepen report sections.

### ✅ `b9665ca1…` — score 7/10
- Series wiring between S11, S12, and S22 is not clearly shown.
- Cross-fault monitoring exclusion is not explicitly indicated.
- Use of PPTX suggests non-standard schematic authoring tool.
  > 💡 Explicitly label S11, S12, S22 connections and note configuration details directly on the schematic.

### ✅ `c6269101…` — score 6/10
- No explicit capability or stability results are stated in the text response.
- Greatest-variability process is not clearly identified or justified.
- Use of provided Excel data is not demonstrated or referenced.
  > 💡 Summarize concrete findings, identify the most variable process, and reference analyses derived from the provided data.

### ✅ `be830ca0…` — score 7/10
- No evidence shown that analyses strictly used Processing Data.xlsx values.
- ANOVA results lack explicit significance conclusions and performance impact discussion.
- PowerPoint content not verifiable due to missing slide previews.
  > 💡 Include key statistical results summaries and screenshots to substantiate analyses and conclusions.

### ✅ `cd9efc18…` — score 6/10
- Document appears far shorter than required 8–11 pages.
- Temporary local guardian Michael T. Fisher not clearly included.
- Execution and self-proving affidavit details not visible in provided preview.
  > 💡 Expand content to full-length will and clearly include all guardianship and execution provisions.

### ✅ `a97369c7…` — score 8/10
- Text response summarizes intent instead of presenting the memo content.
- Moelis is cited as Supreme Court rather than Court of Chancery.
- Reliance on Senate Bill 313 could use clearer temporal context.
  > 💡 Include the full memo text in the main response and verify case court attributions.

### ✅ `3f625cb2…` — score 8/10
- Case law discussion lacks specific case names or citations.
  > 💡 Add brief citations to key COPPA enforcement actions to strengthen legal support.

### ✅ `aad21e4c…` — score 6/10
- Capitalization schedule before and after issuance is not clearly included.
- Minority consent rights section appears incomplete or truncated.
- Customary boilerplate provisions are limited or missing.
  > 💡 Add a clear capitalization schedule and complete all minority consent and boilerplate sections.

### ❌ `5e2b6aab…` — score 4/10
- Required 2D PDF assembly and sub-assembly drawings with BOMs are missing.
- STEP files appear to be placeholder-sized and lack verifiable geometry detail.
- No explicit assembly or exploded-view documentation was provided.

### ❌ `46fc494e…` — score 3/10
- No transient heat transfer calculations were performed or documented.
- Back-face temperatures remain unrealistically constant at initial conditions.
- Assessment incorrectly concludes large thermal margin without physical justification.
  > 💡 Perform and document the actual transient conduction calculation using the specified 22-node model.

### ✅ `3940b7e7…` — score 7/10
- Conclusion section is truncated and incomplete.
- Velocity components are not reported, only velocity magnitude.
- PDF is very brief and lacks detailed computational domain dimensions.
  > 💡 Complete the conclusion and expand results tables with missing variables and clearer domain details.

### ✅ `8077e700…` — score 6/10
- AISI 1045 results lack direct data analysis and rely on assumptions.
- Required graphs and tables from Data.xlsx are largely missing.
- Experimental Procedure lacks sufficient detail on quenching conditions.
  > 💡 Include full AISI 1018 and 1045 datasets with tables, graphs, and explicit quenching parameters.

### ✅ `5a2d70da…` — score 6/10
- Master Tool List lacks subtotal and Suffolk County post-tax grand total.
- Budget compliance is not explicitly demonstrated against the $7,500 limit.
- Manufacturing steps are minimal and omit several required operations.
  > 💡 Add detailed operations and complete cost rollups including tax to clearly prove budget compliance.

### ✅ `81db15ff…` — score 6/10
- NP physician supervision ratios are missing where NPs lack independent practice.
- Spreadsheet omits NP supervision details for Pennsylvania and West Virginia.
- PA chart sign-off requirements may be oversimplified across all states.
  > 💡 Add NP supervision ratios where applicable and validate PA chart sign-off rules by state.

### ✅ `61b0946a…` — score 8/10
- Introduces a $13,000 cadaver budget not specified in the original task.
- Original task lacks a clear deliverable request, requiring assumptions by the author.
  > 💡 Confirm budget assumptions and restate scope based on clarified stakeholder requirements.

### ✅ `61e7b9c6…` — score 6/10
- Off-label menopause symptom treatments like SSRIs or gabapentin are missing.
- Prices were not obtained from online pharmacies as required.
- Spreadsheet contains multiple blank rows and minimal organization.
  > 💡 Add common off-label therapies, source prices from GoodRx, and clean the spreadsheet structure.

### ✅ `c9bf9801…` — score 6/10
- Monthly timeline with milestones and deliverables is not clearly detailed.
- Required 4-month and 8-month evaluation form documents are missing.
- Credits section acknowledging NCIPC Mentoring Program is not evident.
  > 💡 Add the missing timeline, evaluation form documents, and NCIPC acknowledgment to fully meet requirements.

### ❌ `f1be6436…` — score 3/10
- Conference city, dates, and flight details are unspecified or marked TBD.
- Costs are estimates without documented sources or screenshot evidence in the document.
- Department versus discretionary fund calculations and totals are incomplete.
  > 💡 Provide real-time sourced data with complete travel details, embedded screenshots, and full cost allocation calculations.

### ✅ `41f6ef59…` — score 8/10
- Spreadsheet lacks visible drop-down menus or checkboxes for Yes/No fields.
- Subscription Type column lacks predefined options for all three plans.
- No explicit data validation or efficiency-focused formatting is evident in the spreadsheet.
  > 💡 Add data validation dropdowns and checkboxes to all applicable fields to improve efficiency.

### ❌ `6d2c8e55…` — score 3/10
- Articles are placeholder PDFs without actual accessible full texts or links.
- Room scheduling lacks evidence of using availability and holiday files.
- Article DOCX files were produced despite PDF-only requirement.
  > 💡 Provide real accessible article PDFs or link-PDFs and verified scheduling based on the provided files.

### ✅ `4b98ccce…` — score 6/10
- Excel sheets lack required typed name and employee ID signatures.
- Letters do not demonstrably include provided HIPAA clauses and template elements.
- Employee ID from Employee Sheet is not shown anywhere.
  > 💡 Add signatures with name and employee ID to sheets and fully incorporate provided clauses and templates.

### ✅ `60221cd0…` — score 5/10
- Article appears under the 300-word minimum requirement.
- Early in-person voting start date is incorrect for November 2025.
- Voter registration deadline date may be inaccurate.
  > 💡 Verify all election dates on the Virginia Department of Elections website and expand content length.

### ✅ `ef8719da…` — score 7/10
- Hyperlinks to required background articles are not clearly included.
- Text appears truncated, suggesting possible incomplete sections.
- Pitch was delivered via file only, not fully in the text response.
  > 💡 Ensure complete content with explicit hyperlinks and verify all required sections are fully present.

### ✅ `3baa0009…` — score 8/10
- Article lacks specific numerical growth forecasts for global, US, and China.
- Article does not reference or explain the accompanying 2024–2027 growth chart.
  > 💡 Add key forecast percentages and briefly reference the chart within the article text.

### ✅ `5d0feb24…` — score 6/10
- Review insufficiently engages with the specific arXiv study and its novel research methods.
- Document appears to recreate or alter the reporter draft rather than strictly annotating it.
- Future implications and comparison to prior TRAPPIST-1 studies are not clearly grounded in the paper.
  > 💡 Anchor edits explicitly to findings and methods from arXiv:2401.11815 and distinguish them from background context.

### ✅ `6974adea…` — score 8/10
- Reference to dollars may clash with UK style without context.
- File preview truncation prevents full verification of word count.
- Technical acronyms could be briefly redefined later for general readers.
  > 💡 Add a short currency clarification and a brief RTLS recap mid-article for accessibility.

### ✅ `1a78e076…` — score 6/10
- Document appears significantly shorter than the required 10–15 pages.
- Depth of prevalence, age-group variation, and financial impact analysis is unclear.
- Results subthemes and reference count compliance cannot be fully verified.
  > 💡 Expand content to meet page length and clearly detail required analyses and subthemes.

### ✅ `1b9ec237…` — score 6/10
- PPTX content cannot be verified for required elements like pre-test, case study, and AHA stages.
- Slide count and inclusion of speaker notes are not confirmed.
- It is unclear whether the BP illustration is embedded within the slides.
  > 💡 Provide a slide outline or screenshots to verify all required components are included.

### ✅ `0112fc9b…` — score 8/10
- Plan section contains a minor typographical truncation.
  > 💡 Proofread the Plan section to correct minor typographical errors.

### ✅ `772e7524…` — score 8/10
- Follow-up section appears incomplete or truncated in the plan.
  > 💡 Ensure the plan includes a complete, explicit follow-up timeline and reassessment instructions.

### ✅ `e6429658…` — score 6/10
- Appeal letter does not meet the required 2–4 page length.
- Appeal letter appears incomplete or truncated in the provided file preview.
  > 💡 Expand and finalize the appeal letter to a full 2–4 pages with complete clinical justification.

### ❌ `b5d2e6f1…` — score 4/10
- Sales by Store tab is missing from the delivered workbook.
- Sales by Brand does not clearly show required grand totals.
- Pivot table structure and fields are not explicitly verifiable.
  > 💡 Add the Sales by Store pivot tab with required fields and ensure visible grand totals on all summary tabs.

### ✅ `f841ddcf…` — score 8/10
- Filters are not explicitly enabled or demonstrated in the Excel tables.
- Percent_Shipped values are decimals rather than formatted percentages.
- Narrative sheet contains an unnecessary blank first row.
  > 💡 Apply table filters, format percent columns, and clean up the narrative layout for polish.

### ✅ `47ef842d…` — score 8/10
- Text response describes deliverables but does not explicitly show calculation steps.
  > 💡 Briefly summarize key calculations in the text to explicitly demonstrate methodology.

### ✅ `1137e2bb…` — score 9/10
- Summary tables are not explicitly implemented as Excel pivot tables.
- Unit prices show floating-point precision artifacts instead of formatted currency.
  > 💡 Convert SKU summaries to pivot tables and format prices as currency to improve clarity.

### ✅ `c3525d4d…` — score 6/10
- No identification of stores removed between original and final lists.
- Final store list only labels added stores, not unchanged or removed ones.
- Units with overage are fractional instead of whole production units.
  > 💡 Include a store-by-store comparison showing added and removed locations and round production units appropriately.

### ✅ `9a0d8d36…` — score 6/10
- Text response states intent but provides no actual comparison or calculations.
- PPT content cannot be verified for required step-by-step tax calculations.
- Hypothetical data and net proceeds are not demonstrated in the response.
  > 💡 Include summarized slide content with example calculations and tax outcomes to validate the deliverable.

### ✅ `664a42e5…` — score 6/10
- Text response summarizes intent rather than presenting substantive content.
- PPT content cannot be verified from the provided preview.
- No visible confirmation of 2025 gift tax exclusion and Crummey timeline details.
  > 💡 Include slide-by-slide content details or a preview to verify all required elements are addressed.

### ✅ `feb5eefc…` — score 8/10
- PDF page count compliance with the 12-page limit is not explicitly confirmed.
  > 💡 Explicitly state the final PDF page count to confirm adherence to the 12-page requirement.

### ✅ `3600de06…` — score 7/10
- Slide count cannot be verified as exactly ten.
- FINRA and NAIC source citations are not confirmed within slides.
- Specific comparisons and penalties cannot be validated without slide preview.
  > 💡 Provide a slide outline or export images to verify content, slide count, and regulatory citations.

### ✅ `c657103b…` — score 6/10
- Starting 2025 balance is $3.78M, not the stated $3.5M.
- PowerPoint template requirement cannot be verified as business digital tunnel.
- Excel lacks explicit estate tax and heir benefit calculations.
  > 💡 Align assumptions to client data and explicitly document estate and heir tax benefits.

### ✅ `f9f82549…` — score 8/10
- An extra PowerPoint file was produced beyond the specified flowchart headers.
- PDF flowchart appears minimal without visible decision paths or connectors.
- Anonymization of names and store number is not explicitly stated in files.
  > 💡 Add explicit anonymization notes and enhance the flowchart with clear decision arrows.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance concluded at 1:20 a.m., exceeding the authorized end time of 1:00 a.m.
- Investigator arrival time of 7:25 p.m. conflicts with stated 7:30 p.m. start.
- Assessment language implies intimacy without explicit factual confirmation.
  > 💡 Align all times strictly with authorization and use more objective language in assessments.

### ✅ `84322284…` — score 8/10
- Text response is a meta description rather than a substantive executive summary.
- An unrequested DOCX file was produced alongside the required PDF.
- Minor truncation or typo appears in the PDF preview text.
  > 💡 Include a brief executive summary in the text response and proofread final PDFs carefully.

### ✅ `6241e678…` — score 8/10
- Client edit review window is four days but rounds are not clearly delineated.
- Color-coding and legend cannot be verified from provided PDF text preview.
  > 💡 Label each revision round explicitly and include a visible color legend page in the PDF.

### ✅ `e14e32ba…` — score 6/10
- Business hours are missing for all restaurants.
- Physical locations are not explicitly listed.
- Image links point to websites, not specific photo URLs.
  > 💡 Add locations, business hours, and direct photo URLs to fully meet the brief.

### ✅ `b1a79ce1…` — score 8/10
- Text response describes intent more than summarizing delivered visuals.
- No explicit mention of how inner conflict versus outer beauty is visualized.
  > 💡 Briefly describe key visual elements in the final moodboard and how they reflect the song’s themes.

### ❌ `e4f664ea…` — score 4/10
- Script length is only three pages, not the required eight to twelve pages.
- Scene count and story scope are too limited for the specified requirements.
- Text response describes deliverables instead of summarizing creative execution.
  > 💡 Expand the screenplay with additional scenes and character development to meet length requirements.

### ❌ `a079d38f…` — score 4/10
- Spreadsheet lacks detailed line-item costs and totals based on service rates.
- Time estimates per role and total hours are not calculated.
- Column headers and cost calculation structure are unclear or missing.
  > 💡 Add service rates, role-based hours, calculated totals, and clear column headers to complete the breakdown.

### ❌ `02aa1805…` — score 3/10
- No Illinois EPA data was retrieved or reviewed.
- Excel file contains no well data or analysis.
- No viable wells were identified or recommended.
  > 💡 Retrieve and analyze actual Illinois EPA factsheet data and populate the workbook with recommendations.

### ✅ `fd6129bd…` — score 5/10
- Change Request Form is a blank template, not a completed example.
- SOP Change Criteria section lacks defined criteria or table.
- SOP Version History section is incomplete or truncated.
  > 💡 Complete the SOP sections fully and include a filled example Change Request Form.

### ✅ `ce864f41…` — score 8/10
- Written response does not explicitly answer the three analysis questions with findings.
- Utilization percentages are decimals exceeding 1 instead of formatted percentages.
- Column name contains a spelling error: "Wrike Transition Intiative".
  > 💡 Add a concise written summary of findings and standardize formatting and naming conventions.

### ✅ `58ac1cc5…` — score 8/10
- Change control does not reference a specific reviewed COA value or lot data.
- Use of the official attached blank change control form is not explicitly confirmed.
- RMS update scope and approval pathway are only briefly described.
  > 💡 Add explicit COA lot details and confirm alignment with the official change control template.

### ✅ `3c19c6d1…` — score 6/10
- Claims use of reference files that were not provided in the task.
- No evidence Slide 3 includes exact required bullets and numbering.
- Progress summary slide content not verified as tabular summary.
  > 💡 Verify slide-by-slide content against requirements and remove unsupported references to external files.

### ❌ `a99d85fc…` — score 4/10
- Annual rent matrices contain no calculated values or formulas.
- Monthly rent matrices are missing entirely.
- Totals, notes section, and reconciliation are not provided.
  > 💡 Populate dynamic formulas, add complete monthly matrices, totals, notes, and ensure annual-monthly reconciliation.

### ❌ `55ddb773…` — score 4/10
- Missing many required violation types and details from the referenced Violations Questions PDF.
- Numerous OCR/typographical errors and unclear bullet formatting reduce professionalism.
- Architectural regulations are not fully listed individually as required.
  > 💡 Rebuild the form using verified extraction of the source PDF and perform thorough QA for completeness and clarity.

### ❌ `1e5a1d7f…` — score 3/10
- The .docx file does not contain the required task schedule table.
- The four specified columns are missing from the document.
- No actual weekly or monthly task details are provided.
  > 💡 Add a complete table with all required columns and populated weekly tasks aligned to PM duties.

### ✅ `0419f1c3…` — score 8/10
- Acknowledgement-time metric lacks system timestamps to objectively verify compliance.
- One training module name appears truncated or inconsistently labeled.
- Justification linking each training module to specific gaps could be more explicit.
  > 💡 Clarify measurement methods, correct module naming, and explicitly tie each training to identified gaps.

### ✅ `ed2bc14c…` — score 6/10
- Exit survey analysis does not show full categorization into the five required departure reasons.
- Communication plan lacks drafted email content, only high-level descriptions.
- No explicit evidence the Excel reference file was directly analyzed.
  > 💡 Add detailed exit survey categorization and include brief draft renewal emails for each notice stage.

### ✅ `46bc7238…` — score 8/10
- Cold call and email scripts are high-level and lack detailed phrasing.
- One-page flyer is described but not fully designed as a finished template.
- Stock photos are included but sources or usage notes are not specified.
  > 💡 Add more detailed scripts, a fully formatted flyer page, and note stock photo sources.

### ✅ `2d06bc0a…` — score 8/10
- Brokerage section contains a typographical truncation.
- Buyer’s broker representation is not clearly disclosed.
  > 💡 Proofread final document and add explicit buyer broker disclosure before delivery.

### ✅ `0818571f…` — score 6/10
- Properties are illustrative, not verified active listings from Crexi or LoopNet.
- Active listing dates, platform links, and listing IDs are missing.
- Investor PDF criteria is not explicitly matched to each property.
  > 💡 Replace examples with verified June 2025–present Crexi or LoopNet listings including links and IDs.

### ❌ `6074bba3…` — score 3/10
- PDF contains extensive placeholder text and missing property details.
- Comparable sales and active listings are not populated with real data.
- Required graphs are not embedded and sections remain incomplete.
  > 💡 Populate the template fully with real comps, pricing analysis, and embedded graphs before delivery.

### ✅ `5ad0c554…` — score 7/10
- Brochure does not explicitly reference or identify items from the 132 Things REALTORS Do list.
- Word document does not clearly demonstrate a double-sided, two-page layout.
- Visuals appear separate and not clearly integrated into the brochure content.
  > 💡 Explicitly cite relevant items from the 132 Things list and embed visuals within a clear two-page Word layout.

### ✅ `11593a50…` — score 5/10
- Listings appear fabricated and not verified from MLSLI as required.
- Property table lacks required list date column and consistent status values.
- Map pins are illustrative, not actual property locations.
  > 💡 Use verified MLSLI data, complete all required columns, and generate an accurate geocoded map.

### ✅ `94925f49…` — score 7/10
- Reports lack explicit citations to specific reputable school data sources.
- Home listings appear illustrative without MLS IDs or verifiable addresses.
- DOCX files were produced despite PDFs being the only requested format.
  > 💡 Add explicit data source citations and verified MLS listing details, and deliver PDFs only.

### ✅ `90f37ff3…` — score 5/10
- Comparable data lacks dates, sources, and verifiable citations.
- Disclaimer indicates representative data without live internet verification.
- DOCX market rent survey table is missing comparable details.
  > 💡 Provide sourced, dated comparables from LoopNet or Crexi and update both PDF and DOCX.

### ✅ `d3d255b2…` — score 8/10
- Text response is meta-description rather than substantive summary.
- Use of attached market analysis is implied, not explicitly cited.
- Counteroffer recommendation section appears partially truncated in preview.
  > 💡 Include a brief executive summary in the text response and clearly reference the attached market analysis source.

### ✅ `1bff4551…` — score 6/10
- Original song YouTube link is missing and left as a placeholder.
- Song title "Pay to Cum" violates the no heavy curse words requirement.
- No evidence provided that most artists are represented in the Institute collection.
  > 💡 Replace noncompliant content, add a valid original song link, and document collection representation.

### ✅ `650adcb1…` — score 5/10
- No visible color-coding key included on the first Excel page.
- Dates with fewer than two interns working are not clearly listed anywhere.
- Some multi-day requested time off periods are not fully marked as requested.
  > 💡 Add a visible key and shortage list to the first tab and verify all requested dates are correctly labeled.

### ✅ `01d7e53e…` — score 6/10
- Primary contacts lack names, titles, and contact information.
- Signatory block with required individuals is missing.
- Miscellaneous section contains placeholder or truncated standard contract language.
  > 💡 Complete missing contacts, signatories, and fully integrate the City’s standard contract language.

### ✅ `0ec25916…` — score 7/10
- PDF is two pages, not the required single page.
- Table formatting does not clearly present two columns by four rows.
- Text response claims one-page PDF, contradicting actual file.
  > 💡 Condense content to fit a clear two-column, four-row table on one PDF page.

### ✅ `116e791e…` — score 7/10
- PDF exceeds one-page requirement with three pages.
- Text response does not summarize or present the care plan content.
- One-page formatting requirement was not met despite correct content.
  > 💡 Condense layout and formatting so the full care plan fits on a single PDF page.

### ❌ `dd724c67…` — score 4/10
- Facility list is incomplete and includes a non–Long Island facility.
- Task required all Long Island hospitals and rehab facilities, not a preliminary subset.
- TFU guide lacks CMS-defined condition-specific timeframes and relies on generic estimates.
  > 💡 Expand and validate the facility list and align TFU content precisely with CMS PY 2025 specifications.

### ❌ `7151c60a…` — score 4/10
- Pre-screening checklist lacks required table with patient information and tracking columns.
- Company logo is missing from both documents.
- Checklist missing page numbers and patient identifiers on each page.
  > 💡 Add the missing table content, logo, and pagination to fully meet stated regulatory requirements.

### ❌ `90edba97…` — score 3/10
- Required monthly lab values were not entered into the tracker.
- Patient names and MRNs are missing from tracker sheets.
- No medication or treatment changes were documented per protocols.
  > 💡 Request complete Patient Lab Reports and fully populate all tracker fields with protocol-based actions.

### ✅ `91060ff0…` — score 8/10
- Poster lacks clear visual elements like icons, graphics, or charts.
- Table formatting is minimal and may not be visually engaging for a health fair.
- References are cited generally without specific publication dates or links.
  > 💡 Enhance visual design with icons, color sections, and clearer tables to improve engagement.

### ❌ `8384083a…` — score 3/10
- Several days’ supply calculations are incorrect, including Ozempic and Miebo.
- DOCX file lacks the required medication table and detailed content.
- Table formatting, typos, and truncated NDCs reduce clarity and audit usability.
  > 💡 Recalculate all days’ supply accurately, fix formatting and NDC errors, and fully populate the DOCX and PDF tables.

### ✅ `045aba2e…` — score 6/10
- Checklists lack explicit citations to specific California statutes or regulations.
- Weekly and monthly checklist content appears truncated or incomplete.
- Operational roles and responsibilities are not defined despite original task context.
  > 💡 Expand checklists with statute references and ensure all required sections are complete and explicit.

### ❌ `f2986c1f…` — score 3/10
- Medications were not identified from the image.
- Drugs.com was not used to determine medication details.
- Spreadsheet contains only NA placeholder data.
  > 💡 Identify medications from the image using Drugs.com or decline the task upfront if impossible.

### ❌ `ffed32d8…` — score 3/10
- Comparative table lacks per-medication cost, reimbursement, and revenue details.
- Analysis does not use or reference provided Wholesale Price or Reimbursement data.
- Revenue difference of $0.00 appears unsupported and likely incorrect.
  > 💡 Recalculate using source PDFs and include a complete per-drug comparative table with transparent assumptions.

### ✅ `b3573f20…` — score 7/10
- PDF is six pages instead of the required three pages.
- Text response describes intent rather than summarizing delivered document content.
  > 💡 Condense the PDF content to exactly three pages and align the response with the final deliverable.

### ✅ `a69be28f…` — score 8/10
- Revenue by fit is not clearly visualized alongside units on regional slides.
  > 💡 Add revenue-by-fit charts or tables to each regional men’s and women’s slide.

### ✅ `788d2bc6…` — score 6/10
- TikTok Shop and influencer services are not clearly evidenced in the deck preview.
- Slides lack explicit 1–2 sentence service summaries separate from bullet points.
- Visual elements and open-source imagery are not apparent in the PDF preview.
  > 💡 Add clearly labeled TikTok-focused slides with summaries and visuals to fully meet the brief.

### ✅ `74ed1dc7…` — score 8/10
- Text response is meta and lacks a substantive summary of the proposal.
- Proposal does not explicitly map each order type to reference-file challenges.
- No implementation or governance guidance included for ERP changes.
  > 💡 Add a brief executive summary and a challenge-to-order-type mapping table.

### ✅ `69a8ef86…` — score 6/10
- Internal process lacks detailed step-by-step actions, owners, and timelines for each required stage.
- Internal document omits the 14-day warehouse report to CS requirement.
- RA closure procedure after 90 days is not clearly defined with responsibilities.
  > 💡 Expand the internal document with a numbered workflow table detailing actions, timelines, and responsible teams.

### ✅ `ab81b076…` — score 8/10
- Final section appears truncated with an incomplete word.
- Communication escalation timelines are not clearly defined.
- Roles and responsibilities are not explicitly assigned.
  > 💡 Add clear role ownership and escalation timelines, and fix the truncated final section.

### ✅ `7ed932dd…` — score 6/10
- No evidence of highlighted rows for additional pallets or earlier delivery requirements.
- Workbook lacks visibility of source reference tabs and conversion logic.
- Date fields include unnecessary timestamps, reducing professional clarity.
  > 💡 Add clear cell highlighting, simplify dates, and document conversion calculations using the reference tabs.

### ❌ `105f8ad0…` — score 4/10
- Recommended price-per-ounce exceeds competitor averages by far more than ±6%.
- No evidence of required online competitor MSRP research as of September 2025.
- Pricing rationales are repetitive and partially truncated, lacking SKU-specific logic.
  > 💡 Recalculate MSRPs using verified competitor MSRPs and enforce the ±6% price-per-ounce constraint.

### ✅ `b57efde3…` — score 6/10
- Did not systematically review or confirm companies against the official Aqua Nor 2025 exhibitor list.
- Prospecting list is very limited, containing only four example companies.
- Several entries are explicitly marked as requiring verification, indicating placeholder content.
  > 💡 Expand the spreadsheet by fully reviewing the official exhibitor list and validating each relevant company's offerings.

### ❌ `15d37511…` — score 3/10
- Spreadsheet lacks pricing, costs, margins, and totals despite reference email availability.
- Tiered pricing logic and discount application are not calculated or shown.
- Year 1 total gross margin is not computed or summarized.
  > 💡 Populate all pricing data from the email and calculate margins, discounts, and total Year 1 gross margin.

### ✅ `bb863dd9…` — score 6/10
- Grand total price in USD is not shown in the quotation.
- Completeness of all IEHK 2017 modules cannot be verified from the file.
- Use of internal pricing reference is not evidenced or cited.
  > 💡 Add a grand total, confirm all modules are listed, and reference the internal pricing source.

### ✅ `fe0d3941…` — score 8/10
- Survey PDF contains three pages instead of two separate pages as specified.
- An extra DOCX survey file was produced though only a PDF was requested.
  > 💡 Reduce the survey PDF to exactly two pages and omit unrequested file formats.

### ❌ `6a900a40…` — score 4/10
- Transport options with freight costs and grand totals are missing or unclear.
- Item remarks lack transit times and suitability reasoning for each transport mode.
- General remark about freight validity in red font is missing.
  > 💡 Revise the Excel file to clearly add all transport options, remarks, totals, and required general note.

### ✅ `9efbcd35…` — score 7/10
- MSCI performance data lacks explicit index returns or tables.
- No explicit citations to WSJ, FT, or named research sources.
- Technology and CEEMEA sections are not clearly evidenced in preview.
  > 💡 Add explicit MSCI index returns and cite key WSJ or FT articles to strengthen credibility.

### ✅ `1d4672c8…` — score 7/10
- Text response states incorrect professional role compared to original task.
- Data sourcing from MSCI website is not documented or cited in files.
- Correlation matrix sheet has an unnamed first column header.
  > 💡 Add clear data source citations and ensure roles and labels align with task requirements.

### ❌ `4de6a529…` — score 3/10
- Most required sub-asset classes and currencies are missing from the tables.
- Tables lack complete UW/N/OW indicators, consistent arrows, and clear conviction labels.
- Rationales and formatting appear truncated and unprofessional in the final PDF.
  > 💡 Rebuild the tables to fully cover all specified asset classes with complete columns and clean formatting.

### ✅ `4c4dc603…` — score 5/10
- PDF exceeds one page requirement.
- Key economics and salient numbers are vague or missing.
- Contact phone number is incomplete and team profiles lack names.
  > 💡 Condense to one page and add specific metrics, token details, full contacts, and named team profiles.

### ✅ `bb499d9c…` — score 7/10
- Key Reports section appears truncated and incomplete in the document.
- Issuer process customization by issuer groups is not clearly evidenced.
- Text response summarizes intent rather than delivered content.
  > 💡 Expand reports section, explicitly segment issuer flows, and align text summary with delivered document content.

### ✅ `5349dd7b…` — score 6/10
- UPS does not offer true standard flat rate boxes; inclusion may be invalid.
- FedEx and UPS rates may reflect express services, not standard delivery speeds.
- Rate increase research lacks cited sources despite requirement to use search engines.
  > 💡 Verify carrier flat rate eligibility and service levels, and cite authoritative rate sources.

### ✅ `a4a9195c…` — score 8/10
- No explicit citations to specific IPC-A-610G sections.
- Document control elements like revision history are missing.
- Environmental limits such as humidity ranges are not specified.
  > 💡 Add IPC-A-610G section references, document control details, and specific environmental limits.

### ✅ `552b7dd0…` — score 5/10
- No evidence the Excel incident data was reviewed or referenced.
- Results lack specific numeric findings for costs and resolution times.
- Visuals for total cost and incident duration are not provided.
  > 💡 Include concrete metrics derived from the spreadsheet and add missing cost and duration visuals.

### ❌ `76418a2c…` — score 4/10
- Manifest lacks proper headers and required fields like pick ticket and customer.
- Data appears incomplete and not derived from provided pick tickets and parameters.
- Column structure and calculations are inconsistent and unprofessional.
  > 💡 Rebuild the manifest using source files with correct headers, complete data, and verified calculations.

### ❌ `0e386e32…` — score 3/10
- ZIP file size is unrealistically small for a full frontend and smart contract scaffold.
- No verifiable evidence that required frontend, contract, or config files are included.
- Original task requirements are claimed but not demonstrably implemented.
  > 💡 Include and verify a complete, populated codebase with all promised components and documentation.

### ❌ `7de33b48…` — score 3/10
- Zip contents cannot be verified; no code preview or file listing provided.
- No evidence the utility, queuing logic, or WCAG ARIA22 tests are implemented.
- Required visible prop behavior and accessibility tree handling are unverified.
  > 💡 Include full source previews or a file manifest proving all required implementations and tests exist.

### ✅ `4122f866…` — score 5/10
- Terraform likely missing SES DKIM and MAIL FROM records.
- README lacks details on reCAPTCHA configuration and environment variables.
- No evidence API Gateway stage versioning like /v1 is configured.
  > 💡 Explicitly document and implement all SES, API Gateway stage, and reCAPTCHA requirements.

## Failure Analysis

Errors were limited (10 total) but retries were non-trivial (34), indicating intermittent instability rather than systematic failure. Retries likely stemmed from transient execution issues or partial output generation failures, especially in longer or more complex tasks. No single sector showed a dominant error concentration, suggesting failures were configuration- or execution-related rather than domain-specific.

## Recommendations

Increase reasoning level selectively for sectors with lower self-assessed QA confidence (e.g., Health Care, Manufacturing) to improve answer robustness without rerunning the full benchmark. Investigate retry triggers and logs to identify whether failures are tied to audio preprocessing, subprocess timeouts, or output formatting. Consider latency optimization or parallelization for Information-sector tasks, where longer runtimes did not translate into higher self-assessed quality.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 4 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 2 file(s)
- `38889c3b…` (Information): 6 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 1 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 1 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 2 file(s)
- `bbe0a93b…` (Government): 6 file(s)
- `85d95ce5…` (Government): 2 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 4 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 3 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 9 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 2 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 4 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 2 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `61717508…` (Finance and Insurance): 4 file(s)
- `0ed38524…` (Finance and Insurance): 3 file(s)
- `87da214f…` (Finance and Insurance): 2 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 6 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e222075d…` (Information): 7 file(s)
- `c94452e4…` (Information): 2 file(s)
- `75401f7c…` (Information): 2 file(s)
- `a941b6d8…` (Information): 6 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 2 file(s)
- `c7d83f01…` (Finance and Insurance): 5 file(s)
- `46b34f78…` (Finance and Insurance): 1 file(s)
- `a1963a68…` (Finance and Insurance): 2 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 2 file(s)
- `4520f882…` (Finance and Insurance): 1 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `e996036e…` (Wholesale Trade): 2 file(s)
- `327fbc21…` (Wholesale Trade): 1 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 2 file(s)
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
- `1752cb53…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `d4525420…` (Retail Trade): 1 file(s)
- `cecac8f9…` (Retail Trade): 5 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 6 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 10 file(s)
- `46fc494e…` (Manufacturing): 5 file(s)
- `3940b7e7…` (Manufacturing): 2 file(s)
- `8077e700…` (Manufacturing): 3 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 3 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 3 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 20 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 2 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `772e7524…` (Health Care and Social Assistance): 1 file(s)
- `e6429658…` (Health Care and Social Assistance): 2 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 2 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 2 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 8 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `6241e678…` (Information): 2 file(s)
- `e14e32ba…` (Information): 1 file(s)
- `b1a79ce1…` (Information): 1 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 2 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 1 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 8 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 12 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 20 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 11 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 2 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 1 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 2 file(s)
- `91060ff0…` (Retail Trade): 2 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 6 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `ffed32d8…` (Retail Trade): 2 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 2 file(s)
- `788d2bc6…` (Wholesale Trade): 2 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 3 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 3 file(s)
- `4de6a529…` (Finance and Insurance): 2 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `bb499d9c…` (Finance and Insurance): 3 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 3 file(s)
- `76418a2c…` (Manufacturing): 1 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 1 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 6 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
