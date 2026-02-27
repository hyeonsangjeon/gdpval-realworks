# Experiment Report: GPT-5.2 Chat Elicit Capabilities — subprocess (Full 220 tasks)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp004_GPT52Chat_elicit_runner_exec` |
| **Condition** | Elicit |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-02-26 |
| **Duration** | 123m 20s |
| **Generated At** | 2026-02-27T01:40:59.674554+00:00 |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

This experiment evaluated the GPT-5.2 Chat model in an elicitation-focused subprocess execution across 220 tasks spanning multiple economic sectors. The run emphasized task completion under elicitation conditions, with the model providing self-assessed QA confidence scores during execution. Overall, 191 tasks completed successfully, yielding an 86.8% task completion rate, while 29 tasks resulted in errors. A relatively high retry count (68 tasks) indicates multiple attempts were often required to reach acceptable task completion.

The model reported an average self-assessed QA confidence of 5.92/10, with a wide spread from 2 to 9, suggesting moderate confidence in output quality overall and notable variability across tasks. Average latency was high at approximately 21.7 seconds per task, reflecting the computational and reasoning load of the elicitation setup. Key highlights include perfect task completion in the Information sector and consistently strong completion in Government-related tasks, contrasted with lower success rates in Finance and Retail.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 191 (86.8%) |
| Errors | 29 |
| Retried Tasks | 68 |
| Avg QA Score | 5.92/10 |
| Min QA Score | 2/10 |
| Max QA Score | 9/10 |
| Avg Latency | 21,734ms |
| Max Latency | 54,323ms |
| Total LLM Time | 4781s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 162 (87.6%) |
| Failed → dummy created | 23 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 68 | 39 | 29 |

## Quality Analysis

Self-assessed QA confidence scores clustered around the mid-range, with most sectors averaging between 5.2 and 6.9. Higher confidence was observed in Government and Retail Trade tasks, which may reflect clearer task structure or more standardized response expectations. Lower average QA scores in Information and Health Care suggest that, while tasks were completed, the model expressed less confidence in output completeness or precision.

Sector-wise, no single domain exhibited both low completion and low confidence simultaneously, indicating that failures were not strongly correlated with QA confidence alone. Manufacturing and Real Estate showed balanced outcomes with moderate-to-high confidence and solid completion rates. Deliverable file generation quality, as inferred from self-QA and retries, appears acceptable but inconsistent, particularly in sectors requiring more formal or compliance-oriented outputs.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 17 | 68.0% | 5.65/10 | 22,610ms |
| Government | 25 | 24 | 96.0% | 6.83/10 | 20,014ms |
| Health Care and Social Assistance | 25 | 22 | 88.0% | 5.36/10 | 20,991ms |
| Information | 25 | 25 | 100.0% | 5.16/10 | 23,522ms |
| Manufacturing | 25 | 23 | 92.0% | 6.09/10 | 22,949ms |
| Professional, Scientific, and Technical  | 25 | 22 | 88.0% | 5.55/10 | 24,454ms |
| Real Estate and Rental and Leasing | 25 | 22 | 88.0% | 6.05/10 | 21,730ms |
| Retail Trade | 20 | 17 | 85.0% | 6.88/10 | 19,558ms |
| Wholesale Trade | 25 | 19 | 76.0% | 5.89/10 | 19,344ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 19012ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | 2/10 | 19784ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 7 | 7/10 | 16857ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 16 | 6/10 | 19886ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 18 | 6/10 | 20829ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 2/10 | 17027ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 9547ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 5 | 6/10 | 20442ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 8/10 | 25323ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 6 | 6/10 | 20666ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 4 | 4/10 | 30753ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 1 | 5/10 | 17538ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 1 | 3/10 | 20638ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 1 | 2/10 | 24007ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | 4/10 | 19046ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 23640ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 25170ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 9/10 | 26185ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | Yes | 2 | 6/10 | 23335ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 6/10 | 28242ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 17356ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 6/10 | 14778ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | 7/10 | 21412ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | Yes | 4 | 4/10 | 32347ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | Yes | 5 | 8/10 | 15864ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 24475ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 8/10 | 15794ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 1 | 6/10 | 15304ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 10538ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 7/10 | 15622ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 9/10 | 26387ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 7/10 | 25662ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 5/10 | 24751ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 4/10 | 25322ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 6/10 | 31993ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 2/10 | 20022ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 7/10 | 27847ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 22465ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | Yes | 2 | 3/10 | 17493ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 23865ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 17609ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 6/10 | 24142ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 3 | 7/10 | 21313ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 4 | 8/10 | 19836ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 31897ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 8/10 | 19989ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 3 | 8/10 | 25453ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 3 | 8/10 | 15321ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 24003ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 22532ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 23115ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 6/10 | 47319ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | 4/10 | 26401ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | 7/10 | 18687ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 2 | 7/10 | 27506ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 2 | 6/10 | 15020ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 6 | 4/10 | 25034ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | - | 3 | 3/10 | 20686ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | - | 3 | 3/10 | 24855ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | - | 2 | 3/10 | 21351ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 3/10 | 9711ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 3/10 | 21116ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 38400ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 4/10 | 36581ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 25200ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 1 | 6/10 | 25065ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 21932ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 3/10 | 21658ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 29766ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 20436ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 14443ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 7/10 | 19112ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 4/10 | 19744ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 17993ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 17756ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 3 | 4/10 | 16684ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 6/10 | 21335ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 3/10 | 24788ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 12236ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 11 | 4/10 | 18498ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 22019ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | Yes | 1 | 9/10 | 32081ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | Yes | 1 | 8/10 | 17981ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 24049ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 1 | 6/10 | 20048ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 4/10 | 15269ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 21203ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | 3/10 | 19806ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | 6/10 | 16286ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | - | 6 | 7/10 | 12933ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 5/10 | 26404ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 12936ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 8/10 | 12792ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 26954ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 5 | 8/10 | 24554ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 21538ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 6/10 | 21103ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | Yes | 1 | 8/10 | 20786ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 2 | 7/10 | 23208ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | 8/10 | 19994ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 1 | 6/10 | 18813ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 6/10 | 22328ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 5/10 | 22256ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 5 | 7/10 | 23053ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | 8/10 | 26918ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | Yes | 1 | 5/10 | 31608ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 27204ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 30443ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 8/10 | 26408ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 7/10 | 54323ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 4/10 | 37846ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 6 | 3/10 | 32505ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 6/10 | 25550ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 4/10 | 25501ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 6/10 | 26831ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 6/10 | 23191ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | Yes | 1 | 8/10 | 17711ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 23332ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 3/10 | 11227ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 5 | 6/10 | 24150ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 4/10 | 23730ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 8/10 | 14038ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 23107ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 13 | 3/10 | 19728ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | 6/10 | 21450ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 1 | 8/10 | 21226ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 7/10 | 25161ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | 5/10 | 19109ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 2 | 7/10 | 23104ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 8 | 4/10 | 35967ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 37654ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 6/10 | 19551ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 17312ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 14233ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 4 | 6/10 | 28979ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 5/10 | 15235ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 15292ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 8/10 | 16105ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | 9/10 | 17530ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 5 | 5/10 | 21260ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 15386ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 18953ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 25831ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 6/10 | 18040ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 17072ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 7/10 | 13904ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 6/10 | 16342ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | Yes | 3 | 8/10 | 19581ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | Yes | 4 | 6/10 | 24368ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | Yes | 5 | 8/10 | 20937ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 1 | 5/10 | 20373ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 24608ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 23393ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 3 | 5/10 | 18899ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 3 | 7/10 | 14267ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 3/10 | 19512ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 3 | 8/10 | 25961ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 7/10 | 19664ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 7 | 6/10 | 24843ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | Yes | 5 | 6/10 | 19692ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 21983ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 3/10 | 20399ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 3/10 | 14647ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | Yes | 3 | 8/10 | 17214ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 9/10 | 21663ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 7 | 6/10 | 24692ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 7/10 | 16612ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 6/10 | 19048ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 13 | 6/10 | 27335ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 4 | 7/10 | 20861ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 4 | 7/10 | 16835ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 3/10 | 24480ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 5 | 6/10 | 21609ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 2 | 8/10 | 22510ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 26867ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 13750ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 27896ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 5/10 | 24310ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 4 | 6/10 | 19616ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 6 | 6/10 | 22097ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 8/10 | 25803ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 5/10 | 30043ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 3/10 | 25799ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 5 | 4/10 | 16430ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 6 | 3/10 | 13754ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | Yes | 1 | 3/10 | 24534ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 6/10 | 16229ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 6/10 | 14643ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 9895ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 20454ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 3/10 | 17680ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | Yes | 10 | 6/10 | 20748ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | Yes | 2 | 6/10 | 23105ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 8/10 | 19864ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | 7/10 | 22904ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 24287ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 19361ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 6/10 | 22463ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 17701ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 5/10 | 25583ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 6/10 | 21051ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 17695ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 6/10 | 15112ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 6/10 | 27242ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 6 | 6/10 | 14323ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 26423ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 17566ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 24369ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 2 | 6/10 | 18361ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 4 | 7/10 | 26093ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 7/10 | 24562ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 9/10 | 23156ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 4 | 8/10 | 19645ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 16719ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 4 | 4/10 | 15982ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 19492ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 3 | 4/10 | 19492ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 13743ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 4/10 | 23640ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 3/10 | 24848ms |

