# Experiment Report: Codex command-line tool against Foundry — GPT-5.6 Sol, last 97 of exp038's 195

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp040_sol_last97` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.6-sol |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-11-24 |
| **Duration** | 896m 13s |
| **Generated At** | 2026-11-25T01:06:41.224986+00:00 |
| 🤗 HF Target | [HyeonSang/exp040_sol_last97](https://huggingface.co/datasets/HyeonSang/exp040_sol_last97) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 97 / 97 tasks (100.0%) |
| Priced | 0 / 97 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 8 (no record) |
| Not priced | call_reachability_unknown, price_missing, usage_partial |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `ad1678b96951…`)

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 97 |
| Success | 89 (91.8%) |
| Errors | 8 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 542,511ms |
| Max Latency | 1,492,452ms |
| Total LLM Time | 52623s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 77 |
| Successfully generated | 71 (92.2%) |
| Failed (empty outputs preserved) | 6 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 13 | 12 | 92.3% | - | 627,749ms |
| Government | 10 | 10 | 100.0% | - | 577,577ms |
| Health Care and Social Assistance | 6 | 5 | 83.3% | - | 482,754ms |
| Information | 15 | 13 | 86.7% | - | 513,926ms |
| Manufacturing | 9 | 8 | 88.9% | - | 666,732ms |
| Professional, Scientific, and Technical  | 10 | 10 | 100.0% | - | 734,709ms |
| Real Estate and Rental and Leasing | 12 | 11 | 91.7% | - | 430,706ms |
| Retail Trade | 10 | 9 | 90.0% | - | 429,152ms |
| Wholesale Trade | 12 | 11 | 91.7% | - | 439,498ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | - | 458132ms |
| 2 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | - | 780164ms |
| 3 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | - | 590525ms |
| 4 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | - | 450219ms |
| 5 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | - | 551243ms |
| 6 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | - | 326218ms |
| 7 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 5 | - | 865107ms |
| 8 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | - | 834030ms |
| 9 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 6 | - | 469488ms |
| 10 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | - | 861484ms |
| 11 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | - | 640357ms |
| 12 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | - | 1015959ms |
| 13 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | - | 541875ms |
| 14 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 41 | - | 983372ms |
| 15 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | - | 684687ms |
| 16 | `a0552909…` | Health Care and Social | Medical Secretarie | ✅ success | - | 6 | - | 421101ms |
| 17 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | - | 490278ms |
| 18 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | - | 969236ms |
| 19 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | - | 655882ms |
| 20 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 5 | - | 821895ms |
| 21 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | - | 341624ms |
| 22 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 3 | - | 1492452ms |
| 23 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 1 | - | 384196ms |
| 24 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 804550ms |
| 25 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 4 | - | 484770ms |
| 26 | `a73fbc98…` | Government | Recreation Workers | ✅ success | - | 5 | - | 566410ms |
| 27 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 3 | - | 870969ms |
| 28 | `a941b6d8…` | Information | Film and Video Edi | ✅ success | - | 3 | - | 796345ms |
| 29 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 1 | - | 560520ms |
| 30 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 3 | - | 767152ms |
| 31 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | - | 470044ms |
| 32 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | - | 430528ms |
| 33 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | - | 781557ms |
| 34 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 374589ms |
| 35 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 2 | - | 554346ms |
| 36 | `afe56d05…` | Information | Editors | ❌ error | - | 0 | - | 333815ms |
| 37 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | - | 282174ms |
| 38 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | - | 317983ms |
| 39 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | - | 625656ms |
| 40 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | - | 874035ms |
| 41 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | - | 562657ms |
| 42 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 6 | - | 521854ms |
| 43 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | - | 558129ms |
| 44 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | - | 648692ms |
| 45 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | - | 1004878ms |
| 46 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 358125ms |
| 47 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | - | 674535ms |
| 48 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | - | 3 | - | 434962ms |
| 49 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 9 | - | 833950ms |
| 50 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | - | 678509ms |
| 51 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | - | 831924ms |
| 52 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 522708ms |
| 53 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | - | 423266ms |
| 54 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 3 | - | 749974ms |
| 55 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | - | 697429ms |
| 56 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | - | 719009ms |
| 57 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 11 | - | 603050ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | - | 24 | - | 529885ms |
| 59 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | - | 788612ms |
| 60 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | - | 545719ms |
| 61 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 3 | - | 565675ms |
| 62 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | - | 595656ms |
| 63 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | - | 776337ms |
| 64 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | - | 328007ms |
| 65 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | - | 169293ms |
| 66 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | - | 92520ms |
| 67 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 367015ms |
| 68 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 608080ms |
| 69 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | - | 175171ms |
| 70 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 1 | - | 651167ms |
| 71 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | - | 736655ms |
| 72 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 16 | - | 546304ms |
| 73 | `e4f664ea…` | Information | Producers and Dire | ❌ error | - | 0 | - | 205441ms |
| 74 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 524921ms |
| 75 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | - | 527163ms |
| 76 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 2 | - | 478505ms |
| 77 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | - | 356750ms |
| 78 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 352144ms |
| 79 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | - | 550110ms |
| 80 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | - | 796176ms |
| 81 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | - | 285339ms |
| 82 | `efca245f…` | Manufacturing | First-Line Supervi | ❌ error | - | 0 | - | 503425ms |
| 83 | `f1be6436…` | Health Care and Social | Medical Secretarie | ❌ error | - | 0 | - | 2566ms |
| 84 | `f2986c1f…` | Retail Trade | Pharmacists | ❌ error | - | 0 | - | 26443ms |
| 85 | `f3351922…` | Finance and Insurance | Customer Service R | ❌ error | - | 0 | - | 2401ms |
| 86 | `f5d428fd…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 2337ms |
| 87 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | - | 0 | - | 73340ms |
| 88 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | - | 577900ms |
| 89 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 3 | - | 238629ms |
| 90 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 2 | - | 485068ms |
| 91 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 4 | - | 343743ms |
| 92 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | - | 223463ms |
| 93 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 2 | - | 547511ms |
| 94 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | - | 459444ms |
| 95 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | - | 488919ms |
| 96 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 2 | - | 524792ms |
| 97 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 1 | - | 222324ms |

