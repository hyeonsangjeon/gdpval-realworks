# Experiment Report: GPT-5.2 Chat Elicit v2 — subprocess (Full 220 tasks)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp005_GPT52Chat_elicit_v2_runner_exec` |
| **Condition** | Elicit v2 |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-02-27 |
| **Duration** | 138m 37s |
| **Generated At** | 2026-02-27T18:41:44.869668+00:00 |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment executed the GPT-5.2 Chat Elicit v2 configuration across 220 tasks using a subprocess execution mode. The primary objective was to observe task completion behavior, self-assessed QA confidence, latency characteristics, and sector-level variation under the Elicit v2 condition. Out of 220 tasks, 199 completed successfully, yielding a 90.5% task completion rate, with 21 tasks resulting in errors and 59 requiring at least one retry.

The model reported an average self-assessed QA confidence of 6.16/10, with a wide range (2–9), indicating variable confidence depending on task type and sector. Latency was consistently high, averaging approximately 25.4 seconds per task, suggesting substantial reasoning or context-handling overhead in this configuration. Overall, the run demonstrates stable completion with moderate self-evaluated quality and predictable latency costs.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 199 (90.5%) |
| Errors | 21 |
| Retried Tasks | 59 |
| Avg QA Score | 6.16/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 25,437ms |
| Max Latency | 55,814ms |
| Total LLM Time | 5596s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 166 (89.7%) |
| Failed → dummy created | 19 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 59 | 38 | 21 |

## Quality Analysis

Self-assessed QA scores clustered in the mid-range (5–7) across most sectors, with Government tasks standing out for higher average confidence (7.2/10). Information-sector tasks achieved perfect completion but had the lowest average self-assessed QA confidence (5.1/10), suggesting that while tasks were completed reliably, the model expressed lower confidence in output quality or completeness.

Finance, Manufacturing, and Professional/Scientific/Technical Services showed similar QA profiles around 6.0–6.1, indicating consistent but unexceptional self-evaluated quality. Retail Trade had a slightly higher average QA confidence (6.6) with lower latency than most sectors, whereas Manufacturing and Information tasks exhibited some of the highest average latencies, implying greater complexity or prompt length affecting response time.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 21 | 84.0% | 5.9/10 | 26,473ms |
| Government | 25 | 24 | 96.0% | 7.17/10 | 24,258ms |
| Health Care and Social Assistance | 25 | 22 | 88.0% | 6.09/10 | 25,324ms |
| Information | 25 | 25 | 100.0% | 5.12/10 | 27,614ms |
| Manufacturing | 25 | 21 | 84.0% | 6.14/10 | 28,254ms |
| Professional, Scientific, and Technical  | 25 | 23 | 92.0% | 6.0/10 | 26,060ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 6.17/10 | 24,663ms |
| Retail Trade | 20 | 19 | 95.0% | 6.63/10 | 22,798ms |
| Wholesale Trade | 25 | 20 | 80.0% | 6.35/10 | 22,962ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 4/10 | 18740ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 3/10 | 18981ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 7 | 7/10 | 21355ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 5/10 | 25056ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 6/10 | 17040ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 27332ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 15303ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | Yes | 5 | 7/10 | 24789ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 5 | 8/10 | 32976ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | Yes | 6 | 6/10 | 25441ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 6 | 5/10 | 30987ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | Yes | 3 | 5/10 | 29058ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 2 | 3/10 | 55814ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 1 | 2/10 | 20284ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | 3/10 | 19842ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 29912ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 7/10 | 25035ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 24811ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | Yes | 2 | 5/10 | 21191ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 4/10 | 37439ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 9/10 | 21684ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 6/10 | 17936ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | 7/10 | 24561ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 5 | 3/10 | 36857ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 6 | 8/10 | 20477ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 21209ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 17383ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 7/10 | 23918ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 15359ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ❌ error | Yes | 0 | - | 23267ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 25401ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 29882ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 6 | 7/10 | 24551ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 6/10 | 22543ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 9 | 7/10 | 34493ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 3/10 | 19321ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 8/10 | 31927ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 6/10 | 32346ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 4/10 | 21787ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 26015ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 24149ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 26472ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 4/10 | 19686ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 4 | 9/10 | 21513ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 5 | 6/10 | 24219ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 7/10 | 20215ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 6/10 | 30323ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 7/10 | 15804ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 24133ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 16943ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 5/10 | 24535ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 6/10 | 42858ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | 6/10 | 34248ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | Yes | 2 | 8/10 | 21681ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 2 | 4/10 | 31534ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 2 | 8/10 | 16686ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 5 | 4/10 | 25657ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | - | 3 | 4/10 | 23963ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | Yes | 4 | 3/10 | 24523ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | - | 2 | 3/10 | 24962ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 1 | 4/10 | 16022ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 3 | 7/10 | 35860ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 4/10 | 21159ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 4 | 4/10 | 44682ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 26815ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 3 | 6/10 | 33363ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 25151ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 23178ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 4 | 8/10 | 42704ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 3 | 6/10 | 23402ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 19023ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 2 | 6/10 | 21701ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 22784ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 4/10 | 22305ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 23318ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 27631ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 6/10 | 26925ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 4/10 | 24009ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 4 | 4/10 | 14992ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 11 | 4/10 | 19185ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 3 | 6/10 | 34345ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 3 | 8/10 | 25166ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 1 | 8/10 | 22564ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 31918ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 1 | 9/10 | 36161ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 3 | 5/10 | 18881ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 18440ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 23923ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 21833ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 16429ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 4/10 | 20229ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 12597ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 7/10 | 13211ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 5 | 5/10 | 27404ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | 7/10 | 20611ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 22439ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | Yes | 1 | 8/10 | 22481ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 20977ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 26485ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | 7/10 | 22032ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 5/10 | 17998ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 3 | 6/10 | 38348ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 6/10 | 25802ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 5 | 7/10 | 22176ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 8 | 6/10 | 34713ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 28504ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 43015ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 7/10 | 34953ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 7/10 | 28327ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 46276ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 6/10 | 43506ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 3/10 | 41799ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 7/10 | 38764ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 37680ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 6/10 | 30395ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 28417ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 19599ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 23991ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 15658ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | Yes | 4 | 6/10 | 30530ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 5 | 4/10 | 28037ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 2 | 9/10 | 19385ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 23937ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 13 | 5/10 | 25414ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 6/10 | 24249ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 7/10 | 26477ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | Yes | 1 | 6/10 | 25874ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 5/10 | 24305ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 30880ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 8 | 6/10 | 33323ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 4/10 | 29419ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 7/10 | 27601ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 20773ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 7/10 | 21802ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | Yes | 4 | 8/10 | 29273ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 4/10 | 20499ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 19914ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 3 | 8/10 | 19112ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 8/10 | 21377ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 5 | 5/10 | 27941ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 20231ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 27184ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 29485ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 21688ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 28643ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 6 | 9/10 | 22712ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 6 | 6/10 | 31293ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | Yes | 5 | 8/10 | 28583ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 8/10 | 23055ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 5 | 7/10 | 27278ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 1 | 4/10 | 30588ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 21934ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 9/10 | 24207ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | Yes | 5 | 3/10 | 24588ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 3 | 5/10 | 21531ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 22189ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 7/10 | 17900ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 8/10 | 22977ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | Yes | 7 | 8/10 | 30610ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 6/10 | 22679ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 6/10 | 28019ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 3/10 | 23512ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 3/10 | 16500ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 9/10 | 21701ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | Yes | 3 | 8/10 | 22746ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 7 | 6/10 | 29804ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 7/10 | 25835ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 9/10 | 22035ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 15 | 6/10 | 32286ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 5 | 3/10 | 21576ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 7/10 | 22577ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 4/10 | 20687ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 6/10 | 28052ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 7/10 | 30764ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 9/10 | 23058ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 18252ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 7/10 | 27830ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 22392ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 4 | 6/10 | 21203ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 5 | 6/10 | 18116ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 8/10 | 27013ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 3 | 7/10 | 38036ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 6/10 | 29712ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 6/10 | 23953ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 7 | 3/10 | 33550ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 5/10 | 30435ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 6/10 | 30117ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 8/10 | 18780ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 3/10 | 11546ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 5/10 | 23697ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 8/10 | 21032ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 8/10 | 27390ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 6/10 | 38187ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | Yes | 2 | 8/10 | 21626ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 8/10 | 24788ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 5 | 8/10 | 32484ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 22433ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 6/10 | 20675ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 5/10 | 23042ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 16915ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 18128ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 19570ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 6/10 | 20770ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 6 | 8/10 | 28431ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 6 | 6/10 | 20599ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 30918ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 2 | 5/10 | 21914ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 4 | 6/10 | 28821ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 5/10 | 21346ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 7/10 | 31830ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 28737ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 34589ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 4 | 8/10 | 36038ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 21980ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 4 | 6/10 | 15920ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 21657ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 3 | 6/10 | 23940ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 19963ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 3/10 | 28625ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 21834ms |

## QA Issues

### ❌ `83d10b06…` — score 4/10
- Sample selection far exceeds calculated sample size of 68 without justification.
- Variance appears absolute, not percentage, conflicting with >20% variance criterion.
- No evidence provided that all sampling criteria are individually satisfied.
  > 💡 Align sampled rows to calculated sample size and explicitly evidence each selection criterion.