## QA Issues

### ❌ `7b08cd4d…` — score 2/10
- Revenue by tour stop is missing and withholding taxes are not calculated.
- Expenses lack source separation, categories detail, and contain zero placeholder values.
- Combined totals and net income are not calculated or supported by reference data.
  > 💡 Populate the P&L with actual reference data, calculate taxes and totals, and separate sources as required.

### ✅ `7d7fc9a7…` — score 7/10
- Text response does not summarize key figures or reconciliation results.
- Assumptions applied are not documented within the response.
- Produced files list redundantly includes source reference PDFs.
  > 💡 Include a brief summary of reconciled totals and key assumptions in the response.

### ✅ `43dc9778…` — score 6/10
- Required schedules like Schedule A, Schedule 1, or Schedule 3 are not addressed.
- Text response is descriptive but lacks confirmation of completed calculations.
- CONFIDENCE tag appears unprofessional and unnecessary.
  > 💡 Explicitly list and include all required schedules supported by the provided tax documents.

### ✅ `ee09d943…` — score 6/10
- No evidence the April workbook tabs were actually updated with April data.
- Text response summarizes intent instead of detailing completed work and findings.
- No confirmation of TOC updates, CFO notifications, or flagged discrepancies.
  > 💡 Provide a concise completion summary citing specific tabs updated, checks performed, and any issues flagged to the CFO.

### ❌ `f84ea6ac…` — score 2/10
- Word document lacks the required summary table.
- No five academic articles are identified or summarized.
- Research requirements are deferred due to claimed lack of internet access.
  > 💡 Include a complete one-page table summarizing five verified post-2020 public studies.

### ✅ `a328feea…` — score 9/10
- No backup contact specified if Supervisor or Team Lead is unreachable.
- Procedure does not state how lateness duration should be estimated or updated.
  > 💡 Add a brief backup contact and update expectation section to strengthen operational clarity.

### ✅ `27e8912c…` — score 6/10
- Checklist lacks citation or linkage to the NIH or another credible source.
- Word document does not include the required action-items tracking table.
- Image sources are not identified as credible or public-domain.
  > 💡 Add source citations, complete the action-items table with required fields, and document image provenance.

### ✅ `17111c03…` — score 8/10
- Memo sender line lists only role, not an individual name.
- Text response summarizes deliverables instead of presenting memo content.
  > 💡 Add the manager’s name to the memo and include a brief memo excerpt in the text response.

### ✅ `c44e9b62…` — score 6/10
- Revised organizational chart is a list, not a visual chart highlighting reduced positions.
- No evidence the total reductions meet or exceed the required 4% FTE target.
- Regional Support Services 10% reduction is not clearly demonstrated in outputs.
  > 💡 Provide a fully visual revised org chart and explicitly quantify how reductions meet the 4% target.

### ❌ `99ac6944…` — score 4/10
- IEM system cannot provide two independent mixes from a single transmitter.
- Analog mixer lacks onboard compression required by the singers.
- Total estimated cost exceeds the $3,000 budget.
  > 💡 Select a mixer with compression and dual-aux sends plus two IEM transmitters to meet requirements.

### ✅ `f9a1c16c…` — score 5/10
- Vox1 and Vox2 wedges are missing despite requirement for vocalists to hear monitors.
- Wedge numbering counterclockwise from stage right is not clearly indicated.
- Drummer wedge placement at 10 o’clock position is not visually specified.
  > 💡 Add clearly labeled Vox1 and Vox2 wedges, show counterclockwise wedge numbering, and indicate drummer wedge position.

### ❌ `38889c3b…` — score 3/10
- Audio files are silent placeholders, not a real instrumental track.
- Zip size indicates missing 2:17 master and proper stem audio content.
- No evidence of drum reference synchronization or required musical keys.
  > 💡 Provide fully produced audio stems and master meeting length, key, tempo, and format requirements.

### ❌ `ff85ee58…` — score 2/10
- No final mixed WAV audio file was delivered.
- Saxophone was not actually resynced or edited.
- Loudness and peak specifications were not met or verified.
  > 💡 Deliver a properly processed 24-bit/48kHz WAV mix with resynced sax meeting loudness specs.

### ❌ `4b894ae3…` — score 4/10
- Final stereo WAV mix was not delivered as required.
- Actual bass audio edits and mixdown were not performed.
- Deliverable substitutes instructions for required audio processing.
  > 💡 Perform the specified bass edits and deliver the final 48kHz/24-bit stereo WAV mix.

### ✅ `1b1ade2d…` — score 8/10
- Text response focuses on intent rather than summarizing key workflow changes.
  > 💡 Briefly summarize the revised workflow highlights in the text response for quicker executive review.

### ✅ `93b336f3…` — score 8/10
- Introduces a 49:51 partnership split not specified in the original task.
- Chief Procurement Officer name and sign-off section are not explicit.
- Sensitivity analysis on future localisation is brief and not deeply quantified.
  > 💡 Align assumptions strictly to the brief and expand quantified sensitivities and governance details.

### ✅ `24d1e93f…` — score 6/10
- Missing summary sheet with side-by-side NPV comparison and recommendation.
- Year 1 cash flows are discounted despite discounting specified only for years 2–4.
- Tooling amortization does not clearly stop after first 100,000 headlamp sets.
  > 💡 Add a summary sheet, correct discounting logic, fix tooling amortization, and clearly list assumptions.

### ✅ `05389f78…` — score 6/10
- Comparative cost analysis in INR is missing due to unavailable quotation figures.
- Replacement supplier recommendation lacks quantified calculations and cost comparisons.
- Reference quotation file is incomplete and insufficient for required analysis.
  > 💡 Obtain complete numeric quotations and redo a full INR-based comparative analysis with a clear recommendation.

### ✅ `575f8679…` — score 8/10
- Appendix references lack explicit hyperlinks to cited tools and guides.
- Data analysis section lacks timeline and responsibility assignments.
- Summative evaluation endpoint timing is not clearly defined.
  > 💡 Add hyperlinks, an evaluation timeline, and defined endpoints to strengthen rigor and usability.

### ✅ `a74ead3b…` — score 6/10
- Content does not closely follow the required manuals as explicitly stated.
- Evidence of required icebreaker and wrap-up slides is not verified.
- Session timing and 90-minute structure are not demonstrated.
  > 💡 Revise slides to explicitly align with manual content and document required session components.

### ✅ `bbe0a93b…` — score 7/10
- Open web search requirement was not met for the resource guide.
- Resource guide lacks several requested categories like financial assistance, clothing, and counseling.
- Resource listings are minimal and omit addresses or hours.
  > 💡 Conduct a live web search to expand and verify Kent County resources across all requested categories.

### ❌ `85d95ce5…` — score 4/10
- Report length is 3 pages, not the required 8–15 pages.
- Used incorrect reference files with a different student name.
- Final PDF filename formatting is inconsistent and unprofessional.
  > 💡 Revise using correct student notes, expand all sections to 8–15 pages, and resave a properly named PDF.

### ✅ `76d10872…` — score 8/10
- New Case Creation Report content was not previewed for accuracy verification.
  > 💡 Include a brief content excerpt or summary from the generated report for QA validation.

### ✅ `36d567ba…` — score 8/10
- Conflicts of interest topic lacks required Uniform Guidance citation (2 CFR 200.112).
- Applicant point-of-contact question cites Part 200 generally, not specific relevant sections.
  > 💡 Add specific 2 CFR citations for all topics 6–10 to strengthen compliance clarity.

### ✅ `7bbfcfe9…` — score 8/10
- Some §3919 questions test policies and training not expressly required by the statute.
- SCRA-12d includes credit reporting language not explicit in §3937(c).
  > 💡 Tighten questions to track statutory text more precisely and avoid implied obligations.

### ✅ `2696757c…` — score 6/10
- Required PDF was not produced; only a DOCX file was delivered.
- Text response claims PDF generation, conflicting with actual file output.
  > 💡 Convert the document to a single PDF and ensure outputs match stated deliverables.

### ✅ `4c18ebae…` — score 7/10
- Text response describes intent rather than summarizing investigative findings.
- SAR narrative lacks specific transaction dates, amounts, and account identifiers.
- Supporting transaction analysis is not clearly linked within the SAR narrative.
  > 💡 Include explicit transaction examples and reference supporting spreadsheets directly in the SAR narrative.

### ✅ `cebf301e…` — score 9/10
- One integration section contains an incomplete sentence in the document.
  > 💡 Review the document for minor truncations and finalize all section sentences.

