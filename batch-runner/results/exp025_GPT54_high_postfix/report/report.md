# Experiment Report: GPT-5.4 High Reasoning Baseline (post silent-corruption fix)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp025_GPT54_high_postfix` |
| **Condition** | GPT-5.4 reasoning=high + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4 |
| **Execution Mode** | subprocess |
| **Date** | 2026-05-20 |
| **Duration** | 501m 32s |
| **Generated At** | 2026-05-20T14:00:15.467215+00:00 |
| 🤗 HF Dataset | [exp025_GPT54_high_postfix](https://huggingface.co/datasets/HyeonSang/exp025_GPT54_high_postfix) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp025_GPT54_high_postfix/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This run evaluated GPT-5.4 in high-reasoning mode with a gpt-audio-1.5 preprocessor, executed via subprocess, after the silent-corruption fix. Across 220 tasks, 181 completed successfully for an 82.3% task completion rate. There were 17 explicit errors and 66 retried tasks, indicating that end-to-end execution was generally recoverable but still required substantial retry handling.

LLM-evaluated quality was moderate overall. The average self-assessed confidence score was 6.47/10, with observed scores ranging from 2 to 9. That pattern suggests most completed outputs were usable but not consistently high-confidence, with some low-confidence outliers still present despite the strong completion rate.

By sector, Government was the strongest balanced performer at 23/25 success with the highest average self-assessed confidence at 7.1/10, while Retail Trade was also efficient at 19/20 success and relatively low latency. Real Estate and Rental and Leasing had the weakest completion count at 18/25, and Health Care plus Manufacturing showed lower LLM-evaluated quality at 6.0/10. Deliverable file generation quality, inferred from successful completions and self-QA, appears mostly acceptable on completed runs, but the retry volume suggests output generation robustness is not yet fully stable.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 181 (82.3%) |
| Errors | 17 |
| Retried Tasks | 66 |
| Avg QA Score | 6.47/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 73,073ms |
| Max Latency | 277,955ms |
| Total LLM Time | 16075s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 0 |
| Successfully generated | 0 (0.0%) |
| Failed → dummy created | 0 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 23 | 23 | 0 |
| 2 | 43 | 4 | 39 |

## Quality Analysis

The QA profile is centered in the mid range rather than the high end. An average self-assessed confidence of 6.47/10, combined with a minimum of 2 and maximum of 9, indicates broad coverage of task types but uneven confidence in final outputs. In practical terms, the run produced many usable deliverables, yet relatively few that the model rated near the top of the scale.

Sector differences were noticeable. Government led on LLM-evaluated quality at 7.1/10 and also maintained strong completion at 23/25, making it the clearest high-confidence segment in this run. Finance and Insurance also performed well at 22/25 success and 6.9/10, though with the highest average latency. Health Care and Social Assistance and Manufacturing both averaged 6.0/10, marking them as weaker quality areas even though each still reached 20/25 completion. Real Estate and Rental and Leasing had the lowest completion rate at 18/25 with only middling quality at 6.3/10.

Latency does not show a simple positive relationship with quality. Finance had the longest average latency at 95,617 ms and above-average quality, but Information was also slow at 84,356 ms with only 6.3/10. Conversely, Government and Retail were among the faster sectors at 59,529 ms and 55,938 ms while still posting strong self-assessed confidence. This suggests extra runtime was not a reliable path to better deliverables in this configuration.

No occupation-level breakout was provided, so occupation-specific differences cannot be verified from the available summary. Based on the reported metrics, deliverable file generation quality was generally serviceable when tasks completed, but not uniformly strong: the mid-range self-QA scores imply frequent need for review, and the 66 retries indicate that file or output generation often depended on recovery rather than clean first-pass execution.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 22 | 88.0% | 6.91/10 | 95,617ms |
| Government | 25 | 23 | 92.0% | 7.08/10 | 59,529ms |
| Health Care and Social Assistance | 25 | 20 | 80.0% | 5.96/10 | 72,287ms |
| Information | 25 | 21 | 84.0% | 6.3/10 | 84,356ms |
| Manufacturing | 25 | 20 | 80.0% | 6.04/10 | 72,243ms |
| Professional, Scientific, and Technical  | 25 | 19 | 76.0% | 6.4/10 | 74,029ms |
| Real Estate and Rental and Leasing | 25 | 18 | 72.0% | 6.26/10 | 75,693ms |
| Retail Trade | 20 | 19 | 95.0% | 6.75/10 | 55,938ms |
| Wholesale Trade | 25 | 19 | 76.0% | 6.57/10 | 64,534ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 9/10 | 50412ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 6/10 | 51908ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 61674ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 4 | 5/10 | 109423ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 5/10 | 68136ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ⚠️ qa_failed | Yes | 1 | 2/10 | 41277ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 7/10 | 25731ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 9/10 | 61186ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 9/10 | 39319ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 5 | 6/10 | 58212ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 6 | 6/10 | 106397ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 6/10 | 67513ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 7 | 6/10 | 131887ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 3 | 7/10 | 55452ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 5/10 | 47501ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 6/10 | 67027ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 7/10 | 66553ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 6/10 | 57097ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ⚠️ qa_failed | Yes | 1 | 4/10 | 65259ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | Yes | 3 | 5/10 | 79248ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 2 | 9/10 | 62109ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 4 | 6/10 | 91868ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 6 | 6/10 | 70871ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | Yes | 2 | 6/10 | 80291ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | 6/10 | 75838ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 7/10 | 37788ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 7/10 | 24148ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 6/10 | 21155ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 26487ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | Yes | 2 | 6/10 | 63388ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 6/10 | 50661ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 6/10 | 58421ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 6 | 7/10 | 52557ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 1 | 9/10 | 79365ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 3 | 7/10 | 87706ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | Yes | 1 | 5/10 | 43441ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 72523ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ⚠️ qa_failed | Yes | 1 | 4/10 | 55989ms |
| 39 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 62246ms |
| 40 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 9/10 | 61050ms |
| 41 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 6/10 | 42226ms |
| 42 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 4 | 7/10 | 45003ms |
| 43 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 9/10 | 39258ms |
| 44 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 9/10 | 73058ms |
| 45 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 6 | 9/10 | 55367ms |
| 46 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 7/10 | 32792ms |
| 47 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 7/10 | 27007ms |
| 48 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 9/10 | 69749ms |
| 49 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | 7/10 | 109665ms |
| 50 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | 7/10 | 65890ms |
| 51 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 7/10 | 87396ms |
| 52 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 9/10 | 27407ms |
| 53 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 7/10 | 100593ms |
| 54 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 9/10 | 176634ms |
| 55 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 6/10 | 88564ms |
| 56 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 7 | 6/10 | 117165ms |
| 57 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 153876ms |
| 58 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 6/10 | 108453ms |
| 59 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 4 | 7/10 | 86919ms |
| 60 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 111914ms |
| 61 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 89232ms |
| 62 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 52132ms |
| 63 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 5/10 | 50960ms |
| 64 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 7/10 | 56972ms |
| 65 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 104680ms |
| 66 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 3 | 9/10 | 48135ms |
| 67 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 53998ms |
| 68 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 88705ms |
| 69 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 59504ms |
| 70 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 5 | 6/10 | 57592ms |
| 71 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 6/10 | 76223ms |
| 72 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 9 | 5/10 | 65620ms |
| 73 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 1 | 7/10 | 32748ms |
| 74 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 7 | 6/10 | 118493ms |
| 75 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 50645ms |
| 76 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 3 | 9/10 | 61103ms |
| 77 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 3 | 9/10 | 70406ms |
| 78 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 36164ms |
| 79 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 9/10 | 61219ms |
| 80 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | 7/10 | 97794ms |
| 81 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 5/10 | 122359ms |
| 82 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 7 | 6/10 | 171529ms |
| 83 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 80761ms |
| 84 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 7/10 | 39153ms |
| 85 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 7/10 | 112216ms |
| 86 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 85656ms |
| 87 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 21 | 7/10 | 87723ms |
| 88 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 7 | 6/10 | 59909ms |
| 89 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 100375ms |
| 90 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 33192ms |
| 91 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 49182ms |
| 92 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 8 | 7/10 | 108752ms |
| 93 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 9/10 | 29690ms |
| 94 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 6/10 | 49879ms |
| 95 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 9/10 | 28611ms |
| 96 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 32557ms |
| 97 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 6/10 | 27879ms |
| 98 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | 5/10 | 76607ms |
| 99 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 191371ms |
| 100 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 7/10 | 57178ms |
| 101 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | 6/10 | 101841ms |
| 102 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 7/10 | 69606ms |
| 103 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 60176ms |
| 104 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 8/10 | 54839ms |
| 105 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 6/10 | 76036ms |
| 106 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 65687ms |
| 107 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 4 | 6/10 | 86050ms |
| 108 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 7/10 | 75448ms |
| 109 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 6/10 | 76183ms |
| 110 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 5 | 6/10 | 85367ms |
| 111 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 8/10 | 62704ms |
| 112 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 7/10 | 37565ms |
| 113 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 76739ms |
| 114 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 1 | 6/10 | 83203ms |
| 115 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 4 | 5/10 | 83379ms |
| 116 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 7/10 | 64102ms |
| 117 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 9/10 | 92121ms |
| 118 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 6/10 | 74868ms |
| 119 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 6/10 | 101756ms |
| 120 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 9/10 | 93714ms |
| 121 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 7/10 | 86708ms |
| 122 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 7/10 | 113107ms |
| 123 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 7/10 | 100866ms |
| 124 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 9 | 7/10 | 135080ms |
| 125 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 65489ms |
| 126 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 69117ms |
| 127 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 15 | 6/10 | 100309ms |
| 128 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 5/10 | 59337ms |
| 129 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 9/10 | 40637ms |
| 130 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 2 | 9/10 | 60739ms |
| 131 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 73313ms |
| 132 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 43179ms |
| 133 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 6/10 | 41550ms |
| 134 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 6/10 | 39949ms |
| 135 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 5 | 7/10 | 76228ms |
| 136 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 4 | 6/10 | 49777ms |
| 137 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 6 | 6/10 | 60611ms |
| 138 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 6/10 | 50528ms |
| 139 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 35545ms |
| 140 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 9/10 | 83910ms |
| 141 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 7/10 | 109343ms |
| 142 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 62329ms |
| 143 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 7/10 | 57571ms |
| 144 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 38398ms |
| 145 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 7/10 | 48448ms |
| 146 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 5/10 | 91870ms |
| 147 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 6/10 | 88358ms |
| 148 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 9/10 | 214219ms |
| 149 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 9/10 | 45776ms |
| 150 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 6 | 6/10 | 108911ms |
| 151 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 6/10 | 57799ms |
| 152 | `476db143…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 39146ms |
| 153 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 51596ms |
| 154 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 63402ms |
| 155 | `e222075d…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 91026ms |
| 156 | `c94452e4…` | Information | Film and Video Edi | ⚠️ qa_failed | Yes | 3 | 4/10 | 187185ms |
| 157 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 277955ms |
| 158 | `a941b6d8…` | Information | Film and Video Edi | ⚠️ qa_failed | Yes | 5 | 4/10 | 152430ms |
| 159 | `8079e27d…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 75811ms |
| 160 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 7 | 9/10 | 124339ms |
| 161 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 98071ms |
| 162 | `e996036e…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 58602ms |
| 163 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ⚠️ qa_failed | Yes | 2 | 4/10 | 75858ms |
| 164 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ⚠️ qa_failed | Yes | 2 | 2/10 | 44777ms |
| 165 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ⚠️ qa_failed | Yes | 1 | 4/10 | 83482ms |
| 166 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ⚠️ qa_failed | Yes | 3 | 4/10 | 97169ms |
| 167 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 3 | 6/10 | 51645ms |
| 168 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 2 | 5/10 | 82480ms |
| 169 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 54525ms |
| 170 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 6/10 | 38437ms |
| 171 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 6/10 | 57752ms |
| 172 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 33894ms |
| 173 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 10 | 7/10 | 99446ms |
| 174 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 76456ms |
| 175 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ⚠️ qa_failed | Yes | 3 | 4/10 | 73451ms |
| 176 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 6/10 | 86954ms |
| 177 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 2 | 6/10 | 58193ms |
| 178 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 3 | 7/10 | 58700ms |
| 179 | `f1be6436…` | Health Care and Social | Medical Secretarie | ⚠️ qa_failed | Yes | 5 | 3/10 | 77978ms |
| 180 | `a0552909…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 7/10 | 47106ms |
| 181 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 13 | 6/10 | 69350ms |
| 182 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 75645ms |
| 183 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 182520ms |
| 184 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 49861ms |
| 185 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 1 | 6/10 | 51968ms |
| 186 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 8/10 | 69772ms |
| 187 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 6/10 | 62445ms |
| 188 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 6/10 | 54191ms |
| 189 | `e14e32ba…` | Information | Producers and Dire | ✅ success | Yes | 6 | 5/10 | 55730ms |
| 190 | `02aa1805…` | Professional, Scientif | Project Management | ⚠️ qa_failed | Yes | 2 | 3/10 | 61042ms |
| 191 | `3c19c6d1…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 105666ms |
| 192 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | Yes | 3 | 5/10 | 56281ms |
| 193 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ⚠️ qa_failed | Yes | 6 | 4/10 | 180556ms |
| 194 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ⚠️ qa_failed | Yes | 4 | 4/10 | 106416ms |
| 195 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ⚠️ qa_failed | Yes | 3 | 4/10 | 75342ms |
| 196 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ⚠️ qa_failed | Yes | 21 | 3/10 | 78347ms |
| 197 | `01d7e53e…` | Government | Recreation Workers | ✅ success | Yes | 2 | 7/10 | 95307ms |
| 198 | `a73fbc98…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 80992ms |
| 199 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 6/10 | 75865ms |
| 200 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | Yes | 2 | 6/10 | 47529ms |
| 201 | `90edba97…` | Health Care and Social | Registered Nurses | ⚠️ qa_failed | Yes | 2 | 4/10 | 61943ms |
| 202 | `f2986c1f…` | Retail Trade | Pharmacists | ⚠️ qa_failed | Yes | 1 | 3/10 | 29679ms |
| 203 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 9/10 | 48818ms |
| 204 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 6/10 | 69591ms |
| 205 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 6/10 | 47980ms |
| 206 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 47430ms |
| 207 | `105f8ad0…` | Wholesale Trade | Sales Representati | ⚠️ qa_failed | Yes | 2 | 4/10 | 69402ms |
| 208 | `b57efde3…` | Wholesale Trade | Sales Representati | ⚠️ qa_failed | Yes | 1 | 4/10 | 70261ms |
| 209 | `15d37511…` | Wholesale Trade | Sales Representati | ⚠️ qa_failed | Yes | 2 | 4/10 | 48564ms |
| 210 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 5/10 | 89244ms |
| 211 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 129339ms |
| 212 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 5 | 5/10 | 69769ms |
| 213 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ⚠️ qa_failed | Yes | 1 | 4/10 | 57449ms |
| 214 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 5 | 6/10 | 71178ms |
| 215 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 21542ms |
| 216 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 6/10 | 33910ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 43534ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 31210ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 86289ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 6/10 | 80826ms |

## QA Issues

### ✅ `7b08cd4d…` — score 6/10
- Expense breakdown by source columns is not evidenced in the preview.
- Combined total column for income and costs is not clearly shown.
- USD conversion support for international revenue is not documented.
  > 💡 Add explicit source-separated expense columns, combined totals, and documented USD conversion details.

### ✅ `43dc9778…` — score 5/10
- Output promised a summary, not a completed 1040 return.
- Required e-file forms may be incomplete or unverified.
- DOCX file is unnecessary and suggests deliverable mismatch.
  > 💡 Provide a fully completed 2024 Form 1040 PDF with all required attached IRS schedules and forms.

### ✅ `ee09d943…` — score 5/10
- Cash Availability tab still shows 3-31-25, not April.
- TOC lists #3a worksheet name incorrectly versus actual tab.
- Source file references are largely missing from the TOC.
  > 💡 Update stale March carryforwards and complete TOC source references and tab names.

### ❌ `f84ea6ac…` — score 2/10
- Used placeholder studies instead of real articles.
- Did not conduct required online research.
- Document content preview lacks the requested comparison table.
  > 💡 Replace placeholders with five verified public post-2020 academic articles in a one-page table.

### ✅ `a328feea…` — score 7/10
- Text response describes intent instead of delivering document content.
- Procedure preview is truncated, preventing full content verification.
- No explicit one-page compliance confirmed from provided evidence.
  > 💡 Provide the full document content or preview and confirm it is limited to one page.

### ✅ `27e8912c…` — score 9/10
- Source link appears cited but not clearly shown in preview.
- Word document content preview is truncated, limiting full verification.
  > 💡 Ensure the Word file visibly includes all required fields, process steps, and resolution columns.

### ✅ `17111c03…` — score 9/10
- Text response describes deliverables instead of presenting completed memo content.
- DOCX file was produced though only PDF and Excel were requested.
  > 💡 Ensure the response includes the finalized memo text and only requested file types.

### ✅ `c44e9b62…` — score 6/10
- Text response promises work but omits actual reduction details.
- Excel formatting ignores requested exact source structure and labels.
- Org chart extra DOCX file suggests unnecessary deliverable noise.
  > 💡 Provide a complete summary with exact reductions and mirror source file structures more closely.

### ✅ `99ac6944…` — score 6/10
- No evidence the PDF includes retailer web links.
- Professional-grade claim is weak with entry-level Yamaha MG10XU.
- Portable surface requirement may be insufficiently specified or priced.
  > 💡 Verify the PDF contains explicit links, stronger gear justification, and a fully priced portable setup.

### ✅ `f9a1c16c…` — score 6/10
- Output list omits Vox1 and Vox2 wedges despite stated monitor requirement.
- Wedge numbering is inconsistent and skips numbers in the plot.
- Several labels are garbled or misspelled, reducing professionalism.
  > 💡 Revise the PDF to include all required outputs, correct numbering, and clean readable labels.

### ✅ `38889c3b…` — score 6/10
- Exports are 32-bit float, not requested 24-bit float WAV.
- No evidence the provided drum reference track was actually used.
- Bridge stem naming suggests section-only content, not a standard instrument stem.
  > 💡 Export true 48 kHz 24-bit WAVs and explicitly confirm drum-reference integration.

### ✅ `ff85ee58…` — score 7/10
- No evidence the WAV actually contains the resynced saxophone.
- Peak spec misstates LUFS instead of true peak or dBFS.
- Extra DOCX and PNG were unnecessary deliverables.
  > 💡 Verify audio content directly and report true-peak compliance using correct units.

### ✅ `4b894ae3…` — score 5/10
- Report edits do not match provided reference timecodes.
- One referenced edit spot appears missing from applied edits.
- Added report file was not requested in deliverables.
  > 💡 Apply all listed bass edits at the exact supplied timecodes and deliver only the required WAV.

### ✅ `1b1ade2d…` — score 6/10
- Text response describes intent, not the actual workflow deliverable.
- PNG flowchart is produced but not mentioned in the response.
- Preview is truncated, so full content completeness cannot be verified.
  > 💡 Summarize the actual workflow contents and explicitly reference all produced files.

### ✅ `93b336f3…` — score 7/10
- Text response says Chief Procur, appearing incomplete and unprofessional.
- Output adds Excel and PNG though task requested only a Word document.
- Proposal uses unsupported 49:51 partnership split not requested in task.
  > 💡 Ensure the Word proposal alone fully matches the brief with complete, supported assumptions.

### ✅ `15ddd28d…` — score 6/10
- PDF is 4 pages, exceeding the 2–3-page requirement.
- Text response promises files instead of summarizing delivered strategy content.
- No evidence DOCX content was verified against task requirements.
  > 💡 Provide a concise 2–3-page document and summarize key strategy points in the response.

### ❌ `24d1e93f…` — score 4/10
- Summary and vendor sheets leave key NPV and recommendation cells blank.
- Workbook adds an Inputs sheet instead of only required vendor and summary sheets.
- Output claims missing numeric data, but preview shows quotation values were available.
  > 💡 Populate all calculations and recommendations using extracted quotation and volume data.

### ✅ `05389f78…` — score 5/10
- Text response promises creation instead of confirming completed deliverables.
- Email contains placeholder date text, reducing professionalism and completeness.
- Extra PNG file is unnecessary and not requested.
  > 💡 Confirm completed outputs, replace placeholders, and include only requested finalized deliverables.

### ✅ `575f8679…` — score 9/10
- Text response promises file creation rather than summarizing completed deliverable.
- PNG timeline was extra and not explicitly requested.
  > 💡 Revise the text response to confirm completion and briefly summarize key plan contents.

### ✅ `a74ead3b…` — score 6/10
- Manual alignment is unverified because the response admits no external web access.
- Session-specific content accuracy for Sessions 13 and 14 cannot be confirmed.
- Text promises refinement later, suggesting incomplete final deliverables.
  > 💡 Verify both decks directly against the manual and confirm session-specific content coverage.

### ✅ `bbe0a93b…` — score 6/10
- English assessment requested as PDF but a DOCX was also produced.
- Resource guide was not created from an open web search.
- Preview does not confirm required English table columns exactly.
  > 💡 Provide only the required PDFs and verify exact table labels and sourced resource contacts.

### ✅ `85d95ce5…` — score 6/10
- Text response promises work instead of summarizing completed deliverable.
- Evaluation date appears inconsistent with consent and review dates.
- Cannot verify all template fields and placeholders from preview alone.
  > 💡 Ensure the response summarizes completed work and verify all required template fields exactly match instructions.

### ✅ `76d10872…` — score 6/10
- Text response promises creation instead of confirming completed report details.
- Address validation is marked pending, reducing readiness for service.
- Preview shows truncated content, limiting verification of completeness.
  > 💡 Confirm completed deliverable contents and resolve pending validations before submission.

### ✅ `36d567ba…` — score 7/10
- File preview is truncated, preventing full content verification.
- Conflict-of-interest topic may not fully satisfy required structure.
- No confirmation the document stays within 1-2 pages.
  > 💡 Provide full file content or page count to verify all topics and formatting requirements.

### ✅ `7bbfcfe9…` — score 7/10
- File preview is truncated, preventing full verification of all six §3919 questions.
- Citations are section-level only, not more specific to tested requirements.
- Text response describes the file but omits the actual questions.
  > 💡 Provide complete file preview and more precise citations for each question.

### ✅ `2696757c…` — score 6/10
- Header uses hyphen instead of required en dash nomenclature.
- Test questions appear generic and may not reflect exact cited paragraph requirements.
- Text response promises a PDF only, but also produced an unnecessary DOCX.
  > 💡 Use the exact header and align each question to the precise handbook language.

### ✅ `4c18ebae…` — score 6/10
- Text promises analysis code, but no actual investigative narrative is shown.
- Workbook preview lacks clear human trafficking-specific findings or SAR rationale.
- Original task appears truncated, so full requirement coverage is unverified.
  > 💡 Include a complete SAR narrative with explicit findings, rationale, and direct linkage to the subjects.

### ✅ `cebf301e…` — score 6/10
- Original task appears truncated; requirement coverage cannot be fully verified.
- Output describes a document, not the actual requested solution content.
- Future social login extensibility details are likely too high-level.
  > 💡 Provide a complete implementation-ready design covering every stated requirement explicitly.

### ✅ `c2e8f271…` — score 6/10
- Text response promises creation instead of summarizing completed deliverable.
- Preview is truncated, so required sections cannot be fully verified.
- PDF content alone doesn't confirm DOCX content matches exactly.
  > 💡 Provide a concise completion summary listing included sections and confirm both files contain identical content.

### ✅ `2ea2e5b5…` — score 7/10
- Strategic level mapping basis is incomplete in the provided task text.
- Output promises creation but doesn't summarize actual findings professionally.
- No evidence PPT content was validated beyond file existence.
  > 💡 Include key insights and confirm all classification mappings explicitly in the response.

### ✅ `c357f0e2…` — score 9/10
- Workbook preview shows extra unnamed columns beyond the template fields.
- Text response promises formatting details not verifiable from the preview.
  > 💡 Ensure the workbook exactly matches the template structure without extra columns or metadata.

### ✅ `a45bc83b…` — score 7/10
- Summary is paragraph-based, not mirrored bulleted style.
- Diagram contains visible text errors and overlapping labels.
- POC content preview is missing, so completeness is unverified.
  > 💡 Revise the summary into bullets, fix diagram labeling, and verify the POC covers step-by-step implementation.

### ✅ `a10ec48c…` — score 5/10
- Output admits live sources were not used as required.
- Preview shows only headings, not table contents verification.
- No evidence restaurant links or Google Maps details were included.
  > 💡 Verify the DOCX contains complete populated tables sourced from the required websites.

### ✅ `fccaa4a1…` — score 6/10
- PDF preview shows garbled text and layout overlap.
- Photo inclusion is not evident in the PDF preview.
- Age requirement 2-14 is missing or unclear.
  > 💡 Fix formatting, verify the image appears, and explicitly add all required requirements.

### ❌ `f5d428fd…` — score 4/10
- PDF contains obvious garbled text and formatting errors.
- Royalty-free photos were placeholders, not actual included images.
- Research sourcing appears generic without specific cited references per destination.
  > 💡 Include real royalty-free images, clean formatting, and destination-specific source citations.

### ✅ `0e4fe8cd…` — score 6/10
- Text response promises work instead of summarizing completed deliverable.
- Workbook preview shows generic placeholders instead of verified providers and links.
- Original task appears incomplete, risking missing return-home logistics and full itinerary.
  > 💡 Verify all tabs contain researched links, named providers, and complete end-to-end travel details.

### ✅ `a0ef404e…` — score 9/10
- Text response describes deliverables instead of summarizing completed guide content.
- PDF preview is truncated, limiting full content verification.
  > 💡 Include a concise summary of the guide’s completed contents in the text response.

### ✅ `b7a5912e…` — score 6/10
- No evidence calculations were validated against source spreadsheet.
- Text response promises future work instead of confirming completed analysis.
- Workbook preview omits visible management observations content.
  > 💡 Verify all metrics against the source data and confirm observations are included in the workbook.

### ✅ `aa071045…` — score 7/10
- Service request preview omits key fields like customer, agreement, plate, and mileage.
- Excel report evidence for operational conclusions is incomplete due to truncated preview.
- Extra PNG files were produced though not requested in deliverables.
  > 💡 Ensure the Word form visibly includes all required fields and the Excel workbook clearly shows conclusions.

### ✅ `f3351922…` — score 9/10
- Text response describes creating files instead of providing the requested email directly.
  > 💡 Include the full email in the text response and avoid unnecessary extra deliverables.

### ✅ `61717508…` — score 9/10
- Text response is a summary, not a complete deliverable description.
- Escalation guidance references internal policy not shown in preview.
  > 💡 Deliverables appear complete; include explicit escalation steps in the response for clarity.

### ✅ `0ed38524…` — score 9/10
- Summary PDF appears slightly over one page from preview truncation.
- An extra temporary PDF file was produced unnecessarily.
  > 💡 Deliver only the two final PDFs and verify the summary is exactly one page.

### ✅ `d025a41c…` — score 7/10
- Text response only promises work instead of summarizing completed analysis.
- File preview is truncated, so full content compliance cannot be verified.
- No evidence the attached case logs were actually reviewed.
  > 💡 Provide a concise completion summary and ensure the document clearly reflects all three source cases.

### ✅ `401a07f1…` — score 7/10
- Text response describes intent, not the completed editorial deliverable.
- Preview shows no visible reference links despite requiring linked source stories.
- Word count appears around 450, below the requested 500 words.
  > 💡 Provide a complete 500-word DOCX editorial with visible hyperlinks and a matching summary response.

### ✅ `afe56d05…` — score 9/10
- Text response describes intent rather than summarizing completed deliverable.
- Preview does not confirm explicit references section with hyperlinks.
- Word count appears unverified against the 2,200–2,300 target.
  > 💡 Confirm final word count and visible references with hyperlinks in the document.

### ✅ `9a8c8e28…` — score 7/10
- Text response promises PDFs but omits substantive content details.
- No evidence the guide includes bibliography links or legislation coverage.
- Quiz preview is truncated, so answer key completeness is unverified.
  > 💡 Provide fuller response details and verify all PDFs contain every required section.

### ✅ `3a4c347c…` — score 7/10
- Text response promises a document but omits substantive proposal details.
- Reference file name cited inconsistently as Boilerplate.docx.
- Cannot verify all required sections from the truncated file preview.
  > 💡 Ensure the response summarizes key contents and matches the exact reference filename.

### ✅ `ec2fccc9…` — score 7/10
- No evidence secondary keywords are listed after the article.
- Preview shows plain headings, not explicit H2/H3 formatting.
- Referenced artist highlights cannot be verified from preview.
  > 💡 Verify the document includes the keyword list, formatted headers, and all required artist links.

### ✅ `8c8fc328…` — score 9/10
- Text response promises delivery instead of summarizing completed work.
- File preview is truncated, limiting full content verification.
  > 💡 Ensure the text response confirms completion and include a fuller preview for verification.

### ✅ `e21cd746…` — score 7/10
- Text claims internally prepared dataset, reducing reliability for valuation work.
- Private target details may include stale or estimated valuations without clear sourcing.
- Extra PNG files were produced but not requested in deliverables.
  > 💡 Include explicit source dates and verification notes for all private valuations and customer references.

### ✅ `46b34f78…` — score 6/10
- Text response promises deliverables instead of summarizing completed analysis.
- Reference source file appears unreadable, weakening evidence of required public-data usage.
- Preview lacks memo content verification for required sections and recommendations.
  > 💡 Include a concise results summary and ensure the memo clearly evidences sources and required sections.

### ✅ `a1963a68…` — score 6/10
- Output admits no external web access, weakening required market research rigor.
- No evidence cited for using specified Korean transport association sources.
- Text response is summary-level and omits concrete slide content verification.
  > 💡 Include source-backed slide details and explicit citations to required public references.

### ✅ `5f6c57dd…` — score 6/10
- README DOCX was added though not requested.
- Preview does not evidence dropdowns or formula-driven schedules.
- Content preview is truncated, so required calculations remain unverified.
  > 💡 Verify all five tabs contain working dropdowns, formulas, and complete required metrics.

### ✅ `b39a5aa7…` — score 6/10
- Summary total row appears blank instead of calculated.
- Projection results for next two years are not evidenced.
- Year-over-year growth rates are not visible in preview.
  > 💡 Add visible quarterly projection and Y/Y growth sections with completed totals on the summary sheet.

### ✅ `b78fd844…` — score 7/10
- Text response promises deliverables instead of summarizing actual analysis.
- Reference-file assumptions and source data are not explicitly cited.
- PDF content compliance and page count are not evidenced.
  > 💡 Provide a concise results summary in the text response and cite the underlying reference data.

### ✅ `4520f882…` — score 6/10
- Workbook relies on approximated CBA logic from a partial excerpt.
- Validation flags only likely conflicts, not definitive contract compliance.
- Guide indicates note-based string quartet handling may be fragile.
  > 💡 Verify all formulas against the full CBA and strengthen structured validation rules.

### ✅ `ec591973…` — score 6/10
- File content cannot be verified from preview.
- Text response describes intent, not delivered slide content.
- No evidence all required strategy elements are included.
  > 💡 Open and verify the PPTX slide includes all requested channel strategy, challenges, and executive-ready visuals.

### ✅ `62f04c2f…` — score 7/10
- Warehouse phone number is incomplete in the Word document.
- Text response describes files instead of confirming completed deliverables.
- Excel preview lacks visible signature fields for rep, GM, and Sales Manager.
  > 💡 Fix the phone number and verify all required form fields are clearly included.

### ✅ `6dcae3f5…` — score 5/10
- Workbook includes unrequested Word email deliverable.
- ACGME requirement table was placeholder-based, not sourced from the required PDF.
- Preview shows truncated or possibly incomplete benchmark/key indicator labeling.
  > 💡 Use the exact ACGME PDF requirements and ensure workbook labels and benchmark sheets are complete.

### ✅ `1aecc095…` — score 7/10
- Roadmap preview lacks visible workflow content beyond arrows and one note.
- Email is under 100 words based on previewed text.
- Reference source naming appears inconsistent with provided materials preview.
  > 💡 Ensure the roadmap contains readable decision boxes and expand the email to 100-150 words.

### ✅ `8c823e32…` — score 7/10
- Text response describes intent, not completed policy content.
- Preview does not confirm all required sections are present.
- PDF export readiness is claimed, but full content verification is limited.
  > 💡 Provide the full policy text in the response and verify every required section explicitly.

### ✅ `eb54f575…` — score 9/10
- Text response summarizes intent rather than key findings and recommendations.
- PDF content preview is truncated, limiting full verification of section completeness.
  > 💡 Include the final rifle quantity and caliber directly in the text response.

### ✅ `11e1b169…` — score 7/10
- Text response promises creation instead of summarizing completed deliverable.
- PDF preview appears truncated, limiting verification of all required topics.
- No clear confirmation KRS 503.090 content is accurately covered.
  > 💡 State completed results clearly and ensure all required legal topics are fully visible and verified.

### ✅ `a95a5829…` — score 9/10
- Text response promises creation but omits delivered policy specifics.
- Excel workbook was requested as logging instructions, not clearly required deliverable.
  > 💡 Deliverable appears complete; summarize key policy elements directly in the response.

### ✅ `22c0809b…` — score 9/10
- PDF content was not directly previewed.
- Investigation criteria for accepting referrals are not clearly shown.
  > 💡 Preview the PDF directly and add explicit referral acceptance criteria to the form.

### ✅ `9e39df84…` — score 6/10
- Workbook contains an extra 'Lists' sheet beyond the required two worksheets.
- Average Output and Total Output cells appear blank instead of calculated.
- Dashboard uses tables, not actual PivotTables as requested.
  > 💡 Limit workbook to the required sheets and implement real formulas and PivotTables.

### ✅ `68d8d901…` — score 6/10
- No evidence reference file data was accurately extracted and used.
- Production assignments appear generic and may not reflect actual personnel setup.
- Workbook content preview is incomplete, limiting verification of sequence detail.
  > 💡 Verify all workbook tabs directly mirror reference-file roles, capacities, timings, and sequencing details.

### ✅ `bd72994f…` — score 5/10
- Used a DOCX instead of requested email/text within presentation deliverable.
- Collection content appears self-contained, not sourced from official 2025 resort materials.
- PDF is image-based, limiting content verification and professionalism.
  > 💡 Use official brand resort looks and include the outreach template directly in the requested deliverable set.

### ✅ `211d0093…` — score 7/10
- Output claims exact tasks from reference, but source document evidence is missing.
- Manager sign-off appears duplicated per task and again at the end.
- Some table headers are cramped and reduce form usability.
  > 💡 Ensure all source tasks are verified and improve layout clarity before final delivery.

### ✅ `cecac8f9…` — score 6/10
- Preparation plan was submitted as DOCX and PDF, not PDF only.
- UK store plan uses dollar currency instead of pounds.
- Output describes deliverables generally without confirming all required content details.
  > 💡 Submit only PDFs and ensure UK-specific currency and fully evidenced required content.

### ✅ `8f9e8bcd…` — score 9/10
- Text response summarizes instead of presenting document content.
  > 💡 Include a brief summary of key training points in the text response.

### ✅ `02314fc6…` — score 9/10
- Text response says completed PDF but mainly describes intended contents.
- Extra DOCX file produced though not requested.
  > 💡 Ensure the response confirms completion and briefly summarizes the final checklist contents.

### ✅ `4d61a19a…` — score 9/10
- Excel protection for store-editable fields is not verified.
- SharePoint posting instructions may be too brief in training deck.
  > 💡 Verify worksheet protection and clearly show the SharePoint path and submission steps.

### ✅ `6436ff9e…` — score 9/10
- No visible detailed rating items under class and instructor sections.
- Optional demographic coverage appears limited to age and experience only.
  > 💡 Add explicit scaled questions for class and instructor criteria plus a few optional demographic fields.

### ✅ `8a7b6fca…` — score 9/10
- Render PDF appears narrative, not a visual process map.
  > 💡 Ensure all produced PDFs are clearly labeled and match the requested visual deliverable.

### ✅ `40a99a31…` — score 7/10
- Text response lacks actual hardware justification and compatibility logic details.
- An ODT report was produced unnecessarily alongside required PDF.
- Preview suggests pressure mat row content may be truncated or incomplete.
  > 💡 Provide complete deliverable summaries in text and verify all file contents are fully populated.

### ✅ `b9665ca1…` — score 5/10
- Button box stop wire labels are incomplete and inconsistent.
- PDF text is garbled, reducing assembly usability.
- Output adds unsupported SVG deliverable and omits Visio/CAD source.
  > 💡 Provide a clean readable PDF and correct all specified wire labels and source format.

### ✅ `be830ca0…` — score 6/10
- Text response promises deliverables but omits analytical findings and conclusions.
- PPTX content cannot be verified for required charter, A3, and timeline sections.
- No evidence charts were created in Minitab as requested.
  > 💡 Provide verifiable slide content summaries and key statistical results from the presentation.

### ✅ `cd9efc18…` — score 6/10
- PDF is 7 pages, below the requested 8 to 11 pages.
- Output preview does not confirm all required trust duration terms.
- Text response promises files but does not present the drafted will content.
  > 💡 Ensure the PDF meets length requirements and clearly includes every requested clause.

### ✅ `3f625cb2…` — score 7/10
- Text response promises a memo instead of summarizing completed work.
- California law analysis appears tentative and may omit specific statutes.
- No confirmation the PDF is plain-language or client-tailored throughout.
  > 💡 Provide a concise completion summary and cite specific California statutes and client recommendations.

### ✅ `aad21e4c…` — score 7/10
- Excel file was unnecessary and not requested.
- Preview does not confirm all requested consent rights.
- Anti-dilution top-up and exempt issuance carve-outs are not verified.
  > 💡 Confirm the DOCX expressly includes every requested investor protection and remove unrequested extras.

### ✅ `8314d1b1…` — score 6/10
- Text response promises files but omits substantive memo content.
- No proof the memo discusses March 2025 amendments accurately.
- PDF was not requested and may indicate scope drift.
  > 💡 Verify the memo fully analyzes DGCL Section 144 amendments with citations and tailored recommendations.

### ✅ `5e2b6aab…` — score 7/10
- No PDF drawing provided for the body subassembly.
- Battery replacement with gloves is described but not evidenced in drawings.
- STEP files are concept exchange models, not clearly manufacturable CAD solids.
  > 💡 Add the missing body subassembly drawing and verify glove-use features in the assembly documentation.

### ✅ `46fc494e…` — score 6/10
- Text response promises deliverables but omits requested numerical results and conclusion.
- Model uses assumed 0.02 m thickness not specified in the task.
- Back-face summary table at requested time points is not evidenced in preview.
  > 💡 Include explicit temperatures, limit assessment, and justify or avoid unstated modeling assumptions.

### ✅ `74d6e8b0…` — score 9/10
- Research methodology and source selection are not explicitly documented.
- Some topics are only addressed at a high level.
- Live web-verified references were not used.
  > 💡 Include a brief methods section and fully detailed citations for all guideline sources.

### ✅ `81db15ff…` — score 6/10
- Recommendation sheet contains an apparent blank row and truncated summary.
- Several supervision limits are vague instead of specific when applicable.
- Text response promises creation rather than summarizing completed findings.
  > 💡 Provide complete findings with specific state rules and a clean final recommendation sheet.

### ✅ `61e7b9c6…` — score 6/10
- Pricing was not obtained from online pharmacies as required.
- Workbook uses generic Sheet1 instead of a clear formulary sheet name.
- Output adds an unrequested memo deliverable.
  > 💡 Use the provided template exactly and source each price from a cited online pharmacy.

### ✅ `c9bf9801…` — score 7/10
- Guide content preview is missing, so requirements cannot be fully verified.
- No evidence the guide links separate Word templates as required.
- Appendix labeling and monthly timeline deliverables are not confirmed.
  > 💡 Provide the guide preview or verify links, appendix labels, and full timeline coverage.

### ✅ `4b98ccce…` — score 6/10
- Workbook columns do not use exact required header names.
- Signature appears above data, not beneath each table.
- Unknown-status patient remained in transfer sheet, not clearly handled.
  > 💡 Use exact field headers and place the signed name and ID below each completed table.

### ✅ `60221cd0…` — score 9/10
- Text response describes deliverable instead of providing article content.
- Mail voting incorrectly says only eligible voters may request ballots.
  > 💡 Provide the full article in the text response and verify voting method wording against Virginia rules.

### ✅ `ef8719da…` — score 6/10
- Text response describes intent, not the actual pitch content.
- File preview appears truncated, obscuring source links and timeline verification.
- Output includes unnecessary confidence metadata outside the deliverable.
  > 💡 Return the full pitch directly and ensure links, sources, and timeline are clearly visible.

### ✅ `3baa0009…` — score 6/10
- Text response describes deliverables instead of providing the requested article.
- Article is under 300 words in the preview.
- U.S. and China forecast figures are mentioned without specific numbers.
  > 💡 Provide the full 300-500 word article in the response with explicit global, U.S., and China forecasts.

### ✅ `5d0feb24…` — score 5/10
- Text response promises a deliverable instead of presenting the requested review.
- Document admits no internet access, undermining required sourced science edits.
- Reference links appear incomplete or truncated in the file preview.
  > 💡 Provide the actual editorial feedback with verified source links and fully grounded paper-specific edits.

### ✅ `1b9ec237…` — score 6/10
- PPTX content is not previewed, so requirements cannot be fully verified.
- Speaker notes presence cannot be confirmed from provided evidence.
- Slide count, references, and case study inclusion are unverified.
  > 💡 Open the PPTX and verify all required slides, notes, and references are present.

### ✅ `772e7524…` — score 7/10
- Text response describes deliverables instead of providing the SOAP note.
- Assessment and plan details are not fully verifiable from the preview.
- Output includes unnecessary confidence notation and workflow commentary.
  > 💡 Return the complete SOAP note directly in the text response and ensure files mirror it exactly.

### ✅ `e6429658…` — score 6/10
- Application PDF appears one page and likely not the actual AbbVie form.
- Extra blank PDF was produced, not requested by the task.
- Appeal letter date differs from current month requirement of May 2025.
  > 💡 Use the official AbbVie application, fully complete it, and remove unrequested extra files.

### ✅ `b5d2e6f1…` — score 7/10
- Sales by Store sheet preview is missing, so requirement compliance is unverified.
- Data tab lacks separate WTD, MTD, and YTD sell-through fields.
- Output text says pivot-style tables, not confirmed actual pivot tables.
  > 💡 Verify the Sales by Store sheet exists and confirm both summary tabs are real pivot tables.

### ✅ `47ef842d…` — score 9/10
- Summary percentages are unformatted decimals instead of percentages.
- Standalone PNG was extra and not explicitly requested.
  > 💡 Format out-of-stock values as percentages and keep deliverables strictly to requested outputs.

### ✅ `1137e2bb…` — score 8/10
- Summary sheet is not a true drill-down pivot table.
- Summary sheet includes many zero-error SKUs, reducing focus.
- Workbook preview shows awkward blank summary column headers.
  > 💡 Use a proper pivot table with PO drill-down and cleaner headers focused on error SKUs.

### ✅ `c3525d4d…` — score 6/10
- Final store list tab includes removed stores, not just final list.
- Revised unit cost increase appears miscalculated by $1.00, not $0.25.
- Revised production quantity shows fractional units without rounding.
  > 💡 Limit the second tab to final stores only and correct cost and quantity calculations.

### ✅ `9a0d8d36…` — score 6/10
- Text response promises deliverables but doesn't verify slide content.
- PPTX content preview is unavailable, so requirement coverage is unconfirmed.
- No evidence of step-by-step tax calculations in provided preview.
  > 💡 Provide slide-by-slide content evidence confirming calculations, tax treatment, and net proceeds comparison.

### ✅ `664a42e5…` — score 6/10
- PPTX content cannot be verified from the provided preview.
- No evidence the 2025 gift exclusion amount is explicitly stated.
- No evidence side-by-side comparison appears within the presentation itself.
  > 💡 Provide slide-level preview or text export confirming all required presentation content.

### ✅ `feb5eefc…` — score 7/10
- Text response promises creation instead of summarizing completed analysis.
- PDF appears truncated in preview with an incomplete sentence.
- No clear evidence of detailed client-specific scenario examples for both trusts.
  > 💡 Revise the response to summarize findings and verify the PDF fully covers both trust scenarios.

### ✅ `3600de06…` — score 6/10
- PPTX content cannot be verified from the provided preview.
- Source-based FINRA and NAIC coverage is not evidenced.
- Slide count and required talking points are unconfirmed.
  > 💡 Provide slide text or screenshots to verify all required content and sourcing.

### ✅ `c657103b…` — score 6/10
- Presentation content and template compliance cannot be verified from preview.
- Assumptions cite an unrelated reference file, suggesting possible placeholder metadata.
- RMD timing may be incorrect because calculations start at age 72.
  > 💡 Verify slide count/template use and align RMD start year with current IRS required beginning age.

### ✅ `ae0c1093…` — score 8/10
- Guide PDF title differs from required exact filename.
- Extra DOCX files were produced beyond requested PDFs.
- Observation form preview doesn't confirm three lines under every header.
  > 💡 Provide only the two exactly titled PDFs and verify each form section has three solid lines.

### ✅ `57b2cdf2…` — score 7/10
- Start time conflicts with requested 7:30 PM courtesy surveillance.
- Text response promises photo contact sheet not requested by client.
- Photo verification statement appears truncated in PDF preview.
  > 💡 Align all times precisely and ensure the PDF fully includes the photo verification statement.

### ✅ `6241e678…` — score 6/10
- Schedule adds unrequested casting, location, crew, and gear tasks.
- Required task list appears incomplete or altered in preview.
- Text response promises files but omits schedule specifics and confirmations.
  > 💡 Align the schedule exactly to the requested tasks, revisions, reviews, and approvals only.

### ✅ `b1a79ce1…` — score 6/10
- No evidence the PNG includes actual reference pictures.
- Output mentions PDF notes inspection, but no notes were provided.
- Text promises generated panels instead of sourced references requested.
  > 💡 Verify the PNG visibly contains color palette and clear reference imagery aligned to the brief.

### ✅ `e4f664ea…` — score 5/10
- Screenplay PDF is only 6 pages, below required 8–12 pages.
- Output adds unrequested development notes file instead of focusing on screenplay deliverables.
- Claimed 10–12 pages conflicts with actual file length.
  > 💡 Provide a complete 8–12 page production-ready screenplay and ensure claims match delivered files.

### ✅ `a079d38f…` — score 7/10
- No evidence attached video list was fully itemized in costs.
- Time estimate seems simplistic for nine deliverables.
- Workbook lacks detailed line-item breakdown visibility in preview.
  > 💡 Include a per-video and per-day cost breakdown tied directly to source rates.

### ✅ `ce864f41…` — score 6/10
- Required brief responses were delivered as DOCX, not in the text response.
- Text response promises outputs instead of summarizing actual findings.
- Project budget overrun findings are not evidenced in the preview.
  > 💡 Provide concise findings in the response and clearly report project budget variances.

### ✅ `58ac1cc5…` — score 6/10
- QA email and internal note were DOCX files, not requested text deliverables.
- An extra risk assessment PDF was produced without being requested.
- Evidence of source comparison is weak and file content shows possible extraction errors.
  > 💡 Provide the email and Teams note as explicit text and verify deliverables against source documents.

### ✅ `a99d85fc…` — score 9/10
- File preview doesn't confirm color-coding or light-blue editable cells.
- Notes section content is not visible in the preview.
  > 💡 Verify formatting and notes are present and clearly labeled in the workbook.

### ✅ `1e5a1d7f…` — score 7/10
- Text response promises files instead of summarizing completed deliverable content.
- Output adds an unrequested Excel companion file.
- Details text appears truncated or malformed in preview rows.
  > 💡 Summarize the completed .docx schedule clearly and avoid adding unrequested deliverables.

### ✅ `0419f1c3…` — score 7/10
- Text response describes intent instead of summarizing completed deliverable content.
- Acknowledgement KPI was not measured from source data, weakening data-driven analysis.
- Complaint-log analysis appears limited to three complaints without broader validation.
  > 💡 Summarize actual findings in the response and strengthen source-based KPI analysis.

### ✅ `ed2bc14c…` — score 7/10
- Text response promises work instead of summarizing completed deliverables.
- Memo preview appears truncated and may omit full success metrics.
- Evidence of detailed 90/60/30 email drafts is not shown.
  > 💡 Provide a complete summary of finished outputs and verify all memo sections are fully included.

### ✅ `46bc7238…` — score 7/10
- No evidence free stock photos appear on each page.
- PDF is 10 pages, exceeding the requested 5-8 pages.
- Text response promises creation rather than summarizing completed deliverables.
  > 💡 Reduce the PDF to 5-8 pages and verify stock photos on every page.

### ✅ `2d06bc0a…` — score 9/10
- File preview is truncated, limiting full content verification.
- Text response promises delivery rather than confirming completed attachment.
  > 💡 Confirm the attached .docx includes expiration, broker details, and non-binding language.

### ✅ `94925f49…` — score 6/10
- Missing PDF for one required school: Manor Oaks only previewed as ODT/PDF unclear.
- Reports cite static offline data, not reputable live sources as requested.
- Home listing table has visible formatting/data corruption in preview.
  > 💡 Provide five verified PDFs with clean listing tables and cited July 2025 sources.

### ✅ `90f37ff3…` — score 5/10
- Comparable data is offline and not sourced from public platforms as requested.
- Preview lacks visible addresses and individual asking rents for comparables.
- PDF content cannot be verified from the provided preview.
  > 💡 Use sourced comps with addresses and rents, and ensure the PDF clearly shows them.

### ✅ `d3d255b2…` — score 9/10
- Text response promises PDF creation rather than summarizing completed deliverables.
- Market analysis attachment support is referenced but not clearly evidenced in preview.
  > 💡 Revise the text response to confirm completed files and cite attached market analysis explicitly.

### ✅ `1bff4551…` — score 6/10
- Text response promises a PDF instead of summarizing delivered content.
- NMAAHC collection representation was not actually researched or verified.
- YouTube links are search results, not specific song links.
  > 💡 Provide verified collection matches and direct YouTube URLs, and summarize the final set list in the response.

### ✅ `650adcb1…` — score 6/10
- December sheet is not a calendar layout like requested.
- Sixth Time Off Requests tab is missing from the workbook.
- December preview shows January staffing alerts mixed into December sheet.
  > 💡 Add the missing Time Off Requests tab and convert monthly sheets to true calendar layouts.

### ✅ `0ec25916…` — score 6/10
- PDF is 2 pages, not the required 1 page.
- Preview does not confirm use of cited sources.
- Table structure appears incomplete in the preview.
  > 💡 Ensure a single-page PDF with clear 2x4 table layout and source-informed content.

### ✅ `116e791e…` — score 6/10
- PDF is two pages, not one page as required.
- Text response describes intent, not completed care plan content.
- DOCX was produced though only a PDF was requested.
  > 💡 Provide a true one-page PDF and summarize completed content in the response.

### ✅ `91060ff0…` — score 7/10
- Text response describes intent, not completed poster content.
- References are required but not evident in the preview.
- Poster preview appears truncated, limiting verification of all sections.
  > 💡 Include visible references and summarize completed poster sections in the response.

### ✅ `8384083a…` — score 6/10
- Mounjaro, Wegovy, and Zepbound list vague NDCs instead of exact values.
- Guide omits many individual strengths despite requiring each commonly audited medication.
- PDF is only one page and appears truncated at the end.
  > 💡 Add exact NDCs for each strength and verify complete, untruncated PDF content.

### ✅ `045aba2e…` — score 6/10
- Text admits no source verification against required California resources.
- Deliverable includes extra DOCX files beyond requested three PDFs.
- Checklist content appears generic and may miss California-specific legal details.
  > 💡 Provide only three finalized PDFs grounded directly in the cited California sources.

### ✅ `ffed32d8…` — score 6/10
- PDF omits required drug, vial, and reimbursement comparison data.
- Revenue difference exceeds threshold, but methodology uses unequal annual day coverage.
- Text response promises creation instead of summarizing completed analysis.
  > 💡 Include full comparative cost table and clarify annual coverage assumptions before final recommendation.

### ✅ `b3573f20…` — score 9/10
- Text response describes deliverable instead of summarizing completed content.
- DOCX file was produced though only a PDF was requested.
  > 💡 Ensure the response confirms completion and briefly summarizes the PDF's actual sections.

### ✅ `a69be28f…` — score 9/10
- Text response promises creation instead of confirming completion.
- No explicit mention of chart types or slide labels in response.
  > 💡 Confirm completed deliverables and briefly summarize key findings in the text response.

### ✅ `788d2bc6…` — score 7/10
- Text response promises PNG assets, but none are listed as produced.
- Several slides show duplicated bullets, reducing polish and professionalism.
- Open-source image sourcing is not evidenced in the deliverables.
  > 💡 Include all promised assets, remove duplicated content, and document image sources clearly.

### ✅ `69a8ef86…` — score 6/10
- Internal SOP content preview is missing, so required steps cannot be verified.
- Text response describes files but omits the actual requested process details.
- External guide may lack consequences and notification specifics for 90-day closure.
  > 💡 Provide full internal SOP preview and ensure all mandated timelines, owners, and closure rules are explicit.

### ✅ `ab81b076…` — score 7/10
- PDF is 4 pages, exceeding the 1-3 page requirement.
- Text response promises creation but doesn't summarize completed deliverable content.
- Preview shows truncated content, limiting verification of completeness.
  > 💡 Reduce the PDF to 1-3 pages and ensure the response confirms final completed contents.

### ✅ `fe0d3941…` — score 7/10
- Survey PDF includes extra suggested-use text beyond requested question pages.
- PowerPoint content cannot be verified against required workflow slides from preview.
- No evidence title slide includes optional image or reference-based workflow details.
  > 💡 Remove extra survey text and verify PPT contains all specified slides and reference-based workflows.

### ✅ `9efbcd35…` — score 5/10
- Document admits no direct MSCI, WSJ, FT, or research sourcing.
- Performance discussion is qualitative and lacks concrete Q1 2025 MSCI data.
- Output includes caveat-based commentary instead of requested sourced summary.
  > 💡 Revise with explicit MSCI Q1 2025 performance figures and sourced March 31, 2025 references.

### ✅ `4c4dc603…` — score 6/10
- Text response promises creation instead of confirming completed deliverable.
- Key team members lack named profiles and specific biographies.
- PDF preview shows truncated section, suggesting incomplete economics content.
  > 💡 Confirm completion in the response and include complete named team profiles and full economics details.

### ✅ `bb499d9c…` — score 9/10
- No evidence of publicly sourced research citations or references.
- Text response promises Python code, but none is shown.
- File preview is truncated, limiting full content verification.
  > 💡 Add cited industry sources and remove unsupported mentions like unseen Python code.

### ✅ `a4a9195c…` — score 9/10
- Text response describes deliverable instead of summarizing completed SOP content.
- IPC-A-610G reference is cited generally without specific applicable criteria.
  > 💡 Include a brief completion summary and cite key IPC-A-610G sections used.

### ✅ `0e386e32…` — score 6/10
- Output promises files, not the requested implemented system deliverable.
- Provided materials appear scaffold-level and may lack full functional content.
- Original task details are truncated and privacy logic coverage is incomplete.
  > 💡 Provide a complete implemented package with verified functionality and fuller requirement traceability.

### ✅ `2fa8e956…` — score 6/10
- No evidence wineries were sourced from online resources or Google Maps.
- Royalty-free photo provenance is not provided or cited.
- Output says embedded dataset due to no web access, risking accuracy.
  > 💡 Add source citations and verified Google Maps distances directly in the document.

### ❌ `c94452e4…` — score 4/10
- Final spot uses animatic placeholders instead of sourced stock footage.
- Required PSD-based supers and exact final broadcast master are not confirmed.
- Extra WAV delivered while client-ready stock music sourcing was not completed.
  > 💡 Deliver the exact 15-second final MP4 using licensed stock footage, music, and PSD supers.

### ❌ `a941b6d8…` — score 4/10
- Window tracking appears static despite required moving camera matchmove.
- Output package adds reports instead of focusing on required finished VFX shot.
- Codec match and smoke/flash execution are not evidenced clearly.
  > 💡 Deliver a verified final composite matching base clip specs with demonstrated tracking and teleport effects.

### ✅ `c7d83f01…` — score 9/10
- Monte Carlo method details are unverified from notebook preview.
- Excel workbook content preview is truncated and not fully confirmed.
  > 💡 Verify notebook implementations and workbook tables fully match the stated analysis.

### ❌ `327fbc21…` — score 4/10
- Week weighting appears reversed versus required May peak in Week 1.
- Summary document content is not shown, so required topline summary is unverified.
- Workbook preview lacks clear Total, Closed, and Comp roll-up lines.
  > 💡 Verify weekly allocations, include explicit roll-up rows, and ensure the summary states required topline metrics.

### ❌ `0353ee0c…` — score 2/10
- PDF is a framework, not the required exhaustive consolidated guide.
- Presumptive exposures, locations, dates, and conditions are missing.
- Output admits source webpages were not reviewed as required.
  > 💡 Review all 19 links and produce a complete PDF with consolidated eligibility details.

### ❌ `40a8c4b1…` — score 4/10
- Output preview lacks evidence optional unused topics were highlighted yellow.
- Schedule shows generic placeholders like Required by School of Medicine.
- No proof In-Service Study Session was scheduled in late February.
  > 💡 Verify workbook formatting and required February placement, then replace placeholders with exact scheduled topics.

### ❌ `4d1a8410…` — score 4/10
- Master schedule lacks detailed table with room timings and applicant names.
- Schedule timing conflicts with required lunch and PM break structure.
- Itineraries appear incomplete and include unrequested avatar and logos.
  > 💡 Provide full table-based schedules with exact compliant timings and complete one-page applicant itineraries.

### ✅ `bf68f2ad…` — score 6/10
- Text promises a DOCX summary, not the requested email-ready text response.
- Workbook includes extra PNG file not requested by the task.
- Recommended Plan sheet is sparse and not a detailed separate planning workbook.
  > 💡 Provide the brief summary directly in the response and ensure the workbook is the primary deliverable.

### ✅ `efca245f…` — score 5/10
- Output adds an unrequested DOCX summary deliverable.
- Scenario 3 violates no-overtime and fixed scenario naming constraints.
- Workbook content preview is missing, so required daily plans are unverified.
  > 💡 Provide only the required Excel workbook and ensure scenarios exactly match the requested assumptions.

### ✅ `d4525420…` — score 6/10
- Text response is a plan, not the required 5–7 sentence paragraph.
- Output references wrong role title and adds unrequested deliverables.
- Selection rationale depends on files instead of complete response text.
  > 💡 Provide the actual 5–7 sentence recommendation in the text response and avoid extra deliverables.

### ✅ `45c6237b…` — score 6/10
- PDF has 11 pages, exceeding the under-10-slides requirement.
- Preview suggests incomplete next-season images or duplicated section slides.
- Shirt size allocations appear shown only as examples, not all SKUs.
  > 💡 Reduce slide count, ensure all assortment images appear, and show full SKU size allocations.

### ✅ `0fad6023…` — score 6/10
- Preview shows formulas or calculated fields are not populated.
- Visual pan representation is unclear from the worksheet preview.
- Printer-friendly setup is not evidenced in the provided preview.
  > 💡 Populate calculation cells and strengthen visible pan layout and print formatting.

### ✅ `c6269101…` — score 7/10
- No evidence the PowerPoint content was validated against requirements.
- Capability conclusions avoid explicit expectations due to missing provided thresholds.
- Failure Rate Detail sheet contains unnamed columns, suggesting formatting issues.
  > 💡 Validate the deck contents and clean workbook structure before final delivery.

### ✅ `a97369c7…` — score 6/10
- Text response promises files instead of providing substantive memo content.
- Memo omits meaningful discussion of Delaware Senate Bill 313.
- Analysis of Marcus's controller status and fiduciary exposure appears underdeveloped.
  > 💡 Provide a complete substantive response and deepen statutory and controller-duty analysis.

### ❌ `3940b7e7…` — score 4/10
- Report admits unreadable source data and draft limitations.
- Required CFD details and metrics are not fully provided.
- Output includes extra FODT file and likely placeholder content.
  > 💡 Provide a complete PDF with extracted numerical tables and all required simulation details.

### ✅ `8077e700…` — score 6/10
- AISI 1045 analysis is not validated by provided data.
- Required microstructure discussion relies on assumptions, not observations.
- Extra DOCX and XLSX outputs were produced beyond requested PDF deliverable.
  > 💡 Provide validated AISI 1045 data or clearly limit scope and final deliverables to the requested PDF.

### ✅ `5a2d70da…` — score 6/10
- Manufacturing steps file lacks monthly quantity-derived planning detail.
- Master tool list omits subtotal and grand total rows.
- Text claims validation and references not evidenced in deliverables.
  > 💡 Add budget totals, clearer production planning, and ensure deliverables fully substantiate all claims.

### ✅ `61b0946a…` — score 7/10
- Original task appears truncated, so full requirement coverage is unverified.
- Cost analysis assumes identical department costs without supporting evidence.
- Procedure capacity estimate seems optimistic against three-hour thawed-use limit.
  > 💡 Verify the full original task and justify assumptions with explicit scheduling and budget evidence.

### ❌ `f1be6436…` — score 3/10
- Used fabricated estimates instead of live website information and real screenshots.
- Total Costs header lacks the required collection date.
- Lodging used proxy July dates, not actual conference dates.
  > 💡 Recreate the document with live sourced April 2026 pricing, dated headers, and authentic screenshots.

### ✅ `a0552909…` — score 7/10
- Arizona email template content was not previewed for verification.
- Excel preview shows generic header text, not clearly matching reference structure.
- No evidence drop-down validations were actually implemented.
  > 💡 Verify all files fully, especially Arizona template and Excel data validations.

### ✅ `6d2c8e55…` — score 6/10
- Article PDFs are citation/link briefs, not actual articles or saved web pages.
- Schedule workbook content wasn't shown, so booking updates remain unverified.
- Article access links appear generic and may not identify specific articles.
  > 💡 Provide actual accessible article PDFs or saved article webpages and verify workbook bookings explicitly.

### ✅ `6974adea…` — score 6/10
- Text response describes intent instead of delivered article content.
- Guardian style compliance and source use are not clearly evidenced.
- SEO formatting is partial and byline/date may not match brief.
  > 💡 Return the finished article text in the response and verify all brief requirements explicitly.

### ✅ `1a78e076…` — score 8/10
- Search strategy lacks reproducible database details and explicit inclusion/exclusion criteria.
- Results may not clearly report adherence differences across older age subgroups.
- Reference to CINAHL-type literature is vague and not source-specific.
  > 💡 Add explicit search methods, age-stratified findings, and precise database sourcing details.

### ✅ `0112fc9b…` — score 6/10
- Text response describes files instead of providing the SOAP note.
- Assessment and plan likely incomplete in visible preview.
- Neurologic exam omits cranial nerves II, V, VII. 
  > 💡 Provide the full SOAP note directly and ensure complete assessment and safety plan details.

### ✅ `f841ddcf…` — score 6/10
- Prepared date is incorrect for the stated task date.
- Main recap sheet is not an Excel table with proper headers.
- Filterable by account is unclear on the summary sheet.
  > 💡 Use proper Excel tables with correct dates and clear account filters on summary sheets.

### ✅ `f9f82549…` — score 8/10
- PDF title and flowchart title are reversed from requirements.
- Unexpected ODP file produced beyond requested deliverables.
- PPTX content could not be verified from preview.
  > 💡 Match the exact requested titles and provide only the required PDF and PowerPoint files.

### ✅ `84322284…` — score 6/10
- Text response promises work instead of summarizing completed findings.
- Extra PNG file appears unnecessary to task requirements.
- No evidence the PDF conclusion and recommendations were verified.
  > 💡 Provide a concise results-focused summary and ensure only required, verified deliverables are included.

### ✅ `a46d5cd2…` — score 6/10
- Text response promises creation instead of summarizing completed deliverables.
- Report preview appears truncated and may omit full Investigator B findings.
- Letterhead PDF compliance is not clearly evidenced from preview.
  > 💡 Ensure the response confirms completion and the PDF fully includes both investigators' findings with visible letterhead.

### ✅ `e14e32ba…` — score 5/10
- Uses placeholder images instead of actual establishment photos.
- Hours and media links are vague or search-result placeholders.
- Research was not sourced from live internet as requested.
  > 💡 Replace placeholders with verified photos and exact current hours and direct feature links.

### ❌ `02aa1805…` — score 3/10
- Workbook lacks extracted Illinois EPA well data for requested systems.
- Recommendations are unsupported because no viable wells were actually identified.
- Output admits external website access was not used despite task requiring investigation.
  > 💡 Access the Illinois EPA factsheets, extract the required well records, and provide evidence-based recommendations.

### ✅ `55ddb773…` — score 5/10
- Output promises OCR attempt instead of confirming attached requirements were fully incorporated.
- PDF preview shows formatting artifacts and likely OCR errors.
- DOCX and OCR text were produced though task requested a PDF form.
  > 💡 Verify all attached violation items manually and deliver a clean PDF matching every required section.

### ❌ `0818571f…` — score 4/10
- Listings are realistic candidates, not verified active June 2025 Crexi/LoopNet listings.
- Report appears templated and may omit actual property photos and surrounding maps.
- Task required qualified opportunities from attached criteria, but sourcing was not completed live.
  > 💡 Verify 5-10 active June 2025 listings and replace all template content with sourced property data.

### ❌ `6074bba3…` — score 4/10
- PDF contains placeholder fields and template text.
- Only six sold comparables were included.
- Active listings section appears truncated or incomplete.
  > 💡 Complete the template fully and include all required comparable and active listing details.

### ❌ `5ad0c554…` — score 4/10
- Brochure preview shows only three paragraphs, suggesting incomplete double-sided brochure content.
- No evidence it identifies relevant items from the 132 Things resource.
- NAR buyer broker agreement details may be too brief or insufficiently documented.
  > 💡 Expand the Word brochure with milestone sections, cited buyer-service items, and clear BBA guidance.

### ❌ `11593a50…` — score 3/10
- Listings are for Massabama, not Massapequa Park 11762.
- Map PDF is two pages, not the required one page.
- Output admits no live MLS verification, undermining required property identification.
  > 💡 Use verified active Massapequa Park MLS listings and regenerate a compliant two-page packet and one-page map.

### ✅ `01d7e53e…` — score 7/10
- Output adds an extra notes file not requested by the task.
- Primary contact information details are not evident in the preview.
- Required city standard language incorporation is not clearly verifiable from preview.
  > 💡 Remove unrequested files and verify contacts and city boilerplate are explicitly included in the agreement.

### ✅ `dd724c67…` — score 6/10
- Facility list is not verified as all Long Island facilities.
- Output admits no live research, weakening completeness and accuracy.
- TFU guide may not fully reflect official CMS PY 2025 methodology.
  > 💡 Validate every facility and TFU timeframe against current public directories and the CMS report.

### ✅ `7151c60a…` — score 6/10
- File previews omit sender, recipient, fax detail, and checkbox fields.
- Checklist content from required patient information document is not evidenced.
- Logo inclusion and footer page numbers are not verifiable from preview.
  > 💡 Verify both DOCX files contain all required fields, checklist items, logo, and page numbering.

### ❌ `90edba97…` — score 4/10
- Output describes intent, not confirmed completed data entry.
- Summary admits lab values were entered only where reliably extracted.
- Workbook content preview lacks evidence of all patient monthly results and interventions.
  > 💡 Verify every patient-month entry and document all protocol-driven medication changes explicitly.

### ❌ `f2986c1f…` — score 3/10
- Did not identify each medication using Drugs.com as required.
- Workbook contains only one unconfirmed item with many NA fields.
- Added unsupported limitation notes instead of completing required identifications.
  > 💡 Use Drugs.com to identify all visible medications and populate complete spreadsheet fields.

### ✅ `74ed1dc7…` — score 9/10
- Text response promises creation rather than summarizing completed deliverable.
- Proposal references a reviewed file, but source-specific evidence is limited.
  > 💡 State the document was completed and cite more explicit reference-file findings.

### ✅ `d7cfae6f…` — score 6/10
- Projection period is misstated as Q1 2023 in the task.
- Workbook lacks evidence of axis totals and grand total.
- Percent fields are raw decimals, not clearly expressed percentages.
  > 💡 Fix the period labeling, add explicit subtotal and grand total rows, and format percentages properly.

### ✅ `19403010…` — score 6/10
- Workbook title appears as a column header, not verified as sheet title.
- Preview does not confirm Sections 3-5 include required total rows.
- Percent values appear unformatted decimals instead of presentation-ready percentages.
  > 💡 Verify section totals, formatting, and title placement directly in the workbook.

### ✅ `7ed932dd…` — score 6/10
- Text claims supporting tabs, but workbook shows only two sheets.
- Additional Shipments sheet has malformed header columns.
- No evidence row highlighting exists in the file preview.
  > 💡 Ensure the workbook structure, formatting, and stated contents exactly match the deliverable description.

### ❌ `105f8ad0…` — score 4/10
- Required September 2025 competitor web research was not performed.
- Benchmark set lacks documented competitor products, channels, and source prices.
- Workbook preview shows incomplete key outputs and rationale details.
  > 💡 Perform and document channel-specific competitor research, then update the model with SKU-level recommendations and rationale.

### ❌ `b57efde3…` — score 4/10
- Workbook uses seeded prospects instead of official exhibitor list.
- Only eight rows; far too incomplete for hundreds of exhibitors.
- Text admits no live verification, leaving findings unvalidated.
  > 💡 Rebuild the spreadsheet from the official Aqua Nor 2025 exhibitor list with verified prospects.

### ❌ `15d37511…` — score 4/10
- Spreadsheet lacks actual pricing, cost, and margin values.
- Year 1 total gross margin is not completed.
- Output adds an unrequested assumptions document.
  > 💡 Populate all required financial fields from Pricing email.docx and finalize totals.

### ✅ `6a900a40…` — score 5/10
- Transport options and grand totals are not visible in the preview.
- Item remarks for transport suitability and transit times appear missing.
- Red-font freight validity remark is not evidenced in preview.
  > 💡 Verify the workbook includes all transport rows, remarks, totals, and the red general note.

### ✅ `4de6a529…` — score 5/10
- Preview shows truncated content, so completeness cannot be confirmed.
- Change column appears malformed with stray symbols and split header text.
- Output adds unrequested DOCX and XLSX deliverables beyond the PDF requirement.
  > 💡 Verify the final PDF fully includes all required rows, clean headers, and clear change indicators.

### ❌ `5349dd7b…` — score 4/10
- Workbook uses placeholder research because live web research was not completed.
- Historical averages and recommendations cannot be validated from provided preview.
- Task-required carrier cost analysis may rely on unsupported assumed rates.
  > 💡 Complete verified web research and populate all rates and calculations with cited current data.

### ✅ `552b7dd0…` — score 6/10
- No evidence the PPT includes recurring-description takeaways and recommendations.
- Average resolution time overall and separate type statistics are not verified.
- Supplier percentages and totals are claimed, but slide content is unverified.
  > 💡 Provide slide-level evidence or preview confirming all required analyses and summary recommendations are included.

### ✅ `76418a2c…` — score 6/10
- Workbook appears on Sheet1, not the provided manifest template sheet.
- Manifest preview lacks industry average cost column despite required savings comparison.
- Shipping rule thresholds use 25.1 and 100.1, leaving boundary gaps.
  > 💡 Use the exact template structure and include actual and industry average costs for every shipment.

### ✅ `2c249e0f…` — score 6/10
- Text response promises files instead of presenting the required deliverable content.
- OpenAPI YAML content is not shown, so requirement coverage cannot be verified.
- data_flow.txt preview appears truncated and may be incomplete.
  > 💡 Return the full YAML spec and complete data_flow.txt content directly and verify all required endpoints.

## Failure Analysis

The clearest split across all 220 tasks is between bounded office-document work and tasks that needed live research, multimodal generation, or exact template replication. High-performing examples were mostly structured local-output jobs such as dfb4e0cd-a0b7-454e-b943-0dd586c2764c, 4d61a19a-8438-4d4c-9fc2-cf167e36dcd6, a99d85fc-eff8-48d2-a7d4-42a75d62f18d, and bb863dd9-31c2-4f64-911a-ce11f457143b, where the model could stay inside Excel/Word/PDF with provided inputs. In contrast, many low-QA or failed tasks substituted placeholder or offline content where live verification was required: f84ea6ac-8f9f-428c-b96c-d0884e30f7c7 used fake studies, 0353ee0c-18b5-4ad3-88e8-e001d223e1d7 did not review the required PACT Act links, 02aa1805-c658-4069-8a6a-02dec146063a did not extract Illinois EPA well data, 0818571f-5ff7-4d39-9d2c-ced5ae44299e and 11593a50-734d-4449-b5b4-f8986a133fd8 did not verify live real-estate listings, and 105f8ad0-8dd2-422f-9e88-2be5fbd2b215 plus b57efde3-26d6-4742-bbff-2b63c43b4baa missed required web research in wholesale sales. This lines up with the sector summary: Government was strong when tasks were policy/forms oriented, while Real Estate and Health Care admin work degraded when external sourcing was mandatory.

A second failure class is deterministic execution brittleness, especially around parsers that expected exact sheet names, column names, or PDF table layouts. Examples include 7d7fc9a7-21a7-4b83-906f-416dea5ad04f failing to parse invoices, 476db143-163a-4537-9e21-fe46adad703b failing on a move-out PDF that clearly contained rows, 61f546a8-c374-467f-95cc-d0d9b5656eb6 failing on apartment availability rows, 87da214f-fd92-4c58-9854-f4d0d10adce0 missing a Policy Number column, 1752cb53-5983-46b6-92ee-58ac85a11283 failing on a near-match column name, 3c19c6d1-672c-467a-8437-6fe21afb8eae failing on a sheet-name mismatch, 11dcc268-cb07-4d3a-a184-c6d7a19349bc missing Item #, and e996036e-8287-4e7f-8d0a-90a57cb53c45 failing because quarter labels were not found exactly. Environment/runtime issues formed a separate deterministic subgroup: e222075d-5d62-4757-ae3c-e34b0846583b lacked moviepy, 75401f7c-396d-406d-b08e-938874ad1045 crashed on Unicode decoding in subprocess output, 8079e27d-b6f3-4f75-a9b5-db27903c798d hit an openpyxl conditional-formatting range bug, 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 hit a pandas frequency deprecation, and 7de33b48-5163-4f50-b5f3-8deea8185e57, 854f3814-681c-4950-91ac-55b0db0e3781, and 4122f866-01fa-400b-904d-fa171cdab7c7 all died from unterminated triple-quoted strings. Occupation clustering is strong here: Software Developers had 3 errors in 5 tasks, Film and Video Editors had only 1 clean success out of 5, Wholesale First-Line Supervisors of Non-Retail Sales Workers had 3 non-successes out of 5, and Health Care First-Line Supervisors of Office/Admin Support had 3 QA failures out of 5.

Retries helped when the issue was transient generation or recoverable formatting, but they did not fix deterministic parser/runtime bugs or requirement-fidelity gaps. Retried tasks such as 83d10b06-26d1-4636-a32c-23f92c57f30b, ff85ee58-bc9f-4aa2-806d-87edeabb1b81, c357f0e2-963d-4eb7-a6fa-3078fe55b3ba, and c7d83f01-2874-4876-b7fd-52582ec99e1a recovered well, showing the retry loop has value. But many retried tasks still ended as errors or QA failures: e222075d-5d62-4757-ae3c-e34b0846583b, 75401f7c-396d-406d-b08e-938874ad1045, 7de33b48-5163-4f50-b5f3-8deea8185e57, 4122f866-01fa-400b-904d-fa171cdab7c7, 24d1e93f-9018-45d4-b522-ad89dfd78079, f5d428fd-b38e-41f0-8783-35423dab80f6, 327fbc21-7d26-4964-bf7c-f4f41e55c54d, 0353ee0c-18b5-4ad3-88e8-e001d223e1d7, and 0818571f-5ff7-4d39-9d2c-ced5ae44299e. That pattern suggests the current retry policy mostly reruns the same strategy instead of changing parser assumptions, tool choice, or source-acquisition behavior.

Latency appears to measure task complexity more than quality. Some of the longest jobs were weak or failed: 75401f7c-396d-406d-b08e-938874ad1045 took 277955 ms and errored, c94452e4-39cd-4846-b73a-ab75933d1ad7 took 187185 ms and still QA-failed, a941b6d8-4289-4500-b45a-f8e4fc94a724 took 152430 ms and QA-failed, and 1b9ec237-bf9c-41f9-8fa9-0e685fcd93c6 took 191371 ms for only QA 6. By contrast, several high-quality structured tasks were much faster, such as dfb4e0cd-a0b7-454e-b943-0dd586c2764c at 26487 ms and bb863dd9-31c2-4f64-911a-ce11f457143b at 38398 ms. Across successful tasks, the most common quality drag was not catastrophic failure but deliverable-discipline drift: many outputs used intent language instead of confirming completion and often added extra or wrong file types, as seen in 43dc9778-450b-4b46-b77e-b6d82b202035, c44e9b62-7cd8-4f72-8ad9-f8fbddb94083, 05389f78-589a-473c-a4ae-67c61050bfca, bbe0a93b-ebf0-40b0-98dc-8d9243099034, 045aba2e-4093-42aa-ab7f-159cc538278c, and ae0c1093-5ea8-4b84-a81e-53ebf7a4321d.

## Recommendations

First, harden the execution environment before touching prompt strategy. Add a preflight stage that lints generated Python, parses it with ast, and runs a lightweight smoke test before full execution; that would likely have prevented the three Software Developer syntax crashes in 7de33b48-5163-4f50-b5f3-8deea8185e57, 854f3814-681c-4950-91ac-55b0db0e3781, and 4122f866-01fa-400b-904d-fa171cdab7c7. Pin and validate key library versions for media and spreadsheet work, including moviepy/ffmpeg availability for video tasks like e222075d-5d62-4757-ae3c-e34b0846583b, binary-safe subprocess capture or errors=replace handling for 75401f7c-396d-406d-b08e-938874ad1045, and current pandas/openpyxl compatibility to avoid regressions like 1d4672c8-b0a7-488f-905f-9ab4e25a19f7 and 8079e27d-b6f3-4f75-a9b5-db27903c798d. This is the fastest path to lowering explicit error count without any model changes.

Second, replace exact-match ingestion with schema-tolerant parsing. Normalize whitespace, case, punctuation, merged-cell artifacts, and sheet-name variants; allow synonym dictionaries and fuzzy header matching; and fall back to row-level regex extraction when PDF tables are weak. That single change would cover many deterministic failures: 87da214f-fd92-4c58-9854-f4d0d10adce0, 3c19c6d1-672c-467a-8437-6fe21afb8eae, 1752cb53-5983-46b6-92ee-58ac85a11283, 11dcc268-cb07-4d3a-a184-c6d7a19349bc, 476db143-163a-4537-9e21-fe46adad703b, 61f546a8-c374-467f-95cc-d0d9b5656eb6, 7d7fc9a7-21a7-4b83-906f-416dea5ad04f, and e996036e-8287-4e7f-8d0a-90a57cb53c45. The key operational change is to make parse validation explicit: after extraction, print matched headers and first rows, then branch into repair logic if counts look wrong instead of crashing.

Third, change prompt/tool routing for research-heavy tasks and enforce a stricter output contract. When the brief requires live web research or official-source verification, route the task to browsing/retrieval by default and require a source ledger with URL, access date, and which deliverable cell or paragraph it supports. That directly addresses the repeated offline-placeholder failures in f84ea6ac-8f9f-428c-b96c-d0884e30f7c7, 0353ee0c-18b5-4ad3-88e8-e001d223e1d7, 02aa1805-c658-4069-8a6a-02dec146063a, 0818571f-5ff7-4d39-9d2c-ced5ae44299e, 11593a50-734d-4449-b5b4-f8986a133fd8, 105f8ad0-8dd2-422f-9e88-2be5fbd2b215, b57efde3-26d6-4742-bbff-2b63c43b4baa, and f1be6436-ffff-4fee-9e66-d550291a1735. In parallel, add a post-generation validator that compares requested vs produced file types, filenames, page/slide counts, and whether the response confirms completion rather than stating intent; this would raise many mid-QA successes such as 43dc9778-450b-4b46-b77e-b6d82b202035, bbe0a93b-ebf0-40b0-98dc-8d9243099034, 045aba2e-4093-42aa-ab7f-159cc538278c, ae0c1093-5ea8-4b84-a81e-53ebf7a4321d, and f9f82549-fdde-4462-aff8-e70fba5b8c66 with minimal extra latency.

Fourth, make retries and QA thresholds adaptive instead of uniform. Retries are clearly worthwhile for transient execution or serialization issues, as shown by 83d10b06-26d1-4636-a32c-23f92c57f30b, c357f0e2-963d-4eb7-a6fa-3078fe55b3ba, ff85ee58-bc9f-4aa2-806d-87edeabb1b81, and c7d83f01-2874-4876-b7fd-52582ec99e1a, but blind replays waste time on deterministic bugs and evidence gaps. Classify each failure after the first attempt: runtime/syntax gets auto-patched and rerun with a different tool chain, parser mismatch gets a schema-repair branch, and content-fidelity failures get a targeted repair prompt seeded with the QA findings. For QA policy, auto-repair any result at QA 5 or below and apply stricter evidence checks in Health Care, Real Estate, Finance, and research-heavy Wholesale roles, while allowing faster acceptance for bounded internal-form tasks that already perform well in Government and Retail. That should reduce both the 66 retries and the number of usable-but-midconfidence outputs.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 4 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 5 file(s)
- `99ac6944…` (Information): 6 file(s)
- `f9a1c16c…` (Information): 2 file(s)
- `38889c3b…` (Information): 7 file(s)
- `ff85ee58…` (Information): 3 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 3 file(s)
- `93b336f3…` (Manufacturing): 3 file(s)
- `15ddd28d…` (Manufacturing): 3 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `575f8679…` (Government): 2 file(s)
- `a74ead3b…` (Government): 4 file(s)
- `bbe0a93b…` (Government): 6 file(s)
- `85d95ce5…` (Government): 2 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 6 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 3 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 2 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 1 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 2 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 4 file(s)
- `f3351922…` (Finance and Insurance): 3 file(s)
- `61717508…` (Finance and Insurance): 2 file(s)
- `0ed38524…` (Finance and Insurance): 6 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e21cd746…` (Finance and Insurance): 5 file(s)
- `9e8607e7…` (Finance and Insurance): 2 file(s)
- `46b34f78…` (Finance and Insurance): 5 file(s)
- `a1963a68…` (Finance and Insurance): 7 file(s)
- `5f6c57dd…` (Finance and Insurance): 2 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 4 file(s)
- `4520f882…` (Finance and Insurance): 2 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 3 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `9e39df84…` (Manufacturing): 5 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 9 file(s)
- `211d0093…` (Retail Trade): 1 file(s)
- `cecac8f9…` (Retail Trade): 7 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 3 file(s)
- `4d61a19a…` (Retail Trade): 3 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 3 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `be830ca0…` (Manufacturing): 7 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 2 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `5e2b6aab…` (Manufacturing): 21 file(s)
- `46fc494e…` (Manufacturing): 7 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 8 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 2 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 2 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 2 file(s)
- `664a42e5…` (Finance and Insurance): 4 file(s)
- `feb5eefc…` (Finance and Insurance): 3 file(s)
- `3600de06…` (Finance and Insurance): 2 file(s)
- `c657103b…` (Finance and Insurance): 5 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `57b2cdf2…` (Retail Trade): 3 file(s)
- `6241e678…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 1 file(s)
- `e4f664ea…` (Information): 4 file(s)
- `a079d38f…` (Information): 1 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 2 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 2 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 9 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 15 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `403b9234…` (Government): 2 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `91060ff0…` (Retail Trade): 5 file(s)
- `8384083a…` (Retail Trade): 4 file(s)
- `045aba2e…` (Retail Trade): 6 file(s)
- `ffed32d8…` (Retail Trade): 3 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 3 file(s)
- `788d2bc6…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 3 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `bb499d9c…` (Finance and Insurance): 3 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 6 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `c94452e4…` (Information): 3 file(s)
- `a941b6d8…` (Information): 5 file(s)
- `c7d83f01…` (Finance and Insurance): 7 file(s)
- `327fbc21…` (Wholesale Trade): 2 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `efca245f…` (Manufacturing): 2 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `c6269101…` (Manufacturing): 10 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `8077e700…` (Manufacturing): 6 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `61b0946a…` (Health Care and Social Assistance): 3 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `a0552909…` (Health Care and Social Assistance): 7 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 13 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `f9f82549…` (Retail Trade): 3 file(s)
- `84322284…` (Retail Trade): 3 file(s)
- `a46d5cd2…` (Retail Trade): 3 file(s)
- `e14e32ba…` (Information): 6 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 3 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 6 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 3 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 21 file(s)
- `01d7e53e…` (Government): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 2 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `4de6a529…` (Finance and Insurance): 5 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 5 file(s)
- `76418a2c…` (Manufacturing): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
