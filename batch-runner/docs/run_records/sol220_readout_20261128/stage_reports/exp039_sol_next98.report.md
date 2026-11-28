# Experiment Report: Codex command-line tool against Foundry — GPT-5.6 Sol, first 98 of exp038's 195

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp039_sol_next98` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.6-sol |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-11-20 |
| **Duration** | 773m 4s |
| **Generated At** | 2026-11-21T02:43:24.772777+00:00 |
| 🤗 HF Target | [HyeonSang/exp039_sol_next98](https://huggingface.co/datasets/HyeonSang/exp039_sol_next98) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 98 / 98 tasks (100.0%) |
| Priced | 0 / 98 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 6 (no record) |
| Not priced | call_reachability_unknown, price_missing, usage_partial |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `5ef409a55a75…`)

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 98 |
| Success | 92 (93.9%) |
| Errors | 6 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 453,656ms |
| Max Latency | 1,114,069ms |
| Total LLM Time | 44458s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 85 |
| Successfully generated | 79 (92.9%) |
| Failed (empty outputs preserved) | 6 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 9 | 8 | 88.9% | - | 531,539ms |
| Government | 12 | 9 | 75.0% | - | 356,610ms |
| Health Care and Social Assistance | 16 | 16 | 100.0% | - | 516,253ms |
| Information | 7 | 7 | 100.0% | - | 486,252ms |
| Manufacturing | 13 | 12 | 92.3% | - | 485,410ms |
| Professional, Scientific, and Technical  | 12 | 12 | 100.0% | - | 467,605ms |
| Real Estate and Rental and Leasing | 10 | 9 | 90.0% | - | 331,279ms |
| Retail Trade | 8 | 8 | 100.0% | - | 418,721ms |
| Wholesale Trade | 11 | 11 | 100.0% | - | 467,922ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | - | 500660ms |
| 2 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | - | 409870ms |
| 3 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 181967ms |
| 4 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 282984ms |
| 5 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | - | 316682ms |
| 6 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 436725ms |
| 7 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | - | 669586ms |
| 8 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | - | 477362ms |
| 9 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | - | 451582ms |
| 10 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 647689ms |
| 11 | `1bff4551…` | Government | Recreation Workers | ❌ error | - | 0 | - | 95493ms |
| 12 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | - | 503470ms |
| 13 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 1 | - | 263674ms |
| 14 | `22c0809b…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 80875ms |
| 15 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | - | 511372ms |
| 16 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 1 | - | 243659ms |
| 17 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 2 | - | 409221ms |
| 18 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | - | 320213ms |
| 19 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | - | 490417ms |
| 20 | `2fa8e956…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 76872ms |
| 21 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 520339ms |
| 22 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | - | 415242ms |
| 23 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | - | 399779ms |
| 24 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 1 | - | 481135ms |
| 25 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | - | 295714ms |
| 26 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | - | 465345ms |
| 27 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | - | 462665ms |
| 28 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 2 | - | 349775ms |
| 29 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | - | 496778ms |
| 30 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | - | 810771ms |
| 31 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 7 | - | 552121ms |
| 32 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | - | 236514ms |
| 33 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | - | 595451ms |
| 34 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | - | 929417ms |
| 35 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | - | 693068ms |
| 36 | `46b34f78…` | Finance and Insurance | Financial and Inve | ❌ error | - | 0 | - | 108763ms |
| 37 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 7 | - | 574021ms |
| 38 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 15 | - | 346795ms |
| 39 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 3 | - | 143724ms |
| 40 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 343663ms |
| 41 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 2 | - | 926514ms |
| 42 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | - | 390914ms |
| 43 | `4c18ebae…` | Government | Compliance Officer | ❌ error | - | 0 | - | 713075ms |
| 44 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | - | 184729ms |
| 45 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | - | 645823ms |
| 46 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 547749ms |
| 47 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | - | 223993ms |
| 48 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 468696ms |
| 49 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | - | 424789ms |
| 50 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | - | 171367ms |
| 51 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | - | 623951ms |
| 52 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 1 | - | 222307ms |
| 53 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 4 | - | 531348ms |
| 54 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ❌ error | - | 0 | - | 445164ms |
| 55 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | - | 492364ms |
| 56 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | - | 710173ms |
| 57 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 43 | - | 675369ms |
| 58 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | - | 699723ms |
| 59 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 1 | - | 150123ms |
| 60 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | - | 362126ms |
| 61 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 375848ms |
| 62 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | - | 471327ms |
| 63 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | - | 584380ms |
| 64 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | - | 258766ms |
| 65 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | - | 290605ms |
| 66 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 311932ms |
| 67 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | - | 452906ms |
| 68 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | - | 321325ms |
| 69 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | - | 493635ms |
| 70 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | - | 647835ms |
| 71 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | - | 265794ms |
| 72 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | - | 891964ms |
| 73 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 309592ms |
| 74 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 11 | - | 526993ms |
| 75 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | - | 679607ms |
| 76 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 575573ms |
| 77 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | - | 1003854ms |
| 78 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | - | 713072ms |
| 79 | `75401f7c…` | Information | Film and Video Edi | ✅ success | - | 1 | - | 597892ms |
| 80 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 229331ms |
| 81 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 1 | - | 316156ms |
| 82 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 201185ms |
| 83 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 4 | - | 441914ms |
| 84 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | - | 310456ms |
| 85 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | - | 272168ms |
| 86 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | - | 459007ms |
| 87 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 6 | - | 340443ms |
| 88 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 429614ms |
| 89 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | - | 582161ms |
| 90 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | - | 1114069ms |
| 91 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | - | 470494ms |
| 92 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | - | 736675ms |
| 93 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 2 | - | 265129ms |
| 94 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | - | 598418ms |
| 95 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | - | 404271ms |
| 96 | `854f3814…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | - | 220076ms |
| 97 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 1 | - | 438382ms |
| 98 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | - | 653670ms |