### ✅ `c2e8f271…` — score 7/10
- Commit message guidelines section is incomplete or truncated.
- Commit message rules lack concrete examples and conventions.
  > 💡 Complete the commit message section with clear rules and examples before VP review.

### ✅ `2ea2e5b5…` — score 5/10
- Output does not explicitly provide the required activity classification for margin, time sensitivity, and strategic level.
- PowerPoint content is not validated against specified classification rules or shown in the response.
- Original task did not request a presentation format, only classification and grouping.
  > 💡 Include explicit classification tables mapping all 12 activities to margin impact, time sensitivity, and strategic level.

### ❌ `c357f0e2…` — score 4/10
- Test cases count is only 36, far below the required 80–100.
- Column headers do not match the template and appear as Unnamed fields.
- Role permissions are incorrect, as Viewers can create Ideas.
  > 💡 Expand to 80–100 cases, fix headers to match the template, and correct role-based permission scenarios.

### ✅ `a45bc83b…` — score 6/10
- Proposed diagram does not use official GCP icons as explicitly required.
- Architecture summary inaccurately attributes Layer 3/4 DDoS protection solely to Cloud Armor.
- Proposed architecture summary document appears truncated and incomplete.
  > 💡 Revise documents to use official GCP icons, correct security descriptions, and ensure complete content.

### ❌ `a10ec48c…` — score 2/10
- Document lacks required tables, columns, and restaurant rows.
- No restaurant links, hours, descriptions, directions, or categories included.
- Sources were not used and closed restaurants not verified.
  > 💡 Populate full tables with verified downtown restaurants, required details, links, and directions.

### ✅ `fccaa4a1…` — score 7/10
- PDF is three pages; itinerary was intended to be two pages.
- No visible icons or styled visual elements organizing sections.
- Age requirement states 2–14 years, conflicting with included 16-year-old guest.
  > 💡 Revise layout to two pages, add icons and visuals, and correct age requirements for consistency.

### ❌ `2fa8e956…` — score 3/10
- Document does not list all wineries within one-hour drive as requested.
- Required formatting, footer, fonts, and purple grape text are missing.
- Photo is not embedded and sources are not cited.
  > 💡 Revise the Word document to fully meet content scope, formatting, sourcing, and embedding requirements.

### ✅ `0e4fe8cd…` — score 6/10
- Links are placeholders instead of real URLs for most restaurants, services, and activities.
- Return-home travel logistics and final day details are not clearly included.
- High-value individual connections are minimally addressed and lack specifics.
  > 💡 Replace placeholders with verified links, add full return logistics, and expand strategic networking details.

### ✅ `b7a5912e…` — score 6/10
- Booking source revenues do not reconcile with total reported revenue.
- Payment method revenues do not reconcile with total reported revenue.
- Text response describes intent rather than summarizing completed results.
  > 💡 Reconcile all summary revenues to the total and briefly confirm results in the narrative.

### ✅ `aa071045…` — score 7/10
- Damage Revenue Report lacks a clear operational conclusions section.
- Excel preview does not show a dedicated conclusions or insights sheet.
  > 💡 Add a concise conclusions sheet summarizing trends and maintenance recommendations.

### ✅ `476db143…` — score 8/10
- Inspection notice states belongings removed, which may conflict with pre-move-out inspections.
  > 💡 Clarify in the email whether belongings may remain if inspection occurs before move-out.

### ✅ `f3351922…` — score 8/10
- Benefits section for transitioning military members is brief and lacks specific program details.
  > 💡 Expand the benefits section with more military-specific transition details and examples.

### ✅ `61717508…` — score 8/10
- An extra unrequested file was produced (Elder Abuse Internal Policy.pdf).
- Role-play PDF is very short, limiting discussion depth.
  > 💡 Remove the extra file and expand role-play scenarios slightly for richer training use.

### ✅ `0ed38524…` — score 8/10
- Minor typos and grammatical errors appear in constituent quotes.
- One quote contains an extraneous quotation mark affecting professionalism.
  > 💡 Proofread PDFs for spelling and punctuation consistency before final distribution.

### ✅ `d025a41c…` — score 6/10
- Produced extra Word files instead of only the single required Case Feedback document.
- Case Three content appears truncated and incomplete in the final document.
- Section titles are not shown in bold as explicitly required.
  > 💡 Consolidate all cases into one complete document, fix truncation, and format titles correctly.

### ✅ `401a07f1…` — score 6/10
- Document text is truncated and ends mid-sentence.
- Reference outlets are cited without visible hyperlinks or URLs.
- Editorial length appears short of the requested 500 words.
  > 💡 Complete the editorial, ensure ~500 words, and add explicit hyperlinks to all referenced sources.

### ✅ `afe56d05…` — score 6/10
- Document appears significantly shorter than the required 2,200–2,300 words.
- Not all required sections are clearly identifiable in the provided content preview.
- External resource citations and hyperlinks are not clearly evidenced in the file preview.
  > 💡 Expand the document to the required length, ensure all specified sections are explicit, and add clearly linked accredited sources.

### ❌ `9a8c8e28…` — score 4/10
- Files are DOCX, not the required accessible PDF format.
- Framework guide lacks bibliography with links and CMS change notes.
- Quiz is very short and may insufficiently assess understanding.
  > 💡 Convert documents to accessible PDFs and expand content to meet all specified requirements.

### ✅ `3a4c347c…` — score 7/10
- Text response summarizes intent rather than detailing key proposal elements.
- Budget breakdown clarity versus stated £20-25k range is unclear.
- Evidence of VT, radio and podcast re-versioning detail is limited.
  > 💡 Add a concise budget table and explicit VT, radio, and podcast adaptation details.

### ✅ `ec2fccc9…` — score 7/10
- Secondary keywords list is not clearly shown after the article.
- Not all referenced artist collections are clearly linked and highlighted.
- SEO research sources and methodology are not documented.
  > 💡 Add a clear secondary keyword list, ensure all referenced artists are linked, and briefly note SEO research sources.

### ✅ `8c8fc328…` — score 6/10
- Text response describes intent rather than summarizing actual script content.
- Basic script content with timestamps and scenes is not verifiable from preview.
- Alignment with provided sequence overview is not explicitly demonstrated.
  > 💡 Include a brief content summary confirming timestamps, scenes, and alignment with reference sequences.

### ❌ `e222075d…` — score 4/10
- No 30-second H.264 MP4 edit was delivered as required.
- Stock footage and music links are placeholders, not direct preview URLs.
- No scratch voiceover audio track is provided.
  > 💡 Deliver an actual 30-second MP4 with scratch VO and real preview links to all media.

### ❌ `c94452e4…` — score 3/10
- Final 15-second H.264 video file was not produced.
- No actual stock footage or music sources were selected.
- Response reframed task into planning documents without client approval.
  > 💡 Produce and export the actual 15-second broadcast-ready video using stock footage and music as specified.

### ❌ `75401f7c…` — score 3/10
- Final MP4 showreel video was not delivered.
- Task required editing footage, not only providing planning documents.
- No confirmation of correct duration, pacing, or audiovisual sync in an actual edit.
  > 💡 Produce and deliver the finished 01:20 max H.264 MP4 showreel per the specified edit plan.

### ❌ `a941b6d8…` — score 3/10
- Final composited video file was not created as required.
- Core VFX tasks were described but not executed.
- No actual stock smoke footage was sourced or composited.
  > 💡 Produce the finished MP4 with full compositing, tracking, grading, and effects applied.

### ❌ `8079e27d…` — score 3/10
- Excel contains zero rows and no company or sub-sector data.
- Required metrics are placeholders, not populated from public sources.
- Task requested actual analysis, not a template-only deliverable.
  > 💡 Populate the Excel with real S&P 500 data sourced from public market websites.

### ❌ `e21cd746…` — score 3/10
- PDF version of slides was not produced as required.
- Output text is a planning statement, not substantive client-ready content.
- Slide content cannot be verified against requirements from the provided preview.
  > 💡 Produce a PDF of completed slides with verified content covering private targets and public comps.

### ❌ `c7d83f01…` — score 4/10
- Required Python notebook implementing pricing methods is missing.
- Monte Carlo and finite-difference implementations are not provided as code.
- Deliverables claim files that are not actually produced.
  > 💡 Include the full Python notebook with documented implementations and analyses as specified.

### ✅ `a1963a68…` — score 6/10
- Core content slides appear fewer than required 5-6 with missing regulatory and future-proofing depth.
- Strategy lacks robust data citations and explicit use of Korean public sources.
- Actionability is limited with no clear H2 2024 timeline, targets, or KPIs.
  > 💡 Add two data-backed slides on regulation and long-term innovation with clear H2 2024 actions and metrics.