## Deliverable Files

- `8a7b6fca…` (Manufacturing): 2 file(s)
- `8c823e32…` (Government): 2 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `90edba97…` (Health Care and Social Assistance): 1 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 2 file(s)
- `91060ff0…` (Retail Trade): 5 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 6 file(s)
- `99ac6944…` (Information): 5 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `9e39df84…` (Manufacturing): 1 file(s)
- `9e8607e7…` (Finance and Insurance): 41 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `a0552909…` (Health Care and Social Assistance): 6 file(s)
- `a079d38f…` (Information): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `a1963a68…` (Finance and Insurance): 5 file(s)
- `a328feea…` (Government): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 3 file(s)
- `a46d5cd2…` (Retail Trade): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `a69be28f…` (Wholesale Trade): 4 file(s)
- `a73fbc98…` (Government): 5 file(s)
- `a74ead3b…` (Government): 3 file(s)
- `a941b6d8…` (Information): 3 file(s)
- `a95a5829…` (Government): 1 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 3 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `ab81b076…` (Wholesale Trade): 2 file(s)
- `ae0c1093…` (Retail Trade): 2 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b57efde3…` (Wholesale Trade): 3 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `b78fd844…` (Finance and Insurance): 6 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b9665ca1…` (Manufacturing): 1 file(s)
- `bb499d9c…` (Finance and Insurance): 1 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `bbe0a93b…` (Government): 3 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `be830ca0…` (Manufacturing): 9 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c44e9b62…` (Government): 3 file(s)
- `c6269101…` (Manufacturing): 2 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `c7d83f01…` (Finance and Insurance): 11 file(s)
- `c94452e4…` (Information): 24 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 4 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `cecac8f9…` (Retail Trade): 2 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `dd724c67…` (Health Care and Social Assistance): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `e14e32ba…` (Information): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `e222075d…` (Information): 16 file(s)
- `e6429658…` (Health Care and Social Assistance): 2 file(s)
- `e996036e…` (Wholesale Trade): 1 file(s)
- `eb54f575…` (Government): 2 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `ec591973…` (Wholesale Trade): 2 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 1 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `ef8719da…` (Information): 1 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `f9f82549…` (Retail Trade): 2 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 4 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fe0d3941…` (Wholesale Trade): 3 file(s)
- `feb5eefc…` (Finance and Insurance): 1 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `ffed32d8…` (Retail Trade): 1 file(s)