## Deliverable Files

- `0fad6023…` (Retail Trade): 1 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 3 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `15d37511…` (Wholesale Trade): 1 file(s)
- `1752cb53…` (Manufacturing): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `211d0093…` (Retail Trade): 1 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `2696757c…` (Government): 1 file(s)
- `27e8912c…` (Government): 2 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 2 file(s)
- `327fbc21…` (Wholesale Trade): 2 file(s)
- `36d567ba…` (Government): 1 file(s)
- `3940b7e7…` (Manufacturing): 2 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `403b9234…` (Government): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 7 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 2 file(s)
- `4520f882…` (Finance and Insurance): 1 file(s)
- `45c6237b…` (Retail Trade): 4 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 7 file(s)
- `46fc494e…` (Manufacturing): 15 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 3 file(s)
- `47ef842d…` (Wholesale Trade): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `4d61a19a…` (Retail Trade): 2 file(s)
- `4de6a529…` (Finance and Insurance): 2 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 2 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `57b2cdf2…` (Retail Trade): 1 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 2 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `5e2b6aab…` (Manufacturing): 43 file(s)
- `5f6c57dd…` (Finance and Insurance): 2 file(s)
- `60221cd0…` (Information): 1 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 1 file(s)
- `61717508…` (Finance and Insurance): 3 file(s)
- `61b0946a…` (Health Care and Social Assistance): 1 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 2 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 2 file(s)
- `6241e678…` (Information): 3 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `650adcb1…` (Government): 1 file(s)
- `664a42e5…` (Finance and Insurance): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 11 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 1 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `75401f7c…` (Information): 1 file(s)
- `76418a2c…` (Manufacturing): 1 file(s)
- `76d10872…` (Government): 1 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `788d2bc6…` (Wholesale Trade): 4 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 6 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `8077e700…` (Manufacturing): 2 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8384083a…` (Retail Trade): 2 file(s)
- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `854f3814…` (Professional, Scientific, and Technical Services): 2 file(s)
- `85d95ce5…` (Government): 1 file(s)
- `87da214f…` (Finance and Insurance): 1 file(s)
