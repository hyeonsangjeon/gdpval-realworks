# Experiment Report: GPT-5.2 Chat Lightweight Elicit + 16k Tokens — subprocess (Full 220 tasks)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp006_GPT52Chat_token16k_lite_elicit` |
| **Condition** | Lightweight Elicit 16k |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-02-28 |
| **Duration** | 121m 4s |
| **Generated At** | 2026-02-28T07:15:07.457197+00:00 |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated the GPT-5.2 Chat model under a Lightweight Elicit configuration with a 16k token context, executed via subprocess across 220 tasks. The run achieved a high task completion rate of 92.3% (203/220), with 17 tasks ending in errors and a relatively high retry count of 47, indicating intermittent instability rather than systemic failure. Average end-to-end latency was 23.0 seconds, consistent with a long-context, multi-task workload.

Across completed tasks, the model reported an average self-assessed QA confidence of 6.17/10, with a wide range (2–9). These scores represent the model’s own evaluation of response completeness and correctness at generation time, not external grading. Overall, the results suggest reliable task completion with moderate confidence levels, and some variability by sector and task type.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 203 (92.3%) |
| Errors | 17 |
| Retried Tasks | 47 |
| Avg QA Score | 6.17/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 23,032ms |
| Max Latency | 355,890ms |
| Total LLM Time | 5067s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 170 (91.9%) |
| Failed → dummy created | 15 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 47 | 30 | 17 |

## Quality Analysis

Self-assessed QA confidence clustered primarily in the mid-range (5–7), suggesting that the model often judged its outputs as adequate but not strongly confident. Higher average confidence was observed in Government (7.2/10) and Retail Trade (6.9/10), which may reflect more structured or policy-oriented tasks with clearer constraints. Lower averages in Information (5.8/10) and Professional, Scientific, and Technical Services (5.7/10) suggest challenges with open-ended or technically nuanced prompts.

Latency varied meaningfully by sector. Information tasks exhibited notably higher average latency (38.1s) while maintaining full task completion, implying heavier reasoning or longer outputs rather than execution failures. Manufacturing and Finance showed slightly reduced success rates (84–88%), potentially indicating sensitivity to domain-specific constraints or formatting requirements. Deliverable file generation quality was generally sufficient to pass completion checks, but the mid-range self-QA scores indicate that outputs may have required cautious self-evaluation due to ambiguity, partial coverage, or verbosity concerns.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 22 | 88.0% | 5.95/10 | 22,217ms |
| Government | 25 | 24 | 96.0% | 7.17/10 | 19,370ms |
| Health Care and Social Assistance | 25 | 24 | 96.0% | 5.96/10 | 22,809ms |
| Information | 25 | 25 | 100.0% | 5.84/10 | 38,059ms |
| Manufacturing | 25 | 21 | 84.0% | 6.19/10 | 22,055ms |
| Professional, Scientific, and Technical  | 25 | 23 | 92.0% | 5.7/10 | 21,303ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 6.25/10 | 20,896ms |
| Retail Trade | 20 | 18 | 90.0% | 6.89/10 | 20,231ms |
| Wholesale Trade | 25 | 22 | 88.0% | 5.73/10 | 19,788ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 6/10 | 19142ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 15162ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 7 | 4/10 | 17863ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 17 | 7/10 | 25700ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 6/10 | 15928ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 24509ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 12818ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 7/10 | 22736ms |
| 9 | `17111c03…` | Government | Administrative Ser | ❌ error | Yes | 0 | - | 22684ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 6 | 6/10 | 18157ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 6/10 | 25207ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 8/10 | 24545ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 1 | 3/10 | 355890ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 3/10 | 24414ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | 3/10 | 19064ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 9/10 | 21960ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 7/10 | 21163ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 23897ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ❌ error | Yes | 0 | - | 21316ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 4/10 | 27262ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 17553ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 7/10 | 15712ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 5 | 6/10 | 24303ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 5 | 4/10 | 33802ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | Yes | 6 | 8/10 | 18698ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 18349ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 15520ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 8/10 | 15190ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 11810ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 7/10 | 16416ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 18988ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 25138ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 6 | 5/10 | 15984ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 2 | 5/10 | 12381ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 6 | 7/10 | 24132ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 2/10 | 20245ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | Yes | 3 | 8/10 | 24265ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 28221ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 5/10 | 25853ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 19705ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 19244ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 14536ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 6/10 | 16553ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 6 | 9/10 | 16355ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 5 | 7/10 | 15879ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 7/10 | 14754ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 5 | 6/10 | 28758ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 5 | 7/10 | 13322ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 16739ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 17564ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 24002ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 7/10 | 36070ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | Yes | 6 | 8/10 | 30001ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | 8/10 | 20818ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 2 | 6/10 | 27655ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 2 | 8/10 | 22859ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 6 | 6/10 | 30983ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | - | 5 | 3/10 | 29064ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | - | 3 | 4/10 | 19392ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | - | 3 | 3/10 | 31069ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 2/10 | 14953ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 7/10 | 19553ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 8/10 | 32589ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 2 | 3/10 | 36660ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 4/10 | 19980ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 29286ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 22532ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 18001ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 8/10 | 26770ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 7/10 | 21356ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 4/10 | 14875ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 16521ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 3/10 | 19348ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 17357ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 3 | 4/10 | 22820ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 3 | 4/10 | 20574ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 6/10 | 25069ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 3/10 | 23903ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 4/10 | 16047ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 11 | 4/10 | 22211ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 22795ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 22371ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 19160ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 21424ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 19930ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 3 | 4/10 | 19344ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 19181ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 27136ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 17050ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 6 | 6/10 | 13066ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 6/10 | 28306ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 6/10 | 18406ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 8/10 | 14863ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 22822ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 6 | 7/10 | 28606ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 20205ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 17822ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 7/10 | 19839ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 18635ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 17580ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 8/10 | 23452ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | 6/10 | 28263ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 6/10 | 22439ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 5 | 6/10 | 24161ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | 7/10 | 28928ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 3/10 | 20978ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | Yes | 1 | 8/10 | 34367ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 8/10 | 22796ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 7/10 | 22574ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 32831ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 7/10 | 31136ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 4/10 | 27460ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 4/10 | 26991ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 20047ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 4 | 4/10 | 22874ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 23392ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 16130ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 3 | 8/10 | 19606ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 21665ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | 7/10 | 26745ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 4/10 | 30111ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 8/10 | 18991ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 25361ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 5/10 | 29288ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 8/10 | 29422ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 22612ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 7/10 | 26681ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 24433ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | Yes | 2 | 4/10 | 23607ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | Yes | 8 | 6/10 | 34129ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 27024ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 7/10 | 21656ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 18233ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 15143ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 4 | 7/10 | 32491ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 7/10 | 16269ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 17190ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 7/10 | 14159ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 6/10 | 20482ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 5 | 4/10 | 20742ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 19906ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 7/10 | 19213ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 25002ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 26220ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 23519ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 7/10 | 23622ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 8/10 | 15354ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 8/10 | 22863ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 5 | 8/10 | 27237ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 5 | 8/10 | 19574ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 2 | 5/10 | 21583ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 22331ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 7/10 | 22039ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | Yes | 4 | 7/10 | 21336ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 3 | 6/10 | 11684ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 2/10 | 14723ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 21589ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 4 | 6/10 | 24425ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 7 | 6/10 | 19076ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 5 | 6/10 | 21793ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 7/10 | 21146ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 4/10 | 24069ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 3/10 | 13044ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 17557ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 17420ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 9 | 7/10 | 22446ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 19545ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | 7/10 | 16981ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 15 | 5/10 | 27045ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 5 | 3/10 | 17601ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 6/10 | 18495ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 3/10 | 25422ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 16 | 6/10 | 37080ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 7/10 | 17279ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 9/10 | 26412ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 7/10 | 14196ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 21004ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 7/10 | 21839ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 4 | 6/10 | 21768ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 4 | 7/10 | 11507ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 6/10 | 22607ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 7/10 | 25342ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 5/10 | 24663ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 4/10 | 20263ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 6 | 3/10 | 14297ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 7/10 | 21883ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 6/10 | 19708ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 6 | 7/10 | 18131ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 3/10 | 11325ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | Yes | 4 | 6/10 | 17842ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 9/10 | 21744ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 6/10 | 18691ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 7/10 | 26886ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 5/10 | 17270ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 8/10 | 23121ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 8/10 | 24206ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 19834ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 6/10 | 18907ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 6/10 | 20024ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 4/10 | 16841ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 3/10 | 20412ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 23161ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 6/10 | 20607ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 5 | 7/10 | 28872ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 6 | 6/10 | 14369ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 7/10 | 27156ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 2 | 4/10 | 14542ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 5/10 | 20182ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 2 | 5/10 | 21151ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 8/10 | 25721ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 17801ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 19961ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 4 | 7/10 | 20836ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 12441ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 4 | 7/10 | 13208ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 17219ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 3 | 3/10 | 20265ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 17533ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 4/10 | 29997ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 21992ms |

## QA Issues

### ✅ `83d10b06…` — score 6/10
- Sample selection criteria coverage is not evidenced or validated against requirements.
- QoQ variance calculation has missing values where Q2 is zero.
- Inclusion of specific metrics and entities requested is not clearly demonstrated.
  > 💡 Validate variance logic, explicitly evidence criteria coverage, and confirm required metrics and entities are sampled.

### ❌ `7d7fc9a7…` — score 4/10
- Response summarizes intent but does not demonstrate actual amortization calculations or reconciliations.
- Excel workbook content is not evidenced or validated against provided GL balances.
- Includes extraneous confidence tag not requested in deliverables.
  > 💡 Provide verifiable schedule details or excerpts proving calculations, structure, and GL reconciliation accuracy.