### ❌ `b39a5aa7…` — score 3/10
- Media fee and weeks assumptions are incorrect versus provided CBA assumptions.
- No projections for next two years or Y/Y growth are included.
- Quarterly results are duplicated and compensation calculations appear incorrect.
  > 💡 Correct assumptions, add multi-year projection inputs with Y/Y growth, and fix calculation logic.

### ✅ `ec591973…` — score 6/10
- Text response is descriptive and does not summarize slide content.
- Slide content cannot be verified against specific required elements.
- No confirmation the slide is truly one-page and executive-level.
  > 💡 Include a brief content summary and confirm all required strategic elements appear on the single slide.

### ✅ `62f04c2f…` — score 7/10
- Excel form lacks required freight and restocking fee note at the bottom.
- Excel form does not include signature spaces for sales rep, GM, and Sales Manager.
  > 💡 Add the missing fee note and clearly labeled signature and date sections to the Excel form.

### ❌ `3f821c2d…` — score 4/10
- Missing omni-level summary table combining stores and e-commerce.
- EOM inventory, turns, and formulas are largely blank or not calculated.
- Seasonal turn, receipt budget validation, and January EOM constraint are not demonstrated.

### ❌ `6dcae3f5…` — score 4/10
- Excel does not document PGY year each PGY-5 met ACGME key indicator requirements.
- No evidence ACGME requirement numbers from provided link were incorporated.
- Email contains formatting errors and fragmented metric labels.
  > 💡 Revise the Excel to include ACGME requirement numbers and PGY attainment, and clean the report formatting.

### ✅ `1aecc095…` — score 6/10
- Telehealth Roadmap lacks a Visio-style visual workflow and appears text-only.
- Roadmap does not clearly start from MA placing the initial patient call.
- An extra unrequested file was produced beyond the specified deliverables.
  > 💡 Add a one-page visual flow diagram in the Roadmap and remove unrequested files.

### ❌ `0353ee0c…` — score 3/10
- No consolidated presumptive conditions or exposure lists were compiled.
- Document relies on stated limitations instead of required exhaustive content.
- PDF content does not reflect information reviewed from provided links.
  > 💡 Review all provided links and populate the PDF with complete, organized presumptive eligibility details.

### ❌ `4d1a8410…` — score 4/10
- Interview schedule document lacks required table with detailed timings, breaks, lunch, and rotations.
- Personal itineraries omit full-day activities, lunch, breaks, tours, and required timing constraints.
- Specified constraints for physician breaks, early departure, and tour buffers are unmet.
  > 💡 Rebuild the schedule table and itineraries to fully satisfy all timing, break, tour, and formatting requirements.

### ✅ `8c823e32…` — score 6/10
- Required PDF export was not produced; only a DOCX file was delivered.
- Training and oversight section appears incomplete or truncated.
- Text response did not include the actual drafted policy content.
  > 💡 Complete the policy, finalize all sections, and export the document as a professional PDF.

### ✅ `eb54f575…` — score 9/10
- Text response describes intent rather than summarizing report findings.
  > 💡 Align the text response with the actual recommendations and data presented in the PDF.

### ✅ `11e1b169…` — score 8/10
- KRS 503.090 summary omits deadly force standards and statutory limitations.
- No Kentucky-specific case law or examples are included.
- Reference guide lacks citations or reference section.
  > 💡 Add a brief deadly force subsection with Kentucky examples and a short citations list.

### ✅ `a95a5829…` — score 8/10
- Explicit evaluation criteria for approving or denying requests are not clearly defined.
  > 💡 Add a brief section specifying standardized evaluation criteria for training approval decisions.

### ✅ `22c0809b…` — score 6/10
- Required PDF format was not produced; only a DOCX file is provided.
- Text response claims a PDF was generated, which is inaccurate.
- Deliverable evidence does not confirm a 2–4 page finalized PDF form.
  > 💡 Export the completed form to PDF and include it as the primary deliverable.

### ❌ `bf68f2ad…` — score 4/10
- Text response is descriptive only and does not include the required brief summary content.
- Weekly demand values appear inconsistent with stated 438.81 past-due hours.
- Catch-up plan builds an unrealistic excessive buffer without justification.
  > 💡 Recalculate demand using the stated backlog, include the actual summary text, and validate capacity assumptions.

### ❌ `9e39df84…` — score 3/10
- Average Output and Total Output columns are not calculated.
- Dashboard lacks required PivotTables, charts, and data validation.
- KPI summary, leaderboard, and YTD calculations are missing.
  > 💡 Complete formulas, build PivotTables and charts, and fully populate the Dashboard per specifications.

### ✅ `68d8d901…` — score 6/10
- Text response provides no actual schedules, assignments, or sequences.
- Excel content is not validated against production target and batch requirements.
- Unrequested confidence tag and reference file copies add unnecessary clutter.
  > 💡 Summarize key assumptions and verify the Excel meets the 250,000‑lb full‑batch target.

### ✅ `1752cb53…` — score 7/10
- Text response is generic and does not summarize specific planning decisions.
- Unnecessary CONFIDENCE tag included in a professional deliverable.
- No explicit confirmation that all Test Rules constraints were met.
  > 💡 Add a brief summary confirming rule compliance and key assumptions used in the plan.

### ✅ `bd72994f…` — score 5/10
- Presentation is PPTX, not the required PDF format.
- No specific luxury brand or collection is identified.
- Slides content cannot be verified against styling and look requirements.
  > 💡 Convert the presentation to PDF and clearly specify and document the chosen brand and looks.

### ✅ `211d0093…` — score 9/10
- Closing employee verification instructions are not explicitly stated on the DTL.
  > 💡 Add a brief line specifying closing employee responsibility to verify completion before filing.

### ✅ `d4525420…` — score 8/10
- Text response describes the deliverable instead of providing the required evaluation paragraph.
  > 💡 Include the actual 5–7 sentence selection rationale directly in the text response.

### ✅ `cecac8f9…` — score 8/10
- Currency inconsistency between targets PDF using dollars and UK context requiring pounds.
- Text response describes intent rather than summarising delivered content.
- Launch deck is brief and may lack operational detail for full weekend use.
  > 💡 Standardise currency to GBP and expand the launch deck with clearer execution guidance.

### ✅ `8f9e8bcd…` — score 8/10
- Text response summarizes intent instead of content.
- Practice section preview appears truncated but likely complete.
  > 💡 Include a brief content summary in the text response for clarity.

### ✅ `0fad6023…` — score 6/10
- No visual pan layout; only a table, not a graphical planogram.
- Total Used and Remaining fields appear not to calculate automatically.
- Instructions tab is very minimal for beginner Excel users.
  > 💡 Add automatic formulas, a simple visual pan layout using cell widths, and expand step-by-step instructions.

### ✅ `02314fc6…` — score 8/10
- Checklist does not explicitly state monthly inspection frequency.
- Loss Prevention review or signature field is missing.
- Parking lot section lacks cart corrals and striping checks.
  > 💡 Add explicit monthly frequency and LP review fields, and expand parking lot safety items.

### ✅ `4d61a19a…` — score 7/10
- Excel template does not show protected or locked fields for non-store columns.
- PowerPoint content cannot be verified for slide count or required topics.
- Training deck evidence of mock data sample is not visible.
  > 💡 Add field protection to the Excel form and include a brief slide-by-slide content checklist.

### ✅ `6436ff9e…` — score 8/10
- Optional demographic questions are not clearly visible in the previewed sections.
- Instructor-specific evaluation could be more clearly separated from class experience.
  > 💡 Add a clearly labeled demographics section and a distinct instructor evaluation section for clarity.

### ✅ `8a7b6fca…` — score 6/10
- PDF contains multiple typos and formatting artifacts like stray characters and misspellings.
- Decision point labeling and flow arrows are unclear and hard to follow visually.
- Failure handling text contains errors and weakly connects to manual workflow.
  > 💡 Clean up text, fix formatting artifacts, and redraw flows for clarity and professional presentation.

### ✅ `40a99a31…` — score 6/10
- Camera requirement unmet; minimum six cameras not specified or quantified.
- Safety devices lack quantities for six static zones and six pressure mats.
- Report is overly brief and lacks detailed compatibility and IO mapping logic.
  > 💡 Specify quantities per device, expand integration details, and document IO mapping explicitly.

### ✅ `b9665ca1…` — score 5/10
- Button box NO channels and pilot lights with ESx.SIG/STP wiring are missing.
- E-stop series wiring between S11, S12, and S22 is unclear or incorrect.
- Safety schematic lacks explicit parallel stop button wiring details.
  > 💡 Revise the schematic to explicitly show all button box channels, pilot lights, and correct E-stop wiring.