### ❌ `7b08cd4d…` — score 3/10
- Excel report contains no populated revenue or expense data.
- Required breakdown by source and combined totals is missing.
- Net income, tax calculations, and expense categories are not completed.
  > 💡 Populate the Excel with calculated revenues, taxes, expenses by source, totals, and net income.

### ✅ `7d7fc9a7…` — score 7/10
- Text response provides no numeric evidence of reconciliation to GL balances.
- No summary figures are quoted to verify totals through April 2025.
- Assumptions applied to missing amortization periods are not explicitly demonstrated.
  > 💡 Include key reconciliation totals and a brief numeric rollforward summary in the narrative.

### ✅ `43dc9778…` — score 5/10
- Schedule A likely required but not mentioned despite mortgage interest and medical premiums.
- Schedule 1 not mentioned despite student loan interest documentation.
- Text response lacks summarized tax figures and line-level confirmation.
  > 💡 Include all required schedules with a brief summary of key amounts and filing status details.

### ✅ `ee09d943…` — score 6/10
- Produced multiple source files instead of only the consolidated April workbook.
- Text response lacks confirmation of updated TOC and tab-by-tab completion.
- No evidence of review notes or flagged issues communicated to CFO.
  > 💡 Submit only the finalized consolidated workbook with documented updates and CFO review notes.

### ❌ `f84ea6ac…` — score 3/10
- Document lacks the required summary table and study comparisons.
- Five post-2020 publicly available academic articles are not identified or summarized.
- Content is minimal and includes unsupported claims and excuses.
  > 💡 Create a one-page Word table summarizing five specific post-2020 public studies with findings and government implications.

### ✅ `27e8912c…` — score 7/10
- Word document lacks a table with action items, status/comments, and resolution tracking columns.
- Resolution details such as who resolved the issue are missing.
- Ergonomic images lack citation or confirmation of public-domain sources.
  > 💡 Add a structured action-tracking table with full resolution fields and cite public-domain image sources.

### ✅ `17111c03…` — score 8/10
- Memo 'From' line lacks the manager’s personal name.
  > 💡 Add the Administrative Services Manager’s full name to the memo for formality.

### ✅ `c44e9b62…` — score 6/10
- Revised organizational chart lacks full branch structure and clear visual highlighting of reductions.
- FTE reduction calculations and confirmation of meeting minimum 4% target are not explicitly shown.
- Updated Excel FTE report content is not evidenced against previewed data.
  > 💡 Include explicit 4% reduction calculations and fully detailed revised org chart with clear visual markers.

### ✅ `99ac6944…` — score 5/10
- Mixer cannot provide two truly independent IEM mixes for both singers.
- PDF lacks required retailer web links and detailed equipment justifications.
- Cost breakdown spreadsheet has formatting issues and unclear total calculation.
  > 💡 Revise with a mixer supporting two aux mixes, add web links, and cleanly itemize costs.

### ✅ `f9a1c16c…` — score 5/10
- Input list text is garbled with typos, duplicates, and unclear numbering.
- Output list shows duplicated IEM splits and inconsistent wedge numbering.
- Stage plot labels and placements lack clarity and professional readability.
  > 💡 Cleanly reformat input/output lists, correct numbering, and improve label clarity for a professional advance-ready plot.

### ❌ `38889c3b…` — score 3/10
- Audio content is explicitly placeholder, not a finished instrumental production.
- Bit depth is PCM 24-bit, not 24-bit float as required.
- No evidence the provided drum reference track was actually used.
  > 💡 Deliver fully produced audio using the drum reference and correct 24-bit float exports.

### ❌ `ff85ee58…` — score 2/10
- Final 24-bit 48 kHz mix WAV was not produced.
- Saxophone was not resynced, edited, or processed into the mix.
- Loudness targets and peak limits were not met or verified.
  > 💡 Produce the actual final mixed WAV including resynced sax and verify loudness and format compliance.

### ❌ `4b894ae3…` — score 3/10
- Final stereo WAV mix was not delivered.
- No bass edits or stem mixing were actually performed.
- Provided files do not meet required deliverable types.
  > 💡 Produce the edited bass track and export the specified 48k/24b stereo WAV mix.

### ✅ `1b1ade2d…` — score 8/10
- Text response describes intent rather than summarizing the actual proposed workflow.
  > 💡 Include a concise executive summary of the revised workflow in the text response.

### ✅ `93b336f3…` — score 7/10
- Cost analysis lacks explicit baseline current total battery cost in INR.
- Detailed calculation breakdowns are stated but not shown step-by-step.
- Some assumptions like ownership split and location were not requested.
  > 💡 Add a clear cost table showing current vs localised costs with stated assumptions.

### ✅ `15ddd28d…` — score 8/10
- Negotiation agenda and meeting cadence with LPI leadership is not explicitly detailed.
- Risk quantification and worst-case production impact numbers are limited.
  > 💡 Add a one-page negotiation agenda with timelines and quantified production-risk scenarios.

### ✅ `24d1e93f…` — score 5/10
- NPV sheets lack per-unit pricing, tooling amortization, and R&D cost breakdowns.
- Annual costs appear assumed without traceability to vendor quotations.
- Variant-wise volume split is not applied or shown in calculations.
  > 💡 Include transparent cost build-ups per vendor with variant splits, tooling amortization, and upfront R&D clearly shown.

### ❌ `05389f78…` — score 4/10
- Quotation file lacks cost figures, INR calculations, and comparative data.
- Supplier assessment includes Juvoxa and omits required Autonexis versus Vendrax analysis.
- Report cannot justify recommendation without quantified costs, lead times, and forex impact.
  > 💡 Provide complete INR cost data from quotes and redo the comparative analysis and recommendation.

### ✅ `a74ead3b…` — score 6/10
- Manual content was not verified or closely followed as required.
- Deliverable text relies on assumptions about Sessions 13 and 14 themes.
- Quality and completeness of slides cannot be confirmed from preview.
  > 💡 Revise slides using verified manual content and explicitly align each slide to session objectives.

### ✅ `bbe0a93b…` — score 7/10
- Open web search was not actually conducted as required.
- Spanish assessment includes English tracking table headers.
  > 💡 Conduct a true web search and fully translate all Spanish table headers.

### ❌ `85d95ce5…` — score 3/10
- Final PDF is only three pages, not the required 8–15 pages.
- Provided notes file references a different student name, indicating incorrect source material.
- Deliverable content cannot be verified as fully incorporating notes and required recommendations.
  > 💡 Revise using correct JOHN SMITH notes and expand the report to fully meet all length and content requirements.

### ✅ `76d10872…` — score 8/10
- Text response describes process rather than summarizing report contents.
- Adherence to Case Creation Guide formatting is not explicitly confirmed.
  > 💡 Include a brief summary confirming all required guide sections and key data were validated.

### ✅ `36d567ba…` — score 8/10
- Conflict of interest topic includes a two-part question despite the stated exception.
- Topic 8 preview shows a truncated word, suggesting a possible formatting error.
  > 💡 Revise the conflict of interest question format and verify the final document for truncation or formatting issues.

### ✅ `2696757c…` — score 7/10
- Delivered an extra DOCX despite requesting a single PDF deliverable.
- Header punctuation does not exactly match the specified nomenclature.
  > 💡 Provide only the PDF and match the header text exactly as specified, including punctuation.

### ✅ `cebf301e…` — score 8/10
- Backend stack deviates from existing Express REST API without clear migration rationale.
- Six-week delivery plan lacks a concrete timeline and milestones.
  > 💡 Add an explicit six-week execution plan and clarify alignment with the existing Express backend.

### ✅ `c2e8f271…` — score 8/10
- Minor typo in PR titles section: 'imperativ' is misspelled.
- Community-based styling baseline is mentioned but not explicitly defined.
  > 💡 Fix the typo and explicitly name the chosen community style guide as the baseline.

### ✅ `2ea2e5b5…` — score 7/10
- Text response does not explicitly document activity-to-segment classification mappings.
- Strategic level definitions appear incomplete in the task and are not clarified.
- No written summary of analytical findings is provided outside the slides.
  > 💡 Include a brief written table summarizing all activity classifications and key insights.

### ✅ `c357f0e2…` — score 6/10
- Column headers do not match the provided UAT Plan template.
- Viewers are assigned create and promote actions despite view-only permissions.
- Some test cases violate defined role-based access rules.
  > 💡 Align columns exactly to the template and correct role permissions before UAT circulation.

### ✅ `a45bc83b…` — score 7/10
- Cloud Armor is incorrectly described as providing Layer 3 and 4 DDoS protection.
- Architecture diagram contains minor labeling and formatting inconsistencies.
  > 💡 Clarify DDoS protection layers and clean up diagram labels for technical accuracy.

### ❌ `a10ec48c…` — score 3/10
- Document lacks tables with required columns and restaurant rows.
- No restaurant details, hours, links, directions, or categories are provided.
- Sources were not used and permanently closed restaurants not verified.
  > 💡 Populate tables with verified Downtown Sarasota restaurants and complete all required fields.