### ✅ `43dc9778…` — score 7/10
- Text response is descriptive but lacks a concise summary of calculated tax results.
- Draft notes indicate amounts require verification, suggesting placeholder content.
- E-file compliance of embedded schedules is not explicitly confirmed.
  > 💡 Add a brief results summary and explicitly confirm all IRS e-file requirements are fully met.

### ✅ `ee09d943…` — score 6/10
- Workbook content updates and calculations are not evidenced or summarized.
- TOC updates, tab additions, and CFO-reserved tab exclusions are not demonstrated.
- No documented flags of inconsistencies or review notes for the CFO are shown.
  > 💡 Provide a brief summary of tab updates, key balances, and any issues flagged for CFO review.

### ❌ `f84ea6ac…` — score 3/10
- Document lacks the required summary table and study rows.
- No specific articles, authors, dates, or findings are presented.
- Output relies on generic statements instead of actual post-2020 research.
  > 💡 Add a one-page table summarizing five specific, publicly available post-2020 academic studies with findings and implications.

### ✅ `a328feea…` — score 9/10
- Procedure does not specify escalation if supervisor is unreachable by phone.
  > 💡 Add a brief escalation step identifying an alternate contact if the supervisor cannot be reached.

### ✅ `27e8912c…` — score 7/10
- Action Items Word document lacks the required tracking table.
- Action Items document missing employee, department, and resolution tracking fields.
- PDF appendix references images but does not embed the ergonomic images.
  > 💡 Add a structured table with required fields and embed the ergonomic images directly in the PDF appendix.

### ✅ `c44e9b62…` — score 6/10
- Text response is generic and lacks specific FTE counts, positions reduced, and achieved percentage.
- Evidence that the revised org chart visually highlights reduced positions is unclear.
- Updated FTE report does not explicitly demonstrate the minimum 4% reduction achievement.
  > 💡 Include explicit FTE totals, reduction calculations, and clear visual and tabular evidence of the 4% reduction.

### ✅ `99ac6944…` — score 6/10
- Mixer lacks onboard compression required by the task.
- Mixer likely cannot provide two fully independent IEM mixes.
- PDF lacks actual retailer web links for specified products.
  > 💡 Select an analog mixer with onboard compression and dual aux sends, and add explicit retailer URLs.

### ✅ `f9a1c16c…` — score 8/10
- Drummer wedge mix content is not specified to include both vocalists.
- Monitor mix intentions for guitar and bass wedges are not explicitly labeled.
  > 💡 Add brief mix notes beside each wedge indicating intended sources for clarity.

### ❌ `38889c3b…` — score 3/10
- ZIP size far too small for multiple 48kHz 24-bit WAV stems.
- Audio appears to be placeholder synthesis, not a production-ready instrumental.
- No verification that provided drum reference track was actually used or synced.
  > 💡 Provide full-length, high-resolution audio stems genuinely synced to the supplied drum track.

### ❌ `ff85ee58…` — score 3/10
- Final audio mix WAV file was not delivered.
- Output replaces required mix with a procedural report.
- Task explicitly required resynced, processed audio at specified loudness.
  > 💡 Render and deliver the final 24-bit 48 kHz WAV mix meeting all timing and loudness requirements.

### ❌ `4b894ae3…` — score 3/10
- Required edited stereo WAV mix was not actually produced.
- Bass edits were not performed and explicitly omitted.
- Deliverables include documentation instead of requested audio output.
  > 💡 Produce the edited bass track and export the final 48kHz/24-bit stereo mix as specified.

### ✅ `1b1ade2d…` — score 9/10
- Digital system roles and access controls are not explicitly defined.
  > 💡 Add a brief section detailing user roles, access rights, and audit controls for the digital platform.

### ✅ `93b336f3…` — score 7/10
- Ownership split was assumed without being specified in the original task.
- Cost calculations lack a detailed step-by-step breakdown or table.
- Sensitivity considerations around future localisation are minimally addressed.
  > 💡 Add a clear cost calculation table and justify or remove assumed partnership ownership structure.

### ✅ `15ddd28d…` — score 8/10
- Document may be shorter than the requested 2–3 pages.
- Preferred negotiation path section could be more explicitly summarized upfront.
  > 💡 Expand the document with a concise executive summary and fuller negotiation roadmap to ensure 2–3 page depth.

### ❌ `05389f78…` — score 4/10
- Required INR cost comparison and calculations were not performed.
- CPO report is shorter and less detailed than the requested 2–3 pages.
- Quotes file content was qualitative, but task required quantitative analysis.
  > 💡 Obtain or request numeric quotation data and redo a full INR-based comparative analysis.

### ✅ `575f8679…` — score 8/10
- Appendix instrument descriptions appear truncated and may lack full sample items.
- Evaluation lacks a clear timeline for formative and summative activities.
- Community-level outcomes are mentioned but not operationally defined.
  > 💡 Add a concise evaluation timeline and complete appendix instrument summaries with citations.

### ✅ `a74ead3b…` — score 7/10
- Slide content cannot be verified for alignment with exact Session 13 and 14 manual objectives.
- Visual design and use of neutral images are not explicitly described or evidenced.
  > 💡 Include a brief slide outline or screenshots to demonstrate required elements and manual alignment.

### ✅ `bbe0a93b…` — score 6/10
- Resource guide lacks comprehensive categories and detailed contact information.
- Resource guide explicitly states no live web search, contrary to task requirement.
- Tracking table column labels are misformatted and do not match requested titles.
  > 💡 Conduct a verified web search and correct table labels and resource details to fully meet requirements.

### ❌ `85d95ce5…` — score 4/10
- PDF length is 6 pages, not the required 8–15 pages.
- First-page fields were not left blank and include a named social worker.
- School name appears instead of required SCHOOL placeholder.
  > 💡 Revise the report to meet length requirements and correct all placeholder and field instructions.

### ✅ `76d10872…` — score 8/10
- Text response describes process rather than summarizing completed report contents.
  > 💡 Include a brief summary of key case details to confirm report accuracy.

### ✅ `36d567ba…` — score 8/10
- Topic 8 references 2 CFR 200 generally rather than a specific Uniform Guidance section.
  > 💡 Add a specific 2 CFR Part 200 citation for Topic 8 to align with supervisor instructions.

### ✅ `2696757c…` — score 8/10
- An additional DOCX file was produced despite requesting a single PDF deliverable.
- Test questions are high-level and not tightly mapped to specific paragraph obligations.
  > 💡 Tighten test questions to mirror explicit handbook requirements and limit outputs to the requested format.

### ✅ `dfb4e0cd…` — score 9/10
- Text response does not summarize key findings or counts of flagged awards.
  > 💡 Include a brief summary of how many awards were identified as fast or slow spending.

### ✅ `4c18ebae…` — score 7/10
- Text response describes deliverables but does not summarize investigative findings.
- An extra file is produced without explanation or linkage to requirements.
- Confidence tag is informal and not requested in professional deliverable.
  > 💡 Align the text response strictly to task requirements and clearly justify all produced files.

### ✅ `cebf301e…` — score 8/10
- Text response describes intent but does not summarize key design decisions explicitly.
  > 💡 Include a brief executive summary of key architectural choices in the text response.

### ✅ `c2e8f271…` — score 8/10
- No explicit pull request title naming convention is defined.
- Backend testing standards beyond React Testing Library are not specified.
- Database and Drizzle ORM usage standards are minimally covered.
  > 💡 Add brief PR title rules, backend testing guidance, and initial Drizzle/Postgres conventions.

### ✅ `2ea2e5b5…` — score 5/10
- Explicit activity classifications for margin, time sensitivity, and strategic level are not documented.
- Output shifts scope to a presentation without confirming required category mappings.
- Strategic level definitions appear incomplete or unverified in deliverables.
  > 💡 Include a clear table explicitly mapping all 12 activities to margin, time sensitivity, and strategic levels.

### ✅ `c357f0e2…` — score 5/10
- UAT test plan is missing required column headers from the provided template.
- Viewer role test cases include unauthorized actions like submitting and promoting ideas.
- Expected results are vague and not specific or verifiable.
  > 💡 Align headers exactly to the template, correct role permissions, and write clear, testable expected results.

### ✅ `a45bc83b…` — score 7/10
- Cloud Armor is incorrectly described as providing Layer 3 and Layer 4 DDoS protection.
- Architecture does not explicitly describe Google Cloud L3/L4 DDoS via Google Front Ends.
- POC allows ambiguous data stores without clear selection criteria.
  > 💡 Clarify DDoS protection layers, correct Cloud Armor scope, and tighten technology choices in the POC.

### ❌ `a10ec48c…` — score 2/10
- Required tables with columns and restaurant rows are missing.
- No restaurant details, links, hours, categories, or directions provided.
- Sourcing, exclusions, and Google Maps information are not demonstrated.
  > 💡 Populate categorized tables with verified downtown restaurants, complete columns, links, hours, descriptions, and directions.

### ✅ `fccaa4a1…` — score 8/10
- PDF is three pages instead of the intended two-page itinerary length.
- Tour operator description lacks explicit sourcing or citation from TakeWalks.com.
- Icons and styled visual elements are not clearly evident in the PDF preview.
  > 💡 Condense content to two pages and add sourced citations and visible icons for clarity.