### ✅ `c6269101…` — score 7/10
- Text response describes intent rather than summarizing actual analytical findings.
- Highest-variability process is not explicitly identified in the narrative.
- Leadership summary of key results and risks is missing from the text response.
  > 💡 Add a concise executive summary stating key findings, highest-risk process, and priority actions.

### ✅ `be830ca0…` — score 8/10
- Text response includes unnecessary CONFIDENCE tag.
- Statistical conclusions and operational impacts are not explicitly summarized.
- Use of Python instead of Minitab may concern strict stakeholders.
  > 💡 Add a brief summary of key statistical findings and impacts directly in the narrative.

### ✅ `cd9efc18…` — score 5/10
- PDF length is five pages, not the required eight to eleven.
- Execution section lacks specified date, witnesses, and notary details.
- Temporary local guardian Michael T. Fisher not included.
  > 💡 Revise the will to add missing appointments, execution details, and expand content to required length.

### ✅ `a97369c7…` — score 6/10
- Text response summarizes intent rather than providing substantive analysis.
- Memo does not clearly address Delaware Senate Bill 313.
- Generated output includes extraneous confidence tag and planning language.
  > 💡 Ensure the memo fully analyzes all required authorities and remove non-deliverable meta text.

### ✅ `aad21e4c…` — score 8/10
- Previewed clause text appears truncated mid-word, suggesting potential drafting or export issue.
  > 💡 Proofread the DOCX to ensure all provisions are complete and properly formatted.

### ✅ `8314d1b1…` — score 7/10
- Text response summarizes intent rather than substantive analysis.
- Citations to cases and statutes are not visible in provided preview.
- Risk-mitigation recommendations are not clearly delineated as a section.

### ❌ `5e2b6aab…` — score 4/10
- Required 2D PDF assembly and subassembly drawings were not provided.
- Stated environment limitations do not satisfy mandatory deliverables.
- STEP models are described as simplified and may lack manufacturable detail.
  > 💡 Provide the missing PDF drawings and fully defined manufacturable STEP assemblies to meet requirements.

### ❌ `46fc494e…` — score 3/10
- No transient temperature calculations or node-by-node results are actually presented.
- Back-face temperature reported as constant 25 C is physically unrealistic under stated heating.
- Plots and tables lack verifiable numerical data consistent with the specified model.
  > 💡 Perform and document the full transient 22-node conduction calculation and regenerate plots and tables from computed results.

### ✅ `3940b7e7…` — score 6/10
- Report section titles do not match the required headings exactly.
- Text response is a meta-description rather than substantive report content.
- Aerodynamic performance discussion appears limited or unclear.

### ❌ `8077e700…` — score 4/10
- Required PDF report was not produced; only a DOCX file is provided.
- Output contains a promise of analysis, not the actual technical analysis.
- Results and figures for AISI 1045 tempering trends are incomplete or missing.

### ✅ `5a2d70da…` — score 6/10
- Manufacturing steps Excel has malformed columns and minimal step detail.
- Master Tool List lacks sales tax subtotal and post-tax grand total.
- Budget compliance is not explicitly demonstrated in the files.
  > 💡 Fix Excel formatting, add tax calculations, and clearly show total cost within the $7,500 budget.

### ✅ `74d6e8b0…` — score 6/10
- Specific hormone formulations and dosing ranges are not clearly detailed.
- Visible in-text citations and a reference list are not clearly demonstrated.
- Research sources appear generalized rather than explicitly cited.
  > 💡 Add explicit medication dosing tables and clearly cited references from major menopause societies.

### ✅ `81db15ff…` — score 8/10
- Text response describes intent rather than summarizing delivered findings.
- Strategic Recommendation sheet contains an empty first row.
- Spreadsheet lacks citations or sources for regulatory claims.
  > 💡 Revise the text summary to reference actual findings and add sources with minor formatting cleanup.

### ❌ `61e7b9c6…` — score 3/10
- Incorrect generic listed: Bijuva contains estradiol/progesterone, not bazedoxifene.
- Formulary is largely empty and missing most FDA-approved and common off-label menopause medications.
- Completed file does not fully match template structure and lacks comprehensive pricing data.
  > 💡 Populate the full formulary with accurate drug data, correct errors, and complete all required medications and prices.

### ✅ `c9bf9801…` — score 6/10
- NCIPC Mentoring Program acknowledgment not evident in guide credits section.
- Detailed month-by-month timeline with milestones is incomplete or unclear.
- 4- and 8-month evaluation forms are referenced but not provided or linked.
  > 💡 Add missing credits, complete the monthly timeline, and include or link evaluation form templates.

### ❌ `f1be6436…` — score 4/10
- Screenshots are placeholders, not real captured sources.
- Flight details lack airlines, dates, times, and cities.
- Ground transportation section is incomplete and not itemized.
  > 💡 Redo the document using real-time sourced data with complete itemization and embedded screenshots.

### ✅ `41f6ef59…` — score 8/10
- Spreadsheet lacks clearly implemented dropdowns or checkboxes for Yes/No fields.
- Subscription type validation or predefined dropdown options are not explicitly evident.
  > 💡 Add Excel data validation dropdowns and checkboxes to improve input consistency and efficiency.

### ❌ `6d2c8e55…` — score 3/10
- Article PDFs are placeholders rather than actual accessible peer-reviewed articles.
- Articles are not verified as open-access or published within the last 10 years.
- Schedule validity against holidays, spacing, and weekday preference is not demonstrated.
  > 💡 Provide real open-access article PDFs and clearly document compliant scheduling decisions.

### ✅ `4b98ccce…` — score 6/10
- Text response describes intent rather than confirming completed data accuracy.
- No evidence Excel sheets contain all patients with exact required fields.
- Sign-off name and employee ID usage not explicitly verified.
  > 💡 Confirm and summarize actual Excel contents and sign-offs using the provided employee details.

### ✅ `60221cd0…` — score 8/10
- Incorrectly states voters are registered with political parties despite Virginia having no party registration.
  > 💡 Revise the primary election description to accurately reflect Virginia’s open primary system.

### ✅ `ef8719da…` — score 7/10
- Pitch lacks explicit hyperlinks to cited background articles.
- Tentative draft submission timeline is not clearly stated.
- Text response describes deliverable rather than summarizing pitch content.
  > 💡 Add a clear timeline and a section listing live hyperlinks to sources.

### ✅ `3baa0009…` — score 5/10
- Article is under the required 300–500 word length.
- Article does not clearly state or explain negative global growth as specified.
- Lacks specific forecast figures for global, US, and China growth.
  > 💡 Expand the article with concrete forecast numbers and explicitly address negative global growth.

### ✅ `5d0feb24…` — score 7/10
- Text response includes extraneous CONFIDENCE tag, which is unprofessional.
- Response does not explicitly summarize how the arXiv paper’s novel methods are handled.
- Claims about embedded source links are not clearly evidenced in preview.
  > 💡 Remove extraneous tags and briefly summarize how the specific arXiv study’s novelty is addressed.

### ❌ `6974adea…` — score 4/10
- Text response provides a plan, not the required feature article content.
- Article word count, SEO headline, standfirst and subheadings are not demonstrated.
- Compliance with Guardian style and interview-based quotes is not verifiable.
  > 💡 Provide and verify the full 1,000–1,500 word article content within the Word document.

### ✅ `1a78e076…` — score 6/10
- Document length appears shorter than required 10–15 pages.
- Evidence coverage of prevalence, morbidity, mortality, and financial impact is unclear.
- References count and adherence to the 30-source limit are not verified.
  > 💡 Expand content to meet page length and explicitly address all required data elements with verified references.

### ✅ `1b9ec237…` — score 6/10
- Slide count and content requirements cannot be verified from the text response alone.
- Presence and quality of speaker notes are not confirmed.
- Case study risk factors and AHA stage accuracy are not explicitly evidenced.
  > 💡 Open and review the PPT to confirm all specified elements and constraints are fully met.

### ✅ `0112fc9b…` — score 8/10
- Family history is omitted from the SOAP note.
- Cranial nerves II, V, and VII are not documented in the neurologic exam.
  > 💡 Include complete family history and a fully documented cranial nerve exam for thoroughness.

### ✅ `772e7524…` — score 8/10
- Differential diagnoses were not explicitly listed in the Assessment section.
- Antibiotic selection did not address local macrolide resistance considerations.
- Review of systems was not explicitly documented.
  > 💡 Add a brief differential, explicit ROS, and antibiotic rationale aligned with current CAP guidelines.

### ✅ `e6429658…` — score 6/10
- AbbVie assistance form was not completed in the official PDF format.
- Appeal letter page length cannot be verified as 2–4 pages.
- Application completion relied on workaround rather than direct form access.
  > 💡 Complete the AbbVie application in the official PDF and verify appeal letter length compliance.