### ✅ `fccaa4a1…` — score 8/10
- Age requirement wording is unclear and inconsistent with a 16-year-old participant.
- Icons and visual styling are not clearly evident in the PDF preview.
- Tour operator details reference Take Walks but do not cite the specific webpage.
  > 💡 Clarify age requirements, add visible icons, and include a direct TakeWalks.com source citation.

### ✅ `f5d428fd…` — score 6/10
- Royalty-free photos were not embedded despite being explicitly required.
- No citations or evidence of research from specified online sources are included.
- Image limitation disclaimer indicates incomplete fulfillment of deliverable requirements.
  > 💡 Embed verified royalty-free images and add brief source citations to fully meet the original task.

### ❌ `2fa8e956…` — score 4/10
- Does not list all wineries within one-hour drive; only three examples provided.
- Required formatting not demonstrated: footer, font sizes, and purple grape text.
- Sources and Google Maps distance citations are missing.
  > 💡 Expand the winery list, apply specified formatting, and add sourced Google Maps distances and citations.

### ✅ `0e4fe8cd…` — score 6/10
- June 4 return travel itinerary is missing.
- Some service providers are unverified or noted as placeholders.
- Private flight details lack aircraft and tail number.
  > 💡 Add a complete June 4 return tab and fully verify all providers and flight specifics.

### ❌ `aa071045…` — score 4/10
- Service request form lacks required fields and details beyond the title.
- Damage revenue total is incorrect and inconsistent with category and damage breakdowns.
- Service request omits vehicle status, request type, and damage description.
  > 💡 Fully populate the service form and recalculate all revenue totals to align with the source data.

### ✅ `61f546a8…` — score 6/10
- Refrigerator installation day is missing despite requiring an extra day.
- M24 make-ready date not adjusted despite appliance delivery after listed date.
- Staff work overlaps paint day without clarifying vendor sequencing compliance.
  > 💡 Add appliance installation dates and revise make-ready dates to reflect the full timeline.

### ✅ `f3351922…` — score 7/10
- Email contains placeholder [Client Name] instead of a completed salutation.
- Text response describes the deliverable instead of presenting the email content.
- Unnecessary meta commentary reduces professionalism of the text response.
  > 💡 Replace placeholders and present the full email directly in the text response.

### ✅ `61717508…` — score 6/10
- Senior Safe Act is not clearly explained in the training deck.
- FINRA Rule 2165 protections are not summarized in plain language.
- Training deck escalation guidance relies on a separate policy file.
  > 💡 Add brief, plain-language sections on Senior Safe Act and FINRA Rule 2165 directly into the main deck.

### ✅ `0ed38524…` — score 7/10
- Talking points list duplicates "General" and inconsistent category naming.
- Summary contains spelling and punctuation errors, reducing professionalism.
- Service categories do not consistently match Excel source values.
  > 💡 Proofread documents and standardize categories and counts to exactly match the source data.

### ✅ `d025a41c…` — score 6/10
- Bold formatting and 1.5 line spacing are not verifiable in the Case Feedback document.
- Extra case files were produced despite instructions specifying a single Word document.
- The response does not confirm use of the provided chat logs as the source material.
  > 💡 Ensure the Case Feedback document alone meets all formatting requirements and explicitly references the provided case logs.

### ✅ `401a07f1…` — score 5/10
- Reference links are missing or incomplete, preventing verification.
- Required outlet Scientific American is not cited.
- Word count appears below the requested 500 words.
  > 💡 Add complete hyperlinks, include Scientific American, and expand to a verified 500-word count.

### ✅ `afe56d05…` — score 6/10
- Document appears shorter than the required 2,200–2,300 words.
- External resources are referenced but visible hyperlinks are unclear or missing.
- Text response describes intent rather than summarizing delivered content.
  > 💡 Verify word count, add explicit hyperlinks, and align the text response with the completed document.

### ✅ `9a8c8e28…` — score 6/10
- Bibliography lists sources but provides no clickable links.
- Framework guide is very brief and lacks practical examples depth.
- Quiz preview does not clearly show answer key, explanations, and scoring guide.
  > 💡 Expand the guide, add live links, and clearly include a full quiz answer key with scoring.

### ✅ `3a4c347c…` — score 8/10
- Text response describes intent rather than summarising delivered content.
- Reference file name differs from specified Enterprise Technology BOILERPLATE.docx.
- Schedule compliance with Monday/Wednesday/Friday publishing is not explicitly confirmed.
  > 💡 Add a brief executive summary in the response confirming all requirements are met.

### ❌ `ec2fccc9…` — score 4/10
- Article appears significantly under 1,500 words.
- Pull quote caption contains placeholder text.
- Secondary keywords list is missing or not clearly labeled.
  > 💡 Expand content to full length, finalize the pull quote caption, and add a clear secondary keyword list.

### ✅ `8c8fc328…` — score 8/10
- Text response includes unnecessary CONFIDENCE tag.
- Reference document was re-produced instead of only the requested script.
- Script content was not summarized in the text response.
  > 💡 Remove extraneous confidence markers and briefly summarize the script content in the response.

### ❌ `e222075d…` — score 4/10
- No 30-second H.264 MP4 export was delivered as required.
- Scratch voiceover audio track was not produced.
- Stock log lists platform homepages, not direct clip URLs or watermarked previews.
  > 💡 Provide an actual 30-second MP4 with scratch VO and specific watermarked stock clip links.

### ❌ `c94452e4…` — score 4/10
- No 15-second H.264 MP4 video was delivered.
- Stock footage and music sources were not identified or linked.
- Supers PSD was not applied within an actual edited spot.
  > 💡 Deliver the finished 15-second MP4 using sourced stock footage, music, and provided supers.

### ❌ `75401f7c…` — score 3/10
- No final edited MP4 showreel was produced.
- Deliverable is an edit plan, not the requested finished video.
- Most reference footage is unused, weakening showcase completeness.
  > 💡 Produce and deliver the final 01:20 MP4 showreel using the plan and all key footage.

### ❌ `a941b6d8…` — score 3/10
- No actual video file was created matching the base clip specifications.
- Core compositing, tracking, grading, and effects were not executed.
- Deliverables do not fulfill the requested finished VFX shot.
  > 💡 Produce the actual composited video output as specified, not just planning documentation.

### ❌ `8079e27d…` — score 4/10
- Data is illustrative proxy, not sourced from publicly available real market data.
- Companies are generic placeholders, not actual S&P 500 constituents.
- Methodology disclaimer contradicts requirement for real, client-ready analysis.
  > 💡 Rebuild the Excel using real S&P 500 constituents and verifiable public data sources.

### ✅ `e21cd746…` — score 7/10
- Public comparables lack company-specific Revenue, EBITDA, and P/E multiples.
- Several private valuations and funding figures are estimates without cited sources.
- LaserShip pre-merger status may be outdated for April 2025.
  > 💡 Add a table with company-specific public multiples and source citations for all valuation data.

### ❌ `9e8607e7…` — score 4/10
- Slides contain placeholder headings like Topic 1 without substantive analysis.
- Technology, venture, and fintech sections appear missing or underdeveloped.
- PNG output is a single image, not slide-by-slide exports.
  > 💡 Replace placeholders with concrete data-driven insights and fully build all three required sections.

### ❌ `c7d83f01…` — score 4/10
- Missing Python notebook implementing pricing methodologies.
- Monte Carlo methodology not evidenced with code or visuals.
- Text response overpromises undelivered notebook.
  > 💡 Provide a complete Jupyter notebook with implementations, benchmarks, and saved outputs.

### ✅ `a1963a68…` — score 6/10
- Future-proofing and sustainability initiatives are not clearly presented as a dedicated core slide.
- Strategy lacks visible data points or citations from Korean public sources.
- Action plans are high-level with limited quantified targets or KPIs.
  > 💡 Add a future-proofing slide with data-backed initiatives, KPIs, and explicit Korean regulatory references.

### ✅ `b78fd844…` — score 8/10
- Contingency plans are implied but not explicitly detailed for each identified risk.
- Operational risks are less clearly distinguished from financial risks.

### ✅ `4520f882…` — score 6/10
- Text response is high-level and does not confirm specific CBA rules were implemented.
- No user instructions or documentation for updating rates or configurations are provided.
- Workbook functionality cannot be verified from the response or file preview.
  > 💡 Include a brief workbook guide and explicit mapping of CBA provisions to spreadsheet calculations.

### ✅ `ec591973…` — score 6/10
- Text response describes intent rather than presenting actual strategy content.
- Role title included is inaccurate and unprofessional for a strategy deliverable.
- Unable to verify slide addresses all requirements without content preview.
  > 💡 Summarize key slide content and ensure role framing and language are executive-appropriate.

### ✅ `62f04c2f…` — score 6/10
- Excel form lacks signature and date spaces for sales rep, GM, and Sales Manager.
- Excel form missing required note about prepaid freight and restocking fee.
  > 💡 Add missing signature sections and the freight and restocking fee notice to the Excel form.