### ✅ `f5d428fd…` — score 6/10
- Images are placeholders, not actual royalty-free photos included.
- Research sources are not explicitly cited within the document.
- Some activities like fishing lack specific, well-reviewed venue recommendations.
  > 💡 Embed actual royalty-free images and add brief source citations and specific activity venues.

### ✅ `2fa8e956…` — score 5/10
- Document lacks cited sources for wineries and distance data.
- Required footer and specified font formatting are not evident.
- Grape varieties are not shown in purple as specified.
  > 💡 Add sources, apply exact font and color formatting, and include the required footer.

### ✅ `0e4fe8cd…` — score 6/10
- June 1 lacks full logistics beyond departure and omits airport arrival handling.
- Return day flight details are incomplete and truncated.
- Car services, aviation specifics, and high-value contacts lack named providers and links.
  > 💡 Expand each day with complete door-to-door logistics, named vendors, flight specifics, and verified links.

### ✅ `aa071045…` — score 6/10
- Damage Revenue Report lacks an explicit operational conclusions section.
- Summary sheet only shows total revenue without context or annotations.
  > 💡 Add a clear conclusions sheet summarizing trends, risks, and maintenance recommendations.

### ✅ `61f546a8…` — score 7/10
- Refrigerator installation day was not added despite guideline requiring an extra day.
- Appliance installation dates are not explicitly scheduled, only delivery dates shown.
  > 💡 Add explicit appliance installation workdays and adjust timelines and make-ready dates accordingly.

### ✅ `f3351922…` — score 7/10
- Email contains unresolved placeholders for client and sender names.
- Signature line is incomplete and appears truncated.
- Benefits section is brief and could better detail military-specific considerations.
  > 💡 Complete placeholders, fix the signature, and expand the transition benefits section slightly.

### ✅ `61717508…` — score 6/10
- Training deck is only three pages, not approximately ten as requested.
- Role-play PDF content is not previewed to confirm three complete fictional accounts.
- An extra internal policy PDF was produced but not requested.
  > 💡 Expand the training deck to full length and verify role-play examples meet all stated requirements.

### ✅ `0ed38524…` — score 7/10
- Inconsistent category labeling creates duplicate entries like "General" and "General :".
- Summary provides counts only, lacking brief thematic descriptions of constituent concerns.
- Talking points are largely boilerplate and not tailored to district-specific issues.
  > 💡 Standardize categories and add brief thematic summaries with more specific, actionable talking points.

### ✅ `d025a41c…` — score 6/10
- Produced extra Word files not requested in the original task.
- Formatting requirements like bold titles and 1.5 spacing are not verifiable.
- One suggested alternative statement appears truncated and incomplete.
  > 💡 Deliver only the single requested document and verify formatting and content completeness.

### ✅ `401a07f1…` — score 6/10
- No explicit hyperlinks to specific reference articles are visible in the document.
- Editorial length and ending appear truncated, risking non-compliance with 500-word requirement.
- Adherence to the Guardian style guide is not clearly demonstrated.
  > 💡 Add clear hyperlinks to cited articles, verify full 500-word length, and polish to Guardian style standards.

### ✅ `afe56d05…` — score 7/10
- Document appears significantly shorter than the required 2,200–2,300 words.
- No explicit confirmation of word count is provided in the deliverable.
- Some external sources may lack clearly visible inline hyperlinks.
  > 💡 Expand the document to meet the word count and verify all cited resources include clear hyperlinks.

### ✅ `9a8c8e28…` — score 8/10
- Framework guide is very high-level and brief for complex accessibility obligations.
- Quiz depth appears limited for assessing real-world editorial decision-making.
  > 💡 Expand practical examples and scenarios, especially for common newsroom workflows and edge cases.

### ✅ `3a4c347c…` — score 8/10
- Text response is meta-level and does not summarise proposal content.
- Reference file name differs slightly from specified title.
- Six-page length compliance is not explicitly confirmed.
  > 💡 Include a brief executive summary in the text response and confirm page count compliance.

### ✅ `ec2fccc9…` — score 6/10
- Secondary keywords list is not clearly labeled at the end.
- Pull quote and caption are not clearly identified.
- Artist highlights and links appear incomplete or truncated.
  > 💡 Add a clear keyword list, labeled pull quote, and complete artist sections with links.

### ✅ `e222075d…` — score 6/10
- Final 30-second H.264 MP4 export was not delivered as required.
- Stock footage and music links are generic sites, not direct preview links.
- Music edit to exactly 30 seconds is not demonstrated.
  > 💡 Provide a 30s MP4 export with direct clip preview links and a confirmed 30-second music edit.

### ❌ `c94452e4…` — score 3/10
- No 15-second H.264 MP4 commercial was delivered.
- Stock footage and music were not sourced or edited.
- Provided supers PSD was not applied to footage.
  > 💡 Deliver the actual 15-second edited MP4 using stock footage, music, and provided supers.

### ❌ `75401f7c…` — score 4/10
- Final MP4 showreel was not delivered as required.
- EDL contains placeholder clips instead of concrete source selections.
- Task explicitly required a finished edited video, not only planning documents.
  > 💡 Produce and export the complete 01:20 MP4 showreel using the provided plan and assets.

### ❌ `a941b6d8…` — score 3/10
- No composited video file was produced as required by the task.
- Actual stabilization, masking, tracking, and compositing were not executed.
- Delivered planning documents instead of the requested finished VFX shot.
  > 💡 Produce the final MP4 with completed teleportation VFX matching all specified technical requirements.

### ❌ `8079e27d…` — score 2/10
- Excel contains zero populated rows; required S&P 500 company and subsector data missing.
- Deliverable is a template, not populated with publicly available market data as required.
- Cannot analyze P/E versus historical averages without actual metrics.
  > 💡 Populate the workbook with current public data for all S&P 500 companies and subsectors.

### ✅ `e21cd746…` — score 7/10
- Revenue multiples are not explicitly provided for public comparables.
- Several private tuck-in targets lack valuation, funding, investors, and customers.
- Valuations and multiples lack clear source attribution or date specificity.
  > 💡 Add explicit revenue multiples and complete data fields for all listed private targets.

### ✅ `9e8607e7…` — score 8/10
- Slide count is 25, slightly below the ~30-slide guidance.
  > 💡 Consider adding a few slides on country-specific fintech hubs and regulatory considerations.

### ❌ `c7d83f01…` — score 3/10
- Python notebook implementing pricing methodologies is missing.
- Only one visualization provided; required multiple comparative and benchmark plots.
- No actual code or methodology comparison is delivered.
  > 💡 Provide the full Python notebook with implementations, analyses, and supporting visualizations.

### ❌ `46b34f78…` — score 4/10
- No specific oil or gas bond issuers are identified or analyzed.
- Lacks concrete data, forecasts, and actionable trade structures.
- Appendix admits reference material not parsed or used.
  > 💡 Add data-driven market analysis, name specific issuers, and propose executable trades using the reference material.

### ✅ `a1963a68…` — score 6/10
- Lacks explicit future-proofing and sustainability initiatives slide.
- Minimal data, metrics, and cited market research despite requirement.
- Regulatory strategy and Korean UX actions are insufficiently detailed.
  > 💡 Add data-backed slides on regulation, UX localization, and long-term innovation with clear sources.

### ✅ `b78fd844…` — score 8/10
- Text response is meta-level and lacks a concise executive summary.
- Confidence tag is unnecessary for a professional deliverable.
  > 💡 Include a brief executive summary in the text response highlighting key findings and recommendation.

### ✅ `4520f882…` — score 7/10
- Excel model contents are not described in enough detail to verify CBA rule coverage.
- No explicit confirmation that all CBA premiums and doubling rules are implemented.
- Extraneous CONFIDENCE tag is unnecessary for a professional deliverable.
  > 💡 Provide a brief sheet-by-sheet summary and confirm each CBA wage and premium rule is covered.

### ❌ `ec591973…` — score 4/10
- Text response describes intent rather than providing actual strategy content.
- Slide content cannot be verified against requirements without a preview.
- Extraneous confidence tag included in professional deliverable.
  > 💡 Include a detailed slide content summary and remove non-professional tags to enable verification.

### ✅ `62f04c2f…` — score 7/10
- Excel form lacks signature and date sections for sales rep, GM, and Sales Manager.
- Excel form does not clearly include the required freight prepayment and restocking fee notice.
- Exchange Authorization form layout appears incomplete at the bottom section.
  > 💡 Add required fee notice and all signature and date fields to the bottom of the Excel form.

### ❌ `3f821c2d…` — score 3/10
- EOM Inventory and Turn rows are blank with no working formulas.
- Gross receipts total $240k, far below the $675k omni budget.
- Omni, channel turns and January EOM constraints are not demonstrated.
  > 💡 Complete formulas, rebalance receipts to the full budget, and prove omni turn and EOM targets.

### ❌ `327fbc21…` — score 4/10
- Summary LY and planned sales totals are clearly incorrect versus by-door store plans.
- STD trend is not shown or applied anywhere in the by-door planning worksheet.
- Required 1–2 sentence May sales plan summary text is missing from the deliverable.
  > 💡 Recalculate summary rollups correctly, explicitly apply STD trends in planning, and add the required written summary.

