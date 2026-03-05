# Experiment Report: GPT-5.2 Chat Elicit v2 — domain packages + package notice (Full 220)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp011_GPT52Chat_domain_packages` |
| **Condition** | Elicit v2 16k + domain packages |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-05 |
| **Duration** | 134m 16s |
| **Generated At** | 2026-03-05T13:11:54.320529+00:00 |
| 🤗 HF Dataset | [exp011_GPT52Chat_domain_packages](https://huggingface.co/datasets/HyeonSang/exp011_GPT52Chat_domain_packages) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp011_GPT52Chat_domain_packages/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated the GPT-5.2 Chat model under the Elicit v2 configuration with domain packages and package notices enabled, executed across 220 tasks spanning multiple industry sectors. Tasks were run via subprocess execution with a 16k context window, focusing on domain-specific elicitation and deliverable generation. Overall task completion was high, with 211 of 220 tasks completed successfully, indicating broad functional coverage across sectors.

The model reported an overall self-assessed task completion rate of 95.9%, with an average self-QA confidence score of 6.11/10. These scores reflect the model’s own assessment of response adequacy and completeness during execution, not external evaluation. Latency averaged approximately 25.3 seconds per task, with noticeable variation by sector but no systemic execution stalls.

Key highlights include perfect completion in several sectors (Finance, Government, Information, Retail) and relatively stable self-assessed quality across domains, suggesting consistent handling of domain package conditioning while maintaining acceptable execution reliability.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 211 (95.9%) |
| Errors | 9 |
| Retried Tasks | 35 |
| Avg QA Score | 6.11/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 25,294ms |
| Max Latency | 52,577ms |
| Total LLM Time | 5564s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 176 (95.1%) |
| Failed → dummy created | 9 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 21 | 21 | 0 |
| 2 | 14 | 5 | 9 |

## Quality Analysis

Self-assessed QA scores clustered primarily between 5 and 7 across most sectors, indicating moderate confidence in output quality with limited instances of very low or very high confidence. Retail Trade showed the highest average self-QA (7.0/10), while Professional, Scientific, and Technical Services and Health Care trended lower, suggesting greater complexity or ambiguity in those task prompts.

Sector-level variation suggests that structured, transactional domains (e.g., Retail, Government) benefited more from the domain package setup, whereas knowledge-dense or compliance-sensitive sectors (Health Care, Professional Services) exhibited slightly reduced self-assessed confidence. No sector demonstrated systematically poor quality, but several showed narrower margins between minimum and average QA scores, indicating occasional weaker outputs.

Deliverable file generation was generally successful in completed tasks, with no sector-wide degradation observed. Lower QA scores were more commonly associated with nuanced reasoning or multi-step synthesis rather than formatting or file creation failures.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 25 | 100.0% | 5.88/10 | 24,821ms |
| Government | 25 | 25 | 100.0% | 6.8/10 | 24,407ms |
| Health Care and Social Assistance | 25 | 24 | 96.0% | 5.83/10 | 25,888ms |
| Information | 25 | 25 | 100.0% | 5.8/10 | 31,631ms |
| Manufacturing | 25 | 23 | 92.0% | 6.0/10 | 26,018ms |
| Professional, Scientific, and Technical  | 25 | 24 | 96.0% | 5.62/10 | 25,299ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 6.17/10 | 24,295ms |
| Retail Trade | 20 | 20 | 100.0% | 6.95/10 | 23,900ms |
| Wholesale Trade | 25 | 21 | 84.0% | 6.05/10 | 21,109ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 7/10 | 21113ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 3/10 | 22054ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 7 | 6/10 | 23627ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 17 | 5/10 | 20098ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 5/10 | 16137ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 22744ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 13970ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 6/10 | 26945ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 4 | 8/10 | 26527ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | Yes | 6 | 5/10 | 28256ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 4 | 5/10 | 28981ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 7/10 | 25218ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 1 | 5/10 | 27139ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 0 | 3/10 | 42421ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | Yes | 1 | 2/10 | 19817ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 27747ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 21159ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 31269ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 5/10 | 19426ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 5/10 | 34249ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 28312ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 4/10 | 24458ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 6 | 6/10 | 28203ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 5 | 3/10 | 49813ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 6 | 6/10 | 30878ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 22973ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 14097ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 17800ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 16001ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 7/10 | 26642ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 30903ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 8/10 | 27848ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 5/10 | 23761ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 6/10 | 20325ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 6 | 6/10 | 29151ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 3/10 | 23905ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 3 | 7/10 | 28023ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 9 | 6/10 | 31676ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 6/10 | 32335ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 27572ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 21275ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 21006ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 5/10 | 16588ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 6 | 8/10 | 17146ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 5 | 5/10 | 29349ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 6/10 | 19125ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 5 | 5/10 | 28083ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 5 | 8/10 | 18480ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 8/10 | 20756ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 7/10 | 20708ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 26659ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 9/10 | 52577ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 6 | 8/10 | 37524ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | 8/10 | 26534ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 2 | 6/10 | 40675ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 2 | 8/10 | 23443ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | Yes | 5 | 4/10 | 30519ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 3/10 | 28574ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | - | 3 | 3/10 | 30137ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 3/10 | 24204ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 3/10 | 26013ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 6/10 | 23090ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 4 | 7/10 | 34805ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 2 | 3/10 | 37240ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 6/10 | 30804ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 26217ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 2/10 | 27139ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 6/10 | 21123ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 8/10 | 32520ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | 6/10 | 18481ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 14764ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 23001ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 3/10 | 20993ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 2 | 6/10 | 17208ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 24669ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 27298ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 6/10 | 34054ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 3/10 | 29909ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 4/10 | 26522ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 11 | 4/10 | 28178ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 25381ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 24500ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 26939ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 25377ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 21095ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 5/10 | 18868ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 23230ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 6 | 4/10 | 24180ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 19543ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 17041ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 6/10 | 23432ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | 7/10 | 12349ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 8/10 | 12270ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 10 | 7/10 | 28435ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 6 | 6/10 | 27877ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 26570ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 5/10 | 29594ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 21670ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 8/10 | 31880ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 31672ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 2 | 8/10 | 27230ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | 6/10 | 39408ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 7/10 | 27237ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 6 | 6/10 | 36337ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | 7/10 | 41368ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 5/10 | 34189ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 32522ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 8/10 | 30243ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 5/10 | 27391ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 36805ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 6/10 | 27556ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 5 | 4/10 | 35075ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 5/10 | 31531ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 5 | 6/10 | 26192ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 5/10 | 26252ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 39012ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 7/10 | 19786ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 3 | 6/10 | 39002ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 3/10 | 17338ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 5 | 7/10 | 39245ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 3/10 | 19957ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 7/10 | 16344ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ✅ success | Yes | 8 | 9/10 | 25437ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 22 | 4/10 | 31163ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 6/10 | 27556ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 6/10 | 25030ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 8/10 | 25353ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 8/10 | 24727ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 2 | 7/10 | 32986ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 8 | 4/10 | 43665ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 28696ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 7/10 | 29510ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 23755ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 19007ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 4 | 8/10 | 30067ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 6/10 | 19575ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 32642ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 6/10 | 18298ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 8/10 | 17875ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 5 | 5/10 | 20703ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 17466ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 23643ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 7/10 | 24996ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 20125ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 25740ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 9/10 | 19754ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 7/10 | 25834ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 8/10 | 29466ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 5 | 8/10 | 30805ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | Yes | 5 | 8/10 | 35746ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | Yes | 2 | 8/10 | 32129ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 42376ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 31311ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 4 | 3/10 | 44954ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | Yes | 3 | 7/10 | 23811ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 18968ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 17361ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 4 | 6/10 | 24036ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 8 | 8/10 | 34056ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 5 | 6/10 | 29606ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 7/10 | 25045ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 6/10 | 25371ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 3/10 | 12937ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 23650ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 7/10 | 25757ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 9 | 8/10 | 29163ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 7/10 | 24749ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | 7/10 | 18054ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 13 | 5/10 | 29872ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 5 | 3/10 | 23716ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 7/10 | 16928ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 3/10 | 24117ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 11 | 6/10 | 27606ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 8/10 | 24601ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 8/10 | 26930ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 18000ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 6/10 | 23276ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 7/10 | 23633ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 4 | 6/10 | 23560ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 5 | 4/10 | 20790ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 8/10 | 17513ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 7/10 | 16487ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 4/10 | 18644ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 4/10 | 20378ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 7 | 3/10 | 22347ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 7/10 | 21819ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 6/10 | 18799ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 6 | 6/10 | 16172ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 3/10 | 13935ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | Yes | 4 | 6/10 | 19913ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 14382ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 11 | 8/10 | 18369ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 6/10 | 28318ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 8/10 | 20695ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 7/10 | 27711ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 7/10 | 26138ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 25715ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 24802ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 5/10 | 19540ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 4/10 | 16068ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 5/10 | 17105ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 20145ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 4/10 | 18491ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 6 | 8/10 | 20728ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 6 | 6/10 | 19794ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 27862ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 3 | 5/10 | 21596ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 6/10 | 30555ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 3 | 5/10 | 18435ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 7/10 | 25531ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 18253ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 8/10 | 23152ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 4 | 6/10 | 24947ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 15795ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 4 | 5/10 | 13404ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 4/10 | 17840ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | Yes | 1 | 3/10 | 21662ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 18263ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 3/10 | 27397ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 27130ms |

## QA Issues

### ✅ `83d10b06…` — score 7/10
- QoQ variance is not placed in column J as specified.
- Sample selection does not clearly evidence inclusion of metrics A1 and C1.
- Column headers include an empty column causing misalignment with stated requirements.
  > 💡 Align column structure to requirements and explicitly document how each sampling criterion is satisfied.

### ❌ `7b08cd4d…` — score 3/10
- Revenue Detail sheet lacks all tour stop data and calculated amounts.
- Expense Summary contains no category values or source breakdowns.
- P&L Summary shows zero totals, indicating calculations not performed.
  > 💡 Populate all sheets with data from reference files and compute taxes, expenses, and net income accurately.

### ✅ `7d7fc9a7…` — score 6/10
- Text response is generic and does not evidence calculations or reconciliations.
- Includes unnecessary CONFIDENCE tag, reducing professional tone.
- No confirmation that Excel schedules actually reconcile to provided GL balances.
  > 💡 Summarize key figures and explicitly confirm GL reconciliation results in the response.

### ✅ `43dc9778…` — score 5/10
- Return described as draft with placeholders, not a completed 1040.
- No evidence schedules and forms are fully completed per IRS requirements.
- Text response summarizes intent rather than confirming accurate calculations.
  > 💡 Provide a fully completed 2024 Form 1040 PDF with all required schedules finalized.

### ✅ `ee09d943…` — score 5/10
- Response describes intent rather than confirming completed April updates.
- Workbook content accuracy and tab updates are not demonstrated or summarized.
- Unnecessary source files were produced instead of only the consolidated deliverable.
  > 💡 Provide a brief completion summary confirming updated tabs, reconciliations, and key checks performed.

### ❌ `f84ea6ac…` — score 3/10
- Document lacks the required summary table.
- No five academic articles or study details are presented.
- Key findings and government implications are missing.
  > 💡 Add a one-page table summarizing five post-2020 public studies with findings and implications.

### ✅ `a328feea…` — score 9/10
- Backup contact not specified if Supervisor or Team Lead is unreachable.
- Consequences for non-compliance are not defined.
  > 💡 Add a brief backup contact protocol and compliance expectations to strengthen clarity and enforcement.

### ✅ `27e8912c…` — score 6/10
- Organizational Action Items document lacks the required tracking table.
- Employee and workstation detail fields are missing in the action items document.
- Public-domain status and source attribution of images are not clearly stated.
  > 💡 Add the required table with tracking fields and explicitly cite public-domain image sources.

### ✅ `17111c03…` — score 8/10
- Minor typographical truncation appears in memo text ("alongsid").
- Text response is high-level and lacks summary of memo specifics.
  > 💡 Proofread final memo text and briefly summarize key schedule details in the response.

### ✅ `c44e9b62…` — score 5/10
- Revised organizational chart is a text summary, not a visual chart with highlighted reduced positions.
- Regional Support Services 10% reduction is not clearly reflected or quantified in deliverables.
- FTE reduction calculations are not explicitly shown to confirm minimum 4% achieved.
  > 💡 Provide a true revised org chart with visual reductions and clearly document FTE calculations by unit.

### ✅ `99ac6944…` — score 5/10
- PDF lacks detailed pricing, cable list, accessories, and tools required by task.
- Mixer choice does not provide true onboard compression as specified.
- Independent mixes for two singers are not clearly supported by the IEM system.
  > 💡 Revise with a compliant analog mixer, explicit independent mixes, and full itemized budget details.

### ✅ `f9a1c16c…` — score 7/10
- FOH outputs from vocal XLR splits are not listed or labeled.
- Drummer wedge mix requirements for both vocalists are not specified.
- Output numbering counterclockwise from stage right is not clearly indicated.
  > 💡 Add explicit FOH split outputs and clarify monitor mix details and numbering orientation.

### ✅ `38889c3b…` — score 5/10
- Zip contents not inspected, stem presence and counts unverified.
- No evidence the provided drum reference track was actually used.
- Key changes, BPM, duration, and export specs are unverified claims.
  > 💡 Provide a contents manifest and brief technical report verifying stems, specs, and drum track usage.

### ❌ `ff85ee58…` — score 3/10
- No audio files were produced.
- Required resyncing, editing, and mixing were not performed.
- Output only restates intentions without deliverables.
  > 💡 Provide the actual mixed WAV file meeting all technical and loudness specifications.

### ❌ `4b894ae3…` — score 2/10
- No final stereo WAV mix was delivered.
- No evidence of bass edits or mixing was provided.
- Only a reference DOCX file was produced.
  > 💡 Deliver the edited bass and full 48k/24b stereo mix WAV as specified.

### ✅ `1b1ade2d…` — score 8/10
- Text response describes intent rather than summarizing key workflow elements.
  > 💡 Briefly summarize core workflow changes in the text response for executive clarity.

### ✅ `93b336f3…` — score 6/10
- Detailed INR cost breakdown and calculation methodology are missing.
- Introduces JV ownership assumptions not requested in original task.
- Document ends with truncated sentence and incomplete recommendations.
  > 💡 Add explicit INR cost tables, remove unrequested assumptions, and complete all sections cleanly.

### ✅ `15ddd28d…` — score 8/10
- Immediate three-week supply interruption contingency is not explicitly detailed.
- Safety certification milestones for electronics redevelopment are not clearly scheduled.
  > 💡 Add a week-by-week bridge plan and explicit certification milestones to strengthen execution readiness.

### ✅ `24d1e93f…` — score 5/10
- Vendor quotation and volume files lack numeric data used in NPV calculations.
- NPV calculations appear based on unstated assumptions not clearly quantified.
- Recommendation rationale contradicts Autolantic being highest-quote supplier.
  > 💡 Include explicit numeric inputs from quotations and volumes and clearly document all assumptions driving NPVs.

### ✅ `05389f78…` — score 5/10
- Quotation file lacks numeric cost figures required for INR calculations.
- Comparative analysis cannot be validated due to missing pricing and volume data.
- Quotation file incorrectly includes Juvoxa despite being excluded from replacement evaluation.
  > 💡 Provide complete vendor quotations with detailed cost breakdowns to enable a valid comparative analysis.

### ✅ `575f8679…` — score 8/10
- Text response summarizes intent rather than highlighting key evaluation elements.
- Appendix instruments are summarized but include limited sample questions.
- Summative evaluation timing and endpoints could be more explicit.
  > 💡 Add clearer outcome timelines and include brief sample items for each instrument.

### ❌ `a74ead3b…` — score 4/10
- Admits content is an approximation rather than following manuals closely.
- No evidence sessions align specifically with Sessions 13 and 14 manual content.
- Cannot verify inclusion of required elements due to lack of slide preview.
  > 💡 Revise slides to strictly match Sessions 13 and 14 manual content and document alignment.

### ✅ `bbe0a93b…` — score 6/10
- Resource guide omits several requested categories like financial assistance, clothing, counseling, pregnancy support.
- Follow-up tracking table headers are misordered and unclear in both assessments.
- Needs assessment DOCX files appear incomplete or truncated.
  > 💡 Expand resource categories and correct table formatting before final submission.

### ❌ `85d95ce5…` — score 3/10
- PDF length is 6 pages, not the required 8–15 pages.
- Template fields contain placeholders and incorrect entries, including social worker name and school name.
- Content appears incomplete and mismatched, including wrong reference notes and unfilled sections.
  > 💡 Revise the report to fully complete the template, correct placeholders, use correct notes, and meet length requirements.

### ✅ `76d10872…` — score 6/10
- Text response contains no actual report content or extracted case details.
- Extra DOCX file produced despite requirement specifying PDF submission.
- Report content cannot be verified for accuracy from provided response.
  > 💡 Include the full structured report content and ensure only the required PDF is delivered.

### ✅ `36d567ba…` — score 8/10
- Topic 8 cites 2 CFR 200 generally instead of a specific relevant section.
  > 💡 Add a specific Uniform Guidance citation to Topic 8 for clarity and compliance.

### ✅ `7bbfcfe9…` — score 9/10
- Some §3919 questions may be broader than the statute’s explicit language.
  > 💡 Consider tightening §3919 questions to mirror statutory wording more closely.

### ✅ `4c18ebae…` — score 7/10
- SAR contains placeholder '(link)' references instead of actual FinCEN links.
- Text response claims two deliverables but three files were produced.
- Original task analysis is incomplete due to truncated red flags section.
  > 💡 Replace placeholders with real references, align deliverables count, and complete all red flag analysis.

### ✅ `cebf301e…` — score 8/10
- Integration with the existing Express sales admin API is insufficiently specified.
- Security and compliance considerations for future payments are not detailed.
- No metrics or analytics plan is defined for the customer portal.
  > 💡 Add explicit integration, security, and analytics sections with concrete implementation details.

### ✅ `c2e8f271…` — score 8/10
- Commit message guidelines section appears incomplete or truncated in preview.
- Backend testing standards beyond React Testing Library are not explicitly addressed.
- No explicit linting or CI enforcement guidance is included.
  > 💡 Complete the commit section and add backend testing and CI enforcement standards.

### ✅ `2ea2e5b5…` — score 5/10
- Strategic level classification is incomplete and truncated.
- Output does not explicitly list activity classifications for margin, time, and strategy.
- Text response includes unnecessary confidence metadata.
  > 💡 Explicitly document all required activity classifications and ensure strategic levels are complete.

### ✅ `c357f0e2…` — score 6/10
- UAT test plan columns do not match the provided template headers.
- Viewer role incorrectly includes create idea actions, violating defined permissions.
- Role-based permission restrictions are not consistently enforced across test cases.
  > 💡 Align column headers to the template and correct test cases to strictly follow role permissions.

### ✅ `a45bc83b…` — score 6/10
- Layer 3 and 4 DDoS protection is inaccurately attributed solely to Cloud Armor.
- Use of official GCP icons in the architecture diagram is not clearly demonstrated.
- Architecture summary contains minor truncation or formatting errors.
  > 💡 Clarify DDoS protection layers, verify official GCP icons usage, and fix document formatting issues.

### ❌ `a10ec48c…` — score 3/10
- Document lacks required tables with five specified columns.
- No restaurant entries, hours, descriptions, directions, or categories are included.
- Restaurants are not sourced from the specified website or Google Maps.
  > 💡 Populate each cuisine section with complete tables and verified restaurant data per requirements.

### ✅ `fccaa4a1…` — score 7/10
- No visible Statue of Liberty photo included in the PDF.
- Details are not explicitly sourced or cited from TakeWalks.com.
- Icon-based visual styling is not clearly present in the layout.
  > 💡 Add a sourced image, explicit TakeWalks references, and clear iconography to meet all requirements.

### ✅ `f5d428fd…` — score 6/10
- PDF is five pages, not the requested concise two-page itinerary.
- No visible royalty-free photos included with each destination.
- No research sources or image attributions are cited.
  > 💡 Condense to two pages, embed one credited royalty-free image per day, and add brief source citations.

### ✅ `2fa8e956…` — score 6/10
- Footer titled Napa Valley Wineries is not evident in the document.
- Grape varieties are not shown in required purple text formatting.
- No sources or citations are provided for winery selection or drive times.
  > 💡 Add the specified footer, apply required text colors, and include clear source citations.

### ✅ `0e4fe8cd…` — score 6/10
- Incorrect airport code used for Istanbul Airport (IST listed as ISL).
- Return travel and June 4 homeward logistics are missing or incomplete.
- High-value individuals to connect with are minimally identified.
  > 💡 Correct airport codes, add full return-day logistics, and expand curated introductions to notable local figures.

### ✅ `a0ef404e…` — score 9/10
- Text response is descriptive rather than summarizing key guide contents.
  > 💡 Briefly summarize major sections of the guide in the text response for clarity.

### ✅ `aa071045…` — score 5/10
- Service Request Form lacks required details beyond the title.
- Damage revenue totals are inconsistent across summary and breakdown sheets.
- Service request omits mirror replacement description and vehicle status.
  > 💡 Populate the service form fully and reconcile all revenue calculations to match source data.

### ✅ `476db143…` — score 8/10
- Resident email is generic and not customized with individual inspection dates.
  > 💡 Personalize each resident email with their confirmed inspection date and unit number.

### ✅ `61f546a8…` — score 5/10
- Apartment-based section uses vague dates instead of specific scheduled workdays.
- On-site staff two-day schedules are not explicitly assigned or dated.
- Appliance delivery extra-day impacts are not clearly reflected in timelines.
  > 💡 Revise the report with exact dates per unit, explicitly sequencing staff, vendors, and appliance deliveries.

### ✅ `f3351922…` — score 6/10
- Email document appears truncated and ends mid-sentence.
- Benefits for transitioning service members are incomplete due to truncation.
- Text response describes deliverable instead of providing substantive content.
  > 💡 Complete the email content fully and ensure the document is not truncated before delivery.

### ✅ `61717508…` — score 5/10
- Training deck is only two pages, not approximately ten pages.
- Senior Safe Act and FINRA Rule 2165 explanations are missing or insufficient.
- An extra internal policy PDF was produced but not requested.
  > 💡 Expand the training deck to full length and clearly add plain‑language regulatory sections.

### ✅ `0ed38524…` — score 8/10
- District 1 talking points list the General category twice.
- Talking points are generic and lack district-specific action details.
- Text response describes process rather than summarizing results.
  > 💡 Refine talking points with distinct categories and specific next-step actions per district.

### ✅ `87da214f…` — score 8/10
- Text response is generic and lacks a concise summary of findings.
  > 💡 Include a brief executive summary of key results and financial impact in the text response.

### ✅ `d025a41c…` — score 7/10
- Unrequested extra files were produced beyond the single required Case Feedback document.
- Compliance with bold headings and 1.5 spacing is not clearly verifiable.
- Text response describes intent rather than summarizing completed deliverable.
  > 💡 Deliver only the required Case Feedback.docx and briefly confirm formatting compliance in the response.

### ✅ `401a07f1…` — score 6/10
- Referenced outlets lack explicit hyperlinks to verifiable articles.
  > 💡 Add clear in-text hyperlinks to specific Nature, Science, Scientific American, and Guardian articles.

### ✅ `9a8c8e28…` — score 8/10
- Text response is high-level and does not summarise document contents.
- Bibliography and further reading are not clearly evidenced in the preview.
- Quiz answer key and scoring guide are not verified in the preview.
  > 💡 Add a brief contents summary and explicitly confirm bibliography, contact instructions, and quiz answer key presence.

### ✅ `ec2fccc9…` — score 6/10
- Secondary keywords list is not clearly presented at the end of the article.
- Pull quote and its caption are not clearly identified.
- Compliance with the 1,500-word requirement is not explicitly verifiable.
  > 💡 Add a clear secondary keyword list, explicit pull quote caption, and confirm final word count.

### ✅ `8c8fc328…` — score 8/10
- Timestamps and scene structure cannot be verified from the text response alone.
  > 💡 Include a brief script excerpt or timestamp sample in the text response for verification.

### ❌ `e222075d…` — score 4/10
- No 30-second H.264 MP4 export was delivered.
- Scratch voiceover and music audio files were not provided.
- Stock log links are generic sites, not direct preview clips.
  > 💡 Deliver a complete 30-second MP4 with scratch audio and direct stock preview links.

### ❌ `c94452e4…` — score 3/10
- No 15-second H.264 MP4 video was produced or delivered.
- No actual stock footage or music sources were selected or edited.
- Output replaces required finished spot with pre-production planning documents.
  > 💡 Produce and deliver the actual 15-second edited broadcast spot using stock footage and music as specified.

### ❌ `75401f7c…` — score 3/10
- Final edited MP4 showreel was not delivered.
- Required duration, pacing, and audio sync cannot be verified without the video.
- Deliverables do not meet the task's explicit video output requirement.
  > 💡 Produce and deliver the final 1920x1080 H.264 MP4 showreel matching the brief.

### ❌ `a941b6d8…` — score 3/10
- No composited video file was created or delivered.
- Stabilization, masking, tracking, and compositing were not actually performed.
- Flash and smoke effects were only described, not executed.
  > 💡 Produce and deliver the finished composited video matching the base clip specifications.

### ❌ `8079e27d…` — score 3/10
- Excel contains no populated market data for any S&P 500 companies.
- Publicly available data was not leveraged despite being required.
- Missing all 500 companies and complete sub-sector coverage with metrics.
  > 💡 Populate the workbook with current public market data for all S&P 500 constituents and sub-sectors.

### ✅ `e21cd746…` — score 6/10
- Flexport is not a last mile delivery business and misfits the stated focus.
- Roadie is no longer a private target, having been acquired by UPS.
- Some valuations and customer details appear high-level and not clearly sourced.
  > 💡 Refine the private target list to pure-play last mile companies and verify valuations and ownership status.

### ✅ `9e8607e7…` — score 7/10
- Slide count is ~20, below the requested ~30-slide length.
- Delivered content does not fully match the stated ~30-slide scope.
- Limited depth in fintech subsector breakdowns and examples.
  > 💡 Expand to ~30 slides with deeper fintech subsector views and regional examples.

### ❌ `c7d83f01…` — score 3/10
- Python notebook implementing pricing methods is missing.
- No actual code for binomial, finite-difference, or Monte Carlo methods provided.
- Visualizations and runtime benchmarks are incomplete and limited.
  > 💡 Provide a full Jupyter notebook with implemented methods, benchmarks, and comprehensive visual analysis.

### ✅ `46b34f78…` — score 6/10
- Issuer analyses use placeholders rather than named companies.
- No explicit use or citation of provided reference data sources.
- Portfolio constraints are mentioned but not quantified or enforced.
  > 💡 Name specific issuers, cite reference data explicitly, and quantify allocations and duration compliance.

### ✅ `a1963a68…` — score 6/10
- Future-proofing innovation and sustainability pathways slide is missing.
- Core content appears fewer than the required 5–6 strategy slides.
- Lacks robust data, metrics, and cited Korean market research sources.
  > 💡 Add a future-proofing slide with data-backed initiatives and expand content to meet slide requirements.

### ❌ `5f6c57dd…` — score 2/10
- Required five analytical worksheets are missing; only raw data is present.
- No dropdown branch or aggregate selection functionality is evident.
- No income statements, rankings, regional comparisons, or metric calculations are built.
  > 💡 Build all five specified Excel worksheets with calculations, variances, rankings, and dropdown-driven branch aggregation.

### ✅ `b39a5aa7…` — score 6/10
- No visible input fields for adjusting negotiated terms or rates.
- Projections lack quarterly detail by compensation type.
- Calculations tab is minimal and not fully transparent.
  > 💡 Add clear input assumptions, detailed calculation tabs, and projection breakdowns by pay type.

### ✅ `4520f882…` — score 6/10
- Spreadsheet calculations and validations are not described or evidenced in the response.
- No confirmation that payroll totals by CBA category are correctly implemented.
- Robustness for all orchestra configurations is asserted but not demonstrated.
  > 💡 Provide a brief summary of key spreadsheet sheets, formulas, and validation rules to evidence compliance.

### ✅ `ec591973…` — score 6/10
- Text response describes intent but does not present the actual strategy content.
- Slide content cannot be verified against requirements from provided preview.
  > 💡 Include a brief summary of slide content and explicitly map elements to stated requirements.

### ✅ `62f04c2f…` — score 7/10
- Excel form does not clearly show required sales rep, GM, and Sales Manager signature sections.
- Excel form preview does not show the required freight prepayment and restocking fee note.

### ❌ `3f821c2d…` — score 3/10
- Stock flow tables are largely blank with missing sales, EOM inventory, and turn calculations.
- Omni-level table, seasonal turn, and January EOM inventory targets are not shown or validated.
- Excel lacks required working formulas and complete LY vs TY side-by-side formatting.
  > 💡 Complete all monthly values with formulas, add omni rollups, and validate against turn and inventory targets.

### ✅ `e996036e…` — score 6/10
- Cash flow timing by quarter is not shown or modeled.
- No visual chart comparing scenario favorability is included.
- Marketing allowance and revenue are not shown on a quarterly basis.
  > 💡 Add quarterly cash flow modeling and a comparison chart to fully meet scenario analysis requirements.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a Visio-style visual flow and appears as brief narrative text.
- Roadmap does not clearly depict step-by-step flow starting from MA placing patient call.
- An extra unrequested file was produced, creating potential scope confusion.
  > 💡 Convert the Roadmap into a clear visual flowchart in Word and remove unrequested files.

### ❌ `0353ee0c…` — score 3/10
- Did not compile or reproduce presumptive exposures, conditions, locations, or dates.
- PDF appears to list links instead of consolidated content from Document B.
- Response contradicts task by citing internet access limitations.
  > 💡 Regenerate the PDF by extracting and organizing all presumptive details from the provided links.

### ❌ `40a8c4b1…` — score 4/10
- Response describes intent instead of verifying populated schedule content.
- No confirmation column C is fully populated per priorities and conditions.
- Unused optional topics highlighting is not demonstrated.
  > 💡 Explicitly validate and summarize the completed Excel schedule against each stated requirement.

### ❌ `4d1a8410…` — score 4/10
- Interview schedule lacks required detailed table with room-by-room timings and applicant rotations.
- Mandatory breaks and constraints for Dr. Jones and Dr. Garrett are not explicitly scheduled.
- Personal itineraries omit specific physician interviews, room numbers, and transition buffers.
  > 💡 Rebuild the schedule with a detailed table showing all rooms, applicants, interview blocks, buffers, breaks, and constraints.

### ✅ `11e1b169…` — score 8/10
- KRS 503.090 section appears truncated mid-sentence in the PDF.
- Minor formatting inconsistency near the end of the use-of-force section.
  > 💡 Review and correct the KRS 503.090 section to ensure complete, polished text.

### ✅ `a95a5829…` — score 8/10
- Approval section preview appears truncated, making signature workflow verification unclear.
- Policy does not explicitly describe required signature blocks or approval sequence formatting.
- Excel logging instructions may lack explicit column definitions and data standards.
  > 💡 Add explicit approval signature blocks and detailed Excel column standards to strengthen audit readiness.

### ✅ `22c0809b…` — score 7/10
- Signature section is truncated with a typo ('Date Submitte').
- Action pathway indicators lack guidance examples compared to other pathways.

### ✅ `bf68f2ad…` — score 5/10
- Starting past-due backlog of 438.81 hours is not incorporated.
- Spreadsheet only evaluates 6-day capacity, not reductions to 5-day or regular time.
- Text response describes intent but does not summarize actual results or timing.
  > 💡 Incorporate initial backlog, compare multiple workweek scenarios, and clearly state when overtime can end.

### ✅ `efca245f…` — score 6/10
- Scenario 3 violates no-overtime constraint and uses unsupported 170 sets/day capacity.
- Excel lacks explicit cumulative backlog tally and grill guard daily production detail.
- Stat holidays and April 13 transit requirement are not modeled.
  > 💡 Revise scenarios to respect constraints, correct capacities, and add full backlog, holiday, and shipment timing detail.

### ❌ `9e39df84…` — score 4/10
- Average Output and Total Output columns lack formulas and calculated values.
- Dashboard worksheet lacks required PivotTables, slicers, and data validation controls.
- Required charts are not embedded in the Dashboard workbook.
  > 💡 Add formulas, PivotTables with slicers, and embed all four charts directly in the Dashboard sheet.

### ✅ `68d8d901…` — score 6/10
- Text response lacks any concrete schedule, assignments, or sequence details.
- No explicit confirmation production plan meets 250,000 lbs in four weeks using full batches.
- Excel content is not summarized or validated against stated requirements.
  > 💡 Add a brief results summary validating targets, staffing, and dryer throughput from the Excel plan.

### ✅ `bd72994f…` — score 6/10
- No luxury brand or specific 2025 resort collection is identified.
- Looks are generic and not sourced from an official brand lookbook.
- Response cites offline limitations that conflict with task expectations.
  > 💡 Select a named luxury brand and base all looks on its official 2025 resort collection.

### ✅ `211d0093…` — score 7/10
- No clear field for capturing full employee names per task.
- Text response claims one-page PDF, but file is four pages.
- Column labeling is confusing between assigned, initials, and notes.
  > 💡 Add a distinct employee name column and clarify column headers for usability.

### ✅ `d4525420…` — score 8/10
- Document includes a title, creating two paragraphs instead of a single paragraph.
  > 💡 Remove the title or merge it into the paragraph to strictly match instructions.

### ✅ `45c6237b…` — score 7/10
- Final slide lacks a consolidated summary table of all items, SKUs, pricing, and quantities.
- Next Season Assortment slides do not clearly display referenced vendor images in the PDF preview.
  > 💡 Add a clear summary table slide and ensure next season slides visibly include vendor product images.

### ✅ `cecac8f9…` — score 6/10
- Uses USD currency despite UK store context requiring GBP.
- Team launch deck is very brief and lacks detailed weekend instructions.
- Promotional offers are vague and not clearly pulled from Marketing Email.
  > 💡 Localize metrics to GBP and expand the deck with clearer offers and execution guidance.

### ✅ `8f9e8bcd…` — score 8/10
- Practice section lacks examples for need and trust objection types.
- Core Strategies heading contains a grammatical error.
- Practice scenarios are limited and may reduce skill reinforcement.
  > 💡 Add practice examples for all objection types and expand scenarios for stronger training impact.

### ✅ `0fad6023…` — score 5/10
- Automatic calculations for total used and remaining inches are missing.
- Total used space should be a single summed value, not per-column blanks.
- Visual planogram lacks clear pan boundaries or scalable visual cues.
  > 💡 Add clear formulas to sum pan widths and display used versus remaining inches prominently.

### ✅ `02314fc6…` — score 8/10
- Text response summarizes intent instead of detailing checklist contents.
- LP review sign-off section is missing in the checklist.
- Scoring does not specify numeric pass percentage, only missed items count.
  > 💡 Add LP sign-off and clarify scoring methodology with a clear pass percentage.

### ✅ `4d61a19a…` — score 8/10
- Excel template does not include visible instructions or notes for store users.
- Sheet protection for non-editable fields is not clearly verifiable.
- PowerPoint slide count and exact slide content cannot be confirmed from preview.
  > 💡 Add a brief instructions tab and clearly document sheet protection and process steps.

### ✅ `6436ff9e…` — score 8/10
- Final testimonials section appears truncated or incomplete in the document preview.
  > 💡 Add a brief privacy notice and confirm the testimonials section text is complete.

### ✅ `8a7b6fca…` — score 8/10
- Some labels appear truncated or awkwardly line-broken in the PDF.
- Decision point wording is partially unclear due to formatting.
- Manual process steps could be more explicitly sequenced.
  > 💡 Refine PDF layout and text spacing to improve clarity and readability for leadership review.

### ✅ `40a99a31…` — score 6/10
- Camera requirement of minimum six units is not clearly specified or itemized.
- Hardware selections lack detailed justification and safety standard references.
- PDF report is overly brief and missing required depth and specifics.
  > 💡 Expand documentation with explicit quantities, standards compliance, and detailed hardware justification.

### ✅ `b9665ca1…` — score 7/10
- PLC indicator NO channels ES1.SIG, ES2.SIG, ES3.SIG are not clearly shown.
- Drawing tool used is PowerPoint, not standard electrical CAD software.
- Presence of a start button conflicts with specified safety reset-only requirement.
  > 💡 Revise the schematic to explicitly include PLC indicator wiring and remove non-specified controls using proper CAD software.

### ✅ `c6269101…` — score 6/10
- Text response provides no actual findings, metrics, or conclusions.
- Extended analysis and greatest-variability identification are not explicitly stated.
- Includes unnecessary CONFIDENCE tag not requested in requirements.
  > 💡 Summarize key capability results, stability conclusions, and highest-variability process directly in the text response.

### ✅ `be830ca0…` — score 7/10
- Text response promises deliverables but provides no actual analysis results or findings.
- Statistical conclusions for ANOVA and control charts are not explicitly stated.
- Use of CONFIDENCE tag is unprofessional and not requested.
  > 💡 Include summarized statistical results and conclusions directly in the response and remove extraneous tags.

### ✅ `cd9efc18…` — score 5/10
- PDF length is 4 pages, not the required approximately 8–11 pages.
- Execution section with witnesses, notary, and execution date is not shown.
- Generated response promised comprehensive delivery but actual content appears incomplete.
  > 💡 Expand the will to full length with complete execution, affidavits, and standard Texas provisions.

### ✅ `a97369c7…` — score 6/10
- Delaware Senate Bill 313 is not clearly discussed or applied.
- Moelis decision is mischaracterized as a Delaware Supreme Court holding.
- Analysis of Marcus’s controlling-stockholder status is underdeveloped.
  > 💡 Add a clear SB 313 analysis and refine controlling-stockholder and case law discussions.

### ✅ `3f625cb2…` — score 8/10
- California privacy law analysis is high-level and lacks statutory specificity.
- Factual assumptions about data collection lack evidentiary discussion.
  > 💡 Add precise California statutory citations and briefly note evidence needed to support the alleged data collection.

### ✅ `aad21e4c…` — score 5/10
- Anti-dilution and 10% minimum ownership mechanics are not clearly specified.
- Pre-emptive rights and minority consent rights are insufficiently detailed.
- Capitalization schedule exhibit before and after issuance is missing.
  > 💡 Add detailed ownership protection provisions and include a complete capitalization schedule exhibit.

### ✅ `8314d1b1…` — score 8/10
- Minor typographical truncation appears in the document text.
- Discussion of March 2025 DGCL amendments is relatively high-level.
- Text response is descriptive rather than substantive legal analysis.
  > 💡 Proofread the memo and slightly expand the statutory amendment analysis for added depth.

### ✅ `5e2b6aab…` — score 6/10
- Thermal performance and overheating prevention across specified temperatures are not addressed.
- Water ingress sealing strategy and features are insufficiently detailed.
- STEP models content and completeness cannot be verified from provided archive.
  > 💡 Add explicit sealing features, thermal mitigation concepts, and verify complete STEP geometry before review.

### ❌ `46fc494e…` — score 4/10
- Back-face temperatures remain at 25 °C throughout, indicating no transient heat penetration.
- Node temperature profiles and plots appear inconsistent with severe external heating conditions.
- No numerical transient solution details or verification of the 22-node model are provided.
  > 💡 Recompute the transient conduction with validated boundary conditions and include credible temperature evolution results.

### ✅ `3940b7e7…` — score 5/10
- Report lacks required Discussion and Conclusion sections with aerodynamic implications.
- Key performance metrics like lift, drag, shock formation are not discussed.
- Generated text describes intent rather than delivering full drafted content.
  > 💡 Expand the PDF to include complete analysis, discussion, conclusions, and explicit aerodynamic performance assessments.

### ✅ `8077e700…` — score 6/10
- Report lacks explicit analysis and figures for AISI 1045 hardness trends.
- No tables or quantitative time-to-peak hardness values are presented.
- PDF is very brief and omits detailed treatment efficiency comparison.

### ✅ `5a2d70da…` — score 5/10
- Master Tool List lacks visible subtotal, sales tax, and grand total calculations.
- Manufacturing steps file is minimal and lacks detailed operations and sequencing.
- Budget compliance and tooling quantities for breakage are not clearly demonstrated.
  > 💡 Add detailed machining operations and include explicit budget, tax, and total cost calculations.

### ✅ `74d6e8b0…` — score 8/10
- Text response is generic and does not summarize key guideline recommendations.
  > 💡 Add a brief executive summary and confirm all citations are current and clearly formatted.

### ✅ `81db15ff…` — score 7/10
- Some state regulatory details appear inaccurate or outdated, particularly PA supervision limits.
- Pennsylvania NP chart signature requirement is overstated and may be incorrect.
- Arizona PA chart signature requirement is oversimplified and not universally mandated.
  > 💡 Validate each state’s NP and PA regulations against current statutes or licensing board guidance.

### ✅ `61b0946a…` — score 6/10
- Original task did not explicitly request a proposal document or budget analysis files.
- Cost savings assumptions are not clearly derived from provided freeze/thaw cycle constraints.
- Procedure capacity estimates lack quantitative linkage to multi-department sharing.
  > 💡 Explicitly map calculations and deliverables directly to stated constraints and clarify assumptions.

### ❌ `61e7b9c6…` — score 3/10
- Formulary is largely empty and missing most FDA-approved and off-label menopause medications.
- Incorrect generic listed for Bijuva and minimal pricing data provided.
- Completed file does not fully follow the provided template structure.
  > 💡 Populate the spreadsheet with a complete, accurate medication list and verified monthly cash prices per template.

### ✅ `c9bf9801…` — score 7/10
- NCIPC Mentoring Program acknowledgment is missing from the credits section.
- Required 4-month and 8-month evaluation form documents were not produced.
- Guide content is high-level with limited detail on roles and responsibilities.
  > 💡 Add the missing credits, create evaluation form files, and expand role descriptions for completeness.

### ❌ `f1be6436…` — score 3/10
- Document uses estimated costs without real-time web research or verifiable screenshots.
- Total costs, departmental coverage, and discretionary fund calculations are missing.
- Travel plans ignore Dr. Doe’s April 18 departure constraint.
  > 💡 Redo with live research, accurate dates, real screenshots, and complete cost allocation calculations.

### ✅ `41f6ef59…` — score 7/10
- Spreadsheet lacks visible dropdowns, checkboxes, or data validation for efficient entry.
- Subscription type field does not clearly restrict choices to Plans A, B, and C.
- Excel file name does not exactly match the requested title with spaces.
  > 💡 Add data validation dropdowns and checkboxes, and align the Excel file name exactly to the requested title.

### ❌ `6d2c8e55…` — score 4/10
- Articles are placeholders, not actual peer-reviewed open-access PDFs.
- Generated output admits task incomplete pending supervisory approval.
- Requirements to select real articles within 10 years are unmet.
  > 💡 Replace placeholders with verified open-access peer-reviewed PDFs and finalize all materials.

### ✅ `4b98ccce…` — score 6/10
- Excel content not verified for exact columns, patient data accuracy, and required signatures.
- No evidence letters include all Letter Template elements and HIPAA clauses.
- Signature section with name, employee ID, and 'signed' not confirmed in Excel.
  > 💡 Provide previews or confirmation of Excel tables and letter contents meeting all specified requirements.

### ✅ `60221cd0…` — score 6/10
- Virginia does not register voters by party; primaries are open.
- Early voting start date appears incorrect for November 4, 2025.
- An extra DOCX file was produced despite PDF-only requirement.
  > 💡 Verify election facts with the Virginia Department of Elections and deliver only the required PDF.

### ✅ `ef8719da…` — score 8/10
- Background references list article titles without explicit hyperlinks.
- Some reference section content appears truncated or incomplete.
  > 💡 Add full clickable URLs for all cited background articles to strengthen sourcing clarity.

### ✅ `3baa0009…` — score 8/10
- Chart preview does not show explicit growth values or year labels for 2024, 2025, and 2027.
  > 💡 Add clear data labels and source annotation directly on the chart for transparency.

### ✅ `5d0feb24…` — score 7/10
- Novel methods and findings of arXiv:2401.11815 are not clearly summarized or highlighted.
- Some historical details appear ambiguous, including cataloging and discovery timelines.
- Text response promises coverage breadth without summarizing key editorial conclusions.
  > 💡 Add a concise summary explicitly tying edits to the paper’s novel methodology and future implications.

### ❌ `6974adea…` — score 4/10
- Text response is a meta description, not the requested feature article.
- Article content, word count, and SEO elements are not demonstrated in the response.
- Compliance with Guardian style and interview usage cannot be verified.
  > 💡 Include the full article text or a substantial excerpt with word count and structure details.

### ✅ `1a78e076…` — score 6/10
- Document likely does not meet the 10–15 page length requirement.
- Explicit analysis of financial impact and morbidity/mortality is unclear or limited.
- Reference list completeness and adherence to the 30-reference limit is not verified.
  > 💡 Expand content to meet page length and clearly address financial, morbidity, and mortality outcomes.

### ✅ `1b9ec237…` — score 7/10
- Slide count cannot be verified without previewing the presentation.
- Inclusion of speaker notes cannot be confirmed from available information.
- Presence and quality of the pre-test multiple-choice question are unverified.
  > 💡 Provide a brief slide-by-slide outline or preview to verify all instructional requirements are met.

### ✅ `0112fc9b…` — score 8/10
- Family history summarized as noncontributory, losing specific details provided in original case.
  > 💡 Preserve full family history details to maintain accuracy and completeness of the medical record.

### ✅ `772e7524…` — score 8/10
- Follow-up timeframe and reassessment plan are not clearly specified.
- Antibiotic rationale could better reference local CAP guidelines.
- Work restriction sentence appears truncated or incomplete.
  > 💡 Add explicit follow-up timing and guideline-based justification for antibiotic selection.

### ✅ `b5d2e6f1…` — score 6/10
- Pivot tables and required summary tabs are not explicitly verified in the file preview.
- Exact requested column headers and naming conventions are not confirmed.
- Sell-through calculations and grand totals are not clearly demonstrated.
  > 💡 Open the analyzed file and clearly validate pivot tables, headers, ST% formulas, and grand totals.

### ✅ `47ef842d…` — score 6/10
- Weekly unit rate calculation appears incorrect and unrealistically uniform across stores.
- Weeks of supply is averaged rather than derived from total inventory and total sales.
- Active store and out-of-stock definitions are not clearly validated against requirements.
  > 💡 Recalculate sales rates and WOS using aggregated totals per UPC and explicitly document active store logic.

### ✅ `1137e2bb…` — score 8/10
- Text response describes planned delivery rather than summarizing completed analytical findings.
  > 💡 Briefly summarize key error counts and top problematic SKUs in the text response.

### ✅ `c3525d4d…` — score 5/10
- Final store list marks all stores as ADDED instead of identifying only new additions.
- Removed stores and specific checks like stores 4099 and 3737 are not identified.
- Original store count and total cost conflict with values stated in the email trail.
  > 💡 Reconcile store lists accurately, flag only true additions or removals, and align counts and costs to source emails.

### ✅ `9a0d8d36…` — score 6/10
- Text response lacks concrete tax calculations or hypothetical figures.
- No explicit discussion of vesting timing or exercise restrictions is shown.
- Inclusion of CONFIDENCE tag is unprofessional and unnecessary.
  > 💡 Summarize specific slide content, calculations, and tax assumptions to clearly evidence requirement fulfillment.

### ✅ `664a42e5…` — score 6/10
- Text response describes intent rather than summarizing actual presentation content.
- Cannot verify inclusion of 2025 gift tax exclusion specifics.
- No confirmation of step-by-step or side-by-side comparison slides.
  > 💡 Provide a brief slide-by-slide summary confirming all required elements are included.

### ✅ `feb5eefc…` — score 7/10
- No quantitative estate tax projections or calculations comparing GRAT versus CRAT outcomes.
- Marital planning considerations and use of both spouses’ exemptions are not addressed.
- CRAT rules and limitations are summarized but lack technical depth.
  > 💡 Add numeric estate tax illustrations and marital exemption planning to strengthen the recommendation.

### ✅ `3600de06…` — score 6/10
- Slide count and content cannot be verified from the file preview.
- Explicit FINRA and NAIC source citations are not confirmed in slides.
- No evidence each required comparison topic is covered per slide.
  > 💡 Provide a slide-by-slide outline or screenshots confirming sources, topics, and total slide count.

### ✅ `c657103b…` — score 6/10
- Traditional IRA starting balance exceeds stated $3.5M assumption.
- Estate tax exposure and savings are not modeled or quantified.
- Required PowerPoint template usage is not evidenced or confirmed.
  > 💡 Align assumptions precisely, document template compliance, and add explicit estate tax impact analysis.

### ✅ `f9f82549…` — score 7/10
- PDF title does not match required "Missing Bank Deposits Investigation".
- An extra DOCX file was produced but not requested.
- PowerPoint was single file instead of separate documents per header.
  > 💡 Align file titles and formats exactly with requirements and remove unrequested deliverables.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance start time conflicts with stated courtesy start of 7:30 p.m.
- Surveillance extended beyond the client’s requested 1:00 a.m. end time.
  > 💡 Briefly explain the early arrival and extended end time to align with client instructions.

### ✅ `84322284…` — score 8/10
- Daily timeline reconstruction lacks date-by-date detail and specific time entries.
- Staff interactions are summarized but not analyzed individually across the full week.
- Reporting investigator identity is vague and lacks full attribution.
  > 💡 Expand the timeline with daily entries and deeper staff-specific analysis to strengthen evidentiary value.

### ✅ `a46d5cd2…` — score 8/10
- Text response lacks substantive summary of investigative findings.
- Photographic evidence pages lack captions or contextual descriptions.
- Inclusion of CONFIDENCE tag is unprofessional and unnecessary.
  > 💡 Add concise executive summary text and labeled photo captions within the report.

### ✅ `6241e678…` — score 8/10
- Includes additional production tasks not requested, expanding scope without justification.
- Color-coding legend is not explicitly labeled in the files.
- Text response describes schedule but lacks a brief summary of key milestones.
  > 💡 Add a clear color legend and briefly justify or remove non-requested tasks.

### ✅ `e14e32ba…` — score 6/10
- Business hours are missing for all listed restaurants.
- Physical locations are not explicitly stated for each establishment.
- Image links point to websites, not specific photos.
  > 💡 Add explicit addresses, operating hours, and direct photo URLs for each restaurant.

### ❌ `e4f664ea…` — score 3/10
- Text response describes deliverables instead of presenting the screenplay content.
- No evidence the screenplay follows show-not-tell or proper formatting.
- Produced files' screenplay content is not verifiable from provided preview.
  > 💡 Include the full, properly formatted screenplay content and ensure files clearly demonstrate compliance.

### ✅ `a079d38f…` — score 7/10
- Excel sheet lacks clear column headers for costs, rates, hours, and totals.
- Detailed line-item cost calculations are not clearly visible or verifiable.
- Administration fee inclusion is stated but not clearly shown in the spreadsheet.
  > 💡 Add explicit column headers and visible formulas showing hours, rates, subtotals, and final totals.

### ❌ `02aa1805…` — score 3/10
- No Illinois EPA data was pulled or reviewed.
- Excel file contains no well records or analysis.
- Email lacks specific recommended wells or highlighted options.
  > 💡 Populate the workbook with IEPA factsheet data and provide clear well recommendations.

### ✅ `fd6129bd…` — score 8/10
- Text response describes planned delivery rather than summarizing completed deliverables.
- An extra reference file was included beyond the requested SOP and form.
- Formatting compliance is claimed but not explicitly evidenced in the response.
  > 💡 Include a brief confirmation summarizing completed documents and key contents delivered.

### ✅ `ce864f41…` — score 6/10
- Brief written answers to the three executive questions are missing.
- Text response describes intent rather than summarizing analytical findings.
- Professional response includes unnecessary CONFIDENCE tag.
  > 💡 Include concise written answers to each question summarizing key findings and risks.

### ✅ `58ac1cc5…` — score 8/10
- QA escalation email delivered as Word file rather than email-ready text.
- No explicit endotoxin result value from COA cited in documents.
- Change control relies on vendor notification without documented evidence attachment.
  > 💡 Include COA endotoxin value and vendor notification memo to strengthen QA decision-making.

### ✅ `3c19c6d1…` — score 6/10
- PPT slide contents are not shown, so required slide details cannot be verified.
- Progress summary tabular data for slide 4 is not evidenced.
- Output description adds extra slides beyond explicitly requested scope.
  > 💡 Provide a brief slide-by-slide content summary or preview to evidence compliance.

### ✅ `a99d85fc…` — score 7/10
- Notes section below the Annual Rent Matrix is missing.
- Editable variable cells are not clearly color-coded light blue.
- Distinct scenario color-coding is not evident from the file.
  > 💡 Add a Notes section and apply clear color-coding for scenarios and editable input cells.

### ✅ `55ddb773…` — score 6/10
- Not all violation types and qualifying details from the reference PDF are fully included.
- Architectural items are incomplete and contain formatting and typographical errors.
- OCR limitations resulted in missing or unclear violation content.
  > 💡 Re-extract the reference PDF accurately and fully populate all violation categories with clean formatting.

### ❌ `1e5a1d7f…` — score 3/10
- The .docx file lacks the required table format.
- No weekly schedule tasks or time blocks are provided.
- Required columns are missing from the document.
  > 💡 Create a complete table with all specified columns and populate it using the PM duties.

### ✅ `0419f1c3…` — score 8/10
- Text response is meta-descriptive rather than a direct executive summary.
- Inspection preview shows truncated objectives section, though full document likely complete.
  > 💡 Include a brief executive summary in the text response highlighting key findings and actions.

### ✅ `ed2bc14c…` — score 7/10
- Departure reasons were not categorized into the required five distinct categories.
- Exit survey analysis lacks clear methodology and full breakdown beyond top two reasons.
- Communication plan lacks actual draft email content, only high-level descriptions.
  > 💡 Expand the exit survey analysis to five categories and add brief draft language for each renewal email.

### ✅ `46bc7238…` — score 8/10
- Next Steps section not clearly evidenced in the PDF preview.
- One-page flyer template content not fully visible in provided preview.
- Cold outreach scripts could be more customized by QSR category.
  > 💡 Add clearer Next Steps and expand category-specific scripts and flyer details.

### ✅ `2d06bc0a…` — score 7/10
- LOI does not clearly state an explicit expiration date.
- Minor truncation/typo appears in the PSA assignment section.
- Extension deposit applicability differs slightly from stated instruction.
  > 💡 Add a clear LOI expiration date and correct minor drafting inconsistencies.

### ✅ `fd3ad420…` — score 7/10
- Commission split structure lacks specific percentage examples for agents and associate brokers.
- Text response describes the deliverable instead of summarizing its substantive terms.
- Incorporation of Compensation Model Ideas is implied but not explicitly referenced.
  > 💡 Add sample percentage splits and explicitly cite incorporated compensation model terms.

### ✅ `0818571f…` — score 5/10
- Properties are illustrative, not active June 2025 listings from Crexi or LoopNet.
- Shortlist does not clearly deliver 5–10 fully detailed properties.
- Photos and maps are placeholders, not sourced from actual listings.
  > 💡 Source live Crexi or LoopNet listings and update the report with verified property data and visuals.

### ❌ `6074bba3…` — score 3/10
- CMA PDF contains numerous placeholders instead of actual property and market data.
- Comparable sales and active listings are not populated or sourced.
- Graphs and pricing recommendations are missing real values and analysis.
  > 💡 Populate the CMA with verified local comps, completed graphs, and a defensible pricing range.

### ✅ `5ad0c554…` — score 7/10
- Does not explicitly reference or identify items from the 132 Things Realtors Do for Buyers list.
- Brochure text shows no embedded photos or visuals despite requirement.
- Double-sided brochure layout is not demonstrated or specified in the document.
  > 💡 Revise the brochure to cite specific items from the 132-item list, embed visuals, and format clearly as double-sided.

### ❌ `11593a50…` — score 3/10
- Properties are in incorrect town and ZIP, not Massapequa Park 11762.
- Property tour PDF is three pages, exceeding the required two pages.
- Listings and photos appear fabricated placeholders, not sourced from MLSLI.
  > 💡 Redo the deliverables using real MLSLI data strictly matching location, page limits, and authenticity requirements.

### ✅ `94925f49…` — score 6/10
- School statistics are explicitly labeled as representative estimates, not sourced real data.
- Nearby homes lack addresses, distances, or verifiable MLS references.
- Reports do not cite specific reputable sources like Niche or MLSLI.
  > 💡 Replace estimates with cited, current data and include verifiable home listings with locations.

### ✅ `90f37ff3…` — score 8/10
- Comparable listings lack explicit dates to confirm three-year lookback.
- Data sources like LoopNet or Crexi are not explicitly cited.
- Property name appears generic and may not match actual center branding.
  > 💡 Add source citations and listing dates to strengthen data credibility.

### ✅ `d3d255b2…` — score 8/10
- Text response summarizes deliverable instead of presenting advisory content.
- Counteroffer details are not visible in the provided preview excerpt.
  > 💡 Include a brief executive summary in the text response and ensure counteroffer specifics are clearly visible.

### ✅ `403b9234…` — score 6/10
- Slide content cannot be verified from provided preview.
- Slide count and required sections are not confirmed.
- Text response summarizes intent rather than presentation details.
  > 💡 Provide a slide-by-slide outline or screenshots to verify content and compliance.

### ✅ `1bff4551…` — score 6/10
- Total set duration is far under the required 45 minutes.
- Original song has an invalid placeholder YouTube link.
- No evidence songs are represented in the Institute's collection.
  > 💡 Expand the set to 45 minutes, fix the original link, and verify collection representation.

### ✅ `650adcb1…` — score 7/10
- No visible key or legend on the first Excel page.
- Understaffed dates are not explicitly listed or summarized.
- Color coding cannot be verified from the provided file preview.
  > 💡 Add a clear key tab, list understaffed dates, and ensure visible color formatting.

### ✅ `01d7e53e…` — score 6/10
- Text response only summarizes intent, not substantive agreement content.
- Cannot verify all required terms within the draft without explicit confirmation.
- Key program details and clauses are not demonstrated in the response.
  > 💡 Explicitly confirm each required term and clause is fully included in the draft agreement.

### ❌ `a73fbc98…` — score 4/10
- Many vendors are missing; assignment spreadsheet has fewer rows than original list.
- Electricity needs and product-type separation were not clearly implemented in assignments.
- Some vendors were left unassigned, contrary to task requirements.
  > 💡 Complete assignments for all vendors and explicitly honor electricity and product-variety constraints.

### ✅ `0ec25916…` — score 8/10
- DOCX file lacks full SBAR table content.
- References were consulted but not cited within the document.
  > 💡 Ensure the DOCX mirrors the complete PDF content and consider adding a brief references note.

### ✅ `116e791e…` — score 7/10
- PDF is two pages, not one page as required.
- Extra DOCX file produced though only a PDF was requested.
- Text response describes intent rather than summarizing completed content.
  > 💡 Condense the care plan to a single-page PDF and align the text response with delivered files.

### ❌ `dd724c67…` — score 4/10
- Facility list is not comprehensive for all Long Island hospitals and rehabilitation facilities.
- TFU reference lacks citation-specific details from ACO REACH PY 2025 methodology.
- Condition list and timeframes are oversimplified and may be inaccurate.
  > 💡 Expand the facility list comprehensively and align TFU guidance precisely with CMS ACO REACH PY 2025.

### ❌ `7151c60a…` — score 4/10
- Fax cover sheet lacks sender/recipient fields, fax metadata, and urgency options.
- Pre-screening checklist lacks table format, page numbers, and date sent/received and initials fields.
- Checklist does not clearly mark internal-only fields or include patient identifiers on each page.
  > 💡 Revise both documents to explicitly include all required fields, tables, page numbers, and compliance markings.

### ❌ `90edba97…` — score 3/10
- Did not enter monthly lab values into the tracker as explicitly required.
- Assumed lab data were missing despite an attached Patient Lab Reports document.
- Produced extra narrative files instead of fully completing the specified Excel deliverable.
  > 💡 Populate the Monthly Tracker with all patient lab data and document protocol-driven changes per month.

### ✅ `91060ff0…` — score 7/10
- No references or citations are included despite being explicitly required.
- Visual elements like tables, icons, or product comparisons are minimal or unclear.
- OTC product examples and brand comparisons are insufficiently detailed.
  > 💡 Add a references section and clearer visual tables comparing common OTC wart treatments.

### ✅ `8384083a…` — score 6/10
- DOCX file lacks the medication table and calculation details present in the PDF.
- Some NDCs and column formatting are broken or split, reducing clarity.
- Ozempic package description and calculation presentation are confusing.
  > 💡 Ensure the DOCX fully mirrors the PDF content with clear tables and corrected formatting.

### ✅ `045aba2e…` — score 6/10
- Checklists lack explicit citations to California Lawbook or Board self-assessment requirements.
- Monthly self-assessment frequency conflicts with California Board annual self-assessment requirement.
- DOCX files were produced though only PDFs were requested.
  > 💡 Revise checklists to explicitly map tasks to California regulations and correct task frequencies.

### ❌ `f2986c1f…` — score 3/10
- Medications were not identified using Drugs.com as required.
- All spreadsheet fields are NA despite an available image.
- MedlinePlus counseling links were not provided.
  > 💡 Identify each medication from the image using Drugs.com and populate all available fields with accurate data.

### ✅ `ffed32d8…` — score 6/10
- PDF lacks required detailed comparative table of costs, reimbursements, and expenses.
- DOCX file is incomplete and missing the full analysis and tables.
- Revenue threshold logic text contradicts the stated recommendation criteria.

### ✅ `a69be28f…` — score 8/10
- Executive summary highlights overall top fits but lacks explicit regional aggregation.
- Text response describes intent rather than summarizing key analytical findings.
  > 💡 Add a brief written summary of regional insights and merchandising implications.

### ✅ `788d2bc6…` — score 6/10
- TikTok Shop, influencer outreach, and TikTok growth services are missing from the deck.
- Creative optimization and review generation services are not clearly presented as dedicated slides.
- Use of open-source visual elements is not evident from the deck content.
  > 💡 Add dedicated TikTok and creative service slides with clear visuals to fully meet the original brief.

### ✅ `74ed1dc7…` — score 8/10
- Text response is meta-level and does not summarize proposed order types.
- Second Word file appears supplementary and not explicitly requested.
  > 💡 Include a brief summary of key proposed order types in the text response.

### ✅ `69a8ef86…` — score 7/10
- An extra unrequested file was delivered beyond the two required documents.
- The text response does not summarize or verify required internal timelines and roles.
- Internal process content is not evidenced in the provided preview.
  > 💡 Remove extraneous files and clearly validate all required internal steps, timelines, and owners.

### ✅ `ab81b076…` — score 7/10
- PDF exceeds the specified 1–3 page requirement.
- Text response describes intent rather than summarizing delivered procedure.

### ✅ `7ed932dd…` — score 5/10
- Delivered days of inventory after shipments is not calculated or shown.
- Required Excel highlighting for rounded pallets and early deliveries is missing.
- Analysis only covers 10 SKUs, not the full inventory list.
  > 💡 Add delivered DOI calculations, apply required highlights, and complete analysis for all SKUs.

### ❌ `105f8ad0…` — score 4/10
- Did not conduct required online competitor research or document September 2025 MSRPs.
- Competitor benchmarks and cost-per-ounce averages are missing from the Excel model.
- Recommended MSRPs appear duplicated across concentrations, weakening logical pricing hierarchy.
  > 💡 Rebuild the model with documented competitor research, visible benchmarks, and concentration-differentiated pricing.

### ✅ `b57efde3…` — score 5/10
- Did not review the official Aqua Nor 2025 exhibitor list comprehensively.
- Spreadsheet contains placeholder rows instead of validated exhibitor leads.
- Prospecting list is far too small given hundreds of exhibitors.
  > 💡 Expand the spreadsheet with validated exhibitors directly reviewed from the official Aqua Nor 2025 list.

### ❌ `15d37511…` — score 3/10
- Spreadsheet contains multiple TBD placeholders instead of required pricing and cost data.
- Tiered pricing and discount logic are not calculated or shown.
- Total Year 1 gross margin is not computed.
  > 💡 Populate all pricing from the email, apply tiered discounts, calculate margins, and complete totals.

### ❌ `bb863dd9…` — score 4/10
- Quotation lacks itemized module lines with quantities, prices, lead times, and shelf life.
- WHO reference link in quotation is truncated and incomplete.
- Totals and EXW price breakdown per module are missing.
  > 💡 Add a complete itemized pricing table per module with correct quantities, totals, and a full WHO link.

### ✅ `fe0d3941…` — score 8/10
- Survey does not state target sample size of over one hundred respondents.
- Workflow PPT content cannot be fully verified from preview for legend and benefits slide.
  > 💡 Add a brief survey introduction specifying target respondent count and validate PPT slides against requirements.

### ✅ `6a900a40…` — score 6/10
- Cannot verify unit price and lead time match internal table for 400 kits.
- General remark red-font freight validity statement is not evidenced.
- Transport options placement and grand total calculations are not clearly verifiable.
  > 💡 Explicitly verify and document pricing, lead time, remarks formatting, and totals within the revised file.

### ✅ `9efbcd35…` — score 6/10
- Lacks specific MSCI index performance figures or explicit performance data.
- No citations or references to MSCI, WSJ, FT, or research sources.
- Macro and regional sections remain high-level with limited quantitative support.
  > 💡 Add MSCI Q1 2025 return data and clearly reference external sources to strengthen credibility.

### ✅ `1d4672c8…` — score 5/10
- Index return data are simulated, not extracted from MSCI as explicitly required.
- Use of simulated data undermines validity of correlation analysis and conclusions.
- Correlation matrix credibility is compromised without official MSCI sourcing.
  > 💡 Rebuild the Excel and PDF using officially sourced MSCI monthly return data for the specified period.

### ✅ `4de6a529…` — score 6/10
- Currency asset class section and sub-asset views are missing from the main allocation table.
- Several tables have formatting and header errors, including truncated text and misspelled column names.
- Some fixed income and equity sections appear incomplete or cut off mid-entry.
  > 💡 Complete and proofread all asset class sections, especially Currency, ensuring consistent formatting and fully populated tables.

### ✅ `4c4dc603…` — score 5/10
- PDF exceeds one page, violating the one-page requirement.
- Salient numbers like target raise, IRR, token supply, and price are missing or vague.
- Key team member profiles lack names and specific credentials.
  > 💡 Condense to one page and add concrete fund metrics, token economics, and named team profiles.

### ✅ `bb499d9c…` — score 7/10
- Text response summarizes intent instead of key document content.
- No confirmation the Word document is within 25-page limit.
- Compliance requirements are not explicitly verified in preview.
  > 💡 Include a brief executive summary of actual document contents and confirm key constraints.

### ✅ `5349dd7b…` — score 6/10
- Rates and increases are estimates, not researched via search engines as required.
- Business-specific flat rate options are not clearly validated or cited.
- Historical rate increases lack year-by-year source detail from 2020–2025.
  > 💡 Redo analysis using verifiable published sources and clearly document business rate eligibility.

### ✅ `a4a9195c…` — score 8/10
- Reference section appears truncated and lacks full IPC-A-610G citation.
- Document lacks revision history, approval, and effective date sections.
  > 💡 Add document control details and a complete standards reference to strengthen professionalism.

### ✅ `552b7dd0…` — score 6/10
- Text response lacks actual analysis results or metrics.
- PowerPoint content cannot be verified against required calculations.
- Extra Excel file produced without being explicitly requested.
  > 💡 Include key findings and metrics in the text and clearly confirm all required analyses in the presentation.

### ✅ `76418a2c…` — score 5/10
- Daily shipment manifest lacks customer, pick ticket, and shipment method names.
- Spreadsheet headers and required fields are mostly blank or unclear.
- Text response describes intent but not completed task details.
  > 💡 Populate the manifest with full order details, explicit shipping methods, clear headers, and verified savings calculations.

### ❌ `0e386e32…` — score 4/10
- ZIP archive is implausibly small, indicating missing or empty codebase.
- Deliverable claims completeness but provides placeholders instead of functional implementations.
- Privacy logic and zkSNARK components are incomplete or absent.
  > 💡 Provide a fully populated repository with actual contract, frontend, and documentation files.

### ❌ `7de33b48…` — score 3/10
- ZIP size is unrealistically small for required utility, tests, and documentation.
- Cannot verify required TypeScript, tests, or WCAG validations from provided archive.
- Original task specifies files and tests not evidenced in output.
  > 💡 Include full source, tests, package files, and documentation, then provide a verifiable archive.

### ❌ `4122f866…` — score 3/10
- Terraform configuration files are missing or not provided in readable form.
- Lambda function code content is not shown or verifiable.
- README lacks detailed setup, variables, and architecture explanation.
  > 💡 Include full Terraform files, complete Lambda code, and expanded README with configuration details.

### ❌ `2c249e0f…` — score 3/10
- OpenAPI 3.0 YAML specification was not produced.
- Only data_flow.txt exists; required API file is missing.
- Generated output describes intent but lacks actual deliverables.
  > 💡 Provide the complete OpenAPI 3.0 YAML specification alongside the data_flow.txt file.

## Failure Analysis

Nine tasks resulted in errors, with 35 tasks requiring retries. Failures were distributed across Manufacturing, Health Care, Professional Services, and Wholesale Trade, suggesting task-specific complexity rather than a single systemic fault. Retries indicate intermittent execution or generation instability rather than persistent inability to complete tasks.

## Recommendations

Increase targeted prompt scaffolding or domain package specificity for lower-confidence sectors such as Health Care and Professional Services to improve self-assessed output quality.

Investigate retry-triggering tasks to identify common characteristics (e.g., prompt length, multi-document synthesis) and adjust execution safeguards or timeouts accordingly.

Conduct a latency-focused follow-up run with selective sector sampling to determine whether higher-latency domains (e.g., Information) can be optimized without reducing task completion reliability.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 7 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 17 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 18 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `17111c03…` (Government): 4 file(s)
- `c44e9b62…` (Government): 6 file(s)
- `99ac6944…` (Information): 4 file(s)
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
- `e222075d…` (Information): 5 file(s)
- `c94452e4…` (Information): 3 file(s)
- `75401f7c…` (Information): 3 file(s)
- `a941b6d8…` (Information): 3 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 4 file(s)
- `c7d83f01…` (Finance and Insurance): 2 file(s)
- `46b34f78…` (Finance and Insurance): 2 file(s)
- `a1963a68…` (Finance and Insurance): 2 file(s)
- `5f6c57dd…` (Finance and Insurance): 2 file(s)
- `b39a5aa7…` (Finance and Insurance): 2 file(s)
- `b78fd844…` (Finance and Insurance): 3 file(s)
- `4520f882…` (Finance and Insurance): 3 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 2 file(s)
- `e996036e…` (Wholesale Trade): 2 file(s)
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
- `9e39df84…` (Manufacturing): 6 file(s)
- `68d8d901…` (Manufacturing): 3 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 3 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 10 file(s)
- `cecac8f9…` (Retail Trade): 6 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `c6269101…` (Manufacturing): 6 file(s)
- `be830ca0…` (Manufacturing): 8 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 3 file(s)
- `46fc494e…` (Manufacturing): 5 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `8077e700…` (Manufacturing): 5 file(s)
- `5a2d70da…` (Manufacturing): 4 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 2 file(s)
- `61b0946a…` (Health Care and Social Assistance): 3 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 5 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `a0552909…` (Health Care and Social Assistance): 8 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 22 file(s)
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
- `f9f82549…` (Retail Trade): 3 file(s)
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
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 8 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 3 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 9 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 3 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 13 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 5 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 5 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 11 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 4 file(s)
- `a73fbc98…` (Government): 5 file(s)
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
- `a69be28f…` (Wholesale Trade): 11 file(s)
- `788d2bc6…` (Wholesale Trade): 3 file(s)
- `74ed1dc7…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `7ed932dd…` (Wholesale Trade): 2 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 3 file(s)
- `fe0d3941…` (Wholesale Trade): 6 file(s)
- `6a900a40…` (Wholesale Trade): 6 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 3 file(s)
- `4de6a529…` (Finance and Insurance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 3 file(s)
- `bb499d9c…` (Finance and Insurance): 4 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 4 file(s)
- `76418a2c…` (Manufacturing): 4 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 1 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 1 file(s)