### ❌ `e996036e…` — score 4/10
- Projected shipment total contradicts assumption and reference file values.
- Cash flow timing by payment terms is not shown or analyzed.
- Required visual chart and 5–6 sentence summary are missing or incomplete.
  > 💡 Align projections to stated assumptions, add cash flow timing, visuals, and a complete executive summary.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a clear Visio-style visual workflow and appears mostly textual.
- Roadmap does not clearly start from MA placing the call to the patient.
- An extra unrequested file was produced, creating potential confusion.
  > 💡 Revise the Roadmap into a true one-page visual flow diagram and remove unrequested files.

### ❌ `0353ee0c…` — score 4/10
- Document lacks exhaustive lists of presumptive conditions, locations, and dates.
- Content appears high-level summaries rather than compiled details from all links.
- Offline disclaimer suggests information was not fully reviewed or consolidated.
  > 💡 Populate the PDF with complete, detailed tables extracted from every Document B link.

### ❌ `40a8c4b1…` — score 4/10
- Schedule content cannot be verified from provided preview.
- No evidence unused optional topics were highlighted yellow.
- Alternate lab dates and notes section usage are unconfirmed.
  > 💡 Provide a content preview or summary validating all required scheduling conditions were met.

### ❌ `4d1a8410…` — score 4/10
- Interview schedule lacks detailed table with room-level timings, breaks, lunch, and applicant assignments.
- Required constraints like Dr. Jones 8:50 break and Dr. Garrett early departure are not shown.
- Personal itineraries are vague blocks and omit exact interview rotations and buffers.
  > 💡 Rebuild the schedule as a detailed timed table and update itineraries to match exact rotations.

### ✅ `8c823e32…` — score 6/10
- Text response summarizes intent instead of presenting the drafted policy content.
- Policy document appears incomplete with truncated documentation section.
- Claimed page-by-page PNG renderings are not clearly provided.
  > 💡 Include the full finalized policy text in the response and ensure all referenced files are complete and consistent.

### ✅ `eb54f575…` — score 8/10
- Current staffing level below authorization is not stated.
- Over-penetration tradeoff is not explicitly addressed.
- Text response summarizes intent rather than report content.
  > 💡 Add current staffing context and explicitly discuss over-penetration considerations in the caliber analysis.

### ✅ `11e1b169…` — score 8/10
- Reference guide lacks Kentucky-specific case law examples for context.
- Some sections could include brief officer safety or field application tips.
  > 💡 Add brief Kentucky case examples and practical field notes to strengthen officer understanding.

### ✅ `a95a5829…` — score 9/10
- Final approval authority could be clarified relative to Chairman approval.
  > 💡 Explicitly state whether Chairman approval is advisory or co-equal with the Chief.

### ✅ `22c0809b…` — score 9/10
- Background check authorization lacks explicit consent language or subject signature.
- Submission instructions and contact information for the Unit are not specified.
  > 💡 Add consent language with subject signature and clear submission/contact instructions for the Unit.

### ✅ `bf68f2ad…` — score 5/10
- Text response lacks the required brief explanatory summary content.
- Catch-up plan does not reflect stated 438.81 past-due hours at week 4.
- Demand values appear unrealistically low relative to described workload and schedule.
  > 💡 Align initial backlog and demand data to the problem statement and include the actual management summary text.

### ✅ `efca245f…` — score 6/10
- Truck Grill Guard production schedule and weekly 100-unit requirement are not shown in plans.
- Statutory holidays are not identified or excluded from daily production schedules.
- Scenario 3 assumes 10-hour shifts despite stated inability to pay overtime.
  > 💡 Revise the Excel plans to explicitly model grill guard output, holidays, and compliant labor assumptions.

### ✅ `68d8d901…` — score 6/10
- Excel content is not summarized, so requirements fulfillment cannot be verified.
- Daily target stated as 7,680 lbs freeze-dried conflicts with specification yield.
- Staggered dryer end-times are not explicitly demonstrated.
  > 💡 Summarize key Excel tab contents and correct targets to align with yield and staggered cycles.

### ❌ `bd72994f…` — score 4/10
- Presentation delivered as PPTX instead of required PDF format.
- Looks are conceptual and not sourced from an official 2025 resort collection.
- Brand and specific collection selection are not identified or verified.
  > 💡 Provide a PDF with 4–6 looks sourced from one named brand’s official 2025 resort collection.

### ✅ `211d0093…` — score 7/10
- Manager sign-off section is not visible or confirmed at the end of the DTL.
- Notes fields appear inconsistently sized for some tasks.
- An extra DOCX file was produced though only PDF was required.
  > 💡 Add a clearly labeled manager sign-off section at the end and standardize all entry fields.

### ✅ `d4525420…` — score 7/10
- Text response does not include the required 5–7 sentence selection justification.
- Response contains meta commentary instead of the requested evaluative paragraph.
- Extraneous confidence tag included in the response.
  > 💡 Include the full 5–7 sentence justification directly in the text response.

### ✅ `45c6237b…` — score 5/10
- Shirt sizes are not broken out by S/M/L/XL/XXL as required.
- Next Season Assortment images are referenced but not shown in slides.
- Purchase summary table contains NaN values and formatting errors.
  > 💡 Add size-level shirt quantities, embed vendor images, and correct the summary table calculations.

### ✅ `cecac8f9…` — score 7/10
- Financial targets use USD instead of GBP for a UK store.
- Launch deck lacks specific promotional offers referenced in the Marketing Email.
- Text response summarizes intent rather than delivered content details.
  > 💡 Localise currency, explicitly detail promotions in the deck, and align the response to delivered content.

### ✅ `8f9e8bcd…` — score 8/10
- Homework section requirements cannot be fully verified from the preview.
- Minor grammar issues such as missing hyphen in open-ended.
  > 💡 Ensure the Homework section clearly includes a due date line and printed name line.

### ✅ `0fad6023…` — score 8/10
- No graphical visual representation of pan layout beyond a table.
- Start and End columns appear blank in preview, formula results not visible.
  > 💡 Add conditional formatting or a simple bar-style visual to better illustrate pan layout.

### ✅ `02314fc6…` — score 8/10
- Checklist lacks total item count or score calculation for clearer compliance scoring.
- PDF does not specify distribution or submission confirmation to GM, DM, and LP.
  > 💡 Add a scoring summary with total items and include a submission acknowledgment section.

### ✅ `6436ff9e…` — score 7/10
- No explicit testimonial or consent section is visible.
- Experience level option uses unclear or inconsistent wording.
- Marketing data lacks questions about campaign effectiveness.
  > 💡 Add a clear testimonial permission section and refine wording for clarity and completeness.

### ✅ `8a7b6fca…` — score 5/10
- Process map lacks clear visual symbols and swimlane structure.
- Automation failure rerouting is mentioned but not clearly diagrammed.
- Manual processing steps lack sufficient detail and standardization.
  > 💡 Enhance the PDF with clear process symbols, swimlanes, and detailed steps for automation and manual flows.

### ✅ `40a99a31…` — score 6/10
- Camera requirement not met; minimum six cameras specified but quantities are undefined.
- Hardware table lacks quantities for LIDARs, mats, and cameras per CNC.
- Design report lacks device-specific justification and safety standard references.
  > 💡 Add quantities, expand justifications with safety standards, and explicitly specify six cameras and zone coverage.

### ✅ `b9665ca1…` — score 6/10
- E-stop wiring description inconsistently shows series and parallel without clear channel separation.
- Unspecified start and enable buttons appear, adding scope beyond requirements.
- Cross-fault monitoring disabled configuration is not explicitly documented.
  > 💡 Clarify channel wiring logic, remove non-required controls, and explicitly note cross-fault monitoring disabled.

### ✅ `c6269101…` — score 7/10
- Text response is generic and does not summarize actual analytical findings.
- Greatest variability process is not explicitly identified in the response.
- Recommendations and next steps are not concretely described.
  > 💡 Include explicit findings, identified highest-variability process, and specific data-driven recommendations.

### ✅ `be830ca0…` — score 6/10
- Assumed 3400 UPR target without explicit requirement or justification.
- Process capability analysis likely uses unspecified or arbitrary specification limits.
- PowerPoint content cannot be verified against required A3 sections and DMAIC details.
  > 💡 Explicitly document targets, specification limits, and show evidence each required section exists in the slides.

### ✅ `a97369c7…` — score 8/10
- Text response describes deliverables instead of presenting the memo content.
- Response references internal PNG generation irrelevant to client deliverables.
- Confidence tag is extraneous and unrequested.
  > 💡 Present the memo text directly in the response and omit internal process details.

### ✅ `3f625cb2…` — score 7/10
- The memorandum date field is blank.
- The conclusion section appears truncated or incomplete.
  > 💡 Add a complete date and ensure the conclusion is fully written and finalized.