### ❌ `6dcae3f5…` — score 4/10
- Did not identify PGY when each PGY-5 met ACGME key indicator requirements.
- Key indicators labeled as 'Unnamed', indicating incorrect or missing source mapping.
- Deliverables include an unrequested Word document and unclear Excel benchmark structure.
  > 💡 Rebuild the Excel using correct indicator names, ACGME requirements, and explicitly record PGY attainment per PGY-5 resident.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a Visio-style visual workflow and appears text-only.
- Roadmap does not clearly start from MA placing the call to the patient.
- An extra unrequested file was produced, causing scope creep.
  > 💡 Add a true visual flow diagram to the Roadmap and remove unrequested files.

### ❌ `0353ee0c…` — score 3/10
- Did not compile or present presumptive conditions, locations, and dates as required.
- Document contains placeholder sections instead of consolidated information.
- Claims system limitations contrary to task requirement to review provided links.
  > 💡 Review all Document B links and fully populate exhaustive tables of exposures, conditions, locations, and dates.

### ❌ `40a8c4b1…` — score 4/10
- No evidence column C was fully populated per priorities and conditions.
- Alternate lab dates and notes are not demonstrated or verified.
- Optional unused topics highlighting is not confirmed.
  > 💡 Provide a completed schedule summary verifying key constraints and screenshots or details from the Excel file.

### ❌ `4d1a8410…` — score 4/10
- Interview schedule lacks required detailed table with room-by-room timing and applicant assignments.
- Mandatory breaks and constraints for Dr. Jones and Dr. Garrett are not scheduled.
- Personal itineraries omit specific interview times and room assignments.
  > 💡 Rebuild the schedule as a detailed table fully implementing all timing, breaks, constraints, and assignments.

### ✅ `8c823e32…` — score 8/10
- Department name or jurisdiction is not clearly identified as LPD.
- Rapid citywide staging and airborne deployment lacks detailed implementation guidance.
- Vehicle pursuit support section appears briefly defined compared to other sections.
  > 💡 Add jurisdiction-specific identifiers and expand operational detail for rapid deployment and pursuit support.

### ✅ `eb54f575…` — score 8/10
- Rifle quantity recommendation alternates between 430 and 431 without a single definitive number.
- Terminal ballistics section references FBI protocols but lacks specific cited data examples.
  > 💡 Clarify a single final rifle quantity and add one or two concrete FBI test data references.

### ✅ `11e1b169…` — score 7/10
- PDF exceeds required two-page length, totaling three pages.
  > 💡 Condense formatting and content to ensure the PDF is exactly two pages.

### ✅ `a95a5829…` — score 8/10
- Final approval authority is inconsistently stated between sections.
- Division of Parole Chief approval is conditional despite being required.
- Excel logging instructions are not clearly verified in the preview.
  > 💡 Clarify approval authority consistency and explicitly document Excel logging procedures.

### ✅ `22c0809b…` — score 9/10
- Background check authorization lacks explicit consent signature line in that section.
  > 💡 Add a dedicated consent signature and date under the background check authorization section.

### ❌ `bf68f2ad…` — score 4/10
- Weekly demand is hardcoded as 40 hours, ignoring provided MIG demand data.
- Cumulative backlog starts incorrect and conflicts with stated 438.81 past-due hours.
- Catch-up logic builds excessive negative buffer without analyzing demand consequences.
  > 💡 Recalculate using actual weekly demand data and align backlog math to the stated past-due hours.

### ✅ `efca245f…` — score 6/10
- Excel sheets contain blank columns and lack clear cumulative PO tally.
- Stat holidays and non-working days are not explicitly modeled.
- Expanded capacity scenario uses unsupported 170 sets/day assumption.
  > 💡 Revise spreadsheets to correct capacities, include holidays, and add explicit cumulative PO tracking.

### ✅ `68d8d901…` — score 6/10
- Excel content preview missing, so tab accuracy and completeness cannot be verified.
- No demonstrated calculation proving 250,000 lbs achieved with full batches in four weeks.
- Unnecessary duplicate reference files were produced instead of only the requested Excel deliverable.
  > 💡 Include a visible Excel preview and explicit throughput calculations confirming the production target is met.

### ✅ `1752cb53…` — score 6/10
- Completed file sheet name differs from required 'One Week Test Plan'.
- Completed plan appears to omit required columns from original template.
- Compliance with changeover and labor rules is not demonstrated.
  > 💡 Ensure the completed file preserves the original sheet name, full structure, and explicitly meets all test rules.

### ✅ `bd72994f…` — score 6/10
- No brand or official 2025 resort collection is identified.
- Looks are not explicitly sourced from a single confirmed collection.
- PDF contains text-only looks without visual styling imagery.
  > 💡 Specify the luxury brand, cite the official 2025 resort collection, and include product images per look.

### ✅ `211d0093…` — score 6/10
- Tasks are duplicated and misplaced across opening, mid-day, and closing sections.
- Mid-day section incorrectly includes end-of-day filing and manager sign-off task.
- Claim that tasks match the provided list exactly is inaccurate.
  > 💡 Align tasks precisely to the provided source list and place each task in the correct shift section.

### ✅ `d4525420…` — score 8/10
- Text response describes deliverable instead of directly providing the required paragraph.
  > 💡 Include the 5–7 sentence selection paragraph directly in the text response as well.

### ✅ `cecac8f9…` — score 7/10
- Targets use USD instead of GBP for a UK-based store.
- Team Launch Deck is very high-level for all-day instructional use.
- Text response does not summarise plan content or confirm PDF submission explicitly.
  > 💡 Localise targets to GBP and expand the deck with clearer execution guidance by time and role.

### ✅ `8f9e8bcd…` — score 8/10
- Text response summarizes intent rather than briefly confirming completed content.
  > 💡 Include a short confirmation highlighting key sections completed in the document.

### ✅ `0fad6023…` — score 6/10
- No visual case layout beyond a simple table representation.
- Missing total available space and remaining space calculation for 24-foot FSC.
- Printer-friendly formatting like defined print area is not evident.
  > 💡 Add a visual horizontal case layout with total, used, and remaining inches plus defined print settings.

### ✅ `02314fc6…` — score 7/10
- Scoring section lacks corrective action details, owners, and completion dates.
- No explicit instruction or form section for plans when more than 10 items missed.
- Review and sign-off fields for District Manager and Loss Prevention are missing.
  > 💡 Add a corrective action plan table and DM/LP review sections to fully meet requirements.

### ✅ `6436ff9e…` — score 8/10
- No optional contact email field for follow-up or marketing consent.
- Testimonial consent lacks clarity on where and how testimonials may be used.
- Accessibility or accommodation needs are not addressed.
  > 💡 Add optional contact details, clearer testimonial usage consent, and an accessibility accommodations question.

### ✅ `8a7b6fca…` — score 8/10
- Minor labeling typos and truncated text reduce visual clarity.
- Decision point wording is partially unclear in the PDF.
- Manual failure-handling steps could be more explicitly sequenced.
  > 💡 Clean up labels and clarify decision logic text to improve executive readability.

### ✅ `40a99a31…` — score 6/10
- Minimum six cameras not explicitly specified or itemized in the hardware table.
- LIDAR selection lacks detailed justification for six static zones and one robot-mounted zone.
- PDF report is overly brief and misses safety standards and integration detail.
  > 💡 Expand documentation with detailed justifications, explicit quantities, and fuller safety and integration analysis.

### ✅ `b9665ca1…` — score 6/10
- Explicit ES0.K1/K2 and similar E-stop wire labels are not shown.
- Unrequested stop/start button circuitry is included, adding scope beyond requirements.
- Load connections to relay pin 14 and ES.13 grounding are not clearly labeled.
  > 💡 Revise the schematic to strictly match specified wiring labels and remove non-required circuits.

### ✅ `c6269101…` — score 6/10
- Text response is a delivery promise without any analytical findings.
- No explicit capability, stability, or variability conclusions are presented.
- Cannot verify PPT includes required summaries, risks, and recommendations.
  > 💡 Include a concise written summary of key findings and conclusions alongside the deliverables.

### ✅ `be830ca0…` — score 7/10
- Analysis includes Saturdays despite scope stating regular business days only.
- Use of Minitab is claimed but software source is not explicitly evidenced.
- Statistical conclusions are summarized without explicit p-values or decision statements.
  > 💡 Restrict analysis to business days and explicitly document statistical results and tools used.

### ❌ `cd9efc18…` — score 3/10
- PDF is only one page, not the required 8–11 pages.
- Execution section appears incomplete, missing witnesses and notary details.
- Testator signature name is misspelled as Parson instead of Parsons.
  > 💡 Redraft a full-length Texas-compliant will with complete execution pages and correct formatting.

### ✅ `a97369c7…` — score 8/10
- DGCL Sections 109 and 122 are not clearly discussed in the visible memo sections.
  > 💡 Explicitly analyze DGCL Sections 109 and 122 and tie them to the governance provisions.

### ✅ `3f625cb2…` — score 8/10
- Text response only described deliverable instead of summarizing findings.
  > 💡 Include a brief executive summary highlighting conclusions and recommended next steps.

