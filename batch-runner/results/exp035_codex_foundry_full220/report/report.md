# Experiment Report: Codex command-line tool against Foundry — the whole benchmark

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp035_codex_foundry_full220` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.4 |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-09-11 |
| **Duration** | 1439m 40s |
| **Generated At** | 2026-09-12T13:18:34.279065+00:00 |
| 🤗 HF Target | [HyeonSang/exp035_codex_foundry_full220](https://huggingface.co/datasets/HyeonSang/exp035_codex_foundry_full220) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 220 / 220 tasks (100.0%) |
| Priced | 0 / 220 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 70 (no record) |
| Not priced | call_reachability_unknown |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `626cf3f4bab7…`)

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 150 (68.2%) |
| Errors | 70 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 164,123ms |
| Max Latency | 1,265,891ms |
| Total LLM Time | 36107s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 129 (69.7%) |
| Failed (empty outputs preserved) | 56 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 16 | 64.0% | - | 175,184ms |
| Government | 25 | 15 | 60.0% | - | 151,096ms |
| Health Care and Social Assistance | 25 | 17 | 68.0% | - | 180,943ms |
| Information | 25 | 14 | 56.0% | - | 197,811ms |
| Manufacturing | 25 | 19 | 76.0% | - | 178,954ms |
| Professional, Scientific, and Technical  | 25 | 19 | 76.0% | - | 165,223ms |
| Real Estate and Rental and Leasing | 25 | 13 | 52.0% | - | 157,857ms |
| Retail Trade | 20 | 15 | 75.0% | - | 144,761ms |
| Wholesale Trade | 25 | 22 | 88.0% | - | 121,409ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | - | 37792ms |
| 2 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 2 | - | 190959ms |
| 3 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 133145ms |
| 4 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | - | 0 | - | 97334ms |
| 5 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ❌ error | - | 0 | - | 84414ms |
| 6 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | - | 147304ms |
| 7 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 4 | - | 370816ms |
| 8 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | - | 141364ms |
| 9 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 54918ms |
| 10 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 37 | - | 300249ms |
| 11 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | - | 261519ms |
| 12 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 3 | - | 222186ms |
| 13 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 143105ms |
| 14 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 138869ms |
| 15 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | - | 0 | - | 102504ms |
| 16 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | - | 97429ms |
| 17 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ❌ error | - | 0 | - | 187969ms |
| 18 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 82551ms |
| 19 | `11dcc268…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 89105ms |
| 20 | `11e1b169…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 6107ms |
| 21 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | - | 120818ms |
| 22 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | - | 97648ms |
| 23 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | - | 122472ms |
| 24 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | - | 221614ms |
| 25 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 144191ms |
| 26 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ❌ error | - | 0 | - | 84406ms |
| 27 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | - | 172815ms |
| 28 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | - | 108826ms |
| 29 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 262822ms |
| 30 | `1bff4551…` | Government | Recreation Workers | ❌ error | - | 0 | - | 48400ms |
| 31 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | - | 0 | - | 37712ms |
| 32 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | - | 110777ms |
| 33 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | - | 109986ms |
| 34 | `22c0809b…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 47001ms |
| 35 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | - | 234393ms |
| 36 | `2696757c…` | Government | Compliance Officer | ❌ error | - | 0 | - | 57236ms |
| 37 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | - | 221369ms |
| 38 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | - | 120481ms |
| 39 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | - | 60898ms |
| 40 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | - | 170554ms |
| 41 | `2fa8e956…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 44368ms |
| 42 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 3 | - | 228356ms |
| 43 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | - | 201513ms |
| 44 | `36d567ba…` | Government | Compliance Officer | ❌ error | - | 0 | - | 40413ms |
| 45 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 8 | - | 275851ms |
| 46 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ❌ error | - | 0 | - | 179399ms |
| 47 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | - | 119477ms |
| 48 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | - | 158964ms |
| 49 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 2 | - | 217734ms |
| 50 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 3 | - | 198046ms |
| 51 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 257644ms |
| 52 | `401a07f1…` | Information | Editors | ✅ success | - | 2 | - | 540213ms |
| 53 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 2 | - | 81264ms |
| 54 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | - | 470216ms |
| 55 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 4 | - | 318940ms |
| 56 | `4122f866…` | Professional, Scientif | Software Developer | ✅ success | - | 7 | - | 177786ms |
| 57 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | - | 64271ms |
| 58 | `43dc9778…` | Professional, Scientif | Accountants and Au | ❌ error | - | 0 | - | 193104ms |
| 59 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | - | 361059ms |
| 60 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 8 | - | 238543ms |
| 61 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | - | 224831ms |
| 62 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 251842ms |
| 63 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 7 | - | 298280ms |
| 64 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 3 | - | 80383ms |
| 65 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 127263ms |
| 66 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 4 | - | 340314ms |
| 67 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | - | 125264ms |
| 68 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | - | 212055ms |
| 69 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ❌ error | - | 0 | - | 52149ms |
| 70 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ❌ error | - | 0 | - | 177899ms |
| 71 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 5 | - | 219881ms |
| 72 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | - | 198575ms |
| 73 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ❌ error | - | 0 | - | 265350ms |
| 74 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 7 | - | 178932ms |
| 75 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | - | 129956ms |
| 76 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 2 | - | 181297ms |
| 77 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 10 | - | 169493ms |
| 78 | `58ac1cc5…` | Professional, Scientif | Project Management | ❌ error | - | 0 | - | 17798ms |
| 79 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ❌ error | - | 0 | - | 275158ms |
| 80 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ❌ error | - | 0 | - | 65125ms |
| 81 | `5d0feb24…` | Information | News Analysts, Rep | ❌ error | - | 0 | - | 59855ms |
| 82 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ❌ error | - | 0 | - | 306435ms |
| 83 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | - | 0 | - | 410190ms |
| 84 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | - | 212459ms |
| 85 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 25071ms |
| 86 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 193977ms |
| 87 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | - | 514451ms |
| 88 | `61e7b9c6…` | Health Care and Social | Medical and Health | ❌ error | - | 0 | - | 7360ms |
| 89 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | - | 413515ms |
| 90 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | - | 168534ms |
| 91 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 3 | - | 77323ms |
| 92 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 113548ms |
| 93 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 2 | - | 236775ms |
| 94 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | - | 356879ms |
| 95 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | - | 128795ms |
| 96 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 2 | - | 168672ms |
| 97 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | - | 91591ms |
| 98 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | - | 159490ms |
| 99 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 12 | - | 928177ms |
| 100 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | - | 194963ms |
| 101 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 7 | - | 194828ms |
| 102 | `74d6e8b0…` | Health Care and Social | Medical and Health | ❌ error | - | 0 | - | 53013ms |
| 103 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | - | 97831ms |
| 104 | `75401f7c…` | Information | Film and Video Edi | ❌ error | - | 0 | - | 374518ms |
| 105 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 45395ms |
| 106 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | - | 139600ms |
| 107 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | - | 25717ms |
| 108 | `788d2bc6…` | Wholesale Trade | Sales Managers | ❌ error | - | 0 | - | 104162ms |
| 109 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | - | 150084ms |
| 110 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 2 | - | 188974ms |
| 111 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | - | 206017ms |
| 112 | `7de33b48…` | Professional, Scientif | Software Developer | ✅ success | - | 7 | - | 168065ms |
| 113 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 118967ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ❌ error | - | 0 | - | 13849ms |
| 115 | `8079e27d…` | Finance and Insurance | Financial and Inve | ❌ error | - | 0 | - | 90744ms |
| 116 | `81db15ff…` | Health Care and Social | Medical and Health | ❌ error | - | 0 | - | 80504ms |
| 117 | `8314d1b1…` | Professional, Scientif | Lawyers | ❌ error | - | 0 | - | 45871ms |
| 118 | `8384083a…` | Retail Trade | Pharmacists | ❌ error | - | 0 | - | 54107ms |
| 119 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 3 | - | 248443ms |
| 120 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | - | 104330ms |
| 121 | `854f3814…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | - | 47084ms |
| 122 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 3 | - | 235750ms |
| 123 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 134171ms |
| 124 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | - | 148014ms |
| 125 | `8c823e32…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 14716ms |
| 126 | `8c8fc328…` | Information | Film and Video Edi | ❌ error | - | 0 | - | 42945ms |
| 127 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | - | 64584ms |
| 128 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 151968ms |
| 129 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ❌ error | - | 0 | - | 55647ms |
| 130 | `91060ff0…` | Retail Trade | Pharmacists | ❌ error | - | 0 | - | 178181ms |
| 131 | `93b336f3…` | Manufacturing | Buyers and Purchas | ❌ error | - | 0 | - | 25830ms |
| 132 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ❌ error | - | 0 | - | 55808ms |
| 133 | `99ac6944…` | Information | Audio and Video Te | ❌ error | - | 0 | - | 103878ms |
| 134 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | - | 159855ms |
| 135 | `9a8c8e28…` | Information | Editors | ✅ success | - | 7 | - | 194495ms |
| 136 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 2 | - | 163371ms |
| 137 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 8 | - | 244685ms |
| 138 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ❌ error | - | 0 | - | 58412ms |
| 139 | `a0552909…` | Health Care and Social | Medical Secretarie | ✅ success | - | 7 | - | 130380ms |
| 140 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | - | 109262ms |
| 141 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | - | 91424ms |
| 142 | `a10ec48c…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 68311ms |
| 143 | `a1963a68…` | Finance and Insurance | Financial Managers | ❌ error | - | 0 | - | 120268ms |
| 144 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | - | 92175ms |
| 145 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ❌ error | - | 0 | - | 384848ms |
| 146 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | - | 9 | - | 205977ms |
| 147 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | - | 133001ms |
| 148 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 9 | - | 182332ms |
| 149 | `a73fbc98…` | Government | Recreation Workers | ✅ success | - | 6 | - | 272275ms |
| 150 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 5 | - | 260576ms |
| 151 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | - | 0 | - | 634351ms |
| 152 | `a95a5829…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 584211ms |
| 153 | `a97369c7…` | Professional, Scientif | Lawyers | ❌ error | - | 0 | - | 123837ms |
| 154 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | - | 126132ms |
| 155 | `aa071045…` | Real Estate and Rental | Counter and Rental | ❌ error | - | 0 | - | 1265891ms |
| 156 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 4 | - | 239768ms |
| 157 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 119064ms |
| 158 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 3 | - | 77254ms |
| 159 | `afe56d05…` | Information | Editors | ❌ error | - | 0 | - | 22341ms |
| 160 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 2 | - | 185051ms |
| 161 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 3 | - | 66293ms |
| 162 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | - | 218729ms |
| 163 | `b57efde3…` | Wholesale Trade | Sales Representati | ❌ error | - | 0 | - | 168007ms |
| 164 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 70789ms |
| 165 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 3 | - | 101862ms |
| 166 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | - | 78126ms |
| 167 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | - | 232442ms |
| 168 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ❌ error | - | 0 | - | 74416ms |
| 169 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 84736ms |
| 170 | `bbe0a93b…` | Government | Child, Family, and | ❌ error | - | 0 | - | 101493ms |
| 171 | `bd72994f…` | Retail Trade | First-Line Supervi | ❌ error | - | 0 | - | 180465ms |
| 172 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 9 | - | 305085ms |
| 173 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | - | 173263ms |
| 174 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 3 | - | 79990ms |
| 175 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 76170ms |
| 176 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | - | 126192ms |
| 177 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 4 | - | 167989ms |
| 178 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 8 | - | 171125ms |
| 179 | `c657103b…` | Finance and Insurance | Personal Financial | ❌ error | - | 0 | - | 303836ms |
| 180 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 16 | - | 276597ms |
| 181 | `c94452e4…` | Information | Film and Video Edi | ❌ error | - | 0 | - | 153151ms |
| 182 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 7 | - | 186515ms |
| 183 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 3 | - | 196615ms |
| 184 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 3 | - | 101075ms |
| 185 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 3 | - | 110923ms |
| 186 | `cecac8f9…` | Retail Trade | First-Line Supervi | ❌ error | - | 0 | - | 283963ms |
| 187 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | - | 82636ms |
| 188 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | - | 105883ms |
| 189 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | - | 1 | - | 18243ms |
| 190 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 128960ms |
| 191 | `dd724c67…` | Health Care and Social | Registered Nurses | ❌ error | - | 0 | - | 54151ms |
| 192 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | - | 46858ms |
| 193 | `e14e32ba…` | Information | Producers and Dire | ❌ error | - | 0 | - | 46248ms |
| 194 | `e21cd746…` | Finance and Insurance | Financial and Inve | ❌ error | - | 0 | - | 57571ms |
| 195 | `e222075d…` | Information | Film and Video Edi | ❌ error | - | 0 | - | 106601ms |
| 196 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 7 | - | 266640ms |
| 197 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | - | 147922ms |
| 198 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 122514ms |
| 199 | `eb54f575…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 158098ms |
| 200 | `ec2fccc9…` | Information | Editors | ❌ error | - | 0 | - | 102715ms |
| 201 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | - | 69306ms |
| 202 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | - | 61417ms |
| 203 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | - | 2 | - | 298502ms |
| 204 | `ef8719da…` | Information | News Analysts, Rep | ❌ error | - | 0 | - | 38446ms |
| 205 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | - | 218232ms |
| 206 | `f1be6436…` | Health Care and Social | Medical Secretarie | ❌ error | - | 0 | - | 68979ms |
| 207 | `f2986c1f…` | Retail Trade | Pharmacists | ❌ error | - | 0 | - | 34242ms |
| 208 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | - | 89546ms |
| 209 | `f5d428fd…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 84004ms |
| 210 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 108989ms |
| 211 | `f84ea6ac…` | Government | Administrative Ser | ❌ error | - | 0 | - | 69347ms |
| 212 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 5 | - | 192234ms |
| 213 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 13 | - | 117931ms |
| 214 | `fccaa4a1…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 60676ms |
| 215 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | - | 59453ms |
| 216 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 5 | - | 110166ms |
| 217 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 110494ms |
| 218 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | - | 186281ms |
| 219 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 3 | - | 328054ms |
| 220 | `ffed32d8…` | Retail Trade | Pharmacists | ✅ success | - | 3 | - | 81663ms |