### ✅ `aad21e4c…` — score 7/10
- Capitalization schedule before and after issuance is not clearly shown in the document.
- Minority investor consent rights over extraordinary actions are not clearly specified.
- Pre-emptive rights section appears incomplete or truncated.
  > 💡 Add a clear capitalization schedule and explicitly enumerate minority consent rights and complete all sections.

### ✅ `8314d1b1…` — score 8/10
- Text response describes work rather than summarizing substantive conclusions.
- Irrelevant note about LibreOffice conversion included.
- Conclusion section not visible in provided preview.
  > 💡 Remove irrelevant process notes and ensure all required sections are clearly visible.

### ✅ `5e2b6aab…` — score 6/10
- Power switch component is not modeled or listed in drawings or BOM.
- Assembly drawings show BOM tables but no visible item balloons.
- STEP ZIP contents and component count are not verified or documented.

### ❌ `46fc494e…` — score 3/10
- No actual transient calculations were performed; results appear non-physical and constant.
- Required plots and profiles are referenced but contain no quantitative data.
- Back-face temperatures equal ambient, contradicting severe heating conditions.
  > 💡 Perform a real transient conduction analysis and regenerate plots, tables, and conclusions from computed results.

### ✅ `3940b7e7…` — score 7/10
- Convergence criteria and engineering goals driving convergence are not described.
- Velocity components are missing; only velocity magnitude is reported.
- STEP CAD model usage is not explicitly referenced in the report.
  > 💡 Add convergence criteria, velocity components, and explicit CAD/STEP model references to strengthen completeness.

### ✅ `5a2d70da…` — score 6/10
- Master tool list lacks subtotal and post-tax grand total within budget.
- Manufacturing steps file lacks detailed operation descriptions and sequencing.
- Capital budget compliance and Suffolk County sales tax calculation not shown.
  > 💡 Add explicit cost totals with tax and expand manufacturing steps to fully meet requirements.

### ✅ `74d6e8b0…` — score 8/10
- Reference list appears truncated or incomplete in the document preview.
- Detailed dosing tables and stepwise prescribing algorithms are limited.
- Risk stratification criteria for low versus moderate risk could be more explicit.
  > 💡 Expand references, add dosing algorithms, and clarify risk stratification to strengthen clinical usability.

### ✅ `81db15ff…` — score 8/10
- NP physician supervision ratios are not specified where collaborative agreements apply.
- Strategic Recommendation sheet contains an empty first row.
- State regulatory nuances for telehealth-specific rules are not explicitly noted.
  > 💡 Add NP supervision ratios where applicable and remove the blank row to improve completeness.

### ✅ `61e7b9c6…` — score 6/10
- Incorrect brand-generic pairing: estradiol/bazedoxifene is Duavee, not Bijuva.
- Duplicate and partially blank rows reduce clarity and professionalism.
- Off-label menopause treatments list appears incomplete for common nonhormonal options.
  > 💡 Correct drug-brand errors, remove blank rows, and add common nonhormonal off-label therapies.

### ✅ `c9bf9801…` — score 6/10
- Guide lacks detailed month-by-month timeline with milestones and deliverables.
- Appendix missing 4-month and 8-month evaluation form templates.
- Content includes truncation/typo indicating incomplete sections.
  > 💡 Add the missing evaluation templates, complete the timeline section, and correct incomplete text.

### ❌ `f1be6436…` — score 4/10
- Document uses offline estimates instead of real-time sourced costs and screenshots.
- Registration, flight, and lodging details lack itemized calculations and dates per physician.
- Conference dates, partial attendance logistics, and shared room cost allocation are missing.
  > 💡 Redo the document using live ACP and travel sources with accurate screenshots, dates, and physician-specific calculations.

### ✅ `41f6ef59…` — score 9/10
- Spreadsheet does not clearly show data validation, dropdowns, or checkboxes in the preview.
  > 💡 Add visible dropdowns or checkboxes for Yes/No fields to clearly demonstrate data validation.

### ✅ `6d2c8e55…` — score 5/10
- Articles are not fully accessible PDFs and may be behind paywalls.
- Several cited journals contradict the requirement for no login or paywall access.
- Compliance with date spacing, weekday preference, and holidays is not demonstrated.
  > 💡 Replace all articles with confirmed open-access PDFs and clearly document compliant scheduling details.

### ✅ `4b98ccce…` — score 6/10
- Excel sheet contents were not verified against all Patient Information Sheet entries.
- Required signature with correct employee name and ID is not confirmed.
- Extraneous CONFIDENCE tag included in professional text response.
  > 💡 Verify Excel data accuracy, confirm proper signing with employee details, and remove nonprofessional tags.

### ✅ `60221cd0…` — score 7/10
- Primary election date appears incorrect for Virginia’s 2025 statewide primaries.
- An extra DOCX file was produced despite only a PDF being required.
  > 💡 Verify all election dates on the official website and deliver only the required PDF.

### ✅ `ef8719da…` — score 6/10
- No hyperlinks to cited background articles are included in the pitch.
- Document ends abruptly, suggesting truncation or incomplete content.
  > 💡 Add clear hyperlinks to sources and ensure the document is complete and polished.

### ✅ `3baa0009…` — score 5/10
- Article file is truncated and ends mid-sentence.
- Forecast describes slower growth, not negative global growth as required.
- Article does not clearly specify AP report date as June 10, 2025.
  > 💡 Complete the article, align claims with task requirements, and clearly cite June 10, 2025 sources.

### ✅ `5d0feb24…` — score 8/10
- Text response summarizes deliverable instead of detailing key editorial findings.
- Confidence score label is unconventional for professional editorial delivery.
- Explicit confirmation of arXiv paper integration is not stated in the text response.
  > 💡 Briefly summarize the most significant science edits and confirm arXiv-based revisions in the response.

### ✅ `6974adea…` — score 6/10
- Text response summarises intent instead of presenting substantive content.
- Presence of CONFIDENCE tag is extraneous and unprofessional.
- Compliance with style guide and interview usage cannot be verified from response.
  > 💡 Provide a brief excerpt or summary of article content and remove non-standard metadata.

### ❌ `1a78e076…` — score 4/10
- Document length appears far below required 10–15 pages.
- Prevalence, morbidity, mortality, and financial impact data are insufficiently detailed.
- Content appears incomplete with truncated sections and unclear reference list.
  > 💡 Expand the paper to full length with complete sections, detailed data analysis, and a finalized references list.

### ✅ `1b9ec237…` — score 7/10
- Text response describes intent rather than summarizing actual slide content.
- References mention JNC guidance, which is outdated compared to current AHA guidelines.
- Unable to verify inclusion of pre-test question and case study without slide preview.
  > 💡 Provide a brief slide-by-slide summary and confirm exclusive use of current AHA hypertension guidelines.

### ✅ `0112fc9b…` — score 8/10
- Assessment lacks an explicit differential diagnosis section.
- Imaging decision rationale such as PECARN criteria not documented.
  > 💡 Add differential diagnoses and briefly document head imaging decision-making criteria.

### ✅ `772e7524…` — score 7/10
- Plan section appears truncated with incomplete follow-up documentation.
- Antibiotic recommendations lack specific drug, dose, and duration.
- Assessment does not explicitly address outpatient versus inpatient criteria.
  > 💡 Complete the Plan with clear follow-up, return precautions, and fully specified antibiotic therapy.

### ✅ `e6429658…` — score 8/10
- Text response describes intent rather than summarizing completed deliverables.
- Extra reference file was included among produced deliverables.
- Appeal letter length cannot be verified from the response.
  > 💡 Summarize final document contents and exclude non-deliverable reference files.

### ❌ `b5d2e6f1…` — score 4/10
- Sales by Brand pivot tab is not present in the analysis file.
- Sales by Store pivot tab is not present in the analysis file.
- Required ST% calculations and grand totals are not demonstrated.
  > 💡 Add the two specified pivot table tabs with correct fields, calculated ST%, and grand totals.

### ✅ `47ef842d…` — score 8/10
- Percent Stores Out of Stock is shown as a fraction rather than a true percentage.
- Active store definition referencing out-of-stock percentage is not clearly documented.
- Graph is delivered separately and not embedded in the Excel summary.
  > 💡 Convert out-of-stock values to true percentages and clarify definitions within the Excel file.

### ✅ `1137e2bb…` — score 8/10
- Summary tab is a static table, not an explicit pivot with drill-down.
- Text response uses future tense despite files already produced.
  > 💡 Convert the SKU summary into a pivot table with enabled PO-level drill-down.

### ✅ `c3525d4d…` — score 5/10
- Final store count inconsistent between matrix file rows and reported total.
- Final store list marks all stores as new without distinguishing originals.
- Added and removed stores are not explicitly identified or summarized.
  > 💡 Reconcile store counts, clearly flag only added/removed stores, and validate all cost and unit calculations.