### ✅ `aad21e4c…` — score 7/10
- Anti-dilution minimum ownership and top-up mechanics are not clearly specified.
- Minority consent rights over extraordinary actions are not clearly enumerated.
- ROFR and transfer restriction acknowledgments are not expressly addressed.
  > 💡 Explicitly add detailed anti-dilution, consent rights, and ROFR provisions to fully meet requirements.

### ✅ `8314d1b1…` — score 8/10
- Text response is a meta description rather than a substantive summary of conclusions.
  > 💡 Include a brief substantive summary in the text response aligning with the memo’s key conclusions.

### ✅ `5e2b6aab…` — score 7/10
- No explicit design for power switch operable with gloves is described.
- Thermal management to prevent overheating is only implied, not detailed.
- An extra DOCX file was produced that was not requested.
  > 💡 Add a clear glove-friendly switch concept and basic thermal mitigation features in the design description.

### ❌ `46fc494e…` — score 4/10
- No actual transient temperature calculations were performed; results remain at ambient.
- Back-face temperatures are physically unrealistic under stated heating conditions.
- Required plots and contour figures are referenced but not demonstrably included.
  > 💡 Perform and document the full transient conduction calculation and regenerate plots and tables with credible results.

### ❌ `3940b7e7…` — score 4/10
- Numerical results are qualitative; required metrics and tables lack actual values.
- Boundary conditions, material properties, and convergence goals are insufficiently specified.
- Discussion and results appear truncated and contain minor typographical errors.
  > 💡 Populate tables with concrete CFD values, fully specify setup parameters, and correct formatting issues.

### ❌ `5a2d70da…` — score 4/10
- Master Tool List lacks required subtotal, sales tax, and grand total calculations.
- Manufacturing steps are overly minimal and lack detailed, complete operations.
- Budget compliance and tool quantity rationale for breakage are not demonstrated.
  > 💡 Add full cost rollups with Suffolk County tax and expand detailed machining operations and tooling justification.

### ✅ `74d6e8b0…` — score 8/10
- Literature citations are not visible in the provided content preview.
- Specific dosing tables and regimens are not fully shown in preview.
- No explicit regulatory or legal disclaimer for telehealth practice noted.
  > 💡 Add a clearly labeled references section and concise dosing tables with a telehealth disclaimer.

### ✅ `81db15ff…` — score 9/10
- Text response describes deliverable but does not summarize findings directly in narrative.
  > 💡 Add a brief written summary of key findings in the text response.

### ✅ `61b0946a…` — score 8/10
- Annual anatomy lab fee mentioned in task is not quantified in budget analysis.
- Proposal does not explicitly address utilizing the additional 8–10 unused freeze/thaw cycles.
- Cost savings graph is referenced but not interpreted with specific numeric comparisons.
  > 💡 Add explicit anatomy lab fees, unused cycle utilization, and quantified savings interpretation to strengthen alignment.

### ✅ `61e7b9c6…` — score 6/10
- Common off-label menopause treatments like SSRIs, gabapentin, and clonidine are missing.
- Price estimates are approximations without documented GoodRx or pharmacy sourcing.
- Formulary appears incomplete with limited number of therapies for a comprehensive service.
  > 💡 Expand the formulary to include common off-label agents and verify prices using documented online pharmacy sources.

### ✅ `c9bf9801…` — score 7/10
- Detailed monthly timeline with milestones and deliverables is insufficiently defined.
- NCIPC mentoring program acknowledgment is missing or unclear in credits.
- CDC branding elements and logo integration are not evident.
  > 💡 Add a clear month-by-month timeline, explicit NCIPC credit, and CDC branding elements.

### ❌ `f1be6436…` — score 4/10
- All screenshots are placeholders, not real sources captured at completion time.
- Flight details lack airline, cities, dates, and times required by task.
- Department versus discretionary fund cost breakdown is missing.
  > 💡 Recreate the document using live data, real screenshots, and full itemized financial calculations.

### ✅ `41f6ef59…` — score 8/10
- Spreadsheet formatting features like checkboxes or dropdowns are not clearly evident.
- Email subject does not explicitly state this is the third declined payment.
  > 💡 Add visible checkboxes or data validation dropdowns and clarify the email subject line.

### ✅ `6d2c8e55…` — score 5/10
- Article PDFs contain citation lists, not individual article PDFs or link-PDFs.
- No evidence the room bookings were added to Room Availability.xlsx.
- Article accessibility is asserted but not verified with saved links or full texts.
  > 💡 Provide individual PDFs or link-PDFs per article and clearly update room availability with bookings.

### ✅ `4b98ccce…` — score 8/10
- Excel column names and formats were not explicitly confirmed against required exact names.
- Sign-off placement beneath each worksheet table is not evidenced.
- Letter signatures and dates are not explicitly verified.
  > 💡 Include a brief checklist confirming column names, signatures, and letter elements for verification.

### ✅ `60221cd0…` — score 8/10
- An extra DOCX file was produced beyond the requested PDF deliverable.
- The text response includes unnecessary self-referential and confidence metadata.
  > 💡 Provide only the requested PDF and remove meta commentary from the response.

### ✅ `ef8719da…` — score 7/10
- Hyperlinks to background sources are not clearly listed or embedded.
- Tentative draft submission timeline is incomplete or unclear.
- Text response summarizes intent instead of presenting the pitch directly.
  > 💡 Add a clear timeline section and explicit hyperlinks to sources within the document.

### ✅ `3baa0009…` — score 8/10
- Text response is procedural rather than summarizing key findings.
- Article lacks specific numeric growth forecasts for clarity.
- Chart preview does not confirm labeled years and values.
  > 💡 Add explicit growth rate figures and ensure the chart clearly labels 2024, 2025, and 2027.

### ❌ `5d0feb24…` — score 4/10
- Response promises an editor review but provides no actual feedback or edits in text.
- Editor review content is not summarized or evidenced in the response.
- Scientific timeline inconsistencies are not flagged or corrected.
  > 💡 Include concrete editorial comments, proposed edits, and cited corrections directly in the response.

### ✅ `6974adea…` — score 6/10
- Text response describes intent rather than summarising delivered article content.
- No confirmation of word count, SEO headline, or standfirst in response.
- Cannot verify Guardian style or UK English without article preview.
  > 💡 Include a brief summary confirming word count, headline, standfirst, and style compliance.

### ✅ `1a78e076…` — score 6/10
- Document does not meet the required 10–15 page length.
- Prevalence, morbidity, mortality, and financial impact data lack sufficient depth and specificity.
- Compliance with references requirement and limit of 30 sources is unclear.
  > 💡 Expand the manuscript with detailed data analysis and confirm all required sections and reference limits.

### ✅ `1b9ec237…` — score 7/10
- Slide content cannot be verified because the PowerPoint preview is unavailable.
- Presence of pre-test question, case study, and AHA stages cannot be confirmed.
- Slide count, speaker notes, and reference formatting are not verifiable.
  > 💡 Provide a slide outline or screenshots to verify required content and compliance.

### ✅ `0112fc9b…` — score 8/10
- Visual acuity assessment not documented despite reported blurry vision.
- No explicit counseling documented regarding driving after head injury.
- Neuro exam omits documentation of cranial nerves II, V, and VII.
  > 💡 Add visual acuity testing, driving safety counseling, and complete cranial nerve documentation.

### ✅ `772e7524…` — score 6/10
- Text response did not include the SOAP note content.
- SOAP note provided only as a file without inline summary.
- Plan section appears truncated in preview.
  > 💡 Include a complete SOAP note directly in the text response in addition to the file.

### ✅ `e6429658…` — score 7/10
- Appeal letter page length cannot be verified from provided preview.
- AbbVie application lacks provider signature despite digital completion requirement.
  > 💡 Include verification of appeal letter length and digitally sign the assistance application.

### ✅ `b5d2e6f1…` — score 7/10
- Sales by Brand column order does not match the requested specification.
- Grand total rows are not clearly identifiable in the previewed pivot outputs.
- Sell-through percentages appear appended rather than grouped by WTD, MTD, YTD.
  > 💡 Reorder columns and clearly add labeled grand total rows to both pivot tables.

### ✅ `47ef842d…` — score 7/10
- Calculation methodology is not shown or documented despite the requirement to show work.
- Text claims chart is embedded in Excel, but chart is provided as a separate PNG.
- Criteria for defining out-of-stock stores is not explicitly stated or justified.
  > 💡 Add a calculation worksheet explaining formulas and clearly document out-of-stock logic and chart placement.

### ✅ `1137e2bb…` — score 6/10
- Summary or pivot table tab is missing from the Excel deliverable.
- SKU-level aggregation with PO-level drill-down is not demonstrated.
- Excel output does not clearly show case pack error counts by line.
  > 💡 Add a SKU-level summary pivot tab with drill-down enabled and clearly labeled error metrics.

### ❌ `c3525d4d…` — score 4/10
- Final store count appears incorrect versus provided final matrix.
- Added and removed stores are not explicitly identified or listed.
- Final store list incorrectly labels all locations as new.
  > 💡 Recalculate store counts from the final matrix and properly compare lists to flag added and removed stores.