### ✅ `b5d2e6f1…` — score 5/10
- Sales by Brand and Sales by Store tabs are not shown or verified in the analysis file.
- Required pivot tables and specified column headers are not clearly confirmed.
- Grand totals and calculated ST% fields are not demonstrated.
  > 💡 Open Weekly_Sales_Analysis.xlsx and verify both pivot tabs include all required fields, calculations, and grand totals.

### ✅ `47ef842d…` — score 8/10
- Methodology explanation is brief and not explicitly documented in the Excel file.
- Confidence score is extraneous and not part of the requested deliverables.
  > 💡 Add a short methodology note within the workbook explaining key calculations and assumptions.

### ✅ `1137e2bb…` — score 9/10
- Drill-down capability is implied but not explicitly demonstrated as a pivot table.
  > 💡 Explicitly note or label the summary as a pivot table with drill-down enabled.

### ✅ `c3525d4d…` — score 5/10
- Final store count conflicts with provided final matrix file.
- Original total program cost does not match Production email estimate.
- Added and removed stores are not explicitly identified or highlighted.
  > 💡 Reconcile store counts, correct cost calculations, and clearly flag added and removed stores.

### ✅ `9a0d8d36…` — score 6/10
- Slide content cannot be verified due to lack of preview.
- No visible evidence of step-by-step tax calculations.
- Net proceeds comparison clarity cannot be confirmed.
  > 💡 Provide a slide-by-slide content summary or export key slides as images for verification.

### ✅ `664a42e5…` — score 6/10
- Slide content cannot be verified due to unsupported preview.
- No explicit confirmation each required topic is covered in slides.
- 2025 gift tax exclusion amount not stated in the response.
  > 💡 Provide a slide-by-slide outline or text extract confirming all required elements and figures.

### ❌ `feb5eefc…` — score 4/10
- Required PDF was not produced; only a Word document was delivered.
- Text response promises a PDF but output does not match.
- Compliance with 12-page PDF requirement cannot be verified.
  > 💡 Convert the document to a PDF and confirm it meets the page limit and stated deliverables.

### ✅ `3600de06…` — score 6/10
- Slide count and content cannot be verified from the provided preview.
- Explicit FINRA and NAIC source citations are not confirmed in the deliverable.
- Text response lacks detailed talking points or slide summaries.
  > 💡 Include a slide-by-slide outline with citations to clearly demonstrate requirement coverage.

### ✅ `c657103b…` — score 6/10
- Starting IRA balance deviates from stated $3.5M anticipated 2025 value.
- Use of IRS 2025 Uniform Lifetime Table is not documented or validated.
- PowerPoint template requirement cannot be confirmed from provided content.
  > 💡 Align assumptions exactly to client data and explicitly document tax and RMD methodologies.

### ✅ `ae0c1093…` — score 7/10
- Observation Form lacks three solid handwritten lines beneath each header.
  > 💡 Revise the Observation Form to include three solid horizontal lines under every header.

### ✅ `f9f82549…` — score 6/10
- Flowchart PDF lacks a visual flowchart diagram, presenting only a text list.
- Separate PowerPoint documents per flowchart header were not provided.
- Incident details per header cannot be verified from available preview.
  > 💡 Create a true flowchart PDF and individual PowerPoints per header with detailed incident examples.

### ✅ `57b2cdf2…` — score 8/10
- Surveillance start time conflicts with stated 7:30 p.m. courtesy start.
- Surveillance extended past 1:00 a.m. without explicit justification.
- Bullet points display formatting errors using letter l instead of symbols.
  > 💡 Clarify timing deviations and correct bullet formatting for greater professionalism.

### ✅ `84322284…` — score 6/10
- Text response describes intent rather than summarizing actual investigative findings.
- Extraneous confidence tag included in a professional deliverable.
- Report analysis and timeline reconstruction are not demonstrated in the text response.
  > 💡 Include a concise executive summary of findings and remove nonprofessional metadata.

### ✅ `a46d5cd2…` — score 8/10
- Text response describes intent rather than summarizing findings.
- Photographic evidence embedding is not clearly demonstrated in the preview.
  > 💡 Include a brief executive summary in the text response and clearly label embedded photos in the report.

### ✅ `6241e678…` — score 5/10
- Schedule includes unrequested tasks like casting, location scouting, and crew hiring.
- Kickoff call date appears incorrect or missing for July 7, 2025.
- Client review durations are not clearly shown as two days per asset.
  > 💡 Revise the schedule to match only requested tasks, correct dates, and clearly mark client review periods.

### ✅ `e14e32ba…` — score 6/10
- Locations and business hours are missing for all restaurants.
- Image links point to websites, not actual photos of establishments.
- Notable dishes and websites are not consistently labeled as required.
  > 💡 Add explicit locations, business hours, proper photo links, and clearly labeled website and dish sections.

### ✅ `b1a79ce1…` — score 8/10
- Text response describes intended deliverable rather than summarizing the completed moodboard.
  > 💡 Briefly describe the key visuals and color palette shown in the final moodboard.

### ✅ `e4f664ea…` — score 5/10
- Text response is a meta description, not the screenplay itself.
- Screenplay content cannot be verified from provided preview.
- Compliance with show-not-tell and formatting is unconfirmed.
  > 💡 Include or preview key pages of the screenplay to verify formatting and content quality.

### ✅ `a079d38f…` — score 7/10
- Summary sheet subtotal is blank, indicating an incomplete cost calculation.
- Only one videographer is costed despite a two-camera shoot requirement.
- Videographer hours and cost calculation are unclear or inconsistent.
  > 💡 Complete the summary totals and clarify crew quantities and hour calculations, especially for videography.

### ❌ `02aa1805…` — score 3/10
- No Illinois EPA data were pulled; Excel contains zero wells.
- No viable wells identified or highlighted per criteria.
- Email lacks specific recommendations and supporting data.
  > 💡 Retrieve IEPA factsheet data, populate the workbook, and provide data-backed well recommendations.

### ✅ `fd6129bd…` — score 8/10
- Change Request Form appears to be a blank template rather than a completed example.
  > 💡 Include a sample completed change request demonstrating required fields and approvals.

### ✅ `ce864f41…` — score 7/10
- Text response does not directly answer the three executive questions.
- PMO and Professional Education labeled underutilized despite being near target range.
- No explicit confirmation that 15% admin time was excluded in calculations.
  > 💡 Summarize key findings directly in the text response and clarify utilization thresholds applied.

### ✅ `58ac1cc5…` — score 6/10
- The official Change Control Form.pdf is largely unfilled and not completed as required.
- The response claims form completion, but relies on a separate summary PDF instead.
- Risk assessment depth is high-level and may be insufficient for GMP change control.
  > 💡 Fully complete the official Change Control Form with known details and integrate the risk assessment per SOP.

### ✅ `3c19c6d1…` — score 6/10
- Report content does not explicitly confirm all required slide elements and wording.
- Generated description overclaims nine slides beyond specified requirements.
- Dependence on reference files not requested or defined in the original task.
  > 💡 Explicitly map each required slide to its exact content and verify alignment with the task brief.

### ✅ `a99d85fc…` — score 6/10
- Monthly matrix structure and formulas are not clearly verifiable from the file preview.
- Color-coding for scenarios and editable cells cannot be confirmed.
- Notes section content is not visible or clearly defined.
  > 💡 Include clearer labeling, visible notes, and verifiable color-coding and formulas in the workbook.

### ❌ `55ddb773…` — score 3/10
- Specific violation types and qualifying questions from the reference PDF were not included.
- Deliverable is a DOCX, not the requested finalized PDF form.
- Architectural regulation items were not individually listed as required.
  > 💡 Extract and transcribe all violation details from the reference PDF and deliver a completed PDF form.

### ❌ `1e5a1d7f…` — score 3/10
- The .docx lacks the required table and columns.
- No weekly schedule tasks are populated from the PM duties.
- Output does not reflect cyclical weekly structure.
  > 💡 Populate the .docx with a complete table using the four required columns and PM duties.

### ✅ `0419f1c3…` — score 8/10
- Acknowledgement-time performance is not quantitatively analyzed in the summary section.
  > 💡 Add explicit metrics and justification linking each assigned training module to specific performance gaps.

### ✅ `ed2bc14c…` — score 9/10
- Plan lacks explicit KPIs and tracking method tied to the 10% retention goal.
  > 💡 Add clear metrics, baseline retention rate, and a six-month measurement plan to quantify success.

### ✅ `46bc7238…` — score 6/10
- Next Steps section is missing from the PDF.
- One-page flyer template example content is not shown in the PDF.
- Stock photos are not clearly embedded on each PDF page.
  > 💡 Add a Next Steps page, include a visible flyer template page, and embed stock images on every page.