### ✅ `9a0d8d36…` — score 6/10
- Text response describes intent but provides no substantive content.
- Unable to verify step-by-step calculations and tax specifics in PPTX.
- Vesting timeline tax considerations are not explicitly confirmed.
  > 💡 Include a brief slide-by-slide summary with key calculations and tax outcomes in the text response.

### ✅ `664a42e5…` — score 6/10
- No verifiable evidence slides address all specified ILIT requirements.
- 2025 gift tax exclusion amount and Crummey timing not explicitly confirmed.
- Side-by-side ILIT comparison content cannot be validated from text.
  > 💡 Provide a slide outline or screenshots confirming each required topic is fully addressed.

### ✅ `feb5eefc…` — score 6/10
- PDF appears truncated with incomplete sentences and missing conclusion.
- No quantitative projections or calculations illustrating tax outcomes.
- Recommendation is not clearly stated or decisively justified.
  > 💡 Provide a complete, polished PDF with numeric scenarios and a clear final recommendation.

### ✅ `3600de06…` — score 6/10
- Slide count of exactly 10 is not verified.
- Explicit FINRA and NAIC citations within slides are unconfirmed.
- Required comparisons and penalty details cannot be validated from preview.
  > 💡 Open the PPT to verify slide count, content completeness, and clear FINRA/NAIC sourcing.

### ✅ `c657103b…` — score 6/10
- Starting 2025 balance exceeds stated $3.5M anticipated value.
- Spreadsheet omits taxes due on Roth conversion amounts.
- No explicit calculation or summary of projected tax savings shown.
  > 💡 Align assumptions to $3.5M, add conversion tax and cumulative tax savings calculations, and verify presentation template compliance.

### ✅ `f9f82549…` — score 6/10
- Did not create separate PowerPoint files for each flowchart header.
- Produced additional unrequested files, including extra PPT and PNG images.
- Flowchart PDF lacks visible process connections or decision paths.
  > 💡 Create one PowerPoint per flowchart header and remove unrequested supplementary files.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance end time extends to 1:20 a.m., exceeding the client’s requested 1:00 a.m. window.
- Report states subject attended a book club despite background claiming she missed recent meetings.
- PNG file appears unnecessary alongside the required PDF deliverable.
  > 💡 Clarify timeline justifications, reconcile background details, and remove nonessential files from delivery.

### ✅ `84322284…` — score 8/10
- Text response describes intent rather than summarizing findings.
- Reporting period covers only five days of the stated week.
- Timeline bullets use inconsistent formatting characters.
  > 💡 Include a brief executive summary in the text response and ensure full-week coverage consistency.

### ✅ `a46d5cd2…` — score 7/10
- Text response describes intent instead of summarizing investigative findings.
- Report lacks clearly embedded or referenced photographs as evidence.
- Text response omits case-specific details and conclusions.
  > 💡 Provide a concise written summary and explicitly embed or reference photographic evidence in the report.

### ❌ `6241e678…` — score 4/10
- Schedule cells contain no dates or durations, making the timeline unusable.
- Required color-coding for phases and client tasks is not evident or implemented.
- Several required phases are missing, including production shoot, edit rounds, and final delivery.
  > 💡 Populate dates, apply clear color-coding, and add all required phases through final delivery.

### ✅ `e14e32ba…` — score 6/10
- Business hours are missing for all listed restaurants.
- Physical locations and addresses are not provided.
- Image links point to websites, not specific photos.
  > 💡 Add addresses, hours, explicit website links, and direct photo URLs for each deli.

### ❌ `e4f664ea…` — score 3/10
- Response provides a promise, not the actual screenplay content.
- Screenplay formatting and scenes are not visible or verifiable.
- No evidence script follows show-not-tell or page-length requirements.
  > 💡 Include the full production-ready screenplay text and ensure files clearly contain the script.

### ✅ `a079d38f…` — score 5/10
- Audio Recording Kit daily rate is incorrect compared to provided service fees.
- Time estimate is not clearly broken out or explained beyond total hours.
- Cost breakdown appears incomplete or truncated in the provided preview.
  > 💡 Correct the audio kit rate, clarify time assumptions, and ensure full cost line items are visible.

### ❌ `02aa1805…` — score 3/10
- No Illinois EPA well data was extracted or reviewed.
- Excel workbook contains zero wells and only placeholder structure.
- No viable wells were identified or highlighted as top options.
  > 💡 Retrieve Illinois EPA factsheet data, populate the workbook, and provide data-driven well recommendations.

### ✅ `fd6129bd…` — score 7/10
- Text response uses future tense instead of confirming completed deliverables.
- Response does not summarize key SOP elements or confirm alignment to session inputs.
  > 💡 Revise the response to explicitly confirm completion and briefly summarize SOP and form contents.

### ✅ `ce864f41…` — score 8/10
- Timekeeping export shows 25 team members instead of the stated 23 employees.
- Executive summary lacks specific departmental or individual utilization percentages.
  > 💡 Validate employee counts and add quantified utilization results to strengthen executive insights.

### ✅ `58ac1cc5…` — score 8/10
- Text response includes unnecessary CONFIDENCE tag.
- Extra blank change control form included without explanation.
  > 💡 Remove extraneous confidence labeling and briefly explain inclusion of supplemental blank forms.

### ✅ `3c19c6d1…` — score 6/10
- The text response does not confirm inclusion of all specifically required slides and contents.
- No evidence is provided that slides 1–4 meet the exact dated and structured requirements.
- The response relies on claims rather than summarising actual report findings.
  > 💡 Explicitly summarise each required slide’s content and confirm compliance with all specified requirements.

### ✅ `a99d85fc…` — score 6/10
- Annual and monthly rent matrices with full breakdowns are not clearly present.
- Color-coding and light-blue editable variable cells are not evident.
- Notes section and reconciliation between annual and monthly totals are missing.
  > 💡 Expand the workbook to include complete annual and monthly matrices with notes, reconciliation, and clear color-coded editable inputs.

### ❌ `55ddb773…` — score 3/10
- Required violation types and qualifying questions were not transcribed from the attached PDF.
- Architectural regulations were not individually listed with required questions.
- Form relies on placeholders instead of complete, usable inspection guidance.
  > 💡 Manually transcribe all violation types and details from the attached PDF into the questionnaire.

### ❌ `1e5a1d7f…` — score 3/10
- The .docx file lacks the required table with four specified columns.
- No weekly schedule tasks or time-based activities are populated.
- The document contains only introductory text without actionable content.
  > 💡 Populate the .docx with a complete table detailing time, activities, trackers, and week cycles.

### ✅ `ed2bc14c…` — score 8/10
- Exit survey analysis does not explicitly show categorization into five defined departure reasons.
  > 💡 Add a brief table summarizing all five exit categories and counts to strengthen data transparency.

### ✅ `46bc7238…` — score 6/10
- One-page flyer template content is missing from the PDF.
- Next Steps section is not clearly included as a dedicated page.
- Images appear as placeholders, not verified free stock photos.
  > 💡 Add a clear flyer template page, explicit Next Steps section, and licensed free stock images.

### ✅ `2d06bc0a…` — score 7/10
- LOI does not include an explicit expiration date for acceptance.
- Broker section appears incomplete or truncated in the document.
  > 💡 Add a clear 7–10 day expiration date and complete the broker representation section.

### ✅ `fd3ad420…` — score 9/10
- Document does not explicitly reference FL, GA, and NC licensing scope.
- Commission splits are examples but lack stated flexibility ranges.
  > 💡 Add a brief state-scope statement and optional split ranges to strengthen clarity.

### ✅ `0818571f…` — score 6/10
- Listings are representative and not verified active Crexi or LoopNet offerings from June 2025 onward.
- Photos and maps are explicitly representative, not actual property-specific marketing materials.
- No evidence of direct sourcing links or listing IDs from public deal platforms.
  > 💡 Replace representative assets with verified active listings including platform links, real photos, and confirmed deal data.

### ❌ `6074bba3…` — score 3/10
- PDF contains extensive placeholder text instead of populated CMA data.
- Comparable sales and active listings are not filled with real properties.
- Pricing recommendations and valuation range fields are left blank.
  > 💡 Populate the CMA with real market data, completed fields, and finalized graphs before delivery.

### ✅ `5ad0c554…` — score 7/10
- Does not explicitly identify or reference specific items from the 132 Things REALTORS Do list.
- Brochure layout does not clearly indicate or format double-sided printing.
- Content does not explicitly mention first-time buyer education incentives or programs.
  > 💡 Add explicit references to numbered items from the 132 Things list and format pages as front and back panels.

### ❌ `11593a50…` — score 4/10
- Exactly 15 homes included, violating the less-than-15 requirement.
- Missing required columns like status, type, and list date.
- No actual photos included for each home.
  > 💡 Reduce listings to under 15, add missing data fields, and include real property photos from MLS.