### ✅ `9a0d8d36…` — score 6/10
- Slide content cannot be verified because no preview or outline is provided.
- No explicit confirmation of step-by-step hypothetical calculations and net proceeds comparison.
- Vesting timing and pre-vesting exercise limitations are not clearly evidenced.
  > 💡 Include a slide-by-slide outline or screenshots to verify calculations, taxes, and vesting considerations.

### ✅ `664a42e5…` — score 7/10
- PPT content cannot be verified from preview to confirm all required topics are covered.
- 2025 annual gift tax exclusion amount is not explicitly stated.
- Text response describes intent rather than summarizing actual slide content.
  > 💡 Include a brief slide-by-slide summary confirming each required ILIT topic and figures.

### ✅ `feb5eefc…` — score 6/10
- Clear professional recommendation is not evident in the provided PDF preview.
- CRAT scenario section appears truncated or incomplete.
- An extra DOCX file was produced despite only a PDF being requested.
  > 💡 Add a clear concluding recommendation and ensure the PDF fully presents all required sections.

### ✅ `3600de06…` — score 6/10
- Cannot verify the presentation contains exactly 10 slides.
- FINRA and NAIC sourcing and citations are not verifiable from the file preview.
- Specific comparisons, penalties, and regulatory issues cannot be confirmed.
  > 💡 Provide slide thumbnails or a detailed slide-by-slide outline with citations for verification.

### ✅ `c657103b…` — score 6/10
- Starting 2025 balance differs from stated $3.5M anticipated value.
- RMD calculations appear inconsistent with IRS 2025 Uniform Lifetime Table factors.
- Spreadsheet lacks explicit cumulative tax savings comparison between scenarios.
  > 💡 Align assumptions precisely to client data and add a clear cumulative tax savings summary.

### ✅ `ae0c1093…` — score 7/10
- Observation form lacks the required three solid handwritten lines under each header.
- Observation form PDF does not visually show any solid lines for note-taking.
  > 💡 Add three clearly visible solid horizontal lines beneath every header in the observation form PDF.

### ✅ `f9f82549…` — score 8/10
- PDF presents a linear list rather than a visual flowchart with decision points.
  > 💡 Convert the PDF steps into a true diagram with standard flowchart symbols and connectors.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance continued past authorized end time without explicit justification.
- Arrival time precedes stated courtesy start time by five minutes.
- Initial narrative mentions missed book club meetings without reconciling observed attendance.
  > 💡 Clarify authorization for extended surveillance and reconcile minor timeline and narrative inconsistencies.

### ✅ `84322284…` — score 8/10
- Text response is meta-level and lacks a concise summary of investigative findings.
- Extraneous CONFIDENCE tag is unnecessary in a professional deliverable.
- PDF content quality cannot be verified from the text response alone.
  > 💡 Include a brief executive summary of key findings and recommendations in the text response.

### ✅ `a46d5cd2…` — score 8/10
- Text response summarizes intent instead of report findings.
  > 💡 Include a brief executive summary of findings directly in the text response.

### ✅ `6241e678…` — score 5/10
- Text response does not include or summarize the actual production schedule details.
- Schedule includes many unrequested tasks beyond the specified requirements.
- Color-coding and revision rounds are not clearly verifiable from provided content.
  > 💡 Explicitly align the schedule to listed required tasks and clearly document color-coding and revision rounds.

### ✅ `e14e32ba…` — score 6/10
- Business hours and physical addresses are not explicitly listed for each restaurant.
- Image entries link to websites, not direct photos of establishments.
- Several video links appear generic or placeholder rather than verified features.
  > 💡 Add verified addresses, hours, direct photo links, and confirmed media features for each deli.

### ✅ `b1a79ce1…` — score 7/10
- Moodboard visual content cannot be verified from the provided preview.
- Color palette inclusion is not explicitly confirmed in the image.
- Reference image sources or licensing are not mentioned.
  > 💡 Add labeled color swatches and brief captions directly on the moodboard.

### ✅ `e4f664ea…` — score 7/10
- Text response describes deliverables instead of summarizing screenplay content.
- Includes unnecessary CONFIDENCE tag, reducing professional tone.
- Screenplay formatting and show-not-tell compliance not verified in preview.
  > 💡 Include a brief logline or summary and remove nonstandard confidence notation.

### ✅ `a079d38f…` — score 6/10
- Excel lacks per-day or per-video time breakdown tied to listed packages.
- Assumed shoot days and hours are not justified from video list.
- Text claims detailed breakdown, but spreadsheet is overly high-level.
  > 💡 Add per-package shoot time calculations and a per-day schedule sheet justifying total hours and days.

### ❌ `02aa1805…` — score 2/10
- Did not extract or review Illinois EPA well data.
- Excel file contains no well records or analysis.
- No recommendations or highlighted viable wells provided.
  > 💡 Access Illinois EPA factsheets, populate the workbook with data, and recommend specific qualifying wells.

### ✅ `fd6129bd…` — score 8/10
- Change Request Form appears to be a template, not a completed example.
- Text response summarizes intent rather than confirming delivered content details.
  > 💡 Include a fully completed sample Change Request and briefly confirm SOP section alignment.

### ✅ `ce864f41…` — score 6/10
- Text response does not answer the three utilization and budget questions.
- No evidence the Excel includes calculated findings, only described structure.
- Administrative time exclusion and capacity assumptions are not demonstrated.
  > 💡 Include explicit written answers with quantified results and ensure the Excel shows calculated utilization and budget variances.

### ✅ `58ac1cc5…` — score 6/10
- Attached Change Control Form remains largely blank and not formally completed.
- Generated text response summarizes intent rather than delivering substantive drafted content.
- Evidence of QA escalation email content not verifiable from provided preview.
  > 💡 Complete the official change control form fields and include verifiable drafted content for each deliverable.

### ✅ `3c19c6d1…` — score 6/10
- No evidence provided that required slide contents meet specified details.
- Progress summary slide does not confirm summarised tabular data.
- Report text describes intent rather than presenting actual report content.
  > 💡 Include explicit confirmation or excerpts of each required slide to demonstrate compliance.

### ✅ `a99d85fc…` — score 7/10
- Notes section below the Annual Rent Matrix is missing.
- Editable input cells are not clearly color-coded light blue.
- Color-coding for scenarios is unclear or inconsistent.
  > 💡 Add a visible Notes section and apply clear color-coding for scenarios and editable inputs.

### ❌ `55ddb773…` — score 4/10
- Actual violation types and qualifying questions from the reference PDF were not included.
- Architectural regulations were not itemized line by line as required.
- Placeholder instructions shifted transcription responsibility to sub associations.
  > 💡 Manually transcribe and list every violation type, qualifying detail, and architectural item from the reference PDF.

### ❌ `1e5a1d7f…` — score 3/10
- The .docx file lacks the required table format.
- No weekly schedule tasks are populated.
- PM duties are not translated into scheduled activities.
  > 💡 Create a populated table with all required columns using the provided PM duties.

### ✅ `0419f1c3…` — score 8/10
- Acknowledgement time standard was discussed qualitatively but not quantified against the 4-hour requirement.
- Training completion within first 30 days is not explicitly stated in the objectives section.
  > 💡 Add a quantified acknowledgement-time metric and explicitly state training completion deadlines.

### ✅ `ed2bc14c…` — score 8/10
- Text response summarizes intent rather than delivering substantive memo content.
- Exit survey categorization into five defined reasons is not explicitly shown.
- Small sample size is noted but not contextualized for confidence.
  > 💡 Add a brief appendix summarizing all five departure categories and counts.

### ✅ `46bc7238…` — score 7/10
- Cover page stock photo is not clearly identifiable in the PDF preview.
- Next Steps section content is not visible in the PDF preview.
- One-page flyer template content is not shown in the PDF preview.
  > 💡 Ensure the PDF clearly displays a cover image, Next Steps page, and full flyer template content.

### ✅ `2d06bc0a…` — score 9/10
- Section 12 heading appears truncated or contains a typographical error.
- Expiration period length is not clearly visible in the provided preview.
  > 💡 Proofread headings and explicitly state the LOI expiration period in days and a specific date.

### ✅ `fd3ad420…` — score 7/10
- Commission splits lack specific percentage examples for agents and associate brokers.
- No state-specific compliance distinctions for FL, GA, and NC are included.
  > 💡 Add clear example percentage splits and brief state-specific compliance notes.

### ✅ `0818571f…` — score 5/10
- Properties are illustrative, not verified active listings from Crexi or LoopNet.
- Requirement for live June 2025 to date sourcing is unmet.
- Report relies on placeholder examples rather than confirmed market data.
  > 💡 Replace illustrative properties with verified active Crexi or LoopNet listings meeting the stated criteria.

### ❌ `6074bba3…` — score 3/10
- CMA PDF contains extensive placeholder text and missing subject property details.
- Comparable sales and active listings data were not populated with real market information.
- Graphs and pricing recommendations lack actual data and analysis.
  > 💡 Fully populate the CMA template with real comps, accurate property details, and completed graphs before delivery.

### ✅ `5ad0c554…` — score 6/10
- Brochure does not explicitly identify or reference specific items from the 132 Things document.
- Word brochure lacks embedded photos or visuals beyond a separate header image.
- Double-sided, two-page layout is not clearly demonstrated in the document.
  > 💡 Revise the brochure to cite specific numbered buyer services, embed visuals in the Word file, and format as two pages.