### ✅ `2d06bc0a…` — score 7/10
- LOI expiration date is not clearly stated with a specific deadline.
- Non-binding section appears incomplete or truncated in the document.
  > 💡 Add a clear 7–10 day expiration date and complete the non-binding language.

### ✅ `fd3ad420…` — score 6/10
- PDF was not produced; only DOCX files were delivered.
- Commission splits lack specific percentages for agents and associate brokers.
- Text response promises PDF generation but does not deliver it.
  > 💡 Generate and deliver a finalized one-page PDF with explicit commission percentages included.

### ✅ `0818571f…` — score 6/10
- Properties are illustrative, not verified active listings from June 2025.
- Report does not confirm properties were sourced directly from Crexi or LoopNet.
- Document shows photo and map placeholders without embedded visuals.
  > 💡 Replace illustrative examples with verified active listings and embed actual photos and maps from source platforms.

### ✅ `6074bba3…` — score 7/10
- Pricing recommendations lack explicit low, mid, and high tiers.
- Subject summary omits square footage and detailed lease terms.
- Comparable properties lack addresses or location context.
  > 💡 Add explicit pricing tiers, property size details, lease terms, and clearer comp identification.

### ✅ `5ad0c554…` — score 7/10
- Does not explicitly reference or identify items from the 132 Things REALTORS Do for Buyers document.
- Brochure content is generic and not clearly tied to specific listed buyer services.
- Images appear produced but not clearly integrated into the Word brochure layout.
  > 💡 Revise the brochure to explicitly cite and map key milestones to specific items from the 132 Things REALTORS Do for Buyers list and embed visuals.

### ❌ `11593a50…` — score 3/10
- No qualifying homes were researched; PDFs only state none found without MLSLI verification.
- Showing book is one page and lacks required columns, photos, and $/sqft.
- Data source and Excel file reference wrong location and irrelevant listings.
  > 💡 Perform a live MLSLI search and generate proper two-page listing and pinned map PDFs with real properties.

### ✅ `94925f49…` — score 6/10
- School statistics and home listings are representative examples, not verified real data.
- Reports lack explicit citations or links to reputable school and MLS sources.
- Garden City Park report home listings appear truncated or incomplete.
  > 💡 Replace example data with fully sourced, verifiable statistics and complete real home listings.

### ✅ `90f37ff3…` — score 8/10
- Comparable listings lack lease or listing dates to confirm three-year requirement.
- Data sources like LoopNet or Crexi are not explicitly cited.
  > 💡 Add listing dates and explicit data source citations to strengthen credibility and compliance.

### ✅ `650adcb1…` — score 5/10
- Sixth tab for interns time off requests is missing.
- Several requested days off are not fully reflected in the schedule.
- Required color key on the first excel page is not shown.
  > 💡 Add the missing time-off tab, correct all requested dates, and include a visible color key.

### ✅ `01d7e53e…` — score 6/10
- Draft agreement content cannot be verified from provided response or file preview.
- Extra unrelated file produced beyond requested agreement deliverable.
- Response does not confirm inclusion of contacts, compliance clauses, and term specifics.
  > 💡 Provide a brief summary or excerpt confirming all required provisions are included in the draft.

### ✅ `a73fbc98…` — score 6/10
- Assigned table labels do not match numbered tables shown in the official layouts.
- The Excel vendor list was not updated with an Assigned Table(s) column.
- Electricity constraints are not clearly reflected in the table assignments.
  > 💡 Align table numbering with layouts and update the Excel file to clearly reflect assignments and power usage.

### ✅ `0ec25916…` — score 8/10
- Table columns are not clearly delineated in the PDF layout.
  > 💡 Add visible table borders or shading to clearly distinguish the two columns.

### ✅ `116e791e…` — score 5/10
- Required one-page PDF was not produced; only a Word document provided.
- Document likely exceeds one page based on length.
- Text response claims PDF delivery but does not match actual file.
  > 💡 Convert the care plan into a single-page PDF and ensure the delivered file matches the stated format.

### ❌ `dd724c67…` — score 3/10
- Facility contact list contains only placeholders, not researched Long Island facilities.
- Did not compile all hospitals and rehabilitation facilities as required.
- TFU guide lacks explicit ACO REACH PY 2025 condition-specific specifications.
  > 💡 Populate the spreadsheet with verified Long Island facilities and align TFU details to CMS PY 2025 guidance.

### ❌ `7151c60a…` — score 4/10
- Fax cover sheet contains a visible typo and truncated recipient section.
- Confidentiality statement is separate, not included on the fax cover sheet.
- Pre-screening checklist preview lacks required table, page numbers, and internal-only fields.
  > 💡 Revise both documents to fully include all specified elements and correct formatting and content errors.

### ❌ `90edba97…` — score 3/10
- Did not enter monthly or annual lab results into the tracker.
- Medication and treatment changes were not documented per protocols.
- Claimed missing lab data despite provided Patient Lab Reports file.
  > 💡 Populate the Excel tracker with all patient labs and protocol-driven treatment changes from the provided reports.

### ❌ `91060ff0…` — score 3/10
- Poster content is largely missing required sections and educational detail.
- No PDF file produced and layout does not demonstrate 36x24 inch design.
- Lacks visuals, tables, and comprehensive references for self-guided learning.
  > 💡 Create a complete 36x24 inch poster with all specified sections, visuals, and export as a PDF.

### ✅ `8384083a…` — score 6/10
- Missing explicit formula column for each medication.
- Miebo standard SIG and days’ supply are incorrect.
- Miebo is not injectable yet grouped without clarification.
  > 💡 Add a formula column and correct Miebo dosing and days’ supply using FDA-labeled SIG.

### ✅ `045aba2e…` — score 6/10
- Self-assessment frequency is incorrect; California requires biennial, not annual, completion.
- Monthly controlled substance inventory reconciliation is not a California legal requirement.
- Checklist lacks explicit citations to California lawbook or self-assessment sections.
  > 💡 Revise tasks to match statutory frequencies and add lawbook section references for each checklist item.

### ❌ `b3573f20…` — score 3/10
- PDF is only one page instead of the required three pages.
- Missing major sections like company overview, operations, logistics, and compliance.
- Content is too sparse to assess operational and sales readiness.
  > 💡 Expand the document to three pages with comprehensive, clearly labeled questions covering all required areas.

### ✅ `a69be28f…` — score 6/10
- Final presentation was not delivered as a PDF as explicitly requested.
- Text response summarizes intent but does not report actual regional top-performing fits.
- No explicit confirmation or preview of executive summary slide content.
  > 💡 Export the PPTX to PDF and include a brief written summary of key regional fit winners.

### ✅ `788d2bc6…` — score 6/10
- Delivered PPTX instead of requested PDF format.
- No evidence of TikTok Shop or influencer services aligned to documentation.
- Slide-level content, visuals, and count were not demonstrated or verified.
  > 💡 Provide a PDF export and clearly document slide-by-slide content covering all required services.

### ✅ `74ed1dc7…` — score 8/10
- Renaming Bulk may conflict with requirement to add order types in addition to existing ones.
  > 💡 Clarify whether Forecast Bulk is a new type or a reporting sub-class of Bulk.

### ✅ `69a8ef86…` — score 7/10
- Internal process lacks explicit step-by-step actions with timelines and owners.
- Several required deadlines are not clearly documented in the internal process.
- Return Issues.docx appears unnecessary and not requested in the task.
  > 💡 Revise the internal document to list each required step with action, deadline, and responsible team.

### ✅ `19403010…` — score 6/10
- Sections 3–5 do not clearly show all nine required columns.
- Top three functions and total rows are not clearly validated for Sections 3–5.
- Analysis output lacks visible function-level % to total and disco metrics.
  > 💡 Expand Sections 3–5 to explicitly display all required columns and clearly label top three functions and totals.

### ✅ `105f8ad0…` — score 5/10
- No actual online research or cited competitor MSRPs from Macy’s, Ulta, or Sephora.
- Competitor set definition and brand/channel sources are not documented or traceable.
- Competitor $/oz averages appear assumed and identical across concentrations without evidence.
  > 💡 Conduct and document real competitor MSRP research with cited sources and recalibrate $/oz benchmarks by size and concentration.

### ✅ `b57efde3…` — score 6/10
- Exhibitor list was not actually reviewed or validated against the official Aqua Nor 2025 list.
- Prospecting list is very limited with only four companies, not representative of hundreds of exhibitors.
- Several entries are marked as preliminary desk research rather than confirmed leads.
  > 💡 Expand and validate the list using the official exhibitor directory and confirmed product portfolios.