### ✅ `94925f49…` — score 6/10
- School metrics and salaries are estimated rather than verified with concrete cited data.
- Home listings are illustrative examples, not actual active MLS listings.
- Source citations lack specific links or timestamps for verification.
  > 💡 Replace estimates with fully cited, current data and include real active listings with addresses.

### ✅ `90f37ff3…` — score 7/10
- Comparable listings do not show transaction or listing dates within the three-year requirement.
- Comparable addresses lack full street numbers, reducing verification clarity.
- Market data sources are not explicitly cited in the report.
  > 💡 Add dated, fully addressed comparables with cited sources to strengthen data credibility.

### ✅ `1bff4551…` — score 7/10
- Original song lacks a specific YouTube link.
- No evidence songs are represented in the Institute’s collection.
- Set list likely under the required 45-minute duration.
  > 💡 Add collection references, precise song timings, and a valid link for the original song.

### ✅ `650adcb1…` — score 6/10
- Dustin Herman’s requested days off from 3/11–3/13 are not marked as requested.
- Schedule key wording differs from required labels and may confuse users.
- Color coding cannot be verified and may be missing or inconsistent.
  > 💡 Correct requested day markings, align key labels exactly, and verify all required color coding.

### ✅ `01d7e53e…` — score 6/10
- Text response does not summarize or verify inclusion of all required agreement terms.
- No evidence shown of federal, state, or city compliance language included.
- Primary contact details and mutual indemnification are not confirmed in preview.
  > 💡 Provide a brief compliance checklist confirming each required element is included in the draft agreement.

### ✅ `a73fbc98…` — score 6/10
- No evidence electricity needs were considered against outlet locations.
- Plan does not address avoiding similar vendors being placed adjacent.
- At least one vendor entry lacks assigned table numbers.
  > 💡 Explicitly document electricity mapping, product-type spacing logic, and verify all vendors have complete assignments.

### ✅ `0ec25916…` — score 8/10
- DOCX file is incomplete and lacks the SBAR table content.
- PDF table structure is not visually explicit as a two-column grid.
  > 💡 Ensure all distributed formats contain identical, clearly tabulated SBAR content.

### ✅ `116e791e…` — score 7/10
- PDF is two pages, not the required one-page care plan.
- Text response promises a one-page PDF but delivered content exceeds one page.
  > 💡 Condense content to fit a single-page PDF and verify formatting before delivery.

### ✅ `dd724c67…` — score 6/10
- Facility list is incomplete and does not include all Long Island hospitals.
- Rehabilitation facilities are missing entirely from the contact list.
- TFU guidance is not explicitly validated against ACO REACH PY 2025 methodology.
  > 💡 Expand to a comprehensive hospital and rehabilitation list and verify TFU details directly from CMS PY 2025 documentation.

### ✅ `7151c60a…` — score 6/10
- Pre-screening checklist is not presented in a table format.
- Page numbers in the checklist footer are missing or not evident.
- Patient name and date of birth are not shown on each page.
  > 💡 Revise the checklist into a table with page numbers and repeat patient identifiers on every page.

### ❌ `90edba97…` — score 3/10
- Monthly lab results were not entered into the tracker despite task requirements.
- No monthly treatment or medication changes were documented per protocols.
- Excel file contains placeholder notes instead of required patient lab data.
  > 💡 Populate the tracker using Patient Lab Reports and document protocol-driven monthly treatment decisions.

### ✅ `91060ff0…` — score 5/10
- Text contains encoding artifacts and severe typographical corruption.
- Poster lacks required visuals such as tables, icons, or product comparisons.
- No clear indication the PDF is formatted to 36 x 24 inches.
  > 💡 Fix text encoding, add clear visuals, and confirm correct poster dimensions.

### ✅ `8384083a…` — score 6/10
- Multiple table entries contain typos and garbled text reducing professional quality.
- Some SIG and package descriptions are poorly formatted and hard to interpret.
- Several medication rows have spacing and labeling errors affecting clarity.
  > 💡 Proofread and reformat the table to correct typos, spacing, and readability issues.

### ✅ `045aba2e…` — score 8/10
- Checklists lack explicit citations to California law sections or self-assessment questions.
- Some high-risk compliance items are broadly worded without measurable criteria.
  > 💡 Add brief law or self-assessment references and measurable standards to strengthen audit defensibility.

### ❌ `f2986c1f…` — score 3/10
- No medications were identified; all fields were marked NA.
- Required Drugs.com image-based identification was not performed.
- Spreadsheet includes only one row despite multiple medications likely shown.
  > 💡 Identify each pill from the image using Drugs.com and fully populate rows with MedlinePlus links.

### ✅ `ffed32d8…` — score 5/10
- PDF lacks drug cost and vial cost breakdowns required by the analysis.
- Comparative table shows only revenue, not reimbursement and expense components.
- Text response describes intent rather than summarizing actual analysis results.
  > 💡 Revise the PDF to include full cost, reimbursement, and revenue calculations for each fill model.

### ✅ `b3573f20…` — score 8/10
- Limited financial and pricing detail questions for distribution assessment.
- No explicit page separation cues within the PDF content.
  > 💡 Add pricing, margins, returns, and forecasting questions to strengthen readiness evaluation.

### ✅ `a69be28f…` — score 8/10
- Text claims PNG slide exports, but no PNG files were delivered.
  > 💡 Remove the PNG claim or include the referenced PNG slide exports.

### ✅ `788d2bc6…` — score 6/10
- TikTok Shop, influencer, and analytics services are not clearly covered in the deck.
- Slides appear largely text-based with limited visual elements or creative samples.
- Response references technical limitations, reducing professionalism of a client-facing deliverable.
  > 💡 Add dedicated TikTok and influencer slides with visuals and remove internal limitation notes.

### ✅ `74ed1dc7…` — score 8/10
- Initial text response described intent rather than summarizing key proposal outcomes.
- Proposal includes renaming Bulk despite instruction to add beyond existing types.
  > 💡 Add a brief executive summary highlighting decisions required and quantified reporting benefits.

### ✅ `69a8ef86…` — score 8/10
- An extra file was produced that was not requested in the original task.
- Minor typo detected in external guidelines text preview.
- Text response summarizes intent instead of highlighting key completed requirements.
  > 💡 Remove the extra file, correct typos, and briefly confirm all required deadlines and roles are documented.

### ✅ `ab81b076…` — score 8/10
- Visual examples section lacks clearly embedded images within the PDF.
  > 💡 Embed annotated photos and add specific parts distribution center contact details.

### ✅ `19403010…` — score 6/10
- Sections 3–5 are not clearly presented with the required nine columns.
- Top drivers, increases, and detractors are not visibly summarized with totals.
- Excel layout lacks clear column headers for multi-section analysis.
  > 💡 Rebuild the recap sheet with clearly labeled Sections 1–5 and all required columns and totals.

### ✅ `7ed932dd…` — score 5/10
- Spreadsheet lacks visual highlighting for rounded pallets and expedited deliveries.
- Delivered days of inventory metric is not explicitly included.
- Only a small subset of SKUs is shown despite hundreds in source data.
  > 💡 Add delivered days of inventory, apply required highlights, and include all SKUs needing additional shipments.

### ✅ `b57efde3…` — score 6/10
- Did not review or reference the official Aqua Nor 2025 exhibitor list.
- Prospect list is very limited compared to expected scope of hundreds of exhibitors.
- Spreadsheet lacks contact details or fields to connect with leads at the event.
  > 💡 Expand the spreadsheet using the official exhibitor list and add contact and booth information.

### ❌ `15d37511…` — score 3/10
- Spreadsheet lacks numeric pricing, costs, margins, and totals.
- Tiered pricing and 15% discount not applied.
- Consumables revenue and margin not modeled.
  > 💡 Populate the spreadsheet with pricing, costs, discounts, consumables, and compute all margins and totals.

### ✅ `bb863dd9…` — score 6/10
- Quotation file lacks a WHO documentation link explaining IEHK structure.
- EXW incoterm is not explicitly stated in the quotation.
- Quotation date is missing to substantiate 30-day validity.
  > 💡 Add WHO link, explicitly state EXW terms, and include quotation date in the Excel file.

### ✅ `fe0d3941…` — score 8/10
- Text response includes an unnecessary CONFIDENCE tag.
- An extra DOCX survey file was produced beyond requirements.
  > 💡 Remove extraneous confidence tags and limit outputs strictly to requested file types.

### ✅ `6a900a40…` — score 6/10
- Text response is descriptive only and does not summarize key quotation figures.
- Use of CONFIDENCE tag is unprofessional and not requested.
- Red font requirement for freight validity cannot be verified from preview.
  > 💡 Include a concise summary of prices, lead times, and totals directly in the response.

### ✅ `9efbcd35…` — score 6/10
- Lacks explicit MSCI index performance figures and citations.
- Analysis is generic and not clearly sourced to required publications.
- Disclosure of data limitations undermines task requirements.
  > 💡 Include specific MSCI returns with citations and reference named news sources explicitly.