### ❌ `11593a50…` — score 3/10
- Properties are in Massabama 11009, not Massapequa Park 11762.
- Buyer showings PDF is five pages, exceeding the two-page requirement.
- Listings use placeholder data and lack real MLSLI photos and list dates.
  > 💡 Redo the search using live MLSLI data for Massapequa Park and rebuild compliant two-page PDFs.

### ✅ `94925f49…` — score 6/10
- School data is illustrative and lacks citations to reputable sources like Niche.
- Nearby homes are examples, not real listings from accessible real estate platforms.
- Reports do not verify accuracy or timeliness of July 2025 data.
  > 💡 Replace illustrative data with cited school statistics and actual active listings meeting criteria.

### ✅ `90f37ff3…` — score 7/10
- Comparable addresses lack full street details and verification.
- Comparable data sources and dates are not explicitly cited.
- Market survey does not clearly confirm transactions within past three years.
  > 💡 Add cited sources, full addresses, and date ranges to strengthen data credibility.

### ✅ `403b9234…` — score 7/10
- Slide content cannot be verified from the provided preview.
- Slide count and coverage of required topics are unconfirmed.
  > 💡 Include a brief slide-by-slide outline or screenshots for verification.

### ✅ `1bff4551…` — score 6/10
- Includes a song with explicit sexual language, violating the no heavy curse words requirement.
- YouTube links are search result pages instead of direct song links.
- Original song “Fistful of Flyers” by rex is not clearly included in the set list.
  > 💡 Replace the explicit song, add rex’s original clearly, and provide direct YouTube links.

### ✅ `650adcb1…` — score 7/10
- No visible color-coding key on the first Excel page as required.
- No tab or list explicitly noting dates with fewer than two interns working.
- Coverage_Issues tab mentioned in text response is missing from the actual file.
  > 💡 Add a visible key on December and a coverage-issues summary tab noting understaffed dates.

### ✅ `01d7e53e…` — score 6/10
- Text response summarizes intent instead of presenting or verifying actual agreement content.
- No evidence the draft includes required dates, contacts, indemnification, or compliance clauses.
- File list includes references but does not confirm RecFit agreement completeness.
  > 💡 Provide a content-verified summary confirming each required clause exists in the draft agreement.

### ✅ `a73fbc98…` — score 7/10
- Assignments appear to cluster multiple jewelry vendors adjacent, contrary to variety requirement.
- Electricity needs are not clearly verified against tables with power access.
- Text response lacks explanation of how layout PDFs map to assigned table numbers.
  > 💡 Add a brief methodology and validate power and product-spacing compliance in the assignment file.

### ✅ `0ec25916…` — score 6/10
- PDF is two pages, not the required one-page format.
- Table layout is not clearly two columns by four rows.
- Text response describes intent instead of summarizing completed content.
  > 💡 Condense the PDF to one page with a clear 2x4 table and align the text response to delivered content.

### ✅ `116e791e…` — score 7/10
- PDF exceeds the one-page requirement.
- Care plan is limited to PACU, not entire hospital encounter.
  > 💡 Condense content to one page and generalize plan for inpatient course beyond PACU.

### ✅ `dd724c67…` — score 5/10
- Facility list is incomplete and does not include all Long Island hospitals and rehabilitation facilities.
- Online research was not conducted; content relies on general knowledge instead.
- TFU timeframes are generalized and not fully aligned to PY 2025 ACO REACH specifications.
  > 💡 Perform comprehensive online research and update the spreadsheet using the official PY 2025 CMS methodology.

### ❌ `7151c60a…` — score 4/10
- Pre-screening checklist lacks required table listing all patient information elements.
- Checklist is missing page numbers and table repeated fields across pages.
- Fax cover sheet does not clearly include the confidentiality statement content.
  > 💡 Revise documents to add a complete table-based checklist with page numbers and embed the confidentiality statement on the fax cover sheet.

### ❌ `90edba97…` — score 3/10
- Did not enter annual monthly lab results into the tracker as required.
- Medication and treatment changes were not documented per standing orders.
- Claimed missing lab data despite Patient Lab Reports file being provided.
  > 💡 Fully extract lab values from Patient Lab Reports and complete monthly entries with protocol-based treatment changes.

### ✅ `91060ff0…` — score 7/10
- Poster lacks cited references despite requirement for sources.
- No visual elements like tables, icons, or product comparisons included.
- OTC treatment section is narrow and omits common options like cryotherapy.
  > 💡 Add cited references and simple visuals comparing OTC treatments to improve completeness and engagement.

### ✅ `8384083a…` — score 6/10
- Saxenda days’ supply calculation is incorrect; 3 pens at 3 mg daily equals 18 days.
- DOCX file lacks the required medication table and detailed calculations.
- Miebo days’ supply assumption lacks drop-per-mL basis and audit justification.
  > 💡 Correct dosing calculations, complete the DOCX table content, and clarify Miebo days’ supply methodology.

### ✅ `045aba2e…` — score 7/10
- Checklists lack explicit California law or self-assessment section citations.
- Compliance scope is minimal and omits several common Board-required areas.
- Additional DOCX files were produced though only PDFs were requested.
  > 💡 Expand checklist items with California-specific requirements and cite relevant lawbook and self-assessment sections.

### ❌ `f2986c1f…` — score 3/10
- Medications were not identified using Drugs.com as required.
- Excel contains only placeholder NA values without actual identification.
- Text response deflects task instead of completing identification.
  > 💡 Use Drugs.com pill identifier to identify medications from the image and populate all spreadsheet fields.

### ✅ `ffed32d8…` — score 6/10
- Comparative table omits required drug cost, vial cost, and reimbursement details.
- Methodology and calculations are not shown, limiting verification of revenue figures.
- DOCX content is truncated and lacks the full comparative table.
  > 💡 Add complete cost breakdown tables with transparent calculations for both fill models.

### ✅ `a69be28f…` — score 6/10
- Text response describes intent rather than summarizing actual analytical findings.
- Charts appear to show units only, not revenue as required.
- Regional slides for all four regions are not clearly evidenced in preview.
  > 💡 Include explicit written insights and ensure each region shows both units and revenue by fit.

### ✅ `788d2bc6…` — score 7/10
- TikTok Shop and influencer services are not clearly evidenced in the deck preview.
- Creative optimization services lack visible dedicated slides or samples.
- Use of open-source visual elements is not demonstrated or cited.
  > 💡 Add clear TikTok and creative optimization slides with cited visuals to fully meet requirements.

### ✅ `74ed1dc7…` — score 5/10
- Proposal lacks clearly defined new order types and supporting rationale.
- ERP document does not detail reporting impacts per proposed order type.
- Text response describes intent but not substantive deliverable content.
  > 💡 Add explicit new order types with definitions, use cases, and clear reporting benefits.

### ✅ `69a8ef86…` — score 8/10
- An extra Return Issues.docx file was produced but not requested.
- External RA guidelines content was not previewed for verification.
  > 💡 Remove unnecessary files and include previews for all required deliverables.

### ✅ `ab81b076…` — score 8/10
- Visual guidance images are referenced but not clearly embedded within the PDF pages.
- Communication steps with the distribution center lack specific contact methods or timelines.
  > 💡 Embed the example images directly in the PDF and add clear escalation contacts and response time expectations.

### ✅ `19403010…` — score 6/10
- Sales TY and LY totals do not match source data totals.
- Section 3–5 tables do not clearly display all required nine columns.
- Excel headers and formatting are unclear and partially blank.
  > 💡 Recalculate totals from source data and clearly label all required columns in Sections 3–5.

### ✅ `7ed932dd…` — score 6/10
- Spreadsheet lacks required visual highlighting for rounded pallets and early deliveries.
- Projected dates include unnecessary timestamps, reducing clarity and professionalism.
- Output only includes 10 SKUs despite over 900 SKUs in source inventory.
  > 💡 Expand analysis to all SKUs and add clear Excel formatting highlights with clean date fields.

### ❌ `105f8ad0…` — score 4/10
- Required online competitor research and September 2025 MSRPs were not conducted or documented.
- Model uses proxy benchmarks instead of defined competitors from Macy’s, Ulta, or Sephora.
- Rationales do not address COGS linkage and concentration pricing relationships specifically.
  > 💡 Redo the model with documented competitor MSRPs, sources, and explicit COGS-to-concentration pricing logic.

### ❌ `b57efde3…` — score 3/10
- Did not use the official Aqua Nor 2025 exhibitor list.
- Spreadsheet contains placeholder example companies only.
- No validated prospects or real company research provided.
  > 💡 Research the actual Aqua Nor 2025 exhibitors and replace all example entries with verified companies.

### ❌ `15d37511…` — score 3/10
- Spreadsheet contains no pricing, cost, margin, or total gross margin values.
- Tiered pricing and 15% discount are not applied or calculated.
- Year 1 total gross margin is missing, preventing executive decision-making.
  > 💡 Populate all pricing, costs, tiered discounts, and calculated margins using the reference email data.

