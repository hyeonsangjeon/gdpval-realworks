# Experiment Report: GPT-5.2 Chat Elicit v2 — domain packages + package notice (Full 220)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp011_GPT52Chat_domain_packages` |
| **Condition** | Elicit v2 16k + domain packages |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-05 |
| **Duration** | 147m 51s |
| **Generated At** | 2026-03-05T09:41:55.939402+00:00 |
| 🤗 HF Dataset | [exp011_GPT52Chat_domain_packages](https://huggingface.co/datasets/HyeonSang/exp011_GPT52Chat_domain_packages) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp011_GPT52Chat_domain_packages/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated GPT-5.2 Chat under the Elicit v2 16k configuration with domain packages and package notice enabled, across 220 domain-specific tasks executed via subprocess. The run achieved a 95.9% task completion rate, with 211 successful executions and 9 errors. The model produced deliverable outputs for the majority of tasks, with 40 tasks requiring retries to reach completion.

Across completed tasks, the model reported an average self-assessed QA confidence of 6.11/10, indicating moderate confidence in output quality as judged internally by the LLM during execution. Latency was relatively high, averaging ~26.7 seconds per task, consistent with the expanded context window and domain package usage. Key highlights include full success in several sectors and relatively stable QA confidence despite variation in domain complexity.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 211 (95.9%) |
| Errors | 9 |
| Retried Tasks | 40 |
| Avg QA Score | 6.11/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 26,727ms |
| Max Latency | 54,529ms |
| Total LLM Time | 5879s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 177 (95.7%) |
| Failed → dummy created | 8 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 27 | 27 | 0 |
| 2 | 13 | 4 | 9 |

## Quality Analysis

Self-assessed QA confidence scores clustered mostly between 5 and 7 across sectors, suggesting outputs were generally adequate but often not fully confident or polished. The highest average self-QA confidence appeared in Government (6.9/10) and Retail Trade (6.7/10), while Information (5.7/10) and Professional, Scientific, and Technical Services (5.6/10) showed lower internal confidence, potentially reflecting more ambiguous or specification-heavy task requirements.

Latency varied by sector, with Information tasks showing the highest average latency (~31.8s), suggesting heavier reasoning or document synthesis workloads. Deliverable generation quality was sufficient to pass self-checks in most cases, but lower QA confidence in technical and professional domains indicates possible gaps in precision, formatting adherence, or domain nuance handling.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 24 | 96.0% | 6.08/10 | 28,067ms |
| Government | 25 | 25 | 100.0% | 6.88/10 | 25,558ms |
| Health Care and Social Assistance | 25 | 24 | 96.0% | 5.96/10 | 25,685ms |
| Information | 25 | 25 | 100.0% | 5.72/10 | 31,799ms |
| Manufacturing | 25 | 23 | 92.0% | 6.3/10 | 27,515ms |
| Professional, Scientific, and Technical  | 25 | 23 | 92.0% | 5.57/10 | 26,859ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 5.92/10 | 26,700ms |
| Retail Trade | 20 | 20 | 100.0% | 6.65/10 | 26,419ms |
| Wholesale Trade | 25 | 23 | 92.0% | 6.0/10 | 21,879ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 3 | 6/10 | 33402ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 21409ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 7 | 3/10 | 26020ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 17 | 5/10 | 22303ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 6/10 | 18872ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 2/10 | 26962ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 18082ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 7/10 | 27704ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 4 | 9/10 | 31382ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 7 | 5/10 | 30598ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 4/10 | 37480ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 7/10 | 24790ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | Yes | 1 | 5/10 | 31405ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 0 | 3/10 | 26084ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | Yes | 1 | 2/10 | 19827ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 9/10 | 28792ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 7/10 | 27621ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 30095ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 23170ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 6/10 | 34238ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 34312ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 6/10 | 30189ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 6 | 7/10 | 34595ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | Yes | 5 | 4/10 | 47124ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 6 | 6/10 | 29590ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 22720ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 20032ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 8/10 | 25215ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 14128ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 7/10 | 25883ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 33762ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 30588ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 4/10 | 24351ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 3/10 | 30838ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 6 | 7/10 | 42341ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 2/10 | 39921ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 6/10 | 33652ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 9 | 4/10 | 34309ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 5/10 | 39595ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 7/10 | 36771ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 8/10 | 23568ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 21191ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 5/10 | 17732ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 6 | 4/10 | 22164ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 5 | 6/10 | 21853ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 6/10 | 22171ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 5 | 8/10 | 29394ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 5 | 7/10 | 26681ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 7/10 | 23110ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 21658ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 25615ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 7/10 | 43225ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 6 | 6/10 | 30517ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | 6/10 | 26303ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 2 | 7/10 | 33104ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 2 | 8/10 | 26798ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 6 | 6/10 | 39955ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 3/10 | 33055ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 3/10 | 29705ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | Yes | 1 | 3/10 | 38300ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 3/10 | 19210ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 7/10 | 22930ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 7/10 | 43757ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 4 | 3/10 | 54529ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 7/10 | 38697ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 7/10 | 45310ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 23151ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 3/10 | 20471ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 8/10 | 33626ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 6/10 | 22722ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 8/10 | 19686ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 6/10 | 21205ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 2/10 | 19629ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 2 | 6/10 | 18198ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 3 | 4/10 | 26380ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 3 | 4/10 | 26620ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 6/10 | 37027ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 3/10 | 24931ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 5/10 | 24528ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 11 | 4/10 | 20731ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 5/10 | 27603ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 23891ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 21335ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 20490ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 25687ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 3 | 5/10 | 20149ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 24240ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 4/10 | 27578ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 19299ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 6 | 6/10 | 20377ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 6/10 | 24753ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 7/10 | 14322ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 8/10 | 15691ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 7 | 8/10 | 26603ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 6 | 7/10 | 32860ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 25903ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 5/10 | 37214ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 26343ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 7/10 | 29910ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 30818ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 8/10 | 24235ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 4 | 6/10 | 40925ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 6/10 | 35228ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | 6/10 | 26818ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | 7/10 | 49878ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 4/10 | 28700ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | Yes | 1 | 7/10 | 36096ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 9/10 | 24550ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 25246ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 30148ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 5/10 | 22752ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 6/10 | 43013ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 4/10 | 26759ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 5 | 7/10 | 32467ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 6/10 | 29150ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 7/10 | 30251ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 8/10 | 23559ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | 7/10 | 40079ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 3/10 | 16393ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | 6/10 | 38936ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 3/10 | 29930ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 8/10 | 15027ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 28367ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 13 | 5/10 | 28187ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 7/10 | 28267ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 30587ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 7/10 | 30906ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 31080ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | Yes | 2 | 7/10 | 29511ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 8 | 5/10 | 49790ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 28744ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 26518ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 15826ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 19609ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 5 | 8/10 | 32265ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 3/10 | 23056ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 7/10 | 25282ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 8/10 | 18876ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 8/10 | 21362ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 5 | 6/10 | 24488ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | Yes | 1 | 7/10 | 17574ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 22076ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 8/10 | 25138ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 8/10 | 20789ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 30936ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 7/10 | 36929ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 7/10 | 30029ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 8/10 | 32948ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 5 | 7/10 | 35574ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 6 | 8/10 | 27537ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 30380ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | Yes | 7 | 6/10 | 43022ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 29744ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 4 | 6/10 | 32672ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 3 | 6/10 | 21114ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 19528ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | Yes | 3 | 6/10 | 23507ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 6/10 | 31902ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 8 | 8/10 | 27844ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 5 | 5/10 | 24922ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 20630ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 6/10 | 23351ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 4/10 | 18574ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 24569ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 24078ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 8 | 7/10 | 29082ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 7/10 | 26408ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | 8/10 | 15860ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 13 | 6/10 | 34546ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 5 | 3/10 | 27598ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 7/10 | 17383ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 6 | 5/10 | 28971ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 11 | 6/10 | 36147ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 6/10 | 22762ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 8/10 | 26774ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 18384ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 23953ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 18150ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 4 | 7/10 | 25405ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 4 | 5/10 | 15533ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 8/10 | 17617ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 7/10 | 18072ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 5/10 | 28113ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 5/10 | 18716ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 7 | 4/10 | 23820ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 8/10 | 22696ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 7/10 | 23807ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 6 | 6/10 | 19095ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 2/10 | 11859ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | Yes | 4 | 3/10 | 23488ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 7/10 | 24047ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 13 | 8/10 | 24651ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 7/10 | 30691ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 21157ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 7/10 | 26163ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 7/10 | 23726ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 24558ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 5/10 | 22697ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 20066ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 4/10 | 19009ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 15639ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 16703ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 6/10 | 16655ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 5 | 7/10 | 23832ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 6 | 6/10 | 19223ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 29722ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 3 | 5/10 | 22851ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 5/10 | 25210ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 4/10 | 24852ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 6/10 | 35113ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 26643ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 22025ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 4 | 7/10 | 20353ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 17137ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 14942ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 4/10 | 16302ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 3 | 5/10 | 24522ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 22207ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 4/10 | 24568ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 27553ms |

## QA Issues

### ✅ `83d10b06…` — score 6/10
- Text response does not explicitly confirm all task steps were completed.
- No evidence provided that all sampling criteria were each satisfied at least once.
- Variance calculation includes infinite values without explanation or handling.
  > 💡 Explicitly document criteria coverage and address handling of zero-denominator variance calculations.

### ❌ `7d7fc9a7…` — score 3/10
- Text response describes intent, not completed amortization schedules.
- No evidence the Excel workbook contains required calculations or reconciliations.
- GL balance reconciliation and monthly rollforwards are not demonstrated.
  > 💡 Provide the completed Excel workbook with detailed schedules and verified GL reconciliations.

### ✅ `43dc9778…` — score 5/10
- Text response describes intent rather than summarizing actual completed Form 1040 results.
- No verification that the PDF contains a fully populated, review-ready 2024 Form 1040.
- Required schedules are listed but not confirmed as completed with client-specific figures.
  > 💡 Summarize key tax results and explicitly confirm the PDF contains a completed, accurate Form 1040 and schedules.

### ✅ `ee09d943…` — score 6/10
- Response describes intent but provides no summary of actual work performed.
- No confirmation of reconciliations, variances, or issues flagged to CFO.
- Includes nonstandard CONFIDENCE tag not requested in deliverable.
  > 💡 Add a brief completion summary confirming tabs updated, issues found, and CFO notifications.

### ❌ `f84ea6ac…` — score 2/10
- No research summary table or five studies included.
- Missing article details, key findings, and government implications.
- States offline knowledge instead of conducting online public research.
  > 💡 Produce a one-page Word table summarizing five post-2020 public articles with all required fields.

### ✅ `a328feea…` — score 9/10
- Procedure lacks guidance if supervisor or team lead is unreachable.
  > 💡 Add a brief backup contact or escalation step if the primary contact cannot be reached.

### ✅ `27e8912c…` — score 7/10
- Checklist lacks explicit citation and link to the NIH source.
- Ergonomic images do not state public-domain status or source.
- Checklist Word file was produced but not requested as a deliverable.
  > 💡 Add NIH citation with link and image source attributions, and remove or justify extra files.

### ✅ `17111c03…` — score 9/10
- An extra DOCX memo file was produced but not requested.
  > 💡 Limit deliverables to the requested PDF memo and Excel schedule only.

### ✅ `c44e9b62…` — score 5/10
- Revised organizational chart lacks detailed positions and does not show highlighted reductions.
- No clear demonstration that at least 4% FTE reduction was calculated and achieved.
- Briefing note and reports lack explicit linkage to provided reduction assumptions and numbers.
  > 💡 Explicitly quantify FTE reductions, align files to assumptions, and visually mark reduced positions.

### ❌ `99ac6944…` — score 4/10
- Selected analog mixer lacks onboard compression, reverb, and delay effects.
- PDF lacks detailed pricing links, cabling list, and comprehensive system justification.
- Cost breakdown is incomplete with missing total budget calculation.
  > 💡 Replace mixer with analog board featuring onboard effects and complete documentation with finalized budget totals.

### ✅ `f9a1c16c…` — score 7/10
- Bass and guitar stage sides appear reversed from specified Stage Right and Stage Left.
- Monitor mix preferences for drummer and singers are not explicitly indicated.
- Vocalist wedge placement in front of singers is not clearly depicted.
  > 💡 Revise the plot to correct stage sides and clearly annotate monitor mix intentions and wedge positions.

### ✅ `38889c3b…` — score 5/10
- Zip contents are not verified to include required master and four stems.
- No evidence the provided drum reference was actually used and synchronized.
- Bridge stem and Ab major section timing are not confirmed.
  > 💡 Include a clear file manifest and brief verification notes for tempo, keys, stems, and drum sync.

### ❌ `ff85ee58…` — score 3/10
- No audio files were produced or delivered.
- Task required an actual mixed WAV output, not a descriptive summary.
- No evidence of resyncing, editing, or loudness compliance was provided.
  > 💡 Produce and attach the final 24-bit, 48 kHz WAV mix meeting all specified audio requirements.

### ❌ `4b894ae3…` — score 2/10
- Final stereo WAV mix file was not delivered.
- No edited bass stem or evidence of corrections provided.
- Produced file duplicates reference document instead of required deliverables.
  > 💡 Deliver the specified 48k/24b stereo WAV with corrected bass properly mixed in.

### ✅ `1b1ade2d…` — score 9/10
- Text response is descriptive of intent rather than summarizing key outcomes.
  > 💡 Include a brief executive summary of key workflow changes in the text response.

### ✅ `93b336f3…` — score 7/10
- Detailed cost breakdown and per-unit calculations are not explicitly shown in INR.
- Introduces a 49:51 JV ownership assumption not specified in the original task.
- Savings figures are stated without clear calculation steps or assumptions.
  > 💡 Add a transparent INR cost table with step-by-step calculations and justify any new assumptions.

### ✅ `24d1e93f…` — score 6/10
- Final summary and recommendation sheet is missing from the workbook.
- Assumptions are not clearly listed or documented in any sheet.
- Discount factor for Year 3 is inconsistent with 10% rate in Solimoto sheet.
  > 💡 Add a summary sheet with NPV comparison, explicit assumptions, and correct discount factors.

### ✅ `05389f78…` — score 6/10
- Quotation file lacks numerical cost data, preventing required INR calculations and comparisons.
- CPO report appears largely qualitative without detailed cost tables or calculations.
- Quotes file content does not match bidding details described in the task.
  > 💡 Include complete vendor pricing data and add detailed INR-based comparative cost and risk tables.

### ✅ `575f8679…` — score 8/10
- Data analysis plan lacks detail beyond descriptive statistics and pre-post comparisons.
  > 💡 Add a brief evaluation timeline and more specific analytic techniques to strengthen rigor.

### ✅ `a74ead3b…` — score 6/10
- Manual content was not accessed or closely followed as explicitly required.
- Session-specific objectives and activities for Sessions 13 and 14 are not verified.
- Text response lacks summary of actual slide content and learning goals.
  > 💡 Revise presentations using the official manual to ensure accurate, session-specific content alignment.

### ✅ `bbe0a93b…` — score 7/10
- Spanish follow-up table headers are malformed and not clearly separated into three columns.
- Resource Guide omits requested categories like transportation, clothing, and counseling.
- Resource Guide lists limited agencies, reducing usefulness for comprehensive referrals.
  > 💡 Revise the Spanish table formatting and expand the Resource Guide categories and agency listings.

### ❌ `85d95ce5…` — score 4/10
- Report length is five pages, not the required eight to fifteen pages.
- School name and social worker fields are filled instead of using required placeholders or blanks.
- Included notes file references a different student name than JOHN SMITH.
  > 💡 Revise the report to meet length, placeholder, and student-specific documentation requirements before resubmission.

### ✅ `76d10872…` — score 6/10
- Text response describes intent rather than summarizing actual report content.
- No evidence the PDF follows Case Creation Guide sections.
- Unprofessional CONFIDENCE tag included in response.
  > 💡 Include a concise summary of report sections and key data to verify completeness.

### ✅ `36d567ba…` — score 8/10
- Minor typographical error appears in Topic 8 question text.
- Uniform Guidance citation for Topic 8 is generic rather than section-specific.
  > 💡 Proofread for minor errors and add specific 2 CFR Part 200 section citations where possible.

### ✅ `7bbfcfe9…` — score 9/10
- Some §3919 questions focus on policies or training rather than account-level transaction testing.
  > 💡 Refine §3919 questions to focus more directly on borrower-specific account outcomes.

### ✅ `2696757c…` — score 8/10
- Test questions are somewhat generic and not tightly mapped to specific paragraph obligations.
- Exception statements lack specific evidence references or dates for audit traceability.
  > 💡 Refine questions and exceptions to mirror exact handbook language and cite specific missing documentation.

### ✅ `dfb4e0cd…` — score 9/10
- Text response does not summarize counts of fast versus slow spending awards.
  > 💡 Add a brief summary of how many awards met each spending rate criterion.

### ✅ `4c18ebae…` — score 7/10
- Text response describes intended deliverables rather than summarizing investigative conclusions.
- An extra Excel file was produced beyond the two described deliverables.
- SAR narrative lacks specific transaction amounts and date ranges.
  > 💡 Align the text response with actual findings and ensure files exactly match stated deliverables.

### ✅ `cebf301e…` — score 8/10
- Six-week delivery timeline and milestones are not explicitly detailed.
- Metrics or success criteria for the customer portal are not defined.
  > 💡 Add a brief delivery plan with milestones and initial success metrics.

### ✅ `c2e8f271…` — score 8/10
- Minor typo detected in truncated PR guidelines section.
- External style guides referenced without direct links.
- Owner attribution may conflict with document author role.
  > 💡 Proofread final document, add direct links to referenced guides, and clarify document ownership.

### ❌ `2ea2e5b5…` — score 4/10
- Output describes intended presentation, not actual analysis results.
- Required activity classifications for margin, time sensitivity, and strategy are missing.
- No evidence the PPT contains correct mappings or summarized findings.
  > 💡 Include explicit activity classifications and summarized results derived from the source data.

### ❌ `c357f0e2…` — score 3/10
- UAT test plan contains no populated test cases.
- All rows are blank with no roles, modules, or scenarios defined.
- Deliverable does not demonstrate 80–100 test cases as required.
  > 💡 Populate the Excel file with complete role-based UAT test cases matching the implementation outline.

### ✅ `a45bc83b…` — score 7/10
- Cloud Armor is incorrectly described as providing Layer 3 and Layer 4 DDoS protection.
- Architecture summary does not explicitly mention multi-zone or regional redundancy configuration.
- Proposed diagram references GKE or Compute Engine without a clear final selection.
  > 💡 Correct the DDoS protection explanation and clarify availability design and compute platform choice.

### ❌ `a10ec48c…` — score 2/10
- Document lacks required tables with columns and restaurant rows.
- No restaurant details, links, hours, directions, or categories are provided.
- Sources, Google Maps data, and closed-restaurant exclusions are not demonstrated.
  > 💡 Populate each cuisine section with fully completed tables using verified Downtown Sarasota restaurant data.

### ✅ `fccaa4a1…` — score 6/10
- PDF is three pages instead of the intended two-page itinerary.
- No icons or Statue of Liberty photo are visible in the PDF.
- Age requirement excludes the 16-year-old participant.
  > 💡 Revise layout to two pages, add visual icons and photo, and correct age requirements.

### ❌ `f5d428fd…` — score 4/10
- PDF exceeds the required two-page length.
- No destination photos are visible within the PDF.
- Royalty-free image sources are not cited or attributed.
  > 💡 Condense content to two pages and embed properly sourced royalty-free images with attributions.

### ✅ `2fa8e956…` — score 5/10
- Did not provide all wineries within one-hour drive; only a small curated subset.
- Required source citations for winery selection and distances are missing.
- Specified formatting not fully met, including purple grape text and visible footer.
  > 💡 Expand to a comprehensive list with citations and ensure all specified Word formatting is correctly applied.

### ✅ `0e4fe8cd…` — score 7/10
- Fourth day return travel and home arrival logistics are missing.
- Some rows appear truncated or incomplete in the wedding day sheet.
- High-value individual connections are minimally developed.
  > 💡 Add a complete June 4 return itinerary with full flight, transfer, and arrival details.

### ✅ `a0ef404e…` — score 8/10
- Contains a grammatical error and incomplete phrase in the Common Mistakes section.
  > 💡 Proofread the document to correct minor typos and incomplete sentences.

### ✅ `aa071045…` — score 5/10
- Service Request Form lacks populated fields and required damage, request type, and vehicle status details.
- Damage Revenue Report totals do not reconcile with damage-type and category breakdowns.
- Service Request Form does not specify left rearview mirror replacement or vehicle availability.
  > 💡 Fully populate the service form and correct revenue calculations to ensure consistency across all report sections.

### ❌ `476db143…` — score 4/10
- Inspection tracking PDF lacks resident rows and required data.
- Inspection dates were not adjusted per resident responses in NOTES.
- Manager-facing document content is incomplete and unusable.
  > 💡 Populate the tracking PDF with all September move-outs and correct inspection dates per NOTES.

### ✅ `61f546a8…` — score 6/10
- On-site staff scheduled across weekend, violating Mon–Fri requirement.
- M30 on-site staff scheduled four days instead of required two.
- Appliance extra-day impact is not clearly reflected in unit timelines.
  > 💡 Revise schedules to keep on-site work to two weekday-only days and clearly show appliance-added days.

### ✅ `f3351922…` — score 6/10
- Email ends with a truncated, incomplete closing sentence.
- No professional signature block or contact information included.
  > 💡 Complete the closing sentence and add a full professional signature before delivery.

### ✅ `61717508…` — score 8/10
- Internal Policy PDF contains incomplete placeholder bullet points.
- Text response summarizes deliverables but does not explicitly confirm Senior Safe Act and Rule 2165 coverage.
  > 💡 Complete placeholders and explicitly reference regulatory sections in the summary response.

### ✅ `0ed38524…` — score 7/10
- Duplicate category labels with inconsistent spacing appear in the district summary.
- Talking points contain minor spelling and grammar errors.
- Summary lists counts but lacks synthesized narrative themes per district.
  > 💡 Standardize categories, proofread text, and add brief thematic summaries per district.

### ✅ `87da214f…` — score 7/10
- Text response does not summarize actual findings or financial results.
- Confidence line appears unnecessary and unprofessional.
- No verification provided that slide deck includes all required sections.
  > 💡 Include a brief summary of key findings and financial impact directly in the text response.

### ✅ `d025a41c…` — score 6/10
- Produced extra Word files beyond the single required Case Feedback document.
- Section titles are not shown in bold as explicitly required.
- Line spacing requirement of 1.5 is not clearly demonstrated.
  > 💡 Revise to one Word file only, ensure bold section titles, and apply verified 1.5 line spacing.

### ✅ `401a07f1…` — score 6/10
- Editorial is significantly under the requested 500-word length.
- No direct hyperlinks to reference news stories are included.
- References are vague and lack verifiable citations for sub-editing.
  > 💡 Expand to 500 words and add explicit hyperlinks to specific Nature, Science, Scientific American, and Guardian articles.

### ✅ `afe56d05…` — score 7/10
- Document length appears below the required 2,200–2,300 words.
- External resources and hyperlinks are not clearly visible or comprehensive.
  > 💡 Expand sections to meet word count and add explicit, attributed hyperlinks to all referenced sources.

### ✅ `9a8c8e28…` — score 6/10
- Bibliography lacks clickable links as required for further reading.
- Quiz answer key, explanations, and scoring guide are not clearly evidenced.
- International accessibility context beyond UK law is minimally covered.
  > 💡 Add linked bibliography entries, clearly include quiz answers with explanations and scoring, and expand international compliance guidance.

### ✅ `3a4c347c…` — score 6/10
- Text response does not summarise or evidence deliverable content.
- Reference file name differs from task-specified title.
- Cannot confirm all required elements without full document visibility.
  > 💡 Include a brief content summary and explicitly confirm all checklist items are covered.

### ✅ `ec2fccc9…` — score 7/10
- Secondary keywords list is not clearly presented at the end of the article.
- Explicit H2 and H3 heading structure is not clearly indicated.
- SEO research sources or rationale for chosen keywords are not documented.
  > 💡 Add a clearly labeled secondary keyword list and ensure headings use explicit H2 and H3 styles.

### ✅ `8c8fc328…` — score 8/10
- Text response summarizes intent rather than highlighting key script moments.
  > 💡 Include a brief outline of major sequences or timestamps in the text response.

### ✅ `e222075d…` — score 6/10
- No 30-second H.264 MP4 export was delivered.
- Scratch voiceover and music audio files are missing.
- Stock log lacks direct preview links to specific clips.
  > 💡 Provide the final MP4, audio tracks, and precise stock preview links to meet requirements.

### ❌ `c94452e4…` — score 3/10
- Did not deliver the required 15-second H.264 MP4 broadcast spot.
- Provided planning documents instead of the actual edited video output.
- No specific stock footage or music tracks were sourced or referenced.
  > 💡 Produce and export the final 15-second MP4 using stock footage, music, and provided supers as specified.

### ❌ `75401f7c…` — score 3/10
- Final MP4 showreel was not produced as required.
- Output delivers planning documents instead of edited video.
- Task explicitly required video editing and export, not a blueprint.
  > 💡 Deliver the completed 01:20 MP4 showreel matching all sequencing, audio, and technical specifications.

### ❌ `a941b6d8…` — score 3/10
- Required composited video file was not produced.
- No actual stabilization, masking, tracking, or compositing was performed.
- Smoke VFX and final teleportation effect were not created.
  > 💡 Produce the final composited video matching specifications and include all required VFX elements.

### ❌ `8079e27d…` — score 3/10
- Excel contains no data; all sheets have zero rows.
- Publicly available S&P 500 data was not leveraged or populated.
- Sub-sector sheet missing required annual and quarterly EPS columns.
  > 💡 Populate the workbook with full S&P 500 company data and complete all required fields.

### ✅ `e21cd746…` — score 7/10
- Some private targets lack complete valuation, funding, investor, or customer details.
- Shipt and Roadie are subsidiaries, not independent private acquisition targets.
- Certain valuations and investor attributions appear approximate or unsubstantiated.
  > 💡 Refine private target list to independent companies and add fully sourced valuation and investor details.

### ✅ `9e8607e7…` — score 7/10
- Slide count is 27, slightly below the requested ~30 slides.
- Text response does not summarize key insights or findings from the presentation.
- Confidence tag appears non-standard and unnecessary in professional deliverable.
  > 💡 Add a brief executive summary and consider expanding to ~30 slides for fuller coverage.

### ❌ `c7d83f01…` — score 3/10
- Missing required Python notebook implementing American option pricing methodologies.
- Pricing results are inconsistent and implausible for the same American option.
- Finite-difference output indicates a critical implementation or parameter error.
  > 💡 Provide a complete, validated notebook with reconciled prices and reproducible benchmarks.

### ✅ `46b34f78…` — score 7/10
- Bond analyses use representative issuers rather than naming specific oil and gas companies.
- Limited explicit citation of publicly available data sources within the main text.
- Sales strategy recommendations could be more concrete and trade-specific.
  > 💡 Name specific issuers, add clear data citations, and include more granular trade examples.

### ✅ `a1963a68…` — score 7/10
- Limited explicit data citations and source references supporting claims.
- H2 2024 execution timeline and milestones are not clearly specified.
- Future-proofing and sustainability initiatives are insufficiently detailed.
  > 💡 Add clear data sources, an August-start execution roadmap, and a concrete long-term innovation slide.

### ❌ `b39a5aa7…` — score 3/10
- Summary and calculations tabs contain no populated compensation values.
- No projections for next two years or year-over-year growth shown.
- Compensation is not broken out by pay type as required.
  > 💡 Complete and populate calculations, add quarterly projections with Y/Y growth, and include pay-type breakdowns.

### ✅ `b78fd844…` — score 8/10
- Text response is generic and does not summarize key analytical conclusions.
- Reference file is redundantly listed as a produced deliverable.
  > 💡 Include a concise executive summary of findings directly in the text response.

### ✅ `4520f882…` — score 6/10
- Text response describes features but provides no verification of implemented calculations.
- Excel model validation against specific CBA rules is not demonstrated.
- Inclusion of CONFIDENCE tag is unprofessional for deliverable.
  > 💡 Provide a brief walkthrough or screenshots proving the Excel formulas, validations, and CBA compliance.

### ✅ `ec591973…` — score 8/10
- Cannot verify slide content or one-page constraint from preview.
- Channel-specific tactics and examples may lack sufficient specificity.
- 5-minute elevator pitch structure is not explicitly outlined.
  > 💡 Add a brief slide outline confirming one-page format and explicit channel-specific investment examples.

### ✅ `62f04c2f…` — score 6/10
- Excel form lacks required freight prepayment and restocking fee notice.
- Excel form missing signature, name, and date spaces for sales rep, GM, and Sales Manager.
  > 💡 Update the Excel form to add the required fee note and all approval signature sections.

### ❌ `3f821c2d…` — score 2/10
- Excel lacks calculated EOM inventory, turns, and working formulas.
- Omni total flow and seasonal turn calculations are missing.
- Sales cells contain month labels instead of fixed plan values.
  > 💡 Rebuild the workbook with complete formulas, correct sales inputs, and an added omni summary table.

### ✅ `e996036e…` — score 6/10
- Projected shipment total uses $255,000 instead of stated $225,000 assumption.
- Cash flow timing by payment terms is not shown or analyzed.
- No visual chart comparing scenario favorability is included.
  > 💡 Align shipment totals to assumptions, add cash flow timing detail, and include a comparison chart.

### ❌ `327fbc21…` — score 4/10
- Topside May plan misses -15% LY target; comp stores show large positive growth.
- Rollup totals contradict stated business expectations for comparable stores.
- Required 1–2 sentence May sales plan summary is missing.
  > 💡 Rework forecasts to meet the -15% comp target and add the required written May summary.

### ❌ `6dcae3f5…` — score 4/10
- ACGME key indicator requirement analysis and PGY attainment were not completed.
- Excel benchmarks per PGY and requirement comparisons are not clearly demonstrated.
- Stated lack of internet access despite provided ACGME document link.
  > 💡 Complete the ACGME requirement mapping and explicitly document PGY attainment and benchmarks in the Excel file.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a Visio-style visual workflow and appears text-only.
- Telehealth Roadmap is not clearly one-page visual as required.
- An extra unrequested file was produced, causing scope creep.
  > 💡 Add a true visual flow diagram to the Roadmap and remove unrequested files.

### ❌ `0353ee0c…` — score 3/10
- Did not compile presumptive conditions, locations, and dates as required.
- PDF largely repeats links instead of consolidating information.
- Document is not exhaustive and omits organized cancer and non-cancer lists.
  > 💡 Fully extract and organize all presumptive exposures, conditions, locations, and dates from each reference link.

### ✅ `40a8c4b1…` — score 5/10
- Excel schedule content is not verified against required priorities and conditions.
- Text response describes intent but lacks confirmation of completed scheduling details.
- Reference files were included as produced deliverables unnecessarily.
  > 💡 Provide a brief verification summary confirming all required rules were applied in the Excel file.

### ❌ `4d1a8410…` — score 4/10
- Master schedule lacks detailed table with room-by-room interview timings and applicant assignments.
- Breaks, lunch placement, tours, and physician-specific constraints are not explicitly scheduled.
- Personal itineraries omit specific interviewers, rooms, and exact time blocks.
  > 💡 Add a complete time-based table and fully detailed individual itineraries matching all stated constraints.

### ✅ `8c823e32…` — score 5/10
- PDF content appears truncated with incomplete sentences.
- Policy length is insufficient for a comprehensive General Manual procedure.
- Text response summarizes deliverable instead of presenting policy content.
  > 💡 Expand and finalize the PDF to include all required sections with complete, fully reviewed content.

### ✅ `11e1b169…` — score 7/10
- PDF is three pages instead of the required two pages.
- KRS 503.090 section lacks key statutory elements and clear deadly force criteria.
- Guide lacks Kentucky case law or state-specific examples for search and seizure.
  > 💡 Condense formatting to two pages and expand Kentucky-specific legal detail, especially for use of force.

### ✅ `a95a5829…` — score 8/10
- Text response summarizes deliverables without detailing policy procedures.
- Excel logging structure and fields are not described in the response.
  > 💡 Briefly summarize key policy procedures and Excel log structure in the text response.

### ✅ `22c0809b…` — score 7/10
- PDF exceeds required 2–4 page length at five pages.
- Page count requirement was explicitly specified and not met.
  > 💡 Condense layout to four pages while retaining all required sections and indicators.

### ✅ `bf68f2ad…` — score 5/10
- Catch-up plan never reduces workdays or overtime after backlog recovery.
- No positive buffer is achieved or demonstrated within the plan horizon.
- Spreadsheet does not illustrate consequences of reducing days without demand changes.
  > 💡 Extend the plan to show buffer creation and staged reductions to five- and four-day weeks.

### ✅ `efca245f…` — score 6/10
- Scenario 3 violates no-overtime constraint by using a 10-hour shift.
- Capacity increase to 135 sets/day from February 5 is not reflected.
- March/April prioritization logic is not clearly modeled in the plans.
  > 💡 Revise scenarios to respect constraints and explicitly model capacity changes and PO prioritization.

### ❌ `9e39df84…` — score 4/10
- Operator Output Data contains extra unnamed columns not specified in requirements.
- Average Output and Total Output cells are blank instead of auto-calculated.
- Dashboard lacks required PivotTables and four charts specified in the task.
  > 💡 Clean the data table, add required formulas, and fully implement pivots, charts, and interactivity.

### ✅ `68d8d901…` — score 6/10
- Excel content not verified against four-week 250,000 lb requirement.
- Staggered dryer end-times not explicitly demonstrated.
- Unnecessary reference DOCX files were regenerated.
  > 💡 Validate Excel tabs show calculations, staggered cycles, and remove extraneous reference files.

### ✅ `1752cb53…` — score 6/10
- Completed plan alters original template by removing required columns.
- No evidence shown that labor, material, and changeover rules were satisfied.
- Text response describes intent but not specific planning results.
  > 💡 Repopulate the original Week One Test Plan template with all required columns and verified rule compliance.

### ✅ `bd72994f…` — score 6/10
- No specific luxury brand or official 2025 resort collection is identified.
- Slides include a title page, reducing the number of actual styled looks.
- Content appears generic and not clearly sourced from an official lookbook.
  > 💡 Select a named luxury brand and rebuild slides using documented looks from its official 2025 resort collection.

### ✅ `211d0093…` — score 7/10
- No dedicated field to record assigned employee names.
- Column headers are unclear and combine initials, notes, and assignment.
- Document text includes instructional placeholders rather than finalized formatting.
  > 💡 Add a clear employee name column and refine table headers for clarity and professionalism.

### ✅ `d4525420…` — score 8/10
- Text response is a meta description, not the actual evaluative paragraph.
- Decision rationale is only accessible in the attached document.
  > 💡 Include the full 5–7 sentence selection paragraph directly in the text response as well.

### ✅ `45c6237b…` — score 8/10
- Final summary table slide is not clearly visible in the PDF preview.
- Next Season Assortment section lacks item labels or captions for images.
  > 💡 Add a clearly labeled final slide with a full SKU pricing and quantity table and caption images.

### ✅ `cecac8f9…` — score 7/10
- Currency inconsistency between UK plan (£) and targets PDF using dollars ($).
- Team launch deck lacks specific Black Friday promotional offer details.
  > 💡 Align all documents to UK currency and add clear, specific promotional offers to the launch deck.

### ✅ `8f9e8bcd…` — score 6/10
- Homework section is missing required tracking instructions, due date line, and printed name line.
- Conclusion appears truncated and may be incomplete.
- Practice section includes limited objection examples across all required types.
  > 💡 Add a complete Homework section, finish the Conclusion, and expand practice examples to all objection types.

### ✅ `0fad6023…` — score 5/10
- Total and remaining inches do not calculate automatically.
- Running total column appears without confirmed formulas.
- Pan count may not fully represent all possible 24-foot configurations.
  > 💡 Add verified formulas and ensure enough pan rows to cover all 6-inch pan scenarios.

### ✅ `02314fc6…` — score 8/10
- Scoring and follow-up section appears truncated and may lack full corrective action details.
- Signature and acknowledgment fields are not visible in the PDF preview.
  > 💡 Complete the scoring section and add clear signature and corrective action tracking fields.

### ✅ `4d61a19a…` — score 7/10
- Excel fields are not protected to prevent store edits outside allowed columns.
- PowerPoint slide count and inclusion of a visible sample form cannot be verified.
- Excel template lacks brief instructions guiding store completion and submission.
  > 💡 Lock non-store fields, add brief instructions in the Excel, and confirm slide count and sample visibility.

### ✅ `6436ff9e…` — score 8/10
- Text response uses future tense instead of confirming completed delivery.
  > 💡 Revise the text response to clearly state that the deliverable has been completed and reviewed.

### ✅ `8a7b6fca…` — score 8/10
- Start and end symbols are not explicitly labeled in the process map.
- Decision logic criteria for automation compatibility are not clearly defined.
- Failure reroute path lacks detail on handling steps and ownership.
  > 💡 Add explicit start/end markers and brief decision criteria annotations to improve clarity for leadership review.

### ✅ `40a99a31…` — score 6/10
- Report lacks specific hardware makes, models, and detailed justifications.
- PDF is overly brief and missing required section depth.
- Minimum six cameras and LIDAR zone specifics not explicitly documented.
  > 💡 Expand documentation with concrete models, quantities, zone coverage details, and deeper integration logic.

### ✅ `b9665ca1…` — score 6/10
- Source drawing not created in Visio, Electra, or AutoCAD Electrical as required.
- Stop button parallel wiring requirement is unclear or insufficiently demonstrated.
- Button box wire labels differ from specified ES1/ES2/ES3 naming convention.
  > 💡 Recreate the schematic in the specified CAD software and clearly show compliant stop button wiring and labels.

### ✅ `c6269101…` — score 6/10
- Text response describes intent but provides no actual analytical findings.
- Process with greatest variability is not explicitly identified or summarized.
- Capability and stability conclusions are not stated in the narrative.
  > 💡 Include explicit results and conclusions from the analysis, not just a description of deliverables.

### ✅ `be830ca0…` — score 7/10
- PowerPoint content cannot be verified for required sections and interpretations.
- ANOVA results interpretation and performance drivers are not explicitly documented.
- DMAIC phase dates and tollgate status clarity cannot be confirmed.
  > 💡 Include explicit written interpretations and clearly labeled DMAIC dates within the slides.

### ❌ `cd9efc18…` — score 4/10
- PDF is only 3 pages, not the required 8–11 pages.
- Execution and self-proving affidavit details are not evidenced in the file preview.
  > 💡 Expand the will with full Texas customary clauses and include a proper execution and self-proving affidavit section.

### ✅ `a97369c7…` — score 7/10
- Delaware Senate Bill 313 is not clearly discussed or analyzed in the memo.
- Text response describes the memo instead of presenting substantive analysis.
- Minor overpromising of embedded hyperlinks without verification.
  > 💡 Explicitly analyze Senate Bill 313 and ensure all referenced materials are substantively incorporated.

### ✅ `3f625cb2…` — score 9/10
- Memo could more clearly state COPPA lacks a private right of action.
  > 💡 Add a brief clarification distinguishing regulatory enforcement from private claims.

### ✅ `aad21e4c…` — score 6/10
- Agreement text appears truncated and incomplete in key sections.
- Minority-investor consent rights over extraordinary actions are not clearly detailed.
- Capitalization schedule before and after investment is not visible.
  > 💡 Complete all sections, explicitly add consent rights and include a clear pre/post-investment cap table.

### ✅ `8314d1b1…` — score 8/10
- Text response is procedural and does not summarize substantive legal analysis.
  > 💡 Include a brief substantive summary of conclusions in the text response.

### ✅ `5e2b6aab…` — score 5/10
- No evidence of design features addressing thermal limits, grip, glove operation, or sealing requirements.
- PDF contains only one assembly sheet; required sub-assembly drawings are missing.
- STEP ZIP size suggests placeholder or non-detailed models.
  > 💡 Provide detailed STEP models and drawings demonstrating all functional requirements and required sub-assemblies.

### ✅ `46fc494e…` — score 6/10
- Text response describes intended deliverables but provides no actual results or conclusions.
- One listed file is the original task request, not a generated deliverable.
- Numerical temperature results and margins are not visible or clearly summarized.
  > 💡 Explicitly present key numerical results and conclusions in the main response and report summary.

### ❌ `3940b7e7…` — score 4/10
- Text response only describes intent, not the actual CFD report content.
- Generated report likely contains placeholders instead of extracted numerical results.
- No evidence tables and aerodynamic discussion were fully populated from CFD data.
  > 💡 Include the full report content with populated tables and explicit aerodynamic analysis derived from the CFD study.

### ✅ `8077e700…` — score 7/10
- AISI 1045 results lack figures and detailed data presentation.
- No tables are included despite stating tabulated hardness data.
- Hardness increase during tempering is questionable and insufficiently justified.
  > 💡 Add explicit tables and figures for both steels and clarify metallurgical explanations with data support.

### ✅ `5a2d70da…` — score 6/10
- Master Tool List lacks subtotal and Suffolk County sales tax grand total.
- Manufacturing Steps file lacks detailed operation descriptions and sequencing.
- Excel formatting includes empty columns and unclear headers.
  > 💡 Add tax calculations, clarify manufacturing operations, and clean up Excel structure and headers.

### ✅ `74d6e8b0…` — score 7/10
- No explicit in-text citations or reference list are included in the document.
- Guidelines lack direct attribution to specific U.S. or international menopause societies.
- Research methodology and source selection are not described.
  > 💡 Add a clearly labeled references section with in-text citations linked to major menopause guidelines and reviews.

### ✅ `81db15ff…` — score 8/10
- Physician supervision limits use vague terms like typically or varies by agreement.
- No citations or regulatory sources provided to support state-specific rules.
  > 💡 Add authoritative citations and clarify supervision limits with exact statutory language where possible.

### ✅ `61b0946a…` — score 7/10
- Original task did not request a Word document or file-based deliverables.
- Proposal omits operational details like scheduling, freezer constraints, and interdepartmental governance.
- Text references an embedded graph without explicitly confirming placement in the document.
  > 💡 Align deliverables strictly to stated requirements and add concrete operational logistics.

### ❌ `61e7b9c6…` — score 3/10
- Formulary largely empty and missing most FDA-approved and common off-label menopause medications.
- Bijuva is incorrectly listed as estradiol/bazedoxifene instead of estradiol/progesterone.
- Estimated prices lack sourcing and many rows contain placeholder blanks.
  > 💡 Fully populate the spreadsheet with accurate drugs, correct formulations, and sourced price estimates.

### ✅ `c9bf9801…` — score 6/10
- Detailed monthly timeline with milestones is missing.
- 4-month and 8-month evaluation form documents were not produced.
- Credits section acknowledging NCIPC is not evident.
  > 💡 Add a month-by-month timeline, include evaluation form files, and clearly add NCIPC acknowledgment.

### ❌ `f1be6436…` — score 3/10
- All screenshots and costs are placeholders, not sourced from live data.
- Flight dates and Dr. Doe’s early departure requirement are not addressed.
- Cost calculations are inconsistent and show incorrect negative remaining balances.
  > 💡 Redo the document using live sourced data with accurate dates, screenshots, and corrected calculations.

### ✅ `41f6ef59…` — score 8/10
- Spreadsheet does not clearly demonstrate data validation, dropdowns, or checkboxes.
  > 💡 Add visible dropdowns or checkboxes to Yes/No tracking columns to improve usability.

### ✅ `6d2c8e55…` — score 5/10
- Article PDFs contain placeholder example.com links, not verified peer-reviewed accessible sources.
- Requirement for fully accessible articles without paywall is not demonstrably met.
- Email draft is truncated and incomplete at the closing sentence.
  > 💡 Replace placeholders with real accessible articles and complete the email before resubmission.

### ✅ `4b98ccce…` — score 7/10
- Text response describes intent rather than confirming completed data population.
- Excel sheets content and signatures are not verifiably confirmed.
- HIPAA clauses and template elements inclusion in letters is not explicitly evidenced.
  > 💡 Explicitly confirm completed data entry, signatures, and clause inclusion with brief evidence.

### ✅ `60221cd0…` — score 8/10
- Early in-person voting start date appears one day earlier than Virginia’s 45-day rule.
  > 💡 Verify and correct the early voting start date to ensure full factual accuracy.

### ✅ `ef8719da…` — score 7/10
- Text response is meta description, not the actual pitch content.
- Preview does not clearly show hyperlinks to required background sources.
- Tentative draft submission timeline not visible in preview.
  > 💡 Include the full pitch text in the response and clearly show links and timeline.

### ✅ `3baa0009…` — score 8/10
- Article may be close to or slightly under the 300-word minimum.
- Chart title does not explicitly list all requested years including 2025.
- Global growth is subdued but not clearly described as negative as tasked.
  > 💡 Clarify chart labeling and explicitly address the task’s wording on negative growth.

### ✅ `5d0feb24…` — score 7/10
- Specific findings from arXiv:2401.11815 are not clearly cited in visible sections.
- Evidence of linked sources supporting science edits is not clearly shown.
- Producing a new Reporter Draft file was unnecessary and potentially confusing.
  > 💡 Explicitly reference key results from the cited paper with visible hyperlinks in the review.

### ✅ `6974adea…` — score 5/10
- Text response provides a plan, not the requested feature article content.
- Compliance with word count, style guide, and SEO elements is not verifiable.
- Use of interviewee quotations and UK English cannot be confirmed.
  > 💡 Include the full article text or a detailed content summary to verify requirements.

### ✅ `1a78e076…` — score 6/10
- Document length appears far below the required 10–15 pages.
- Prevalence, morbidity/mortality, and financial impact data are insufficiently explicit.
- Use of CDC and AHA data is not clearly demonstrated.
  > 💡 Expand the paper to required length with explicit epidemiologic, outcome, and cost data from CDC and AHA sources.

### ✅ `1b9ec237…` — score 8/10
- Text response describes intent rather than summarizing actual slide content.
- Slide count and inclusion of all required elements cannot be independently verified.
- AHA guideline year and citation specificity not confirmed.
  > 💡 Provide a brief slide-by-slide summary confirming all required elements and slide count.

### ✅ `0112fc9b…` — score 8/10
- Family history is omitted from the SOAP note.
- Plan does not address driving restrictions after head injury.
  > 💡 Include family history and counsel on avoiding driving until concussion symptoms fully resolve.

### ✅ `772e7524…` — score 8/10
- Plan section contains a truncated word indicating minor proofreading error.
- Antibiotic plan lacks duration and specific follow-up timeframe.
- Severity assessment or risk stratification not documented.
  > 💡 Add treatment duration, follow-up plan, and proofread final document before submission.

### ✅ `e6429658…` — score 8/10
- AbbVie assistance application appears limited to one page; full form completion is unclear.
- Provider and patient signatures are not visible in the assistance application preview.
- Appeal letter page length cannot be verified from the provided preview.
  > 💡 Confirm signatures and ensure the full multi-page AbbVie application and appeal letter length meet requirements.

### ❌ `b5d2e6f1…` — score 3/10
- Required "Sales by Brand" pivot table tab is missing.
- Required "Sales by Store" pivot table tab is missing.
- No evidence of grand totals or ST% calculations in analysis tabs.
  > 💡 Add the specified pivot tables with exact headers, ST% formulas, and grand totals to the analysis workbook.

### ✅ `f841ddcf…` — score 7/10
- Summary narrative text is truncated mid-sentence.
- Excel tables are not clearly formatted as filterable Excel tables.
- June ship-window criteria application is not explicitly documented.
  > 💡 Format summaries as Excel tables and fix the truncated summary text.

### ✅ `47ef842d…` — score 8/10
- Text response lacks analytical insights or interpretation of inventory risks.
  > 💡 Add a brief narrative summarizing key out-of-stock risks and WOS implications.

### ✅ `1137e2bb…` — score 8/10
- Drill-down capability to PO level in the summary is not explicitly described.
- Reference data file inclusion was not requested in the final deliverables.
  > 💡 Explicitly document or demonstrate SKU-to-PO drill-down functionality in the summary tab.

### ✅ `c3525d4d…` — score 6/10
- Original total program cost conflicts with Production email estimate.
- Final store list marks all stores as new, not only additions.
- Removed stores are not identified or documented anywhere.
  > 💡 Recalculate costs to match source emails and correctly flag only added and removed stores.

### ✅ `9a0d8d36…` — score 7/10
- PPT content cannot be verified due to lack of previewable slide text.
  > 💡 Include a brief slide-by-slide summary or exported PDF for verification.

### ✅ `664a42e5…` — score 6/10
- Slide content cannot be verified from file preview alone.
- 2025 gift tax exclusion timing not explicitly confirmed.
- Side-by-side ILIT comparison content not verified.
  > 💡 Include slide outlines or screenshots to confirm all required topics are fully addressed.

### ✅ `feb5eefc…` — score 8/10
- Text response is meta and does not summarize findings or recommendation.
- Professional recommendation section appears truncated in file preview.
  > 💡 Include a concise executive summary and explicit recommendation in the text response and PDF.

### ✅ `3600de06…` — score 8/10
- Slide count and detailed content cannot be verified from the text response.
- Explicit FINRA and NAIC source citations are not confirmed within the slides.
- Talking points detail per slide is not summarized in the response.
  > 💡 Include a brief slide-by-slide outline and explicit source citations to strengthen compliance assurance.

### ✅ `c657103b…` — score 6/10
- Starting 2025 balance conflicts with stated $3.5M anticipated year-end value.
- Spreadsheet omits taxes owed on Roth conversion amounts.
- Projected tax savings are not explicitly calculated or summarized.
  > 💡 Align assumptions to $3.5M, add conversion tax calculations, and clearly summarize cumulative tax savings.

### ✅ `ae0c1093…` — score 7/10
- Observation form preview does not show three solid handwritten note lines under headers.
  > 💡 Add three clearly visible solid lines beneath each observation form header and regenerate the PDFs.

### ✅ `f9f82549…` — score 7/10
- Incident details require separate PowerPoint per flowchart header, but only one was provided.
- An extra flowchart PowerPoint was produced but not requested.
- PowerPoint incident content cannot be verified from preview.
  > 💡 Create one incident-details PowerPoint per flowchart header and remove unrequested files.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance start time conflicts with stated 7:30 p.m. courtesy start.
- Arrival at book club relies on signage, which may be mildly interpretive.
  > 💡 Align stated start time precisely with internal instructions and clarify observational versus inferential details.

### ✅ `84322284…` — score 7/10
- Text response summarizes intent rather than presenting findings.
- PDF professional assessment section appears truncated.
- Generated output includes unnecessary confidence score.
  > 💡 Ensure the text response summarizes conclusions and verify the PDF assessment is complete.

### ✅ `a46d5cd2…` — score 8/10
- Report PDF does not clearly display the provided company letterhead branding.
- Photographic evidence appears referenced but limited captions and visual integration.
- Text response summarizes intent rather than findings.
  > 💡 Apply the official letterhead to the report PDF and more clearly embed and caption photographs.

### ✅ `6241e678…` — score 6/10
- Text response describes intent but does not summarize or explain the actual schedule.
- PDF date labels appear garbled, reducing readability and professionalism.
- Color-coding and task durations cannot be clearly verified from provided previews.
  > 💡 Add a brief written summary and verify date formatting and visible color-coding in exports.

### ✅ `e14e32ba…` — score 6/10
- YouTube and interview links are placeholders rather than real media references.
- Pastrami Queen business hours are truncated and incomplete.
- Photo inclusion is unclear within the document content itself.
  > 💡 Replace placeholders with verified links, fix incomplete data, and ensure photos are embedded in the document.

### ✅ `e4f664ea…` — score 6/10
- Response summarizes intent instead of presenting or evidencing the screenplay content.
- Inclusion of CONFIDENCE tag is unprofessional and not requested.
- Formatting and show-not-tell compliance are asserted without verification.
  > 💡 Include a brief excerpt or verification notes demonstrating the screenplay meets formatting and storytelling requirements.

### ✅ `a079d38f…` — score 6/10
- Excel lacks a clear total time estimate summary and setup-time allocation.
- Venue rental costs are omitted without justification from task requirements.
- Assumed shoot days and hours are not explained or tied to video list.
  > 💡 Add a time summary sheet, justify shoot-day assumptions, and clarify inclusion or exclusion of venue costs.

### ❌ `02aa1805…` — score 3/10
- No Illinois EPA data was extracted or reviewed.
- Excel file contains empty sheets with no well records.
- Email provides no recommendations or highlighted viable wells.
  > 💡 Access the EPA factsheets, populate the workbook with real data, and recommend qualifying wells.

### ✅ `fd6129bd…` — score 6/10
- Change Request Form appears to be a blank template, not a completed example.
- An unnecessary reference summary file was included as a produced deliverable.
- SOP compliance with required formatting and version history is not evidenced.
  > 💡 Provide a filled example Change Request Form and remove non-deliverable reference files.

### ✅ `ce864f41…` — score 6/10
- Written findings lack specific departments, individuals, and projects identified as risks.
- Excel tracker content is not evidenced to include required analyses and calculated utilization results.
- Stakeholder Registry presence as a workbook tab is not clearly demonstrated.
  > 💡 Include explicit, data-backed results naming affected departments, individuals, and projects, and verify all required tabs and calculations in the workbook.

### ✅ `58ac1cc5…` — score 8/10
- QA escalation email content not previewed for verification.
- Some change control fields remain blank pending dates and approvals.
  > 💡 Finalize dates, signatures, and confirm QA email content aligns with leadership expectations.

### ✅ `3c19c6d1…` — score 5/10
- Text response describes intent rather than summarising delivered report content.
- Claims nine-slide structure not specified in original task excerpt.
- No explicit confirmation slides 1–4 meet stated content requirements.
  > 💡 Include a brief slide-by-slide summary confirming compliance with each stated requirement.

### ✅ `a99d85fc…` — score 6/10
- Color-coding and light-blue editable cells are not evident in the file.
- Monthly Rent Matrix structure and 120-line monthly detail are not clearly verified.
- Annual and monthly totals reconciliation is not explicitly demonstrated.
  > 💡 Add visible color-coding, confirm editable cells, and clearly reconcile annual and monthly totals for each scenario.

### ✅ `55ddb773…` — score 6/10
- Form contains typographical and formatting errors that reduce professionalism.
- Violation list may be incomplete or inaccurately transcribed from the attached PDF.
- Generated text response describes intent rather than summarizing delivered content.
  > 💡 Proofread the form carefully and verify every violation item matches the source PDF exactly.

### ❌ `1e5a1d7f…` — score 4/10
- The .docx lacks the required table with four specified columns.
- No actual weekly schedule tasks are present in the document.
- PM duties are not mapped into a time-based weekly cadence.
  > 💡 Populate the .docx with a complete table detailing times, activities, trackers, and week-of-month assignments.

### ✅ `0419f1c3…` — score 8/10
- Task volume KPI is not explicitly analyzed or benchmarked in the performance gaps.
- Acknowledgement time performance is not quantified in the gaps section.
  > 💡 Add quantified task volume and acknowledgement-time metrics to strengthen the data-driven analysis.

### ✅ `ed2bc14c…` — score 8/10
- Exit survey categorization into five defined reasons is not explicitly documented.
- Email communications lack draft subject lines or sample copy.
- Data analysis methodology from the Excel file is briefly summarized.
  > 💡 Add a short appendix detailing survey categorization logic and sample renewal email drafts.

### ✅ `46bc7238…` — score 7/10
- Next Steps section is missing from the PDF content.
- One-page flyer template is not clearly included as a dedicated PDF page.
- Stock photos are not clearly present on each PDF page.
  > 💡 Add a Next Steps page, embed the flyer as a full page, and ensure images appear on every page.

### ✅ `2d06bc0a…` — score 7/10
- LOI does not state an explicit expiration date for acceptance.
- Broker involvement and commission terms are not clearly disclosed.
- Closing costs section appears truncated or incomplete.
  > 💡 Add a clear 7–10 day expiration date, broker disclosure, and complete the closing costs section.

### ✅ `fd3ad420…` — score 8/10
- Commission splits lack specific percentage figures for agents and brokers.
  > 💡 Add clear percentage ranges and brief state-specific compliance disclaimers.

### ✅ `0818571f…` — score 6/10
- Properties are illustrative, not active June 2025 listings from Crexi or LoopNet.
- Use of placeholder photos and maps instead of verified property media.
- No evidence of live sourcing or listing links supporting acquisition readiness.
  > 💡 Source and document 5–10 verified active listings with links, real media, and current deal metrics.

### ❌ `6074bba3…` — score 3/10
- PDF contains numerous placeholders and missing populated data.
- Comparable sales and active listings are not filled with real properties.
- Graphs are referenced but not embedded or labeled with actual data.
  > 💡 Populate the template fully with verified comps, completed summaries, and embedded graphs before submission.

### ✅ `5ad0c554…` — score 7/10
- Double-sided brochure layout is not demonstrated in the Word document.
- Visuals are not embedded in the brochure content.
- Specific referenced items from the 132 Things Realtors list are not identified.
  > 💡 Add a clear two-page layout with embedded visuals and cite specific referenced service items.

### ✅ `11593a50…` — score 5/10
- Home selection PDF exceeds required two pages.
- Listings and map are illustrative, not verified MLSLI data or true GPS pins.
- Property pages do not show photos for each home.
  > 💡 Use verified MLSLI listings, include property photos, and condense the booklet to exactly two pages.

### ✅ `94925f49…` — score 6/10
- School statistics are representative estimates without verifiable citations to reputable sources.
- Listed nearby homes appear illustrative and not confirmed active MLS listings.
- Reports lack explicit source citations and neighboring school comparisons.
  > 💡 Add cited, current school data and verified MLS listings with clear source references.

### ✅ `90f37ff3…` — score 6/10
- PDF is only two pages instead of the required four pages.
- Market rent survey lacks dates to confirm comparables within past three years.
- Text response promises a four-page report not delivered.
  > 💡 Expand the PDF to four pages and add dated comparable data to fully meet requirements.

### ✅ `d3d255b2…` — score 8/10
- Text response describes deliverable rather than summarizing conclusions for the seller.

### ✅ `1bff4551…` — score 6/10
- Original song has a non-specific placeholder YouTube link.
- No evidence songs are represented in the Institute's collection.
- Total runtime not specified or justified as 45 minutes.
  > 💡 Add verified collection references, accurate durations, and a valid link for the original song.

### ✅ `650adcb1…` — score 6/10
- Missing required sixth tab documenting intern time-off requests.
- Color coding cannot be verified and key lacks explicit color descriptions.
- December sheet contains extra blank columns reducing clarity and professionalism.
  > 💡 Add a dedicated time-off requests tab and ensure clear, consistent color-coded formatting across all sheets.

### ✅ `01d7e53e…` — score 7/10
- Primary day-to-day contact information is not clearly identified in the agreement.
- Specific RecFit scheduling hours and days are not explicitly detailed.
- Self-insured status and mutual indemnification language are not clearly confirmed.
  > 💡 Add explicit contacts, detailed schedules, and clear self-insurance indemnification language to strengthen completeness.

### ✅ `a73fbc98…` — score 5/10
- Vendor assignment file includes fewer vendors than original list.
- No evidence electricity limitations were validated against layout outlets.
- Text response lacks confirmation that product-type adjacency rules were enforced.
  > 💡 Ensure all original vendors are assigned tables and explicitly document constraint checks.

### ✅ `0ec25916…` — score 8/10
- DOCX file appears incomplete compared to the full PDF content.
- Table formatting and line breaks look misaligned in places.
  > 💡 Ensure the DOCX mirrors the PDF exactly and refine table alignment for clarity.

### ✅ `116e791e…` — score 7/10
- PDF exceeds one-page requirement with three pages.
- Original task explicitly required a one-page PDF only.
  > 💡 Condense content formatting so all required elements fit on a single PDF page.

### ✅ `dd724c67…` — score 5/10
- Facility list is non-exhaustive and omits rehabilitation facilities required by task.
- CMS TFU guide is generic and not clearly sourced to PY 2025 methodology.
- Online research requirement unmet; content notes lack of real-time validation.
  > 💡 Expand all Long Island hospitals and rehab facilities and align TFU guidance explicitly to CMS PY 2025.

### ✅ `7151c60a…` — score 5/10
- Pre-screening checklist lacks required table format with date sent/received and staff initials fields.
- Checklist does not show page numbers or internal-use-only labeling for received information.
- Fax cover sheet does not clearly include the confidentiality statement on the document.
  > 💡 Revise both Word documents to explicitly include all required fields, tables, labels, and statements.

### ❌ `90edba97…` — score 4/10
- Did not complete monthly lab data entry as required.
- Did not document monthly treatment or medication changes.
- Assumed missing data instead of completing task.
  > 💡 Ensure all provided lab data are entered and required clinical actions documented per protocols.

### ✅ `91060ff0…` — score 8/10
- Poster lacks clearly labeled visuals like tables or icons for quick scanning.
- References are listed but not formatted as full citations.
- Visual design elements are minimal in the PDF preview.
  > 💡 Add simple icons or a comparison table and expand references with full citations.

### ✅ `8384083a…` — score 7/10
- PDF exceeds requested 1-2 page length.
- Miebo drop-per-mL assumption lacks justification or reference.
- Ozempic package description oversimplifies multi-dose pen details.
  > 💡 Condense to two pages and clarify assumptions with brief footnotes.

### ✅ `045aba2e…` — score 6/10
- Checklists are overly high-level and miss key California-specific compliance requirements.
- No explicit items for CURES reporting, CSOS handling, or mandated self-assessment completion.
- Content lacks clear traceability to specific Lawbook or Self-Assessment sections.
  > 💡 Expand checklists with explicit California Board requirements and reference relevant Lawbook and self-assessment sections.

### ❌ `f2986c1f…` — score 2/10
- Medications were not identified from the image as required.
- Spreadsheet contains placeholder NA values instead of researched details.
- No Drugs.com identification or MedlinePlus links were provided.
  > 💡 Identify pills from the image using Drugs.com and populate all fields with verified information.

### ❌ `ffed32d8…` — score 3/10
- Comparative table with costs, reimbursements, and per-drug revenues is missing.
- Analysis shows zero revenue difference without supporting calculations or data usage.
- Drug, vial, and fill-frequency cost calculations are not presented.
  > 💡 Rebuild the report with explicit per-drug calculations, tables, and justified revenue differences using provided PDFs.

### ✅ `b3573f20…` — score 7/10
- PDF is four pages instead of the required three pages.
- Generated text response describes intent rather than delivering document content.
  > 💡 Revise the PDF to exactly three pages and ensure the response summarizes delivered content.

### ✅ `a69be28f…` — score 8/10
- Text response lacks specific regional best-fit findings.
- Visuals appear focused on units, with revenue breakdown unclear.
- Text response is descriptive rather than analytical.
  > 💡 Include concise callouts of top fits by region and add explicit revenue charts or tables.

### ✅ `788d2bc6…` — score 7/10
- TikTok Shop and influencer services are not clearly evidenced in the deck preview.
- Visual elements and open-source image usage are not demonstrated in the preview.
- Some promised services like DSP lack clear alignment with the supporting document.
  > 💡 Add explicit TikTok-focused slides with visuals and ensure all services strictly match SERVICESV5 content.

### ✅ `69a8ef86…` — score 7/10
- Extra Return Issues.docx file included beyond requested deliverables.
- Text response summarizes intent but not key process details.
- Internal SOP content not validated in preview for roles and timelines.
  > 💡 Remove extraneous files and briefly summarize key steps and owners in the text response.

### ✅ `ab81b076…` — score 7/10
- Visual examples are referenced but not embedded or described in the PDF.
- PDF lacks explicit instructions for documenting damage photos step-by-step.
  > 💡 Embed or describe visual examples directly in the PDF to strengthen guidance.

### ✅ `19403010…` — score 5/10
- Sections 3–5 tables are missing the full required 9-column structure.
- Function-level sections lack clear subtotals for the three functions.
- Excel recap does not clearly label or calculate % DISCO by function.
  > 💡 Rebuild Sections 3–5 with all nine specified columns, clear headers, and subtotal rows.

### ❌ `105f8ad0…` — score 4/10
- No documented competitor research or sources from Macy’s, Ulta, or Sephora.
- Recommended MSRPs ignore required concentration-based premiums relative to COGS differences.
- Pricing rationale is generic and not SKU-specific or analytically justified.
  > 💡 Add sourced competitor MSRPs, recalculate concentration premiums from COGS, and tailor rationales per SKU.

### ❌ `b57efde3…` — score 4/10
- Did not review or reference the official Aqua Nor 2025 exhibitor list.
- Spreadsheet contains placeholder example companies, not real qualified exhibitors.
- Prospecting research and lead identification were not actually performed.
  > 💡 Populate the spreadsheet with real Aqua Nor 2025 exhibitors verified to offer AUV, ROV, or UC products.

### ❌ `15d37511…` — score 3/10
- Spreadsheet uses zero pricing and costs despite available pricing email data.
- Tiered pricing and discount logic are not applied or calculated.
- Gross margin totals and percentages are missing or blank.
  > 💡 Populate spreadsheet with actual pricing, apply tiered discounts, and calculate all margins and totals.

### ✅ `bb863dd9…` — score 6/10
- Quotation lacks itemized module line table with quantities and prices.
- Article numbers, shelf life, and lead times per module are not clearly listed.
- Total pricing per module and overall total USD are missing.
  > 💡 Add a detailed line-item table per IEHK module including quantities, prices, lead times, shelf life, and totals.

### ✅ `fe0d3941…` — score 7/10
- Survey PDF has three pages instead of two specified pages.
- No indication survey targets or samples over a hundred people.
- Workflow slides content cannot be verified against reference steps.
  > 💡 Align survey format and scope exactly to stated requirements and explicitly document assumptions.

### ✅ `6a900a40…` — score 6/10
- Quantity column header appears replaced with value "400" in revised quotation.
- Header row formatting deviates from original quotation structure.
- Transport option details and red-font general remark cannot be clearly verified.
  > 💡 Correct the header structure and verify all specified remarks, formatting, and transport sections precisely match requirements.

### ✅ `9efbcd35…` — score 6/10
- Document lacks explicit MSCI index performance figures and proper source citations.
- Methodology relies on synthesized trends rather than verifiable Q1 2025 data.
- Some sections appear generic and not clearly quarter-specific.
  > 💡 Include concrete MSCI Q1 2025 returns and clearly cite data and news sources throughout.

### ✅ `1d4672c8…` — score 5/10
- Historical returns were simulated instead of extracted from MSCI as explicitly required.
- Excel analysis relies on proxy data, undermining validity of correlations.
- PDF analysis is overly brief for required structured institutional review.
  > 💡 Rebuild the Excel and PDF using actual MSCI monthly return data for the specified period.

### ✅ `4de6a529…` — score 5/10
- Currency sub-asset classes table is missing line items and views.
- Several sections show formatting breaks and truncated words.
- Change indicators and conviction levels are inconsistent across rows.
  > 💡 Complete the currency sub-asset class views and clean formatting to ensure consistency and completeness.

### ❌ `4c4dc603…` — score 4/10
- Product Summary PDF is two pages, not a single one-page document.
- Salient numbers and key economics lack specific figures like target raise, IRR, token supply.
- Key team section omits named individuals and roles.
  > 💡 Condense to one page and add concrete metrics, token details, and named team profiles.

### ✅ `bb499d9c…` — score 6/10
- Document content cannot be verified against required sections and page limit.
- Flowchart customization by issuer group is claimed but not evidenced.
- Compliance requirements and regulations are not explicitly demonstrated.
  > 💡 Provide excerpts or summaries proving each required section and compliance coverage exists in the document.

### ✅ `5349dd7b…` — score 6/10
- Used proxy industry averages instead of researched historical rate increases.
- Assumed flat-rate offerings for UPS and FedEx without verification.
- Business rate eligibility and sources were not documented.
  > 💡 Redo analysis using verified carrier rate cards and cited historical increase sources.

### ✅ `a4a9195c…` — score 8/10
- IPC-A-610G is referenced but not explicitly mapped to specific requirements.
- Environmental controls and monitoring responsibilities are minimally detailed.
- Document lacks revision history and change control section.
  > 💡 Add explicit IPC-A-610G clause references and include revision control and monitoring details.

### ✅ `552b7dd0…` — score 7/10
- Text response provides no actual findings or metrics from the analysis.
- No explicit confirmation of summary slide takeaways and recommendations content.
- Unable to verify average resolution time split details from provided description.
  > 💡 Include key quantitative results and explicitly summarize recommendations in the text response.

### ❌ `0e386e32…` — score 4/10
- ZIP size suggests placeholder without real source code.
- Frontend and smart contract files not verifiable or previewable.
- No evidence of zkSNARK, Aave, or Connext implementations.
  > 💡 Include a fully populated codebase with actual source files and detailed README documentation.

### ✅ `7de33b48…` — score 5/10
- Zip contents cannot be verified to include the required TSX utility and tests.
- Testing setup lacks TypeScript/Jest configuration and typings, risking nonfunctional tests.
- ARIA22-specific test assertions are not demonstrated or documented.
  > 💡 Include verifiable TSX source and explicit ARIA22 tests in the zip with a runnable TypeScript Jest setup.

### ❌ `4122f866…` — score 4/10
- README lacks required detailed setup, variables, and deployment documentation.
- Terraform and Lambda contents cannot be verified; required resources may be missing.
- No visible evidence of reCAPTCHA validation, SES templates, or API Gateway configuration.
  > 💡 Expand README and expose or document all Terraform and Lambda components explicitly.

### ❌ `2c249e0f…` — score 3/10
- OpenAPI 3.0 YAML specification is completely missing.
- Only data_flow.txt was produced; required API definition file absent.
- Text response describes intent but not actual deliverables.
  > 💡 Provide a complete OpenAPI 3.0 YAML spec and include it alongside data_flow.txt.

## Failure Analysis

Nine tasks failed outright, and 40 required retries before successful completion. Failures were distributed across multiple sectors rather than isolated to a single domain, indicating systemic rather than domain-specific instability. The retry rate suggests sensitivity to prompt complexity or execution constraints in subprocess mode, with some tasks likely failing initial self-validation or encountering generation interruptions.

## Recommendations

Reduce retry frequency by tightening task prompts or adding intermediate validation steps before full output generation, particularly for longer or multi-part tasks. Consider sector-specific prompt adjustments or domain package tuning for Information and Professional Services tasks to improve internal confidence levels. Finally, evaluate latency optimizations, such as context pruning or staged generation, to reduce average execution time without degrading output completeness.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 3 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 7 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 17 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 18 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `17111c03…` (Government): 4 file(s)
- `c44e9b62…` (Government): 7 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 2 file(s)
- `38889c3b…` (Information): 1 file(s)
- `4b894ae3…` (Information): 1 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 1 file(s)
- `24d1e93f…` (Manufacturing): 2 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 2 file(s)
- `bbe0a93b…` (Government): 6 file(s)
- `85d95ce5…` (Government): 5 file(s)
- `76d10872…` (Government): 6 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 6 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 3 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 9 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 3 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 6 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 5 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `61717508…` (Finance and Insurance): 5 file(s)
- `0ed38524…` (Finance and Insurance): 5 file(s)
- `87da214f…` (Finance and Insurance): 3 file(s)
- `d025a41c…` (Finance and Insurance): 4 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 6 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `ec2fccc9…` (Information): 2 file(s)
- `8c8fc328…` (Information): 2 file(s)
- `e222075d…` (Information): 6 file(s)
- `c94452e4…` (Information): 3 file(s)
- `75401f7c…` (Information): 3 file(s)
- `a941b6d8…` (Information): 1 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 2 file(s)
- `c7d83f01…` (Finance and Insurance): 4 file(s)
- `46b34f78…` (Finance and Insurance): 2 file(s)
- `a1963a68…` (Finance and Insurance): 3 file(s)
- `b39a5aa7…` (Finance and Insurance): 2 file(s)
- `b78fd844…` (Finance and Insurance): 3 file(s)
- `4520f882…` (Finance and Insurance): 3 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 2 file(s)
- `e996036e…` (Wholesale Trade): 2 file(s)
- `327fbc21…` (Wholesale Trade): 3 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 3 file(s)
- `1aecc095…` (Health Care and Social Assistance): 4 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 4 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 4 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 11 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 2 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `efca245f…` (Manufacturing): 3 file(s)
- `9e39df84…` (Manufacturing): 2 file(s)
- `68d8d901…` (Manufacturing): 3 file(s)
- `1752cb53…` (Manufacturing): 6 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 3 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 7 file(s)
- `cecac8f9…` (Retail Trade): 6 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `c6269101…` (Manufacturing): 8 file(s)
- `be830ca0…` (Manufacturing): 8 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 2 file(s)
- `46fc494e…` (Manufacturing): 6 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `8077e700…` (Manufacturing): 5 file(s)
- `5a2d70da…` (Manufacturing): 4 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 2 file(s)
- `61b0946a…` (Health Care and Social Assistance): 4 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 4 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 13 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 7 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 2 file(s)
- `5d0feb24…` (Information): 2 file(s)
- `6974adea…` (Information): 8 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `772e7524…` (Health Care and Social Assistance): 1 file(s)
- `e6429658…` (Health Care and Social Assistance): 5 file(s)
- `b5d2e6f1…` (Wholesale Trade): 2 file(s)
- `f841ddcf…` (Wholesale Trade): 2 file(s)
- `47ef842d…` (Wholesale Trade): 3 file(s)
- `1137e2bb…` (Wholesale Trade): 3 file(s)
- `c3525d4d…` (Wholesale Trade): 5 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 3 file(s)
- `57b2cdf2…` (Retail Trade): 4 file(s)
- `84322284…` (Retail Trade): 5 file(s)
- `a46d5cd2…` (Retail Trade): 6 file(s)
- `6241e678…` (Information): 2 file(s)
- `e14e32ba…` (Information): 7 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `e4f664ea…` (Information): 4 file(s)
- `a079d38f…` (Information): 3 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 5 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 8 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 3 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 8 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 3 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 13 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 5 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 6 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 11 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 4 file(s)
- `a73fbc98…` (Government): 4 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 5 file(s)
- `90edba97…` (Health Care and Social Assistance): 7 file(s)
- `91060ff0…` (Retail Trade): 2 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 6 file(s)
- `f2986c1f…` (Retail Trade): 2 file(s)
- `ffed32d8…` (Retail Trade): 4 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 13 file(s)
- `788d2bc6…` (Wholesale Trade): 3 file(s)
- `74ed1dc7…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `19403010…` (Wholesale Trade): 2 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 3 file(s)
- `fe0d3941…` (Wholesale Trade): 5 file(s)
- `6a900a40…` (Wholesale Trade): 6 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 3 file(s)
- `4de6a529…` (Finance and Insurance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 3 file(s)
- `bb499d9c…` (Finance and Insurance): 4 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 4 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 3 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 1 file(s)
