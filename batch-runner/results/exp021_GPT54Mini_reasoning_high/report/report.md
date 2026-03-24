# Experiment Report: GPT-5.4-Mini Reasoning HIGH — Full Benchmark (Ablation 1/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp021_GPT54Mini_reasoning_high` |
| **Condition** | GPT-5.4-Mini reasoning=high + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4-mini |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-24 |
| **Duration** | 79m 6s |
| **Generated At** | 2026-03-24T12:06:24.256730+00:00 |
| 🤗 HF Dataset | [exp021_GPT54Mini_reasoning_high](https://huggingface.co/datasets/HyeonSang/exp021_GPT54Mini_reasoning_high) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp021_GPT54Mini_reasoning_high/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 188 (85.5%) |
| Errors | 32 |
| Retried Tasks | 53 |
| Avg QA Score | 6.77/10 |
| Min QA Score | 2/10 |
| Max QA Score | 10/10 |
| Avg Latency | 13,800ms |
| Max Latency | 38,812ms |
| Total LLM Time | 3036s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 158 (85.4%) |
| Failed → dummy created | 27 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 21 | 21 | 0 |
| 2 | 32 | 0 | 32 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 21 | 84.0% | 6.43/10 | 16,953ms |
| Government | 25 | 25 | 100.0% | 7.16/10 | 15,196ms |
| Health Care and Social Assistance | 25 | 22 | 88.0% | 6.82/10 | 13,799ms |
| Information | 25 | 22 | 88.0% | 6.55/10 | 14,637ms |
| Manufacturing | 25 | 21 | 84.0% | 6.19/10 | 13,638ms |
| Professional, Scientific, and Technical  | 25 | 18 | 72.0% | 6.83/10 | 12,293ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 6.96/10 | 15,710ms |
| Retail Trade | 20 | 17 | 85.0% | 7.71/10 | 11,806ms |
| Wholesale Trade | 25 | 18 | 72.0% | 6.33/10 | 9,773ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 9/10 | 11141ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 8/10 | 13878ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 6/10 | 17779ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 3 | 6/10 | 15188ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 444ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 1 | 3/10 | 10068ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 1 | 9/10 | 5893ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 5 | 7/10 | 17707ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 2 | 9/10 | 12535ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 3 | 8/10 | 22219ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 4 | 8/10 | 25072ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 3 | 8/10 | 18333ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | Yes | 6 | 9/10 | 37361ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | - | 1 | 8/10 | 14615ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | - | 3 | 6/10 | 20643ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 12368ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 14356ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 10676ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 11855ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 15587ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 18511ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 2 | 8/10 | 15479ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | 4/10 | 15646ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ✅ success | - | 3 | 4/10 | 29994ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | Yes | 1 | 3/10 | 26033ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 2 | 6/10 | 11798ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 10/10 | 8501ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 6326ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 7885ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 2 | 6/10 | 21825ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 2 | 8/10 | 13833ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 8/10 | 12723ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 5 | 6/10 | 14419ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | - | 1 | 9/10 | 22701ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 4 | 8/10 | 12745ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 3/10 | 14026ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 4 | 8/10 | 28664ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 9 | 6/10 | 18813ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 19739ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 7/10 | 21642ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 17496ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 18672ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 4/10 | 17928ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 9/10 | 11823ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 22553ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 4/10 | 9493ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 6/10 | 23906ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | 6/10 | 15328ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 2 | 4/10 | 16951ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 4/10 | 10887ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 4/10 | 12000ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 6/10 | 18731ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 3 | 6/10 | 27183ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | 6/10 | 17994ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 6/10 | 20497ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 9/10 | 9716ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 4/10 | 15116ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 3 | 4/10 | 10699ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 71ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 71ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | 7/10 | 18833ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 2 | 8/10 | 17705ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 9/10 | 28426ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 6 | 8/10 | 32859ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 1 | 6/10 | 18668ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 3 | 8/10 | 22896ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ❌ error | Yes | 0 | - | 119ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 8/10 | 24463ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 4/10 | 18123ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 8/10 | 23239ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 4/10 | 11246ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 10746ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 82ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 4/10 | 9961ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 4/10 | 12349ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ❌ error | Yes | 0 | - | 107ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 8/10 | 12612ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 2 | 4/10 | 22433ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 4/10 | 18108ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 4/10 | 21773ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 6/10 | 16166ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | Yes | 2 | 8/10 | 12544ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | - | 2 | 7/10 | 11968ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 12664ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 18800ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 12498ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 6/10 | 14196ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 140ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 1 | 6/10 | 8954ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ❌ error | Yes | 0 | - | 126ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 4 | 8/10 | 13339ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 10063ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ❌ error | Yes | 0 | - | 94ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 6/10 | 20112ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 5 | 8/10 | 17799ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 10535ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | Yes | 1 | 9/10 | 11413ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | Yes | 2 | 9/10 | 15793ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ✅ success | - | 3 | 9/10 | 19948ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 9906ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 9/10 | 16193ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 6/10 | 19158ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 3 | 5/10 | 14433ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 4/10 | 25938ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 4/10 | 27296ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 23612ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 5/10 | 24841ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 12610ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | Yes | 1 | 8/10 | 24022ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 22902ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 14 | 6/10 | 19162ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | - | 9 | 6/10 | 21842ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 4/10 | 23736ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 4 | 6/10 | 15989ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 8/10 | 18954ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 7/10 | 17621ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 9/10 | 8832ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 13917ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 4/10 | 9130ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 4 | 8/10 | 18156ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 6/10 | 18549ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 9/10 | 9111ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 93ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 11 | 6/10 | 16311ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 9/10 | 13163ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 2 | 9/10 | 7219ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 8877ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | 9/10 | 11128ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 2 | 4/10 | 10334ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 14068ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 8/10 | 20108ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 20223ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 7846ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 10933ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 3 | 8/10 | 14445ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 4/10 | 18251ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 14910ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 10548ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 7/10 | 11484ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ❌ error | Yes | 0 | - | 153ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 19050ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 2 | 8/10 | 24572ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 4/10 | 16138ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 8/10 | 27461ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 7/10 | 30318ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 9/10 | 8558ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | - | 3 | 8/10 | 15618ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 4/10 | 11384ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 6/10 | 14145ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ❌ error | Yes | 0 | - | 117ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 18876ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 16465ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ❌ error | Yes | 0 | - | 337ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 16794ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 13716ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 71ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 79ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 6/10 | 16455ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 5 | 6/10 | 16936ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ❌ error | Yes | 0 | - | 162ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 9/10 | 14278ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 13758ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 3/10 | 9227ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 8/10 | 12804ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 6/10 | 13278ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 8/10 | 23568ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 9746ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 6042ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 3/10 | 18325ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 4 | 6/10 | 13759ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 7/10 | 17755ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 18 | 6/10 | 17018ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 6 | 8/10 | 18588ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ❌ error | Yes | 0 | - | 79ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 9/10 | 13165ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 9/10 | 12908ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 5 | 6/10 | 16613ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 9/10 | 11489ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 4 | 6/10 | 20425ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | - | 3 | 8/10 | 15900ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 11991ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 11869ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 6/10 | 38812ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ❌ error | Yes | 0 | - | 80ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 2/10 | 8746ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 2 | 8/10 | 25641ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 6/10 | 13253ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 9/10 | 11512ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 6/10 | 6567ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 320ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 6/10 | 10202ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 11 | 7/10 | 27458ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ❌ error | Yes | 0 | - | 78ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 8/10 | 13324ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 8/10 | 14191ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | 8/10 | 16529ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 144ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 13031ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 98ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 85ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 2/10 | 16281ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 8/10 | 12459ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 9180ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 74ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 11466ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 11839ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 71ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 100ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | 8/10 | 11880ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ❌ error | Yes | 0 | - | 503ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 9/10 | 11228ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 71ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | 6/10 | 15475ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 114ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 2/10 | 10600ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 1 | 4/10 | 13939ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 71ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 71ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 71ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 8/10 | 16630ms |

## QA Issues

### ✅ `7d7fc9a7…` — score 6/10
- Summary ending balances do not match the provided GL balances.
- Prepaid Insurance details appear incomplete in the preview.
- Text response is generic and does not confirm reconciliation accuracy.
  > 💡 Revise the workbook to fully reconcile all balances and verify complete insurance schedules.

### ✅ `43dc9778…` — score 6/10
- Output includes a workpaper summary, not just the required tax return package.
- PDF content appears summary-based, not a completed Form 1040 with actual line items.
- No evidence all required e-file forms were correctly determined from the source documents.
  > 💡 Provide a completed 1040 package with all required schedules and remove unsupported assumptions.

### ❌ `f84ea6ac…` — score 3/10
- Document lacks the required research summary table.
- No evidence of five reviewed articles or required study details.
- File content appears to be only a title and subtitle.
  > 💡 Provide a one-page table with five studies, findings, and government implications.

### ✅ `27e8912c…` — score 7/10
- Checklist is only 2 pages, not the requested maximum five pages.
- Some checklist text appears garbled or duplicated in the preview.
- Word document preview is sparse and may lack the required tracking table details.
  > 💡 Verify formatting, expand the Word table content, and ensure the checklist is clean and complete.

### ✅ `99ac6944…` — score 8/10
- PDF is only three pages, so the last-page image requirement may be tight.
- The setup uses one transmitter for two packs, which may limit truly independent mixes.
- No obvious placeholder content, but the budget margin is very small.
  > 💡 Verify the PDF page layout and confirm the transmitter supports the required mix routing.

### ✅ `4b894ae3…` — score 6/10
- Report file names are inconsistent between DOCX and PDF.
- Text response promises a report not required by the task.
- No direct evidence the WAV is correctly mixed at reference bass level.
  > 💡 Provide only the required WAV and ensure all deliverable names match exactly.

### ✅ `1b1ade2d…` — score 8/10
- Output is a DOCX, but the preview is truncated.
- No obvious missing workflow elements in the visible content.
- Text response is professional but slightly generic.
  > 💡 Verify the full document includes all approval and change-control details.

### ✅ `93b336f3…` — score 6/10
- Cost savings appear overstated and may not reflect the stated assembly-only assumptions.
- The document preview shows truncated content, so completeness cannot be fully verified.
- The response repeats itself and does not directly summarize the deliverable professionally.
  > 💡 Revise the business case calculations and ensure the document is complete, concise, and fully proofread.

### ✅ `15ddd28d…` — score 6/10
- Document appears truncated in preview.
- Original task asks for 2–3 pages; length cannot be verified.
- No clear evidence of complete negotiation roadmap and timeline.
  > 💡 Verify the full document covers all required sections and fits 2–3 pages.

### ✅ `05389f78…` — score 6/10
- Report content is truncated, so completeness cannot be verified.
- No evidence the quotation file was used for detailed INR calculations.
- Text response mentions a Python script not listed among produced files.
  > 💡 Provide the full report content with explicit INR comparisons and confirm all referenced deliverables exist.

### ❌ `bbe0a93b…` — score 4/10
- Assessment files are DOCX, not PDF.
- English and Spanish forms may lack required table details.
- Resource guide preview shows formatting and content corruption.
  > 💡 Convert both assessments to PDFs and verify all tables and resource entries are complete and clean.

### ❌ `85d95ce5…` — score 4/10
- Only 7 pages; task required 8-15 pages.
- Two PDF files were produced; filename should be a single J.S. PDF.
- Content may still contain template placeholders and incomplete fields.
  > 💡 Revise the report to meet page length, remove duplicates, and ensure all required fields are completed correctly.

### ❌ `76d10872…` — score 3/10
- Key fields are blank in the report, including case number, dates, and support amounts.
- Participant details appear incomplete and inconsistent, with missing child and CP information.
- The PDF exists, but content does not fully satisfy the required case creation report.
  > 💡 Regenerate the PDF with all required fields completed and verified against the source records.

### ✅ `36d567ba…` — score 6/10
- PDF preview is truncated, so full compliance cannot be verified.
- Text response mentions a PDF, which was not requested.
- Required 2 CFR references for topics 6-10 may be incomplete.
  > 💡 Provide the complete 1-2 page tool with all required topic references and no extra deliverables.

### ✅ `4c18ebae…` — score 6/10
- Text response is generic and omits case-specific findings.
- No evidence the SAR content meets FinCEN narrative requirements.
- File content preview is truncated, so completeness cannot be confirmed.
  > 💡 Add a concise, case-specific SAR narrative and verify all required file contents.

### ✅ `2ea2e5b5…` — score 6/10
- Missing evidence that all 12 categories were fully classified.
- Original task required Excel-based analysis, but source workbook use is unverified.
- Text response is generic and omits key findings or validation details.
  > 💡 Verify the workbook-driven classifications and summarize the actual results in the presentation.

### ✅ `a45bc83b…` — score 8/10
- POC preview is truncated, so completeness cannot be fully verified.
- No direct evidence the diagram uses official GCP icons.
- No explicit confirmation of mirrored bulleted style in the summary.
  > 💡 Verify the full POC content and diagram icon usage against the source requirements.

### ❌ `a10ec48c…` — score 3/10
- Document appears incomplete with only three paragraphs and no restaurant tables.
- Required restaurant data, links, hours, directions, and categories are missing.
- No evidence of sourcing from Downtown Sarasota or Google Maps is included.
  > 💡 Populate the Word file with sourced restaurant tables and complete all required fields.

### ✅ `f5d428fd…` — score 6/10
- Images are locally created, not verified royalty-free sources.
- The itinerary appears truncated in the preview.
- No evidence of researched source citations is shown.
  > 💡 Provide full destination text and verify each image from legitimate royalty-free platforms.

### ✅ `2fa8e956…` — score 6/10
- Missing visible winery details in the preview.
- No evidence of required Google Maps distances and drive times.
- Cannot verify four-page limit or formatting from preview.
  > 💡 Verify the document includes all winery fields, exact travel data, and required formatting.

### ✅ `0e4fe8cd…` — score 7/10
- Preview is truncated, so full requirement coverage cannot be verified.
- No evidence of all four day tabs' complete content and links.
- Text response promises a summary sheet not explicitly requested.
  > 💡 Verify all tabs, links, and logistics are fully populated before delivery.

### ❌ `aa071045…` — score 4/10
- Summary total revenue appears incorrect versus source data.
- Service form content cannot be verified from preview.
- Operational insights may not match the required breakdowns exactly.
  > 💡 Verify calculations and ensure both files fully reflect the provided task details.

### ❌ `f3351922…` — score 4/10
- Text response is not the requested email draft.
- Preview shows incomplete content and truncation.
- Benefits section may omit required detail and final polish.
  > 💡 Provide a complete professional email with the exact subject and full TSP details.

### ✅ `61717508…` — score 6/10
- Role-play PDF has only 4 pages, not the requested three-account packet plus structure.
- Quick guide content preview is truncated, so completeness cannot be verified.
- Text response mentions internal reporting steps not confirmed in the provided task.
  > 💡 Ensure the quick guide fully covers required rules and the role-play PDF clearly presents all three scenarios.

### ✅ `0ed38524…` — score 6/10
- Summary PDF is two pages, not one page.
- District 1 text appears corrupted and unreadable.
- Talking points preview is truncated, so completeness is unclear.
  > 💡 Regenerate a clean one-page summary and verify the full talking points PDF.

### ❌ `87da214f…` — score 4/10
- No evidence the slides include required financial figures or percentages.
- Text response is generic and does not summarize actual findings.
- Policy remediation and next steps are not specifically detailed.
  > 💡 Revise the deck to include concrete claim results, financial impact, and specific remediation actions.

### ❌ `d025a41c…` — score 4/10
- File content appears truncated and incomplete.
- Case Three is missing from the preview.
- Some required explanations may be absent.
  > 💡 Ensure all three cases are fully included and verify the document content end-to-end.

### ❌ `401a07f1…` — score 4/10
- The file content is truncated and may be incomplete.
- Reference links are not visible in the preview.
- The editorial may not fully meet the 500-word requirement.
  > 💡 Provide the full document with visible links and verify word count.

### ✅ `afe56d05…` — score 6/10
- Text response is only a status note, not the requested deliverable.
- Word count and section completeness cannot be verified from the preview.
- Preview is truncated, so missing content or formatting issues may exist.
  > 💡 Provide the full DOCX content and verify all required sections and length.

### ✅ `9a8c8e28…` — score 6/10
- Guide preview is truncated, so completeness cannot be fully verified.
- No visible evidence of the required bibliography links or quiz answer key details.
- The final sentence in the task appears cut off, suggesting possible missing content.
  > 💡 Verify all three PDFs include every required section and that the guide is fully complete.

### ✅ `3a4c347c…` — score 6/10
- PDF is only 3 pages, under the six-page limit but may be too compressed.
- Preview truncation suggests some required story and schedule details may be missing.
- Text response is repetitive and not a complete professional summary.
  > 💡 Verify the full document includes all required sections and concise, non-redundant detail.

### ✅ `ec2fccc9…` — score 6/10
- Word count and full article quality cannot be verified from the preview.
- Reference artist links and secondary keywords are not visible in the provided content.
- The required pull quote caption and final 'what's next' section are not confirmed.
  > 💡 Verify the document includes all required sections, links, and SEO keywords before delivery.

### ❌ `e222075d…` — score 4/10
- No actual 30-second MP4 was produced.
- Deliverables are planning documents, not the requested edit.
- PDF content appears truncated and incomplete.
  > 💡 Produce the final 30-second H.264 video with all required media and timing.

### ❌ `c94452e4…` — score 4/10
- No actual MP4 video file was produced.
- Required stock footage and music sources were not provided.
- Deliverables are planning documents, not the finished 15-second spot.
  > 💡 Produce the exact 15-second H.264 MP4 with sourced footage, music, and burned-in supers.

### ✅ `8079e27d…` — score 7/10
- Only 394 companies are included, not all 500 S&P 500 constituents.
- The workbook appears to use offline or synthetic data, not clearly public web sources.
- No explicit evidence of all sub-sectors and index-weight calculations being fully complete.
  > 💡 Add all 500 constituents with sourced public data and verify complete sector/sub-sector coverage.

### ✅ `c7d83f01…` — score 8/10
- No actual Jupyter notebook file was produced.
- Monte Carlo accuracy for American exercise may be insufficiently validated.
- Summary document appears truncated in the preview.
  > 💡 Provide the notebook file and verify all deliverables are complete and fully rendered.

### ✅ `46b34f78…` — score 6/10
- Report appears to target 2025 but is dated 2026-03-24.
- Preview is truncated, so completeness cannot be fully verified.
- No evidence of the required source-data appendix or issuer specifics in preview.
  > 💡 Verify the memo date, include explicit issuer analyses and source appendix, and ensure the full report meets all requirements.

### ✅ `a1963a68…` — score 8/10
- PDF has 8 pages, slightly above the requested 5-6 core slides.
- Text response is generic and does not summarize the strategy content.
- No obvious appendix/reference detail is visible in the preview.
  > 💡 Trim the deck to 5-6 core slides and add a concise executive summary in the response.

### ❌ `b78fd844…` — score 4/10
- Only a 2-page report was produced, not within the 15-page requirement context.
- The response lacks the required detailed financial analysis and capital allocation specifics.
- Risk mitigation content appears incomplete or truncated in the preview.
  > 💡 Revise the report to include fuller NPV/IRR analysis, complete risks, and explicit allocation details.

### ✅ `4520f882…` — score 8/10
- Workbook appears to use placeholder base wage value 1.
- No clear evidence of full CBA rate logic validation.
- Summary document may be unnecessary for the core deliverable.
  > 💡 Replace placeholders with actual contract rates and verify all CBA rules are implemented.

### ❌ `ec591973…` — score 4/10
- Text response is duplicated and not a complete executive deliverable.
- PPTX content cannot be verified from the preview, so required slide quality is uncertain.
- No evidence the slide includes all required channel-specific strategy elements.
  > 💡 Provide a single polished slide with explicit channel tactics and executive-ready messaging.

### ❌ `e996036e…` — score 4/10
- Workbook uses 255,000 shipments, not the required 225,000.
- Only one scenario appears; three distinct term structures are not shown.
- Summary text is missing from the workbook preview.
  > 💡 Revise the workbook to use the correct shipment total, include all three scenarios, and add the executive summary.

### ❌ `327fbc21…` — score 4/10
- Summary text says it will create a workbook, not the actual plan details.
- No evidence of weekly percentage weighting or rounding rules being validated.
- Text response is generic and omits the required May sales summary figures.
  > 💡 Provide a concise summary confirming the completed workbook and key plan metrics.

### ❌ `0353ee0c…` — score 4/10
- PDF preview is truncated and may omit required presumptive conditions.
- No evidence the document exhaustively compiles all 19 source links.
- Text response promises a DOCX support file, but task requested only the PDF deliverable.
  > 💡 Verify completeness against all source links and remove unsupported deliverable claims.

### ❌ `40a8c4b1…` — score 4/10
- No evidence the workbook was actually populated or validated.
- In-Service Study Session placement is not confirmed.
- Text response mentions current directory, not the delivered file.
  > 💡 Verify the schedule against all constraints and confirm the final workbook contents.

### ❌ `4d1a8410…` — score 4/10
- Personal itineraries are incomplete and only contain placeholder headings.
- Master schedule lacks the required detailed table with rooms, applicants, and timings.
- The response mentions extra images not evidenced in the provided file previews.
  > 💡 Rebuild the documents with full schedules, complete itineraries, and verified content.

### ✅ `8c823e32…` — score 6/10
- No actual PDF content verification is shown.
- Text response promises DOCX and PDF, but only summary is provided.
- Policy may lack full legal and operational completeness.
  > 💡 Verify the final PDF contains the complete policy and all required sections.

### ✅ `eb54f575…` — score 8/10
- PDF preview is truncated, so full section completeness cannot be fully verified.
- Only one image file is included; no evidence it is required or referenced in the PDF.
- Ballistics justification appears general, with limited objective FBI data shown in preview.
  > 💡 Provide the full PDF text with explicit FBI test references and ensure all five sections are fully detailed.

### ✅ `11e1b169…` — score 7/10
- PDF preview is truncated, so completeness cannot be fully verified.
- KRS 503.090 content is not visible in the preview.
- Text response mentions source document generation, which was not explicitly required.
  > 💡 Verify the full PDF includes all required topics and the Kentucky force statute.

### ✅ `efca245f…` — score 6/10
- Scenario 1 and 2 may not fully satisfy the May 1 catch-up requirement.
- The workbook preview is truncated, so completeness of all three plans is uncertain.
- Text response is professional but omits specific scenario implications.
  > 💡 Verify all scenario sheets fully cover the required dates and backlog targets.

### ✅ `68d8d901…` — score 6/10
- Production Sequences sheet appears duplicated and partially incomplete.
- No evidence the workbook content was verified against all reference details.
- Text response is generic and does not confirm editable workbook specifics.
  > 💡 Review the workbook for completeness, remove duplicate rows, and verify all required sequence details are populated.

### ✅ `bd72994f…` — score 8/10
- PDF is only one page, not a 4-6 slide presentation.
- No evidence the looks were selected from the brand's official 2025 resort materials.
- Text response mentions separate document file, but deliverables are not clearly described.
  > 💡 Provide a true 4-6 slide PDF and cite the official collection source clearly.

### ✅ `45c6237b…` — score 6/10
- PDF has 6 pages, but the task required under 10 slides only.
- Shirt size quantities appear inconsistent with the stated historical mix.
- Next Season Assortment section may be empty or missing vendor images.
  > 💡 Revise the presentation to ensure all required images, sizing logic, and summary details are fully included.

### ✅ `6436ff9e…` — score 8/10
- Text response is generic and not tailored to the completed form.
- No evidence of visual layout quality beyond section headings.
- Optional demographics are included, but specific questions are not shown in preview.
  > 💡 Add a brief summary of the form’s key improvements and verify the final layout visually.

### ✅ `40a99a31…` — score 6/10
- Report preview shows corrupted text and truncation.
- Hardware matrix appears incomplete in preview.
- No evidence of six cameras and seven LIDAR placements in deliverables.
  > 💡 Regenerate files with clean, complete content and verify all required hardware coverage.

### ✅ `b9665ca1…` — score 5/10
- Missing evidence of all specified wire labels and stop-button details.
- Source file is a summary, not the required schematic content.
- Text response promises files, but does not confirm full requirement coverage.
  > 💡 Verify the schematic includes every specified connection and label exactly.

### ❌ `c6269101…` — score 4/10
- No evidence the deck includes actual capability or stability results.
- No supporting analysis files or charts were produced.
- Text response promises analysis but only describes intended deliverables.
  > 💡 Provide the completed analysis with explicit findings, charts, and recommendations in the deck.

### ❌ `be830ca0…` — score 4/10
- No evidence the required analyses or charts were actually included.
- Text response is generic and does not confirm results or findings.
- Timeline and A3 completeness cannot be verified from the provided output.
  > 💡 Verify slide content includes all required analyses, A3 sections, and DMAIC timeline details.

### ✅ `cd9efc18…` — score 6/10
- PDF is only 5 pages, not the requested 8 to 11 pages.
- Preview truncation prevents confirming all required trust and guardianship provisions.
- Text response promises validation, but no substantive completion details are provided.
  > 💡 Expand the will to the requested length and verify all required provisions appear in the final PDF.

### ✅ `a97369c7…` — score 5/10
- Text response promises a memo, not the memo itself.
- No clear analysis of all three requested fiduciary duty issues.
- File content appears truncated and may omit required legal conclusions.
  > 💡 Provide the full memorandum text with explicit analysis of each requested issue.

### ✅ `3f625cb2…` — score 6/10
- PDF is only one page, not a complete memorandum.
- Case law discussion is generic and lacks specific authorities.
- Legal options are incomplete and may omit key procedural steps.
  > 💡 Expand the memo with specific cases and fuller client options while keeping it under three pages.

### ✅ `aad21e4c…` — score 8/10
- Minority consent rights may need tighter drafting for enforceability.
- Capitalization schedule details were not fully verified from the preview.
- Word file content appears comprehensive but not fully reviewable here.
  > 💡 Confirm the final document includes all requested rights and a complete cap table.

### ✅ `8314d1b1…` — score 6/10
- Output includes a PDF, but the task requested a Word document only.
- The memo appears truncated in the preview, so completeness cannot be confirmed.
- No clear evidence the March 2025 DGCL amendments were accurately researched and applied.
  > 💡 Provide a complete .docx memo with verified March 2025 Delaware law analysis and no extra file types.

### ✅ `5e2b6aab…` — score 6/10
- No individual component drawings were required, but only subassembly PDFs are shown.
- The concept summary is included, but the task did not request a DOCX deliverable.
- Thermal and sealing details are conceptual; no explicit validation against the temperature range.
  > 💡 Provide only the required STEP and PDF deliverables, and add clearer concept validation notes.

### ✅ `46fc494e…` — score 6/10
- Missing 20-minute time-trace plot for nodes 1, 13, and 22.
- No 0.5-minute profile file is listed in the produced files.
- Reported temperatures stay at 25 C, suggesting a likely non-physical result.
  > 💡 Regenerate the thermal solution and include all required plots and realistic transient temperatures.

### ❌ `3940b7e7…` — score 4/10
- Objective is incorrect and omits key analysis goals.
- Results and field-variable tables are not verified in the preview.
- Text response is repetitive and not fully professional.
  > 💡 Revise the report to match the CFD data exactly and verify all required tables and conclusions.

### ✅ `8077e700…` — score 6/10
- AISI 1045 results are not clearly supported by attached data.
- The report preview appears truncated, risking missing required sections.
- Direct microstructure observations are mentioned but not evidenced.
  > 💡 Verify the full PDF includes both steels, all required sections, and data-backed microstructure discussion.

### ✅ `5a2d70da…` — score 8/10
- Files appear complete, but purchase links are generic placeholders.
- No evidence the referenced source drawings were directly validated.
- Text response is brief and omits key manufacturing details.
  > 💡 Replace placeholders with verified links and confirm all part-specific requirements against the drawings.

### ✅ `74d6e8b0…` — score 7/10
- Word and PDF were produced, but the task required Word format only.
- The text response promises files but does not mention the actual guideline content details.
- The preview is truncated, so completeness and citations cannot be fully verified.
  > 💡 Provide a Word-only deliverable with fully visible, complete guideline content and citations.

### ✅ `61b0946a…` — score 6/10
- Output is truncated, so completeness cannot be verified.
- No evidence the Excel budget file was actually used.
- The proposal may omit required detailed procedure-capacity calculations.
  > 💡 Provide the full proposal with verified budget-based calculations and complete file content.

### ❌ `61e7b9c6…` — score 4/10
- Text response is generic and does not confirm completed content.
- Workbook may include incorrect generic names for some brands.
- No evidence prices were sourced from online pharmacies.
  > 💡 Verify all drug mappings, prices, and populate the workbook with sourced formulary data.

### ✅ `f1be6436…` — score 6/10
- Travel section lacks hotel-to-airport details for all required dates.
- Discretionary fund calculations are missing despite over-budget totals.
- Original task text appears truncated in the source prompt.
  > 💡 Add complete transportation details and explicit discretionary fund calculations for each physician.

### ✅ `6d2c8e55…` — score 6/10
- No evidence the schedule avoided all holiday and conference dates.
- One October source is only a URL record, not a full article PDF.
- The email draft is present, but attachment completeness is not verified.
  > 💡 Verify dates against the holiday file and ensure all nine articles are fully accessible PDFs.

### ✅ `ef8719da…` — score 6/10
- The pitch file appears truncated in the preview.
- No clear draft timeline is visible in the provided text.
- The response does not verify the hyperlinks are actually embedded.
  > 💡 Confirm the full pitch includes all required sections and functioning links.

### ❌ `5d0feb24…` — score 4/10
- Response ignores the requested review and only describes file creation.
- No actual editorial feedback, accuracy checks, or source links were provided.
- The output is generic and does not assess the draft’s science or structure.
  > 💡 Provide concise, source-backed editorial notes on accuracy, clarity, and missing context.

### ✅ `6974adea…` — score 6/10
- No evidence the Word document meets the 1,000-word minimum.
- The response mentions code validation, but no code is provided.
- The article content may be incomplete or truncated in the preview.
  > 💡 Verify the document length, include the requested validation code, and ensure the full article is present.

### ✅ `0112fc9b…` — score 8/10
- Text response does not actually present the SOAP note.
- Plan content is truncated in the preview.
- No clear confirmation of complete file content review.
  > 💡 Provide the full SOAP note in the response and verify the complete plan is included.

### ✅ `772e7524…` — score 8/10
- Text response mentions file creation instead of the SOAP note content.
- No explicit confirmation of file correctness or opening verification.
- Plan details may be incomplete in the response text.
  > 💡 Provide the full SOAP note content and verify the generated files explicitly.

### ✅ `e6429658…` — score 8/10
- Appeal letter is only two pages, not clearly 2-4 pages.
- AbbVie application may contain unverified or incomplete fields.
- Text response is brief but professional.
  > 💡 Verify all form fields and ensure the appeal letter length meets the requested range.

### ❌ `b5d2e6f1…` — score 4/10
- Only a text response is shown; workbook changes are not verifiable.
- Required tab names and pivot outputs are not confirmed.
- Grand totals and exact headers are not validated.
  > 💡 Provide the completed workbook and verify all requested tabs, headers, and totals.

### ✅ `1137e2bb…` — score 7/10
- Text response claims creation, but no actual analysis summary is provided.
- SKU summary preview shows a blank column, suggesting formatting or export issues.
- No explicit Word content summary is shown for identified error patterns.
  > 💡 Verify the workbook formatting and include a concise, data-backed summary in the Word report.

### ❌ `9a0d8d36…` — score 4/10
- Text response promises content but does not confirm the deck includes it.
- No file content preview available to verify calculations or tax details.
- Vested timing and hypothetical step-by-step examples are not evidenced.
  > 💡 Verify the PPTX contains explicit examples, tax comparisons, and net proceeds calculations.

### ❌ `feb5eefc…` — score 4/10
- PDF is only 2 pages, not the requested 12 or fewer with full analysis.
- Preview is truncated, so completeness and recommendation cannot be fully verified.
- Text response is a process note, not the required professional deliverable summary.
  > 💡 Provide a complete client-ready PDF with full comparison, scenario, and recommendation.

### ✅ `c657103b…` — score 7/10
- A PDF was produced instead of only the requested PowerPoint and Excel files.
- Spreadsheet preview does not show the required year-by-year comparison details or full period coverage.
- No evidence of exact IRS factor usage or baseline RMD-only comparison output.
  > 💡 Provide the required PPTX and XLSX deliverables with complete period-by-period modeling and baseline comparison.

### ✅ `f9f82549…` — score 8/10
- PPTX content was not previewed, so completeness is unverified.
- Source DOCX is included, though not requested in the task.
- Flowchart title and PDF filename differ slightly in wording.
  > 💡 Confirm the PPTX details and align filenames exactly with the requested titles.

### ❌ `57b2cdf2…` — score 4/10
- PDF is seven pages, exceeding the two-page limit.
- The report includes an extra Photograph Review section not requested.
- Timeline differs from the stated assignment window and may need verification.
  > 💡 Revise the report to two pages, keep only the required sections, and verify all times against the assignment.

### ✅ `84322284…` — score 6/10
- Text response promises DOCX conversion, but task required only PDF submission.
- Report preview appears truncated, suggesting incomplete content.
- No explicit recommendation details are visible in the provided preview.
  > 💡 Verify the PDF contains the full report, timeline, assessment, and recommendations.

### ✅ `6241e678…` — score 6/10
- Preview shows extra tasks not requested, like casting and location scouting.
- Client graphics task is truncated in the prompt, risking incomplete coverage.
- Need confirmation all required review and approval windows are correctly scheduled.
  > 💡 Verify the schedule matches only the requested tasks and all client review windows.

### ✅ `e14e32ba…` — score 6/10
- Some required details may be incomplete or unverified.
- Photo content is missing; files show 'Image not available'.
- Only four delis are shown in the preview, meeting the minimum but not the full range.
  > 💡 Verify all hours, add real photos, and confirm every deli has complete media links.

### ✅ `e4f664ea…` — score 6/10
- Text response promises DOCX/PDF instead of delivering the screenplay content.
- Preview shows truncation, so completeness cannot be verified.
- No evidence of required 8-12 page, 10-15 scene target being met.
  > 💡 Provide the full screenplay content and confirm page count, scene count, and final PDF readiness.

### ✅ `ce864f41…` — score 6/10
- No brief responses to the three questions were provided.
- Department risk labels appear inconsistent with the stated 95%-105% target.
- Summary text file may not satisfy the requested supplemental responses.
  > 💡 Revise the workbook labels and include concise answers to all three questions.

### ✅ `58ac1cc5…` — score 6/10
- QA escalation email and internal summary note files were not previewed for content verification.
- Change control form appears incomplete with blank fields and truncated risk assessment text.
- Risk assessment may not fully address the vendor notification breakdown and mitigation actions.
  > 💡 Verify all deliverables contain complete, professional content and fully document the vendor communication failure.

### ✅ `55ddb773…` — score 6/10
- No evidence the PDF includes all attached violation questions.
- Preview shows truncated content, so completeness cannot be verified.
- Text response is generic and does not confirm specific form details.
  > 💡 Verify the PDF contains every required violation category and question from the attachment.

### ❌ `1e5a1d7f…` — score 3/10
- DOCX lacks the required task table.
- No weekly schedule content or PM duties were included.
- Text response promises verification, but no evidence is shown.
  > 💡 Regenerate the DOCX with the full four-column schedule table and duty-based entries.

### ✅ `0419f1c3…` — score 8/10
- Preview shows the document is truncated, so full completeness cannot be fully verified.
- No obvious formatting or placeholder issues are visible in the preview.
- Training recommendations appear aligned with the stated performance gaps.
  > 💡 Confirm the full DOCX includes all objectives, support details, consequences, and signatures.

### ✅ `ed2bc14c…` — score 6/10
- File content preview is truncated, so completeness cannot be fully verified.
- No evidence the memo includes the required 30-day email draft details.
- No confirmation that the two resident events are specifically low-cost and high-impact.
  > 💡 Verify the full memo covers all four required components with specific, actionable details.

### ✅ `46bc7238…` — score 8/10
- Preview is truncated, so full completeness cannot be fully verified.
- No obvious file-type or content mismatches were detected.
- The response is professional and aligned with the requested deliverable.
  > 💡 Confirm the PDF includes all required pages and stock photos throughout.

### ✅ `2d06bc0a…` — score 9/10
- Purchase price appears correct but cap-rate math is not shown.
- Expiration date is mentioned generally, not specifically set in the LOI.
- Text response says current directory, which is unnecessary but not harmful.
  > 💡 Add a specific 7-10 day expiration date and show the pricing calculation clearly.

### ❌ `0818571f…` — score 3/10
- Listings are representative placeholders, not verified June 2025 public deals.
- Required photos and maps are not actual sourced property assets.
- Output lacks true live sourcing from Crexi or LoopNet.
  > 💡 Replace placeholders with verified active listings and include sourced images, maps, and deal data.

### ✅ `6074bba3…` — score 6/10
- Subject property details are incomplete and include placeholder text.
- Comparable and active listing tables contain missing fields and placeholders.
- Text response promises future work instead of confirming completed analysis.
  > 💡 Replace placeholders with verified market data and ensure the PDF is fully populated.

### ✅ `5ad0c554…` — score 7/10
- PDF preview shows truncated text and a cut-off word.
- No evidence the brochure is truly double-sided in layout.
- Text response promises validation but provides no verification details.
  > 💡 Ensure the brochure is fully formatted, complete, and clearly double-sided before delivery.

### ✅ `11593a50…` — score 6/10
- Summary PDF lacks actual photos and shows placeholder content.
- List date is N/A, not sourced from MLSLI as requested.
- One property exceeds the $1,500,000 limit in the preview.
  > 💡 Replace placeholders with real listing data and verify every home meets all criteria.

### ✅ `94925f49…` — score 8/10
- Reports are only one page each, not up to 10 pages.
- School data sources are mentioned but not clearly cited in the PDFs.
- Text response is generic and does not summarize the actual report contents.
  > 💡 Add explicit source citations and richer school/home details in each PDF.

### ✅ `1bff4551…` — score 6/10
- Only a text response is shown; PDF content cannot be verified here.
- Set list details appear truncated, so completeness is uncertain.
- No evidence confirms all songs meet the no-heavy-curse-word requirement.
  > 💡 Verify the PDF includes the full set list, links, and content checks before delivery.

### ✅ `01d7e53e…` — score 6/10
- Attachment A appears to reference Summer Fun, not RecFit.
- No evidence the City contract language was incorporated correctly.
- Text response is generic and does not confirm all required terms were included.
  > 💡 Revise the draft to align all exhibits and confirm every required clause is present.

### ✅ `dd724c67…` — score 6/10
- Only rehabilitation facilities are listed; hospitals are missing.
- TFU guide appears incomplete and may omit some conditions.
- Sheet formatting is awkward with blank columns and merged content.
  > 💡 Add all Long Island hospitals and complete TFU condition timeframes in a cleaner table.

### ❌ `90edba97…` — score 2/10
- No patient lab data or monthly changes were actually entered.
- Response only describes intent, not completed workbook content.
- Potentially incomplete file content cannot be verified from the preview.
  > 💡 Populate all patient sheets with actual values and documented treatment changes.

### ✅ `8384083a…` — score 6/10
- Text response is generic and not the actual guide content.
- PDF appears to contain formatting issues and awkward line breaks.
- Some days-supply calculations may be oversimplified without clear SIG details.
  > 💡 Revise the guide with cleaner formatting and explicit medication-specific dosing assumptions.

### ✅ `f2986c1f…` — score 6/10
- Workbook lacks confirmed medication names and strengths.
- All entries are marked unknown, limiting clinical usefulness.
- Text response does not mention the actual identified medications.
  > 💡 Verify pill identifications from Drugs.com and populate all available fields.

### ✅ `b3573f20…` — score 6/10
- Document is 6 pages, not the requested 3 pages.
- The response claims a PDF workflow but does not confirm final content quality.
- No clear evidence all required operational and sales prompts are included.
  > 💡 Revise the PDF to exactly three pages and verify all required onboarding questions are present.

### ✅ `a69be28f…` — score 7/10
- No evidence the PDF was actually generated from the PPTX.
- Text response promises an Excel workbook not required by the task.
- Regional slides may be incomplete if all four regions are not clearly shown.
  > 💡 Ensure the PDF is verified, keep only required deliverables, and confirm all four regions appear on separate men’s and women’s slides.

### ✅ `74ed1dc7…` — score 8/10
- Document content is slightly truncated in the preview.
- No explicit mention of all existing order type changes in detail.
- Could be more specific on implementation rules for each new type.
  > 💡 Add a concise table mapping each order type to its reporting and operational rules.

### ✅ `69a8ef86…` — score 8/10
- Internal preview is truncated, so full compliance cannot be fully verified.
- No obvious evidence of missing required timelines in the provided preview.
- External guidelines appear to include required request and labeling details.
  > 💡 Provide the full internal document text to confirm every required step and deadline.

### ✅ `ab81b076…` — score 8/10
- Preview is truncated, so final completeness cannot be fully verified.
- No obvious major content gaps were visible in the provided excerpt.
  > 💡 Verify the PDF includes all sections and complete damage documentation visuals.

### ❌ `b57efde3…` — score 2/10
- Only one lead was identified instead of hundreds of exhibitors.
- The lead appears incorrect and generic, not a verified AUV/UC/ROV manufacturer.
- The workbook lacks the required prospecting depth and event-ready detail.
  > 💡 Rebuild the spreadsheet by reviewing the full exhibitor list and validating each qualifying company.

### ❌ `bb863dd9…` — score 4/10
- Pricing and module details are not shown in the text response.
- Cannot verify all IEHK 2017 modules and quantities from the preview.
- Excel content may be incomplete without visible line items and totals.
  > 💡 Provide the full quotation table with all modules, prices, shelf life, lead times, and totals.

### ❌ `6a900a40…` — score 4/10
- Transport options and grand totals are not visible in the preview.
- General remark red-font requirement cannot be verified from the preview.
- Text response is generic and does not confirm all task-specific updates.
  > 💡 Verify the spreadsheet contains all three freight options, totals, and formatted remarks.

### ✅ `9efbcd35…` — score 6/10
- Document content is truncated in the preview.
- Source citations are not visible in the provided text.
- Cannot verify all required sections are fully developed.
  > 💡 Confirm the full DOCX includes complete, cited coverage of all requested topics within four pages.

### ✅ `552b7dd0…` — score 6/10
- Missing evidence of total cost and average resolution time calculations.
- No proof the summary slide includes recurring themes and recommendations.
- Only two chart files are listed; duration visuals may be absent.
  > 💡 Verify the presentation includes all required metrics, analysis, and a complete management summary.

### ❌ `76418a2c…` — score 2/10
- Shipment weights are zero, so methods and costs are likely incorrect.
- No tracking numbers or shipment details were populated.
- Text response promises a PDF summary, but content appears generic.
  > 💡 Recalculate from source files and populate all shipment fields accurately.

### ❌ `0e386e32…` — score 4/10
- Zip contents were not verifiable from the preview.
- No evidence of complete frontend, contracts, and relayer implementation.
- Privacy and cross-chain requirements may be only described, not fully delivered.
  > 💡 Provide a verifiable file listing and confirm all required components are implemented.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7b08cd4d…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 3 file(s)
- `f84ea6ac…` (Government): 1 file(s)
- `a328feea…` (Government): 1 file(s)
- `27e8912c…` (Government): 5 file(s)
- `17111c03…` (Government): 2 file(s)
- `c44e9b62…` (Government): 3 file(s)
- `99ac6944…` (Information): 4 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `38889c3b…` (Information): 6 file(s)
- `ff85ee58…` (Information): 1 file(s)
- `4b894ae3…` (Information): 3 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 2 file(s)
- `bbe0a93b…` (Government): 3 file(s)
- `85d95ce5…` (Government): 3 file(s)
- `76d10872…` (Government): 1 file(s)
- `36d567ba…` (Government): 2 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 1 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 4 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 4 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 9 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `b7a5912e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 2 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 2 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 1 file(s)
- `f3351922…` (Finance and Insurance): 2 file(s)
- `61717508…` (Finance and Insurance): 2 file(s)
- `0ed38524…` (Finance and Insurance): 3 file(s)
- `87da214f…` (Finance and Insurance): 2 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 3 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e222075d…` (Information): 3 file(s)
- `c94452e4…` (Information): 3 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 2 file(s)
- `9e8607e7…` (Finance and Insurance): 5 file(s)
- `c7d83f01…` (Finance and Insurance): 6 file(s)
- `46b34f78…` (Finance and Insurance): 1 file(s)
- `a1963a68…` (Finance and Insurance): 3 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 2 file(s)
- `4520f882…` (Finance and Insurance): 2 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `e996036e…` (Wholesale Trade): 1 file(s)
- `327fbc21…` (Wholesale Trade): 1 file(s)
- `1aecc095…` (Health Care and Social Assistance): 3 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 2 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 2 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `bf68f2ad…` (Manufacturing): 2 file(s)
- `efca245f…` (Manufacturing): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 4 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 5 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `4d61a19a…` (Retail Trade): 3 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 2 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 3 file(s)
- `c6269101…` (Manufacturing): 1 file(s)
- `be830ca0…` (Manufacturing): 1 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 2 file(s)
- `5e2b6aab…` (Manufacturing): 14 file(s)
- `46fc494e…` (Manufacturing): 9 file(s)
- `3940b7e7…` (Manufacturing): 2 file(s)
- `8077e700…` (Manufacturing): 4 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 2 file(s)
- `81db15ff…` (Health Care and Social Assistance): 2 file(s)
- `61b0946a…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 4 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 11 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 2 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 3 file(s)
- `5d0feb24…` (Information): 2 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 1 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 2 file(s)
- `feb5eefc…` (Finance and Insurance): 1 file(s)
- `3600de06…` (Finance and Insurance): 3 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 2 file(s)
- `f9f82549…` (Retail Trade): 3 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `6241e678…` (Information): 2 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 2 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 2 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 1 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 1 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 2 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 1 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 2 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 3 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 18 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 6 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 3 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 5 file(s)
- `650adcb1…` (Government): 1 file(s)
- `01d7e53e…` (Government): 4 file(s)
- `a73fbc98…` (Government): 3 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `90edba97…` (Health Care and Social Assistance): 1 file(s)
- `91060ff0…` (Retail Trade): 2 file(s)
- `8384083a…` (Retail Trade): 3 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `b3573f20…` (Wholesale Trade): 2 file(s)
- `a69be28f…` (Wholesale Trade): 11 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 4 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `6a900a40…` (Wholesale Trade): 1 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `4c4dc603…` (Finance and Insurance): 2 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 3 file(s)
- `76418a2c…` (Manufacturing): 2 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 1 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