### ✅ `bb863dd9…` — score 6/10
- Quotation details sheet preview is truncated, preventing verification of pricing totals.
- Cannot confirm quantities match requirement of 10 basic and 1 of each other module.
- Offer validity date lacks explicit quotation issue date reference.
  > 💡 Provide full visible quotation details including quantities, unit prices, and total USD amounts for verification.

### ✅ `fe0d3941…` — score 7/10
- Survey PDF has three pages instead of exactly two required pages.
- An extra DOCX survey file was produced though not requested.
- Survey lacks guidance on sampling size for over one hundred respondents.
  > 💡 Reduce the survey PDF to two pages and remove unrequested files.

### ✅ `6a900a40…` — score 6/10
- General remark validity range conflicts with road freight 10-day validity.
- Red font requirement for general remark cannot be verified.
- Revised quotation preview truncation prevents confirming all required calculations.
  > 💡 Align validity wording with each freight quote and confirm formatting visibility.

### ✅ `9efbcd35…` — score 7/10
- Lacks specific MSCI index figures or quantified returns for Q1 2025.
- No explicit citations to MSCI, WSJ, FT, or named research sources.
- Text response includes an unnecessary disclaimer about lack of internet access.
  > 💡 Add concrete MSCI performance figures and brief source citations to strengthen credibility.

### ❌ `1d4672c8…` — score 4/10
- Uses internally generated proxy data instead of MSCI-sourced historical returns.
- Excel workbook lacks the required correlation matrix tab.
- PDF analysis is overly brief and lacks detailed recommendations and next steps.
  > 💡 Source actual MSCI data, add a correlation matrix sheet, and expand the PDF with deeper analysis.

### ✅ `4de6a529…` — score 5/10
- Many required sub-asset classes from the provided lists are missing or incomplete.
- DOCX file lacks the full allocation tables and detailed content.
- An extra PDF is included without clear purpose or required formatting.
  > 💡 Ensure all specified asset and sub-asset classes are fully populated in a single, consistent PDF.

### ✅ `4c4dc603…` — score 5/10
- Product Summary is two pages, not a concise one-page document.
- Key figures like target raise, IRR, token supply, and price are missing or vague.
- Text response claims intent rather than summarizing deliverable content.
  > 💡 Condense to one page and include concrete fund metrics and token economics from the IM.

### ✅ `bb499d9c…` — score 8/10
- Document page length under 25 pages is not explicitly confirmed.
- Customization of issuer flow by issuer group is not clearly evidenced.
- Use of external industry best-practice research is not explicitly cited.
  > 💡 Add a brief executive summary noting page count, research sources, and issuer-specific customizations.

### ✅ `5349dd7b…` — score 6/10
- Historical rate increases and flat rates are estimates, not researched from published sources.
- Carrier flat rate offerings and business rates are not verified or cited.
- UPS and FedEx flat rate size definitions may not match actual published programs.
  > 💡 Redo analysis using verified published carrier data with sources and confirm eligible flat rate programs.

### ✅ `a4a9195c…` — score 8/10
- Document lacks revision history, approval, and document control metadata.
- Alignment to IPC-A-610G is referenced but not explicitly mapped to procedures.
  > 💡 Add document control details and briefly cite IPC-A-610G sections within procedures.

### ✅ `552b7dd0…` — score 7/10
- Text response describes intent rather than summarizing actual analytical results.
- PowerPoint content cannot be verified for required metrics from provided preview.
- Summary slide takeaways and recommendations are not evidenced in text.
  > 💡 Include a brief results summary and key metrics directly in the response for verification.

### ✅ `76418a2c…` — score 7/10
- Text response describes intent rather than summarizing completed results.
- Manifest lacks clear customer and pick ticket identifiers.
- Spreadsheet headers and structure are unclear and partially blank.
  > 💡 Add clear headers and order identifiers, and summarize results instead of planned actions.

### ❌ `0e386e32…` — score 3/10
- ZIP size implausibly small for a full implementation-ready codebase.
- No verifiable source files, contracts, or README content are previewable.
- zkSNARK privacy logic and cross-chain withdrawal details appear unspecified or placeholder.
  > 💡 Provide complete, inspectable source files with substantive implementations and documentation.

### ❌ `7de33b48…` — score 3/10
- ZIP contents are not provided or verified to include required TypeScript JSX implementation.
- No evidence of React Testing Library and Sinon tests validating ARIA22 requirements.
- Queueing behavior and visible prop accessibility handling are not demonstrated.
  > 💡 Include full source code and tests in the ZIP and document exact WCAG validation coverage.

### ❌ `4122f866…` — score 4/10
- Terraform configuration files and resources cannot be verified from the provided preview.
- Lambda function code content is not shown, so requirements compliance is unconfirmed.
- SES, API Gateway, and IAM details are not documented or evidenced.
  > 💡 Include full Terraform files and Lambda source previews to demonstrate all required resources and logic.

### ❌ `2c249e0f…` — score 3/10
- OpenAPI 3.0 YAML specification was not produced.
- Only data_flow.txt was delivered; required API file is missing.
- No machine-readable API contract exists for uploads and processing.
  > 💡 Provide a complete OpenAPI 3.0 YAML file covering resumable uploads, prioritization, and pipeline triggers.

## Failure Analysis

Failures were limited in number (17) but accompanied by a relatively high retry count (47), suggesting transient execution issues such as timeouts, partial generations, or tool/subprocess interruptions rather than consistent prompt misunderstanding. Sectors with lower success rates, such as Manufacturing and Retail Trade, likely contributed disproportionately to retries, indicating that certain task schemas or data structures were more brittle under this configuration.

## Recommendations

Reduce retry frequency by tightening timeout handling and subprocess recovery logic, particularly for sectors with lower success rates. Consider prompt or schema refinements for Manufacturing and Information tasks to reduce ambiguity and improve self-assessed confidence. Finally, evaluate whether selective context-length reduction or response length constraints could lower latency in high-delay sectors without materially impacting task completion.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 7 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 17 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 18 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `c44e9b62…` (Government): 6 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 2 file(s)
- `38889c3b…` (Information): 1 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 2 file(s)
- `bbe0a93b…` (Government): 5 file(s)
- `85d95ce5…` (Government): 5 file(s)
- `76d10872…` (Government): 6 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 6 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 6 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 3 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 3 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 6 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 5 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `61717508…` (Finance and Insurance): 5 file(s)
- `0ed38524…` (Finance and Insurance): 5 file(s)
- `d025a41c…` (Finance and Insurance): 4 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 6 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `ec2fccc9…` (Information): 2 file(s)
- `8c8fc328…` (Information): 2 file(s)
- `e222075d…` (Information): 6 file(s)
- `c94452e4…` (Information): 5 file(s)
- `75401f7c…` (Information): 3 file(s)
- `a941b6d8…` (Information): 3 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 2 file(s)
- `c7d83f01…` (Finance and Insurance): 2 file(s)
- `46b34f78…` (Finance and Insurance): 2 file(s)
- `a1963a68…` (Finance and Insurance): 2 file(s)
- `b78fd844…` (Finance and Insurance): 3 file(s)
- `4520f882…` (Finance and Insurance): 3 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 2 file(s)
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
- `68d8d901…` (Manufacturing): 3 file(s)
- `1752cb53…` (Manufacturing): 6 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 3 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 6 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 1 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 8 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 3 file(s)
- `46fc494e…` (Manufacturing): 4 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `5a2d70da…` (Manufacturing): 4 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 3 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 4 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 7 file(s)
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
- `e6429658…` (Health Care and Social Assistance): 4 file(s)
- `b5d2e6f1…` (Wholesale Trade): 2 file(s)
- `47ef842d…` (Wholesale Trade): 3 file(s)
- `1137e2bb…` (Wholesale Trade): 3 file(s)
- `c3525d4d…` (Wholesale Trade): 5 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 2 file(s)
- `57b2cdf2…` (Retail Trade): 4 file(s)
- `84322284…` (Retail Trade): 5 file(s)
- `a46d5cd2…` (Retail Trade): 5 file(s)
- `6241e678…` (Information): 2 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `e4f664ea…` (Information): 4 file(s)
- `a079d38f…` (Information): 3 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 4 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 7 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 3 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 9 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 3 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 15 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 5 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 5 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 16 file(s)
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
- `90edba97…` (Health Care and Social Assistance): 6 file(s)
- `91060ff0…` (Retail Trade): 2 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 6 file(s)
- `f2986c1f…` (Retail Trade): 2 file(s)
- `ffed32d8…` (Retail Trade): 4 file(s)
- `b3573f20…` (Wholesale Trade): 1 file(s)
- `a69be28f…` (Wholesale Trade): 3 file(s)
- `788d2bc6…` (Wholesale Trade): 3 file(s)
- `74ed1dc7…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `19403010…` (Wholesale Trade): 2 file(s)
- `7ed932dd…` (Wholesale Trade): 2 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 3 file(s)
- `fe0d3941…` (Wholesale Trade): 5 file(s)
- `6a900a40…` (Wholesale Trade): 6 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 2 file(s)
- `4de6a529…` (Finance and Insurance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `bb499d9c…` (Finance and Insurance): 4 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 4 file(s)
- `76418a2c…` (Manufacturing): 4 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 3 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 1 file(s)