### ✅ `1d4672c8…` — score 5/10
- Return data are simulated, not extracted from MSCI as explicitly required.
- Excel workbook lacks a correlation matrix tab comparing index returns.
- PDF analysis is brief and missing detailed portfolio recommendations.
  > 💡 Use official MSCI data, add a correlation matrix sheet, and expand the analytical depth.

### ✅ `4de6a529…` — score 6/10
- Several required sub-asset classes from the reference lists are missing.
- Column headers and formatting contain typos and line-break errors.
- Change indicators and conviction levels are inconsistently applied across rows.
  > 💡 Expand coverage to all referenced sub-asset classes and clean formatting for consistency.

### ✅ `4c4dc603…` — score 5/10
- Missing specific salient numbers like target raise, target IRR, and price per token.
- Key economics lack valuation methodology, pricing frequency, and concrete token supply details.
- Team section lacks named profiles and roles of key members.
  > 💡 Add concrete financial metrics, detailed token economics, and named team profiles sourced directly from the IM.

### ✅ `bb499d9c…` — score 7/10
- Text response summarizes deliverables but provides no substantive process content.
- Cannot verify all required sections without reviewing the Word document.
- No confirmation the document is within the 25-page limit.
  > 💡 Include an executive summary of each required section in the text response for verifiability.

### ✅ `5349dd7b…` — score 6/10
- Carrier rate increases were assumed averages, not researched via search engines as required.
- Flat rate prices are undocumented assumptions without cited published carrier sources.
- Text claims PNG renderings were provided, but no such files exist.
  > 💡 Redo the analysis using cited carrier sources and remove claims of unproduced deliverables.

### ✅ `a4a9195c…` — score 8/10
- No revision history or document control section included.
- ESD grounding test frequencies are not specified.
- Environmental limits lack specific humidity ranges.
  > 💡 Add document control, testing frequencies, and explicit humidity limits to strengthen compliance and training value.

### ✅ `552b7dd0…` — score 8/10
- Text response does not summarize key findings or recommendations explicitly.
  > 💡 Include a brief written summary of key metrics and recommendations in the text response.

### ✅ `76418a2c…` — score 6/10
- Manifest lacks pick ticket numbers and customer names from WMS files.
- Spreadsheet headers and structure do not match a professional shipment manifest.
- Text response promises consolidation logic but does not explain applied calculations.
  > 💡 Include all required order details with clear headers and briefly document calculation logic.

### ❌ `0e386e32…` — score 3/10
- ZIP size far too small to contain promised complete scaffold.
- No verifiable source files or documentation content provided for inspection.
- Privacy logic and requirements not fully implemented or evidenced.
  > 💡 Include a complete, inspectable codebase with contracts, frontend, documentation, and adequate file contents.

### ✅ `7de33b48…` — score 6/10
- Zip contents are not verifiable, preventing confirmation of utility implementation and tests.
- No explicit evidence of message queuing or non-interference across multiple components.
- ARIA role and live-region attributes are not demonstrated in provided previews.
  > 💡 Include full source previews or summaries of zip contents proving ARIA22 compliance and queuing behavior.

### ❌ `4122f866…` — score 3/10
- Terraform configuration files are not provided or visible.
- Lambda function code content cannot be verified.
- README lacks required detailed setup and configuration instructions.
  > 💡 Include explicit Terraform files and full Lambda code with comprehensive documentation.

### ❌ `2c249e0f…` — score 3/10
- OpenAPI 3.0 YAML specification was not produced.
- Text response claims two files but only one exists.
- data_flow.txt is incomplete and cuts off required description.
  > 💡 Provide the full OpenAPI 3.0 YAML file and complete data_flow.txt as specified.

## Failure Analysis

The 21 errors and 59 retried tasks indicate intermittent execution instability rather than systemic failure. Retries were relatively high compared to total errors, suggesting transient issues such as subprocess timeouts, context overload, or response formatting problems rather than persistent task incompatibility. Sectors with lower success counts (e.g., Wholesale Trade and Finance) may involve prompts that are more sensitive to such execution constraints.

## Recommendations

1. Investigate high-latency sectors (Information, Manufacturing) to determine whether prompt length, instruction complexity, or output formatting requirements can be optimized to reduce execution time.
2. Analyze retried tasks to identify common prompt structures or subprocess conditions that trigger retries, and adjust execution parameters or prompt templates accordingly.
3. Consider targeted prompt refinement in sectors with lower self-assessed QA confidence to improve clarity and reduce model uncertainty while maintaining the current task completion rate.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 7 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 18 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 18 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 5 file(s)
- `17111c03…` (Government): 5 file(s)
- `c44e9b62…` (Government): 6 file(s)
- `99ac6944…` (Information): 6 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `38889c3b…` (Information): 2 file(s)
- `ff85ee58…` (Information): 1 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 1 file(s)
- `24d1e93f…` (Manufacturing): 2 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 2 file(s)
- `bbe0a93b…` (Government): 3 file(s)
- `85d95ce5…` (Government): 5 file(s)
- `76d10872…` (Government): 6 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 6 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 9 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 2 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 3 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 3 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 4 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 5 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `61717508…` (Finance and Insurance): 3 file(s)
- `0ed38524…` (Finance and Insurance): 3 file(s)
- `d025a41c…` (Finance and Insurance): 4 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `ec2fccc9…` (Information): 2 file(s)
- `8c8fc328…` (Information): 2 file(s)
- `e222075d…` (Information): 5 file(s)
- `c94452e4…` (Information): 3 file(s)
- `75401f7c…` (Information): 4 file(s)
- `a941b6d8…` (Information): 2 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 3 file(s)
- `9e8607e7…` (Finance and Insurance): 3 file(s)
- `c7d83f01…` (Finance and Insurance): 4 file(s)
- `a1963a68…` (Finance and Insurance): 3 file(s)
- `b78fd844…` (Finance and Insurance): 4 file(s)
- `4520f882…` (Finance and Insurance): 3 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `e996036e…` (Wholesale Trade): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 4 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 3 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 4 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 11 file(s)
- `8c823e32…` (Government): 3 file(s)
- `eb54f575…` (Government): 3 file(s)
- `11e1b169…` (Government): 1 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 1 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `efca245f…` (Manufacturing): 3 file(s)
- `68d8d901…` (Manufacturing): 3 file(s)
- `bd72994f…` (Retail Trade): 2 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 5 file(s)
- `cecac8f9…` (Retail Trade): 4 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 1 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `8a7b6fca…` (Manufacturing): 1 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 1 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 8 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 4 file(s)
- `46fc494e…` (Manufacturing): 3 file(s)
- `3940b7e7…` (Manufacturing): 4 file(s)
- `5a2d70da…` (Manufacturing): 6 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
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
- `e6429658…` (Health Care and Social Assistance): 4 file(s)
- `b5d2e6f1…` (Wholesale Trade): 2 file(s)
- `47ef842d…` (Wholesale Trade): 3 file(s)
- `1137e2bb…` (Wholesale Trade): 3 file(s)
- `c3525d4d…` (Wholesale Trade): 5 file(s)
- `9a0d8d36…` (Finance and Insurance): 2 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `feb5eefc…` (Finance and Insurance): 1 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 6 file(s)
- `f9f82549…` (Retail Trade): 6 file(s)
- `57b2cdf2…` (Retail Trade): 5 file(s)
- `84322284…` (Retail Trade): 4 file(s)
- `a46d5cd2…` (Retail Trade): 5 file(s)
- `6241e678…` (Information): 1 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `e4f664ea…` (Information): 5 file(s)
- `a079d38f…` (Information): 3 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 5 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 7 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 2 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 3 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 7 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 4 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 15 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 5 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 5 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 5 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 2 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 4 file(s)
- `a73fbc98…` (Government): 5 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 3 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 5 file(s)
- `90edba97…` (Health Care and Social Assistance): 7 file(s)
- `91060ff0…` (Retail Trade): 1 file(s)
- `8384083a…` (Retail Trade): 1 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 2 file(s)
- `ffed32d8…` (Retail Trade): 3 file(s)
- `b3573f20…` (Wholesale Trade): 1 file(s)
- `a69be28f…` (Wholesale Trade): 3 file(s)
- `788d2bc6…` (Wholesale Trade): 3 file(s)
- `74ed1dc7…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `ab81b076…` (Wholesale Trade): 5 file(s)
- `19403010…` (Wholesale Trade): 2 file(s)
- `7ed932dd…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 3 file(s)
- `fe0d3941…` (Wholesale Trade): 6 file(s)
- `6a900a40…` (Wholesale Trade): 6 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 2 file(s)
- `4de6a529…` (Finance and Insurance): 4 file(s)
- `4c4dc603…` (Finance and Insurance): 4 file(s)
- `bb499d9c…` (Finance and Insurance): 4 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 4 file(s)
- `76418a2c…` (Manufacturing): 4 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 3 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 1 file(s)
