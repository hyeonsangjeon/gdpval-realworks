# Experiment Report: GPT-5.4 Reasoning HIGH — Full Benchmark (Ablation 1/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp013_GPT54_reasoning_high` |
| **Condition** | GPT-5.4 reasoning=high + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4 |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-24 |
| **Duration** | 44m 18s |
| **Generated At** | 2026-03-24T12:07:59.925534+00:00 |
| 🤗 HF Dataset | [exp013_GPT54_reasoning_high](https://huggingface.co/datasets/HyeonSang/exp013_GPT54_reasoning_high) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp013_GPT54_reasoning_high/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 28 (12.7%) |
| Errors | 192 |
| Retried Tasks | 192 |
| Avg QA Score | 5.81/10 |
| Min QA Score | 3/10 |
| Max QA Score | 9/10 |
| Avg Latency | 9,134ms |
| Max Latency | 173,197ms |
| Total LLM Time | 2009s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 25 (13.5%) |
| Failed → dummy created | 160 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 2 | 192 | 0 | 192 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 0 | 0.0% | 0.0/10 | 120ms |
| Government | 25 | 12 | 48.0% | 6.67/10 | 24,539ms |
| Health Care and Social Assistance | 25 | 0 | 0.0% | 0.0/10 | 143ms |
| Information | 25 | 5 | 20.0% | 4.6/10 | 26,253ms |
| Manufacturing | 25 | 5 | 20.0% | 5.4/10 | 11,774ms |
| Professional, Scientific, and Technical  | 25 | 6 | 24.0% | 5.4/10 | 17,145ms |
| Real Estate and Rental and Leasing | 25 | 0 | 0.0% | 0.0/10 | 172ms |
| Retail Trade | 20 | 0 | 0.0% | 0.0/10 | 116ms |
| Wholesale Trade | 25 | 0 | 0.0% | 0.0/10 | 140ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 4/10 | 42569ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 5/10 | 58022ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 4/10 | 61136ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 1043ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 511ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 2 | 4/10 | 41753ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 8/10 | 27218ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 6 | 7/10 | 78783ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | 7/10 | 52562ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ❌ error | Yes | 0 | - | 309ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 4/10 | 143694ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 2 | 3/10 | 173197ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 10 | 7/10 | 156417ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 3 | 5/10 | 101572ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 3 | 4/10 | 77716ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 7/10 | 57323ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 43182ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | 7/10 | 65391ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 3/10 | 63606ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 4/10 | 61637ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 2 | 9/10 | 92563ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 4 | 4/10 | 77717ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ❌ error | Yes | 0 | - | 74ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ❌ error | Yes | 0 | - | 114ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 3 | 6/10 | 77361ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 28315ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 27272ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 4/10 | 15730ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 24139ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 3 | 4/10 | 68070ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 7/10 | 103410ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 7/10 | 75460ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | - | 84187ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ❌ error | Yes | 0 | - | 85ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ❌ error | Yes | 0 | - | 165ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 118ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 74ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 74ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 74ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ❌ error | Yes | 0 | - | 74ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 74ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 96ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 91ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 154ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 225ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 75ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 140ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 86ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 107ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ❌ error | Yes | 0 | - | 85ms |
| 51 | `401a07f1…` | Information | Editors | ❌ error | Yes | 0 | - | 74ms |
| 52 | `afe56d05…` | Information | Editors | ❌ error | Yes | 0 | - | 74ms |
| 53 | `9a8c8e28…` | Information | Editors | ❌ error | Yes | 0 | - | 74ms |
| 54 | `3a4c347c…` | Information | Editors | ❌ error | Yes | 0 | - | 107ms |
| 55 | `ec2fccc9…` | Information | Editors | ❌ error | Yes | 0 | - | 78ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 138ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 111ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 100ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 74ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 75ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 74ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 78ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 74ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 74ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ❌ error | Yes | 0 | - | 75ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 76ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 128ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 94ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 160ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 92ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 76ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 75ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 86ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 82ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 185ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 117ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 79ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 399ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 108ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 81ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ❌ error | Yes | 0 | - | 74ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ❌ error | Yes | 0 | - | 74ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ❌ error | Yes | 0 | - | 74ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ❌ error | Yes | 0 | - | 74ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ❌ error | Yes | 0 | - | 81ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 90ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 154ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 84ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 93ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 136ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 74ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 79ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 98ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 98ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 102ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 74ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 75ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 74ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 74ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 125ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ❌ error | Yes | 0 | - | 76ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ❌ error | Yes | 0 | - | 75ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ❌ error | Yes | 0 | - | 79ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ❌ error | Yes | 0 | - | 214ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ❌ error | Yes | 0 | - | 87ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 75ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 75ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 75ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 74ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ❌ error | Yes | 0 | - | 74ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 74ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 154ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 454ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 220ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ❌ error | Yes | 0 | - | 569ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 74ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 77ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 84ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 88ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ❌ error | Yes | 0 | - | 81ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 74ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 76ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 96ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 182ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 1002ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 175ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 74ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 74ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 95ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ❌ error | Yes | 0 | - | 114ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ❌ error | Yes | 0 | - | 74ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ❌ error | Yes | 0 | - | 74ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ❌ error | Yes | 0 | - | 74ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ❌ error | Yes | 0 | - | 76ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ❌ error | Yes | 0 | - | 83ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 180ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 99ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 563ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 88ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 166ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 75ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 227ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 75ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 75ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ❌ error | Yes | 0 | - | 78ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 74ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 74ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 81ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 594ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 124ms |
| 151 | `6241e678…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 74ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 80ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 346ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 1568ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 230ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 74ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 82ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 114ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 539ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 386ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 74ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 1143ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 165ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 87ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ❌ error | Yes | 0 | - | 87ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ❌ error | Yes | 0 | - | 74ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ❌ error | Yes | 0 | - | 74ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ❌ error | Yes | 0 | - | 79ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ❌ error | Yes | 0 | - | 107ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ❌ error | Yes | 0 | - | 85ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 78ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 108ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 75ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 82ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 924ms |
| 176 | `403b9234…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 74ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 74ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 75ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 94ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 794ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 74ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 74ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 126ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 87ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 204ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 78ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 81ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 74ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 75ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 197ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 75ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 304ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 82ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 81ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 80ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 74ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 152ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 215ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 139ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 90ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 74ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 78ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 158ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 78ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 223ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 74ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 74ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 107ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 277ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 515ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 74ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 74ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 267ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 120ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 110ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 74ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 75ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 74ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 150ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 91ms |

## QA Issues

### ❌ `83d10b06…` — score 4/10
- Sheet names do not match required titles and tab order.
- Selected sample tab is not copied from original Population sheet structure.
- Variance appears as ratio, not quarter-on-quarter variance percentage in column J.
  > 💡 Rename tabs exactly, preserve original columns, and calculate variance per the source sheet requirements.

### ✅ `7b08cd4d…` — score 5/10
- Expense breakdown by source columns is not evidenced in preview.
- Combined total column for Tour Manager and production company is unclear.
- Text claims reference inspection and validation without supporting detail.
  > 💡 Ensure the workbook visibly includes source-separated expense columns and combined totals.

### ❌ `7d7fc9a7…` — score 4/10
- Prepaid Insurance does not reconcile to GL balances through April.
- Summary ending insurance balance conflicts with requested GL amount.
- Output mentions reconciliation adjustments, indicating unresolved variances.
  > 💡 Reconcile insurance schedules exactly to monthly GL balances and update the summary totals.

### ❌ `f84ea6ac…` — score 4/10
- DOCX preview lacks the required comparison table content.
- No evidence all five articles are publicly available and post-2020.
- Output adds an unrequested Excel file instead of focusing on Word deliverable.
  > 💡 Include the full one-page Word table with verified open-access post-2020 academic sources.

### ✅ `a328feea…` — score 8/10
- Text response describes the file instead of delivering the requested procedure content.
- Procedure preview appears truncated with an incomplete implementation note.
- No explicit one-page confirmation; document may exceed the requested length.
  > 💡 Provide the full procedure text in the response and ensure the document is complete and one page.

### ✅ `27e8912c…` — score 7/10
- Checklist source citation appears incomplete or not linked clearly.
- Public-domain image sourcing is not explicitly documented.
- No actual content preview confirms required employee fields in checklist.
  > 💡 Add explicit source URLs, image attributions, and verify all required fields are visible in both files.

### ✅ `17111c03…` — score 7/10
- Memo date conflicts with schedule start year and may confuse staff.
- Output claims attached sample reference, but source PDF conversion cannot be verified.
- Extra DOCX file was produced though not requested.
  > 💡 Align memo timing with the schedule and ensure all deliverables clearly match the reference.

### ❌ `99ac6944…` — score 4/10
- Proposal includes only one SM58 despite requiring two vocal microphones.
- AS-950 provides one stereo mix, not independent mixes for both singers.
- PDF requirement was met, but primary proposal was also delivered as DOCX.
  > 💡 Use a dual-mix IEM system and include two microphones with verified itemized costs.

### ❌ `f9a1c16c…` — score 3/10
- Text only promises deliverables without verifying required stage plot details.
- PDF is extremely small, suggesting missing or incomplete visual content.
- ODT content is unverified, so required labels and I/O lists are not confirmed.
  > 💡 Open both files and confirm all required visual elements, labels, and numbered I/O lists are present.

### ✅ `38889c3b…` — score 7/10
- Required ZIP should include only master and specified stems.
- Bit depth says 24-bit float, which is not a standard WAV format.
- No evidence files are tightly synchronized to the provided drum track.
  > 💡 Remove extra deliverables and verify standard export specs and drum-locked alignment.

### ✅ `ff85ee58…` — score 5/10
- Final loudness is -18.21 LUFS, outside the required -16 ±1 LUFS.
- Text promises verification details, but sync accuracy cannot be confirmed from outputs.
- Extra PNG and DOCX were produced though not requested.
  > 💡 Remaster to compliant loudness and provide verifiable sync/timing evidence in the required audio deliverable.

### ❌ `4b894ae3…` — score 4/10
- Report edits don't match provided reference timecodes.
- Extra PDF file was produced beyond requested deliverables.
- Text claims detected fixes from audio analysis, not supplied references.
  > 💡 Use only the provided edit spots and deliver just the required final WAV.

### ✅ `1b1ade2d…` — score 7/10
- Text response describes deliverables instead of summarizing the actual workflow content.
- Original task requested a first-level workflow draft; platform requirements may exceed scope.
- No evidence the PDF content was verified against the DOCX preview.
  > 💡 Provide a concise workflow summary in the response and confirm both files contain identical finalized content.

### ✅ `93b336f3…` — score 6/10
- Partnership ownership split is invented and unsupported by the task.
- Per-pack savings calculation appears inconsistent with provided assembly and overhead inputs.
- Response text says CPO, but original task target appears truncated.
  > 💡 Remove unsupported assumptions and verify all INR cost calculations against the given inputs.

### ✅ `15ddd28d…` — score 7/10
- Text response promises files instead of summarizing delivered strategy content.
- Original task asked for Word or PDF, but both were produced unnecessarily.
- Preview does not confirm all negotiation roadmap elements were fully covered.
  > 💡 Summarize key recommendations in the response and explicitly map document sections to task requirements.

### ❌ `24d1e93f…` — score 3/10
- NPV values and rankings are blank on the summary sheet.
- Vendor sheets contain missing input cells for volumes and quotations.
- No clear supplier recommendation is provided despite the task requirement.
  > 💡 Populate all numeric inputs, calculate NPVs, and finalize a recommendation with assumptions.

### ❌ `05389f78…` — score 4/10
- Output preview lacks the termination email content for verification.
- Report admits missing numeric quote values, weakening required INR calculations.
- Generated text promises deliverables instead of presenting completed content.
  > 💡 Verify both DOCX contents and include complete INR-based comparison using the source quotes.

### ❌ `a74ead3b…` — score 4/10
- Manual content was not followed closely as required.
- No evidence sessions match assigned Session 13 and 14 topics.
- Text response admits inability to access required source materials.
  > 💡 Rebuild both decks using the actual manual content and verify session-specific coverage.

### ✅ `76d10872…` — score 6/10
- Text response promises creation instead of confirming completed report details.
- Output adds unrequested XLSX and DOCX files without justification.
- Preview shows truncated content, limiting verification of completeness against guide.
  > 💡 State completed deliverables clearly and ensure the PDF fully matches the Case Creation Guide.

### ✅ `36d567ba…` — score 9/10
- Text response describes deliverable instead of summarizing completed content.
- File preview is truncated, limiting verification of topics 7-11 details.
  > 💡 Include a brief completion summary and ensure all cited sections are fully visible for review.

### ❌ `2696757c…` — score 4/10
- Output text promised a PDF instead of providing the requested content directly.
- Test questions appear generic and may not track the cited paragraphs precisely.
- Header uses a hyphen instead of the exact required en dash nomenclature.
  > 💡 Provide the exact requested template content in the PDF with precise citations and exact header formatting.

### ❌ `4c18ebae…` — score 4/10
- Text promises a SAR narrative but provides no actual investigative narrative.
- Workbook dates conflict with account closure timeline and stated investigation period.
- Unexpected PNG file appears, while required content completeness is unverified.
  > 💡 Provide the full SAR narrative and reconcile all transaction data with the case timeline.

### ✅ `cebf301e…` — score 7/10
- Text response only describes the document, not the actual solution.
- Preview is truncated, so full requirement coverage cannot be verified.
- Requirement list appears cut off, risking incomplete coverage.
  > 💡 Include a concise summary of key decisions and verify every stated requirement explicitly.

### ✅ `c2e8f271…` — score 7/10
- Text response describes intent, not delivered document contents.
- No evidence the document stays within the six-page limit.
- Staged rollout is mentioned but may be insufficiently detailed.
  > 💡 Summarize actual document coverage and verify page count explicitly in the response.

### ❌ `2ea2e5b5…` — score None/10
- QA API error: Error code: 403 - {'error': {'code': 'AuthenticationTypeDisabled', 'message': 'Key based authentication is disabled for this resource.'}}

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 2 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 6 file(s)
- `17111c03…` (Government): 3 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 2 file(s)
- `38889c3b…` (Information): 10 file(s)
- `ff85ee58…` (Information): 3 file(s)
- `4b894ae3…` (Information): 3 file(s)
- `1b1ade2d…` (Manufacturing): 2 file(s)
- `93b336f3…` (Manufacturing): 2 file(s)
- `15ddd28d…` (Manufacturing): 3 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 2 file(s)
- `a74ead3b…` (Government): 4 file(s)
- `76d10872…` (Government): 3 file(s)
- `36d567ba…` (Government): 1 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 3 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 1 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