### ❌ `15d37511…` — score 3/10
- Spreadsheet omits required pricing, cost, margin, and totals.
- Tiered pricing and discounts are not calculated or applied.
- Output relies on placeholders despite reference pricing file provided.
  > 💡 Populate all pricing from the email and fully calculate margins and Year 1 totals.

### ✅ `bb863dd9…` — score 6/10
- WHO reference link in the quotation appears truncated.
- Line-item table with quantities and unit prices is not clearly structured.
- Total USD amounts per item or overall are not clearly shown.
  > 💡 Ensure a complete itemized table with quantities, unit and total prices, and a full WHO reference link.

### ✅ `fe0d3941…` — score 6/10
- Survey was delivered as DOCX instead of required PDF.
- Survey pages are not clearly separated into two titled pages.
- Text response claims PDF delivery but files do not match.
  > 💡 Convert the survey to a properly formatted two-page PDF with correct titles.

### ✅ `6a900a40…` — score 6/10
- Quotation header columns appear misaligned, with quantity replacing the column header.
- Red-font general remark about freight validity cannot be verified in the file preview.
- Correct discounted unit price and total calculations are not clearly confirmed.
  > 💡 Review and correct the Excel layout, formatting, and pricing calculations before final submission.

### ✅ `9efbcd35…` — score 6/10
- MSCI performance data and specific figures are not explicitly cited or presented.
- Document relies on generalized themes rather than sourced Q1 2025 performance evidence.
- Technology section appears truncated, indicating a possible formatting or content error.
  > 💡 Include explicit MSCI index returns with citations and ensure all sections are complete and proofread.

### ✅ `4c4dc603…` — score 6/10
- Missing specific numeric targets like target raise, IRR, token supply, and price per token.
- Team section lacks named key members and roles.
- Salient market size and valuation frequency are vague or omitted.
  > 💡 Add concrete numeric metrics and detailed team profiles to meet investor-ready standards.

### ✅ `bb499d9c…` — score 7/10
- Text response does not explicitly confirm all required sections are fully addressed.
- Document page count compliance with 25-page limit is not evidenced.
- No visible confirmation of specific regulatory compliance coverage.
  > 💡 Add a requirements checklist and executive summary confirming scope, compliance, and page length.

### ✅ `5349dd7b…` — score 7/10
- Historical rate increases lack cited sources or evidence of actual searches.
- Business rate eligibility and assumptions are not clearly documented.
- Specific flat-rate service names and delivery levels are not specified.
  > 💡 Add cited sources and explicitly document business-rate programs and flat-rate service definitions.

### ✅ `552b7dd0…` — score 8/10
- Text response lacks explicit confirmation of summary slide insights and recommendations.
- An additional Excel file was produced though not explicitly requested.
  > 💡 Briefly confirm key takeaways and recommendations are clearly presented on the final slide.

### ❌ `76418a2c…` — score 4/10
- Completed manifest lacks pick ticket numbers, customers, and correct weights.
- Shipping methods are incorrect; all shipments show UPS regardless of weight.
- Savings and costs appear hardcoded and not derived per shipping parameters.
  > 💡 Recalculate each shipment using pick ticket weights and populate the manifest with correct fields and methods.

### ❌ `0e386e32…` — score 3/10
- ZIP archive is too small to contain a complete production-style codebase.
- No verifiable source files or code content are provided for inspection.
- Claims of complete implementation conflict with missing or inaccessible artifacts.
  > 💡 Provide a fully populated ZIP with inspectable frontend, smart contracts, and documentation files.

### ❌ `7de33b48…` — score 4/10
- No ScreenReaderStatusMessage TypeScript JSX implementation is shown or verifiable.
- Required WCAG ARIA22 tests are not evidenced or described in sufficient detail.
- Zip contents and filenames cannot be validated against stated requirements.
  > 💡 Include and verify the actual TSX utility and test files with explicit WCAG ARIA22 assertions.

### ❌ `4122f866…` — score 4/10
- Terraform configuration files are not visible or evidenced in the deliverable.
- Lambda implementation details for reCAPTCHA validation and SES sending are unverified.
- README lacks required variable definitions, architecture details, and SES/API Gateway setup steps.
  > 💡 Include full Terraform files, complete Lambda source, and a detailed README matching all specified requirements.

### ❌ `2c249e0f…` — score 3/10
- OpenAPI 3.0 YAML specification file is completely missing.
- Deliverable claims files not actually produced.
- API design details and endpoints are absent.
  > 💡 Provide the full OpenAPI 3.0 YAML spec and ensure all claimed files are included.

## Failure Analysis

Errors were present in 29 tasks, with Finance and Insurance and Retail Trade showing the lowest success rates. The 68 retried tasks indicate that initial responses frequently did not meet internal acceptance criteria, potentially due to formatting issues, incomplete deliverables, or insufficient adherence to elicitation prompts. Retries appear to have mitigated some failures but at the cost of increased latency. No single sector dominated error counts, suggesting cross-cutting issues related to prompt complexity or subprocess execution stability rather than domain-specific knowledge gaps.

## Recommendations

Refine prompt templates for sectors with lower success rates (e.g., Finance and Retail) to reduce ambiguity and improve first-pass task completion. Introduce stricter intermediate validation checks to catch common causes of retries earlier in the subprocess. Finally, evaluate latency drivers by profiling retries and long-running tasks, with the goal of reducing average execution time without sacrificing task completeness or self-assessed quality.

## Deliverable Files

- `7b08cd4d…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 7 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 16 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 18 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 5 file(s)
- `17111c03…` (Government): 3 file(s)
- `c44e9b62…` (Government): 6 file(s)
- `99ac6944…` (Information): 4 file(s)
- `f9a1c16c…` (Information): 1 file(s)
- `38889c3b…` (Information): 1 file(s)
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
- `85d95ce5…` (Government): 4 file(s)
- `76d10872…` (Government): 5 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 1 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 2 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 3 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 4 file(s)
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
- `e222075d…` (Information): 6 file(s)
- `c94452e4…` (Information): 3 file(s)
- `75401f7c…` (Information): 3 file(s)
- `a941b6d8…` (Information): 2 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 1 file(s)
- `c7d83f01…` (Finance and Insurance): 3 file(s)
- `a1963a68…` (Finance and Insurance): 1 file(s)
- `b39a5aa7…` (Finance and Insurance): 2 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 2 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 3 file(s)
- `1aecc095…` (Health Care and Social Assistance): 4 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 3 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 11 file(s)
- `8c823e32…` (Government): 1 file(s)
- `eb54f575…` (Government): 1 file(s)
- `11e1b169…` (Government): 1 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 1 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `9e39df84…` (Manufacturing): 2 file(s)
- `68d8d901…` (Manufacturing): 3 file(s)
- `1752cb53…` (Manufacturing): 6 file(s)
- `bd72994f…` (Retail Trade): 2 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 5 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 1 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `8a7b6fca…` (Manufacturing): 1 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 1 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 8 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 2 file(s)
- `46fc494e…` (Manufacturing): 6 file(s)
- `3940b7e7…` (Manufacturing): 2 file(s)
- `8077e700…` (Manufacturing): 4 file(s)
- `5a2d70da…` (Manufacturing): 4 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 5 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 13 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 7 file(s)
- `60221cd0…` (Information): 1 file(s)
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
- `feb5eefc…` (Finance and Insurance): 1 file(s)
- `3600de06…` (Finance and Insurance): 1 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 2 file(s)
- `f9f82549…` (Retail Trade): 2 file(s)
- `57b2cdf2…` (Retail Trade): 3 file(s)
- `84322284…` (Retail Trade): 4 file(s)
- `a46d5cd2…` (Retail Trade): 5 file(s)
- `6241e678…` (Information): 1 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `e4f664ea…` (Information): 3 file(s)
- `a079d38f…` (Information): 3 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 5 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 7 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 7 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 13 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 4 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 3 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 5 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 1 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 4 file(s)
- `a73fbc98…` (Government): 6 file(s)
- `0ec25916…` (Health Care and Social Assistance): 1 file(s)
- `116e791e…` (Health Care and Social Assistance): 1 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 5 file(s)
- `90edba97…` (Health Care and Social Assistance): 6 file(s)
- `91060ff0…` (Retail Trade): 1 file(s)
- `8384083a…` (Retail Trade): 1 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `b3573f20…` (Wholesale Trade): 1 file(s)
- `a69be28f…` (Wholesale Trade): 10 file(s)
- `788d2bc6…` (Wholesale Trade): 2 file(s)
- `74ed1dc7…` (Wholesale Trade): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `19403010…` (Wholesale Trade): 2 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 3 file(s)
- `fe0d3941…` (Wholesale Trade): 4 file(s)
- `6a900a40…` (Wholesale Trade): 6 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
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