## Deliverable Files

- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `01d7e53e…` (Government): 2 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `045aba2e…` (Retail Trade): 4 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 37 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 2 file(s)
- `0ec25916…` (Health Care and Social Assistance): 3 file(s)
- `0ed38524…` (Finance and Insurance): 3 file(s)
- `0fad6023…` (Retail Trade): 2 file(s)
- `1137e2bb…` (Wholesale Trade): 3 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `11dcc268…` (Manufacturing): 1 file(s)
- `15d37511…` (Wholesale Trade): 4 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `17111c03…` (Government): 3 file(s)
- `1752cb53…` (Manufacturing): 3 file(s)
- `19403010…` (Wholesale Trade): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 4 file(s)
- `1b1ade2d…` (Manufacturing): 3 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 2 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `24d1e93f…` (Manufacturing): 2 file(s)
- `27e8912c…` (Government): 6 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 2 file(s)
- `327fbc21…` (Wholesale Trade): 3 file(s)
- `3600de06…` (Finance and Insurance): 3 file(s)
- `38889c3b…` (Information): 8 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `3baa0009…` (Information): 3 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 3 file(s)
- `3f821c2d…` (Wholesale Trade): 2 file(s)
- `401a07f1…` (Information): 2 file(s)
- `403b9234…` (Government): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 2 file(s)
- `40a99a31…` (Manufacturing): 4 file(s)
- `4122f866…` (Professional, Scientific, and Technical Services): 7 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `4520f882…` (Finance and Insurance): 3 file(s)
- `45c6237b…` (Retail Trade): 8 file(s)
- `46b34f78…` (Finance and Insurance): 3 file(s)
- `46fc494e…` (Manufacturing): 7 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 3 file(s)
- `47ef842d…` (Wholesale Trade): 2 file(s)
- `4b894ae3…` (Information): 4 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `4d61a19a…` (Retail Trade): 5 file(s)
- `4de6a529…` (Finance and Insurance): 2 file(s)
- `552b7dd0…` (Manufacturing): 7 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `575f8679…` (Government): 2 file(s)
- `57b2cdf2…` (Retail Trade): 10 file(s)
- `60221cd0…` (Information): 2 file(s)
- `61717508…` (Finance and Insurance): 3 file(s)
- `61b0946a…` (Health Care and Social Assistance): 4 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 2 file(s)
- `6241e678…` (Information): 3 file(s)
- `62f04c2f…` (Wholesale Trade): 3 file(s)
- `6436ff9e…` (Retail Trade): 2 file(s)
- `650adcb1…` (Government): 2 file(s)
- `664a42e5…` (Finance and Insurance): 3 file(s)
- `68d8d901…` (Manufacturing): 2 file(s)
- `6974adea…` (Information): 2 file(s)
- `69a8ef86…` (Wholesale Trade): 3 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 12 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 3 file(s)
- `7151c60a…` (Health Care and Social Assistance): 7 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `76418a2c…` (Manufacturing): 1 file(s)
- `76d10872…` (Government): 2 file(s)
- `772e7524…` (Health Care and Social Assistance): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7bbfcfe9…` (Government): 2 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `7de33b48…` (Professional, Scientific, and Technical Services): 7 file(s)
- `7ed932dd…` (Wholesale Trade): 2 file(s)
- `83d10b06…` (Professional, Scientific, and Technical Services): 3 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `854f3814…` (Professional, Scientific, and Technical Services): 2 file(s)
- `85d95ce5…` (Government): 3 file(s)
- `87da214f…` (Finance and Insurance): 3 file(s)
- `8a7b6fca…` (Manufacturing): 3 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `90edba97…` (Health Care and Social Assistance): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 3 file(s)
- `9a8c8e28…` (Information): 7 file(s)
- `9e39df84…` (Manufacturing): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 8 file(s)
- `a0552909…` (Health Care and Social Assistance): 7 file(s)
- `a079d38f…` (Information): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 2 file(s)
- `a328feea…` (Government): 1 file(s)
- `a46d5cd2…` (Retail Trade): 9 file(s)
- `a4a9195c…` (Manufacturing): 3 file(s)
- `a69be28f…` (Wholesale Trade): 9 file(s)
- `a73fbc98…` (Government): 6 file(s)
- `a74ead3b…` (Government): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 4 file(s)
- `ab81b076…` (Wholesale Trade): 2 file(s)
- `ae0c1093…` (Retail Trade): 3 file(s)
- `b1a79ce1…` (Information): 2 file(s)
- `b3573f20…` (Wholesale Trade): 3 file(s)
- `b39a5aa7…` (Finance and Insurance): 2 file(s)
- `b5d2e6f1…` (Wholesale Trade): 2 file(s)
- `b78fd844…` (Finance and Insurance): 3 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 2 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 2 file(s)
- `be830ca0…` (Manufacturing): 9 file(s)
- `bf68f2ad…` (Manufacturing): 3 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 3 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c44e9b62…` (Government): 4 file(s)
- `c6269101…` (Manufacturing): 8 file(s)
- `c7d83f01…` (Finance and Insurance): 16 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 7 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 3 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 3 file(s)
- `d025a41c…` (Finance and Insurance): 2 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `d4525420…` (Retail Trade): 1 file(s)
- `d7cfae6f…` (Wholesale Trade): 2 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
- `e4f664ea…` (Information): 7 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `e996036e…` (Wholesale Trade): 2 file(s)
- `ec591973…` (Wholesale Trade): 2 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 3 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 2 file(s)
- `efca245f…` (Manufacturing): 3 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 2 file(s)
- `f9a1c16c…` (Information): 5 file(s)
- `f9f82549…` (Retail Trade): 13 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 3 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 5 file(s)
- `fe0d3941…` (Wholesale Trade): 2 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `ff85ee58…` (Information): 3 file(s)
- `ffed32d8…` (Retail Trade): 3 file(s)
