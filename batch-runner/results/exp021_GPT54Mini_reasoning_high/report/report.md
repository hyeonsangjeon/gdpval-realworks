# Experiment Report: GPT-5.4-Mini Reasoning HIGH — Full Benchmark (Ablation 1/4)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp021_GPT54Mini_reasoning_high` |
| **Condition** | GPT-5.4-Mini reasoning=high + gpt-audio-1.5 preprocessor |
| **Model** | gpt-5.4-mini |
| **Execution Mode** | subprocess |
| **Date** | 2026-03-24 |
| **Duration** | 92m 26s |
| **Generated At** | 2026-03-24T18:39:08.660538+00:00 |
| 🤗 HF Dataset | [exp021_GPT54Mini_reasoning_high](https://huggingface.co/datasets/HyeonSang/exp021_GPT54Mini_reasoning_high) |
| 📊 Self-Report | [self_report.json](https://huggingface.co/datasets/HyeonSang/exp021_GPT54Mini_reasoning_high/blob/main/self_report.json) |
| 📊 Grading | ⏳ Awaiting (`scores.json`) |

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 220 |
| Success | 207 (94.1%) |
| Errors | 13 |
| Retried Tasks | 53 |
| Avg QA Score | 6.65/10 |
| Min QA Score | 2/10 |
| Max QA Score | 10/10 |
| Avg Latency | 17,341ms |
| Max Latency | 132,952ms |
| Total LLM Time | 3814s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 174 (94.1%) |
| Failed → dummy created | 11 |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 1 | 29 | 29 | 0 |
| 2 | 24 | 11 | 13 |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 25 | 25 | 100.0% | 6.76/10 | 21,728ms |
| Government | 25 | 23 | 92.0% | 7.0/10 | 14,947ms |
| Health Care and Social Assistance | 25 | 24 | 96.0% | 6.21/10 | 14,679ms |
| Information | 25 | 24 | 96.0% | 6.46/10 | 21,064ms |
| Manufacturing | 25 | 24 | 96.0% | 6.12/10 | 15,648ms |
| Professional, Scientific, and Technical  | 25 | 21 | 84.0% | 6.19/10 | 17,838ms |
| Real Estate and Rental and Leasing | 25 | 24 | 96.0% | 6.67/10 | 19,555ms |
| Retail Trade | 20 | 18 | 90.0% | 7.67/10 | 13,518ms |
| Wholesale Trade | 25 | 24 | 96.0% | 7.0/10 | 16,326ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ✅ success | - | 1 | 8/10 | 14387ms |
| 2 | `7b08cd4d…` | Professional, Scientif | Accountants and Au | ❌ error | Yes | 0 | - | 25908ms |
| 3 | `7d7fc9a7…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 6/10 | 22948ms |
| 4 | `43dc9778…` | Professional, Scientif | Accountants and Au | ✅ success | - | 4 | 6/10 | 19460ms |
| 5 | `ee09d943…` | Professional, Scientif | Accountants and Au | ✅ success | Yes | 1 | 6/10 | 14970ms |
| 6 | `f84ea6ac…` | Government | Administrative Ser | ✅ success | - | 2 | 4/10 | 11319ms |
| 7 | `a328feea…` | Government | Administrative Ser | ✅ success | - | 2 | 9/10 | 11049ms |
| 8 | `27e8912c…` | Government | Administrative Ser | ✅ success | - | 2 | 6/10 | 17469ms |
| 9 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 2 | 9/10 | 12273ms |
| 10 | `c44e9b62…` | Government | Administrative Ser | ✅ success | - | 4 | 4/10 | 19392ms |
| 11 | `99ac6944…` | Information | Audio and Video Te | ✅ success | - | 5 | 8/10 | 30569ms |
| 12 | `f9a1c16c…` | Information | Audio and Video Te | ✅ success | - | 3 | 9/10 | 15553ms |
| 13 | `38889c3b…` | Information | Audio and Video Te | ✅ success | Yes | 6 | 6/10 | 34349ms |
| 14 | `ff85ee58…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 9/10 | 43948ms |
| 15 | `4b894ae3…` | Information | Audio and Video Te | ✅ success | Yes | 2 | 6/10 | 18334ms |
| 16 | `1b1ade2d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 6/10 | 13613ms |
| 17 | `93b336f3…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 13000ms |
| 18 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 8/10 | 8696ms |
| 19 | `24d1e93f…` | Manufacturing | Buyers and Purchas | ✅ success | - | 1 | 8/10 | 14296ms |
| 20 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | 6/10 | 14944ms |
| 21 | `575f8679…` | Government | Child, Family, and | ✅ success | - | 1 | 8/10 | 15812ms |
| 22 | `a74ead3b…` | Government | Child, Family, and | ✅ success | - | 4 | 8/10 | 15419ms |
| 23 | `bbe0a93b…` | Government | Child, Family, and | ✅ success | - | 3 | 6/10 | 18426ms |
| 24 | `85d95ce5…` | Government | Child, Family, and | ❌ error | Yes | 0 | - | 28837ms |
| 25 | `76d10872…` | Government | Child, Family, and | ✅ success | - | 2 | 9/10 | 19022ms |
| 26 | `36d567ba…` | Government | Compliance Officer | ✅ success | - | 2 | 7/10 | 13918ms |
| 27 | `7bbfcfe9…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 9253ms |
| 28 | `2696757c…` | Government | Compliance Officer | ✅ success | - | 2 | 8/10 | 8508ms |
| 29 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 1 | 9/10 | 8363ms |
| 30 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 2 | 6/10 | 22991ms |
| 31 | `cebf301e…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 8/10 | 19354ms |
| 32 | `c2e8f271…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | 8/10 | 14011ms |
| 33 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 6/10 | 14459ms |
| 34 | `c357f0e2…` | Professional, Scientif | Computer and Infor | ✅ success | Yes | 1 | 9/10 | 20836ms |
| 35 | `a45bc83b…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | 8/10 | 18312ms |
| 36 | `a10ec48c…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 6/10 | 132952ms |
| 37 | `fccaa4a1…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 8/10 | 16364ms |
| 38 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 6/10 | 16837ms |
| 39 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | 2/10 | 14840ms |
| 40 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | 7/10 | 16409ms |
| 41 | `a0ef404e…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 9/10 | 11368ms |
| 42 | `b7a5912e…` | Real Estate and Rental | Counter and Rental | ❌ error | Yes | 0 | - | 17410ms |
| 43 | `aa071045…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 2 | 6/10 | 13744ms |
| 44 | `476db143…` | Real Estate and Rental | Counter and Rental | ✅ success | Yes | 2 | 9/10 | 12967ms |
| 45 | `61f546a8…` | Real Estate and Rental | Counter and Rental | ✅ success | - | 1 | 4/10 | 20260ms |
| 46 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 8/10 | 8843ms |
| 47 | `61717508…` | Finance and Insurance | Customer Service R | ✅ success | - | 4 | 6/10 | 18463ms |
| 48 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 2 | 8/10 | 13532ms |
| 49 | `87da214f…` | Finance and Insurance | Customer Service R | ✅ success | Yes | 1 | 3/10 | 16209ms |
| 50 | `d025a41c…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | 4/10 | 13187ms |
| 51 | `401a07f1…` | Information | Editors | ✅ success | - | 1 | 6/10 | 10450ms |
| 52 | `afe56d05…` | Information | Editors | ✅ success | - | 1 | 6/10 | 17813ms |
| 53 | `9a8c8e28…` | Information | Editors | ✅ success | - | 7 | 7/10 | 22037ms |
| 54 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | 6/10 | 14544ms |
| 55 | `ec2fccc9…` | Information | Editors | ✅ success | - | 1 | 6/10 | 13078ms |
| 56 | `8c8fc328…` | Information | Film and Video Edi | ✅ success | - | 1 | 9/10 | 9514ms |
| 57 | `e222075d…` | Information | Film and Video Edi | ✅ success | - | 2 | 4/10 | 11177ms |
| 58 | `c94452e4…` | Information | Film and Video Edi | ✅ success | Yes | 2 | 3/10 | 6882ms |
| 59 | `75401f7c…` | Information | Film and Video Edi | ✅ success | Yes | 1 | 4/10 | 120876ms |
| 60 | `a941b6d8…` | Information | Film and Video Edi | ❌ error | Yes | 0 | - | 20833ms |
| 61 | `8079e27d…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 1 | 6/10 | 22450ms |
| 62 | `e21cd746…` | Finance and Insurance | Financial and Inve | ✅ success | - | 3 | 8/10 | 27663ms |
| 63 | `9e8607e7…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 8/10 | 31697ms |
| 64 | `c7d83f01…` | Finance and Insurance | Financial and Inve | ✅ success | - | 5 | 6/10 | 27679ms |
| 65 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | Yes | 1 | 8/10 | 14112ms |
| 66 | `a1963a68…` | Finance and Insurance | Financial Managers | ✅ success | - | 5 | 6/10 | 29082ms |
| 67 | `5f6c57dd…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 8/10 | 39413ms |
| 68 | `b39a5aa7…` | Finance and Insurance | Financial Managers | ✅ success | - | 1 | 9/10 | 22718ms |
| 69 | `b78fd844…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | 6/10 | 15516ms |
| 70 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | Yes | 2 | 8/10 | 24515ms |
| 71 | `ec591973…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 8/10 | 11872ms |
| 72 | `62f04c2f…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 2 | 10/10 | 11045ms |
| 73 | `3f821c2d…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 14931ms |
| 74 | `e996036e…` | Wholesale Trade | First-Line Supervi | ✅ success | - | 1 | 6/10 | 17714ms |
| 75 | `327fbc21…` | Wholesale Trade | First-Line Supervi | ✅ success | Yes | 1 | 3/10 | 17829ms |
| 76 | `6dcae3f5…` | Health Care and Social | First-Line Supervi | ✅ success | - | 2 | 4/10 | 15194ms |
| 77 | `1aecc095…` | Health Care and Social | First-Line Supervi | ✅ success | - | 4 | 7/10 | 14874ms |
| 78 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | Yes | 3 | 6/10 | 17531ms |
| 79 | `40a8c4b1…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | 4/10 | 20968ms |
| 80 | `4d1a8410…` | Health Care and Social | First-Line Supervi | ✅ success | - | 3 | 4/10 | 18597ms |
| 81 | `8c823e32…` | Government | First-Line Supervi | ✅ success | - | 2 | 6/10 | 16070ms |
| 82 | `eb54f575…` | Government | First-Line Supervi | ✅ success | - | 1 | 6/10 | 17807ms |
| 83 | `11e1b169…` | Government | First-Line Supervi | ✅ success | Yes | 2 | 4/10 | 15286ms |
| 84 | `a95a5829…` | Government | First-Line Supervi | ✅ success | - | 2 | 9/10 | 15291ms |
| 85 | `22c0809b…` | Government | First-Line Supervi | ✅ success | - | 2 | 8/10 | 13060ms |
| 86 | `bf68f2ad…` | Manufacturing | First-Line Supervi | ✅ success | Yes | 2 | 9/10 | 10121ms |
| 87 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 4/10 | 13333ms |
| 88 | `9e39df84…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 6/10 | 16204ms |
| 89 | `68d8d901…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 8/10 | 10605ms |
| 90 | `1752cb53…` | Manufacturing | First-Line Supervi | ✅ success | - | 1 | 4/10 | 8398ms |
| 91 | `bd72994f…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 3 | 9/10 | 12440ms |
| 92 | `211d0093…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 8531ms |
| 93 | `d4525420…` | Retail Trade | First-Line Supervi | ✅ success | Yes | 2 | 4/10 | 14921ms |
| 94 | `45c6237b…` | Retail Trade | First-Line Supervi | ✅ success | - | 2 | 9/10 | 20624ms |
| 95 | `cecac8f9…` | Retail Trade | First-Line Supervi | ✅ success | - | 4 | 7/10 | 18566ms |
| 96 | `8f9e8bcd…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 10721ms |
| 97 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 1 | 9/10 | 11184ms |
| 98 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | 9/10 | 11482ms |
| 99 | `4d61a19a…` | Retail Trade | General and Operat | ❌ error | Yes | 0 | - | 24770ms |
| 100 | `6436ff9e…` | Retail Trade | General and Operat | ✅ success | - | 1 | 8/10 | 10703ms |
| 101 | `8a7b6fca…` | Manufacturing | Industrial Enginee | ✅ success | - | 1 | 9/10 | 26956ms |
| 102 | `40a99a31…` | Manufacturing | Industrial Enginee | ✅ success | Yes | 3 | 8/10 | 22493ms |
| 103 | `b9665ca1…` | Manufacturing | Industrial Enginee | ✅ success | - | 2 | 4/10 | 16791ms |
| 104 | `c6269101…` | Manufacturing | Industrial Enginee | ✅ success | - | 5 | 6/10 | 17018ms |
| 105 | `be830ca0…` | Manufacturing | Industrial Enginee | ✅ success | - | 7 | 6/10 | 29846ms |
| 106 | `cd9efc18…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 4/10 | 22437ms |
| 107 | `a97369c7…` | Professional, Scientif | Lawyers | ✅ success | Yes | 2 | 6/10 | 32866ms |
| 108 | `3f625cb2…` | Professional, Scientif | Lawyers | ✅ success | - | 2 | 6/10 | 16286ms |
| 109 | `aad21e4c…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 7/10 | 27763ms |
| 110 | `8314d1b1…` | Professional, Scientif | Lawyers | ✅ success | - | 1 | 6/10 | 21374ms |
| 111 | `5e2b6aab…` | Manufacturing | Mechanical Enginee | ✅ success | - | 21 | 4/10 | 16452ms |
| 112 | `46fc494e…` | Manufacturing | Mechanical Enginee | ✅ success | Yes | 9 | 4/10 | 37931ms |
| 113 | `3940b7e7…` | Manufacturing | Mechanical Enginee | ✅ success | - | 3 | 6/10 | 16268ms |
| 114 | `8077e700…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 4/10 | 17950ms |
| 115 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | 6/10 | 16269ms |
| 116 | `74d6e8b0…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 9/10 | 20503ms |
| 117 | `81db15ff…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 9/10 | 7389ms |
| 118 | `61b0946a…` | Health Care and Social | Medical and Health | ✅ success | - | 2 | 6/10 | 14111ms |
| 119 | `61e7b9c6…` | Health Care and Social | Medical and Health | ✅ success | - | 1 | 8/10 | 8480ms |
| 120 | `c9bf9801…` | Health Care and Social | Medical and Health | ✅ success | - | 5 | 6/10 | 28144ms |
| 121 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 5 | 6/10 | 13435ms |
| 122 | `41f6ef59…` | Health Care and Social | Medical Secretarie | ✅ success | - | 2 | 9/10 | 11817ms |
| 123 | `a0552909…` | Health Care and Social | Medical Secretarie | ❌ error | Yes | 0 | - | 13740ms |
| 124 | `6d2c8e55…` | Health Care and Social | Medical Secretarie | ✅ success | - | 11 | 4/10 | 16015ms |
| 125 | `4b98ccce…` | Health Care and Social | Medical Secretarie | ✅ success | - | 3 | 7/10 | 15509ms |
| 126 | `60221cd0…` | Information | News Analysts, Rep | ✅ success | - | 1 | 8/10 | 4925ms |
| 127 | `ef8719da…` | Information | News Analysts, Rep | ✅ success | Yes | 1 | 6/10 | 9639ms |
| 128 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 4 | 6/10 | 10441ms |
| 129 | `5d0feb24…` | Information | News Analysts, Rep | ✅ success | - | 1 | 4/10 | 10899ms |
| 130 | `6974adea…` | Information | News Analysts, Rep | ✅ success | - | 1 | 6/10 | 13802ms |
| 131 | `1a78e076…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 16568ms |
| 132 | `1b9ec237…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 8/10 | 27985ms |
| 133 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | 6/10 | 7304ms |
| 134 | `772e7524…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | 4/10 | 6872ms |
| 135 | `e6429658…` | Health Care and Social | Nurse Practitioner | ✅ success | Yes | 3 | 6/10 | 10042ms |
| 136 | `b5d2e6f1…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 13995ms |
| 137 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | Yes | 1 | 9/10 | 21313ms |
| 138 | `47ef842d…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | 9/10 | 14265ms |
| 139 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 6/10 | 14287ms |
| 140 | `c3525d4d…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | 9/10 | 16216ms |
| 141 | `9a0d8d36…` | Finance and Insurance | Personal Financial | ✅ success | - | 1 | 8/10 | 26317ms |
| 142 | `664a42e5…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | 6/10 | 31130ms |
| 143 | `feb5eefc…` | Finance and Insurance | Personal Financial | ✅ success | Yes | 2 | 6/10 | 16135ms |
| 144 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 4 | 8/10 | 30080ms |
| 145 | `c657103b…` | Finance and Insurance | Personal Financial | ✅ success | Yes | 3 | 8/10 | 29463ms |
| 146 | `ae0c1093…` | Retail Trade | Private Detectives | ✅ success | - | 4 | 9/10 | 9904ms |
| 147 | `f9f82549…` | Retail Trade | Private Detectives | ✅ success | Yes | 4 | 6/10 | 14138ms |
| 148 | `57b2cdf2…` | Retail Trade | Private Detectives | ✅ success | Yes | 2 | 9/10 | 9735ms |
| 149 | `84322284…` | Retail Trade | Private Detectives | ✅ success | - | 2 | 6/10 | 13431ms |
| 150 | `a46d5cd2…` | Retail Trade | Private Detectives | ✅ success | Yes | 2 | 9/10 | 11387ms |
| 151 | `6241e678…` | Information | Producers and Dire | ✅ success | - | 3 | 5/10 | 19649ms |
| 152 | `e14e32ba…` | Information | Producers and Dire | ✅ success | - | 2 | 8/10 | 13002ms |
| 153 | `b1a79ce1…` | Information | Producers and Dire | ✅ success | - | 1 | 8/10 | 25323ms |
| 154 | `e4f664ea…` | Information | Producers and Dire | ✅ success | - | 2 | 6/10 | 16279ms |
| 155 | `a079d38f…` | Information | Producers and Dire | ✅ success | - | 1 | 9/10 | 12675ms |
| 156 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 2/10 | 13814ms |
| 157 | `fd6129bd…` | Professional, Scientif | Project Management | ✅ success | - | 2 | 6/10 | 21234ms |
| 158 | `ce864f41…` | Professional, Scientif | Project Management | ✅ success | - | 1 | 4/10 | 12612ms |
| 159 | `58ac1cc5…` | Professional, Scientif | Project Management | ✅ success | - | 4 | 6/10 | 16120ms |
| 160 | `3c19c6d1…` | Professional, Scientif | Project Management | ✅ success | - | 1 | 4/10 | 16787ms |
| 161 | `a99d85fc…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 9/10 | 14720ms |
| 162 | `55ddb773…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 6/10 | 13973ms |
| 163 | `1e5a1d7f…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | 4/10 | 10379ms |
| 164 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | 8/10 | 15678ms |
| 165 | `ed2bc14c…` | Real Estate and Rental | Property, Real Est | ✅ success | Yes | 1 | 6/10 | 11828ms |
| 166 | `46bc7238…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 8/10 | 19891ms |
| 167 | `2d06bc0a…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 1 | 9/10 | 10203ms |
| 168 | `fd3ad420…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | 9/10 | 9460ms |
| 169 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | 3/10 | 12008ms |
| 170 | `6074bba3…` | Real Estate and Rental | Real Estate Broker | ✅ success | Yes | 4 | 8/10 | 17758ms |
| 171 | `5ad0c554…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 4 | 8/10 | 18316ms |
| 172 | `11593a50…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 4/10 | 16775ms |
| 173 | `94925f49…` | Real Estate and Rental | Real Estate Sales  | ✅ success | Yes | 8 | 4/10 | 16694ms |
| 174 | `90f37ff3…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 3 | 8/10 | 16458ms |
| 175 | `d3d255b2…` | Real Estate and Rental | Real Estate Sales  | ✅ success | - | 2 | 9/10 | 11584ms |
| 176 | `403b9234…` | Government | Recreation Workers | ✅ success | - | 1 | 8/10 | 8577ms |
| 177 | `1bff4551…` | Government | Recreation Workers | ✅ success | - | 2 | 4/10 | 11304ms |
| 178 | `650adcb1…` | Government | Recreation Workers | ✅ success | - | 1 | 6/10 | 13312ms |
| 179 | `01d7e53e…` | Government | Recreation Workers | ❌ error | Yes | 0 | - | 16522ms |
| 180 | `a73fbc98…` | Government | Recreation Workers | ✅ success | Yes | 2 | 8/10 | 14402ms |
| 181 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 9/10 | 12709ms |
| 182 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 8/10 | 12571ms |
| 183 | `dd724c67…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 6/10 | 15435ms |
| 184 | `7151c60a…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | 4/10 | 13073ms |
| 185 | `90edba97…` | Health Care and Social | Registered Nurses | ✅ success | - | 1 | 3/10 | 8102ms |
| 186 | `91060ff0…` | Retail Trade | Pharmacists | ✅ success | - | 4 | 9/10 | 22307ms |
| 187 | `8384083a…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 7/10 | 10839ms |
| 188 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | 8/10 | 14200ms |
| 189 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | 3/10 | 5522ms |
| 190 | `ffed32d8…` | Retail Trade | Pharmacists | ❌ error | Yes | 0 | - | 14950ms |
| 191 | `b3573f20…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 7/10 | 9725ms |
| 192 | `a69be28f…` | Wholesale Trade | Sales Managers | ✅ success | - | 13 | 9/10 | 25656ms |
| 193 | `788d2bc6…` | Wholesale Trade | Sales Managers | ✅ success | - | 9 | 9/10 | 38138ms |
| 194 | `74ed1dc7…` | Wholesale Trade | Sales Managers | ✅ success | - | 1 | 6/10 | 15284ms |
| 195 | `69a8ef86…` | Wholesale Trade | Sales Managers | ✅ success | - | 2 | 9/10 | 14507ms |
| 196 | `ab81b076…` | Wholesale Trade | Sales Representati | ✅ success | - | 3 | 9/10 | 12822ms |
| 197 | `d7cfae6f…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 1 | 4/10 | 16533ms |
| 198 | `19403010…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 13338ms |
| 199 | `7ed932dd…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 12273ms |
| 200 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 4/10 | 13276ms |
| 201 | `b57efde3…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 2/10 | 23472ms |
| 202 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | 3/10 | 14455ms |
| 203 | `bb863dd9…` | Wholesale Trade | Sales Representati | ✅ success | - | 1 | 9/10 | 12372ms |
| 204 | `fe0d3941…` | Wholesale Trade | Sales Representati | ✅ success | Yes | 2 | 4/10 | 17938ms |
| 205 | `6a900a40…` | Wholesale Trade | Sales Representati | ❌ error | Yes | 0 | - | 14890ms |
| 206 | `9efbcd35…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 6/10 | 10253ms |
| 207 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 2 | 4/10 | 24372ms |
| 208 | `4de6a529…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 1 | 4/10 | 12865ms |
| 209 | `4c4dc603…` | Finance and Insurance | Securities, Commod | ✅ success | Yes | 1 | 9/10 | 13563ms |
| 210 | `bb499d9c…` | Finance and Insurance | Securities, Commod | ✅ success | - | 1 | 8/10 | 23953ms |
| 211 | `5349dd7b…` | Manufacturing | Shipping, Receivin | ✅ success | Yes | 1 | 6/10 | 10548ms |
| 212 | `a4a9195c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | 6/10 | 9647ms |
| 213 | `552b7dd0…` | Manufacturing | Shipping, Receivin | ✅ success | - | 3 | 8/10 | 13333ms |
| 214 | `11dcc268…` | Manufacturing | Shipping, Receivin | ❌ error | Yes | 0 | - | 7022ms |
| 215 | `76418a2c…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | 3/10 | 9458ms |
| 216 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 3 | 6/10 | 16970ms |
| 217 | `7de33b48…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 7028ms |
| 218 | `854f3814…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 1599ms |
| 219 | `4122f866…` | Professional, Scientif | Software Developer | ❌ error | Yes | 0 | - | 17121ms |
| 220 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | 8/10 | 17287ms |

## QA Issues

### ✅ `7d7fc9a7…` — score 6/10
- Summary ending balances do not match the provided GL balances.
- Prepaid Insurance schedule appears to have incorrect ending balance reconciliation.
- Text response is generic and does not confirm completed workbook details.
  > 💡 Verify all reconciliations and provide a concise completion summary.

### ✅ `43dc9778…` — score 6/10
- No actual Form 1040 or required schedules are shown in the package.
- Text says 'likely' attachments, not confirmed completed e-file forms.
- Workpaper summary is included, but not requested as a deliverable.
  > 💡 Provide the completed 1040 PDF with all required schedules and forms.

### ✅ `ee09d943…` — score 6/10
- No evidence the workbook was actually updated with April source data.
- Text response claims validation without showing completed schedules or TOC changes.
- Potentially missing required April tabs or documented exceptions.
  > 💡 Verify all April tabs, updates, and TOC entries are completed and reflected in the workbook.

### ❌ `f84ea6ac…` — score 4/10
- Output lacks the required five study details in the visible content.
- Text response is generic and does not summarize findings or implications.
- File preview suggests incomplete or truncated table content.
  > 💡 Provide a complete one-page table with five fully summarized post-2020 open-access studies.

### ✅ `27e8912c…` — score 6/10
- Checklist is only one page, not a full five-page PDF.
- Word document lacks a visible action-item tracking table.
- Checklist text shows formatting errors in keyboard and mouse section.
  > 💡 Revise the PDF layout, add the required tracking table, and fix text formatting errors.

### ❌ `c44e9b62…` — score 4/10
- Reduction totals appear below the required 4% target.
- Briefing note preview is truncated and may omit required alignment details.
- FTE report shows generic 'Supervisor' rows, reducing clarity by position title.
  > 💡 Revise the package to clearly exceed 4% and ensure all deliverables specify exact position-level reductions.

### ✅ `99ac6944…` — score 8/10
- PDF is only three pages, but the task requested a full one-stop document.
- The mixer choice may not fully satisfy independent vocal mix and onboard compression requirements.
- The cost breakdown image and spreadsheet details are present, but retailer links are not clearly verified.
  > 💡 Add explicit retailer links and confirm the mixer supports the required processing and routing.

### ✅ `38889c3b…` — score 6/10
- No evidence the files are exactly 2:17 long.
- Bridge stem naming is ambiguous and may not match required stem set.
- Text mentions an unrelated ADSR error correction.
  > 💡 Verify duration, stem contents, and remove irrelevant commentary.

### ✅ `4b894ae3…` — score 6/10
- Deliverable name uses spaces instead of the requested underscore format.
- A DOCX summary was added, which was not requested.
- No evidence confirms the bass edits match all reference spots.
  > 💡 Rename the WAV to the exact required filename and verify all edit spots were applied.

### ✅ `1b1ade2d…` — score 6/10
- Missing the requested Python script file.
- Workflow draft is high-level and lacks detailed approval trail requirements.
- Text response promises a script not actually produced.
  > 💡 Add the script and expand the workflow with explicit traceability and signoff steps.

### ✅ `93b336f3…` — score 8/10
- Cost section is truncated in the preview, limiting verification of calculations.
- No obvious file type or content errors were detected.
- The document appears professional and aligned to the procurement brief.
  > 💡 Verify the full cost table and assumptions are clearly shown in the final document.

### ✅ `15ddd28d…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit evidence of final negotiation ask or decision criteria.
- File content appears professional and aligned, but exact page length is unconfirmed.
  > 💡 Verify the full document includes a clear ask, decision criteria, and 2–3 page length.

### ✅ `05389f78…` — score 6/10
- Report preview is truncated, so completeness cannot be verified.
- No evidence the email includes all required recipients and termination language.
- No attached quote file analysis is visible for exact calculations.
  > 💡 Verify full document content, recipient details, and quotation-based calculations before submission.

### ✅ `a74ead3b…` — score 8/10
- Text response mentions validation step not requested.
- Cannot verify slide content closely matches manual from preview.
- No obvious missing required file types.
  > 💡 Review slide content against the manual for tighter alignment.

### ✅ `bbe0a93b…` — score 6/10
- Spanish PDF preview is truncated, so completeness cannot be verified.
- Resource guide omits some requested categories like education and financial literacy.
- Assessment form lacks visible bilingual content in the English PDF.
  > 💡 Provide fully verified bilingual assessment PDFs and expand the resource guide to cover all requested categories.

### ✅ `36d567ba…` — score 7/10
- PDF preview is truncated, so full compliance cannot be verified.
- No evidence the Word document is 1-2 pages exactly.
- Text response mentions a PDF, which was not requested.
  > 💡 Provide the complete 1-2 page Word tool and ensure all required topics and citations are fully visible.

### ✅ `4c18ebae…` — score 6/10
- Output omits the required narrative SAR details and subject analysis.
- Excel content appears generic and may not fully reflect the case facts.
- Text response promises files but does not summarize key findings professionally.
  > 💡 Include a concise SAR narrative with subjects, typologies, and transaction examples.

### ✅ `c2e8f271…` — score 8/10
- PDF preview is truncated, so full content cannot be fully verified.
- No explicit evidence of the 6-page limit being enforced beyond the preview.
- Text response mentions validation, but file content validation details are not shown.
  > 💡 Provide the full document preview or page count confirmation for complete verification.

### ✅ `2ea2e5b5…` — score 6/10
- Missing evidence that the source workbook was actually used.
- Original task text is truncated in the strategic level section.
- No verification of slide content or table accuracy is provided.
  > 💡 Confirm workbook-driven mappings and validate the PPTX contents against all required categories.

### ✅ `a45bc83b…` — score 8/10
- Text response is brief and not fully professional.
- POC document may not explicitly mirror all requested source details.
- Diagram content cannot be fully verified from preview.
  > 💡 Review the documents for completeness, style alignment, and explicit requirement coverage.

### ✅ `a10ec48c…` — score 6/10
- No actual restaurant tables are visible in the preview.
- Restaurant details and links cannot be verified from the provided content.
- Text response is professional but only describes the document, not its contents.
  > 💡 Verify the document contains complete tables with sourced restaurant data and clickable links.

### ✅ `fccaa4a1…` — score 8/10
- PDF text preview is slightly truncated at the end.
- Tour operator details are brief and not deeply sourced.
- No explicit confirmation of royalty-free image source is shown.
  > 💡 Verify the final PDF includes complete sourced details and image attribution.

### ✅ `f5d428fd…` — score 6/10
- PDF is five pages, not the requested two pages.
- The itinerary appears incomplete in the preview, with Day 6 text truncated.
- No verified evidence is shown for royalty-free image sourcing.
  > 💡 Condense to two pages, complete all seven days, and document image sources clearly.

### ❌ `2fa8e956…` — score 2/10
- Document lacks winery details and required comparisons.
- No hours, addresses, phones, distances, or drive times included.
- Only a title and intro paragraph are present.
  > 💡 Rebuild the document with complete winery entries and required formatting.

### ✅ `0e4fe8cd…` — score 7/10
- Day 2 preview is truncated, so completeness cannot be fully verified.
- No evidence of factual online links being populated for all entities.
- Potentially missing the full four-day itinerary details in the preview.
  > 💡 Verify all four sheets contain complete, linked, and fully populated itinerary entries.

### ✅ `aa071045…` — score 6/10
- Service form preview lacks customer, agreement, mileage, and charge details.
- Request type and vehicle status are not shown in the preview.
- Text response is duplicated and not fully professional.
  > 💡 Include all required form fields and provide a concise, non-duplicated summary.

### ❌ `61f546a8…` — score 4/10
- No actual report content is provided in the text response.
- The response mentions Python code, which was not requested.
- The PDF content appears to have formatting and spacing errors.
  > 💡 Provide a complete, polished PDF report with the required two sections only.

### ✅ `f3351922…` — score 8/10
- Text response mentions file creation instead of providing the email content.
- Preview is truncated, so completeness cannot be fully verified.
- No obvious formatting or content errors in the visible email draft.
  > 💡 Provide the full email text directly in the response and ensure all requested details are included.

### ✅ `61717508…` — score 6/10
- Training deck content was not fully verified from the preview.
- Role-play PDF is only 2 pages, not the requested ~10-page deck.
- No evidence the Senior Safe Act and FINRA Rule 2165 were clearly summarized.
  > 💡 Review the deck for length, required legal summaries, and complete content coverage.

### ✅ `0ed38524…` — score 8/10
- Talking points content is truncated in the preview.
- No direct verification of exact district-by-district completeness.
- Text response is generic rather than summarizing findings.
  > 💡 Confirm the talking points include all district themes and specific constituent concerns.

### ❌ `87da214f…` — score 3/10
- No evidence the deck includes required analysis or financial figures.
- Text response is only a file-creation statement, not a complete summary.
- Cannot verify agenda, purpose, remediation, or policy update content from preview.
  > 💡 Provide a content summary confirming all required slide elements and key findings.

### ❌ `d025a41c…` — score 4/10
- Output is only a summary, not the required case feedback content.
- Case Two and Case Three content appears truncated or incomplete.
- No verification of bold headings or 1.5 spacing in the document.
  > 💡 Provide the full Word document with complete case analyses and formatting.

### ✅ `401a07f1…` — score 6/10
- DOCX text appears truncated and ends mid-sentence.
- Reference links are mentioned but not visibly included in the preview.
- Word count may be below the requested 500 words.
  > 💡 Provide a complete 500-word editorial with explicit source links and a finished ending.

### ✅ `afe56d05…` — score 6/10
- Text response is not the required JSON-only QA output.
- File preview is truncated, so completeness cannot be fully verified.
- No clear validation of word count or hyperlink accreditation is shown.
  > 💡 Provide a concise JSON assessment and verify the document fully meets all content requirements.

### ✅ `9a8c8e28…` — score 7/10
- PDFs and source files were produced, but the checklist content was not fully verified.
- The guide preview is truncated, so some required sections may be missing.
- No clear evidence of the quiz answer key, explanations, or scoring guide in the preview.
  > 💡 Confirm the full guide, checklist, and quiz include all required sections and answer materials.

### ✅ `3a4c347c…` — score 6/10
- Missing detailed story ideas and named contributors.
- No explicit 4-week publication and broadcast schedule shown.
- KPIs and sponsorship success measure are not fully specified.
  > 💡 Add the missing sections with specific contributors, dates, and measurable KPIs.

### ✅ `ec2fccc9…` — score 6/10
- Word count and full content could not be verified from the preview.
- Reference links and artist profile targets are not fully confirmable.
- Text response is repetitive and not clearly complete.
  > 💡 Verify the DOCX includes all required sections, links, and target length before delivery.

### ❌ `e222075d…` — score 4/10
- No actual video edit or MP4 file was produced.
- Deliverables are documents only, not the required broadcast spot.
- Response promises local generation instead of completed media.
  > 💡 Produce the 30-second H.264 MP4 and include complete source logs.

### ❌ `c94452e4…` — score 3/10
- No actual 15-second MP4 was produced.
- Only planning documents were delivered, not the broadcast spot.
- Required stock footage and music were not sourced or assembled.
  > 💡 Produce the final 1920x1080 H.264 spot with licensed media and exact 15-second timing.

### ❌ `75401f7c…` — score 4/10
- No evidence the required opening and closing logo shots were used.
- No confirmation of required sound effects or embedded audio placement.
- Text response mentions an extra QC log file not requested.
  > 💡 Verify the edit includes all specified shots, audio cues, and exact runtime constraints.

### ✅ `8079e27d…` — score 6/10
- Workbook has only 70 company rows, not all 500 S&P 500 constituents.
- SubSectors sheet preview is truncated and may omit required market cap and index share fields.
- Text response mentions a blocked web request instead of summarizing delivered analysis.
  > 💡 Expand the workbook to all 500 constituents and verify every required column is present on both sheets.

### ✅ `e21cd746…` — score 8/10
- Some private target details are truncated in the preview.
- No obvious errors in file types or slide count.
- Public comps appear included, but exact valuation tables are not fully visible.
  > 💡 Verify the full deck for completeness and exact company data before sending.

### ✅ `9e8607e7…` — score 8/10
- Deck is 22 pages, below the requested roughly 30 slides.
- Text response mentions PPTX conversion, but the task asked for PDF export.
- No obvious placeholder content, but the deck may be slightly short for a half-hour discussion.
  > 💡 Expand to about 30 slides and ensure the PDF is the primary deliverable.

### ✅ `c7d83f01…` — score 6/10
- No Python notebook file was produced.
- Finite-difference results show severe numerical instability.
- Summary appears truncated and incomplete.
  > 💡 Provide the notebook and stabilize the finite-difference implementation before resubmitting.

### ✅ `a1963a68…` — score 6/10
- Public web research was not directly fetched, weakening source robustness.
- The deck includes extra deliverables beyond the requested PDF presentation.
- Content preview suggests some slides may be truncated or overly generic.
  > 💡 Rebuild the PDF with fully sourced, detailed slides and remove unnecessary extra files.

### ✅ `b78fd844…` — score 6/10
- Only 2 pages; may not meet the 15-page report expectation.
- The allocation section appears truncated in the preview.
- No evidence of full detailed analysis beyond directional estimates.
  > 💡 Provide a complete, non-truncated board report with all required sections.

### ✅ `3f821c2d…` — score 6/10
- Text response is generic and does not confirm target turn or EOM compliance.
- Workbook preview shows blank EOM Inventory and Turn formulas may be missing.
- No evidence the LY comparison is fully formatted side by side.
  > 💡 Verify formulas, targets, and side-by-side LY formatting in the workbook.

### ✅ `e996036e…` — score 6/10
- Only three quarters are shown; Q4 data appears missing.
- Written summary paragraph is not visible in the preview.
- Scenario favorability visual is not verifiable from the provided content.
  > 💡 Confirm the workbook includes all quarterly data, the summary paragraph, and a clear favorability chart.

### ❌ `327fbc21…` — score 3/10
- Workbook targets -15% but actual total is -28.0%.
- No evidence of required 61-63% weekly weighting validation.
- Response is generic and omits the required summary details.
  > 💡 Revise the workbook to meet target percentages and include the required summary.

### ❌ `6dcae3f5…` — score 4/10
- Text response promises an email draft, but task requested Excel analysis deliverable.
- No evidence the benchmark calculations or PGY requirement mapping were completed.
- Output may omit required resident-level identification of when requirements were met.
  > 💡 Verify the workbook contains all calculations, requirement mappings, and resident-level results.

### ✅ `1aecc095…` — score 7/10
- Email content is truncated in the preview.
- No evidence the email is 100-150 words.
- Visio-style visual may not be fully verified from preview.
  > 💡 Verify the email length and review the visual layout against the requested workflow.

### ✅ `0353ee0c…` — score 6/10
- PDF preview is truncated, so completeness cannot be verified.
- No evidence the guide exhaustively consolidates all 19 source links.
- Text response adds filing resources not confirmed in the task sources.
  > 💡 Verify all source links were fully incorporated and remove any unsupported additions.

### ❌ `40a8c4b1…` — score 4/10
- Text response promises validation, but no evidence is provided.
- Schedule may not fully verify required priorities and holiday exclusions.
- No confirmation that unused optional topics were highlighted.
  > 💡 Provide a brief completion summary with explicit checks for required events, dates, and formatting.

### ❌ `4d1a8410…` — score 4/10
- Files appear to contain only headings, not the required detailed schedule.
- Personal itineraries lack the requested one-page applicant-specific timing details.
- Text response mentions photos and logos not requested in the task.
  > 💡 Populate the documents with full timing tables and applicant-specific itineraries.

### ✅ `8c823e32…` — score 6/10
- Text response is only a summary, not the completed policy.
- File content preview appears truncated and may omit required sections.
- No evidence of a fully formatted, review-ready PDF policy document.
  > 💡 Provide the full policy text with all required sections and verify the PDF is complete.

### ✅ `eb54f575…` — score 6/10
- PDF is only 2 pages and the preview shows truncated content.
- Ballistics section appears incomplete in the file preview.
- No evidence the report fully addresses all five required sections.
  > 💡 Provide the complete five-section report with full ballistics justification in the PDF.

### ❌ `11e1b169…` — score 4/10
- PDF is only one page, not the required two pages.
- The PDF preview appears truncated and may omit required legal content.
- Text response mentions source document generation, which was not requested.
  > 💡 Revise the PDF to two complete pages covering every required topic clearly.

### ❌ `efca245f…` — score 4/10
- Scenario 3 capacity is inconsistent with the task's 10-hour shift requirement.
- The workbook preview suggests incomplete validation of all scenario outputs.
- The response does not confirm stat holiday handling or May 1 timing compliance.
  > 💡 Verify each scenario against the task constraints and correct the production assumptions.

### ✅ `9e39df84…` — score 6/10
- Week 1 rows for Operator 1 are blank in the data table.
- Dashboard KPI cells appear incomplete or empty.
- Text response says Dashboard Output.xlsx, but file is named Dashboard Output.xlsx.
  > 💡 Populate all Week 1 data and verify dashboard formulas, charts, and KPI outputs.

### ❌ `1752cb53…` — score 4/10
- No evidence the workbook was actually populated correctly.
- Text response is generic and omits specific plan details.
- File content preview suggests many blank planning cells remain.
  > 💡 Verify all yellow cells are completed and the workbook matches the planning rules exactly.

### ❌ `d4525420…` — score 4/10
- No 5–7 sentence paragraph was provided.
- Response describes files instead of selecting an employee.
- Selection rationale and final recommendation are missing.
  > 💡 Provide a concise paragraph naming the chosen employee and explaining the leadership-focused decision.

### ✅ `cecac8f9…` — score 7/10
- Preparation plan was produced as DOCX, not PDF.
- Launch deck PDF exists, but the plan PDF is missing.
- Text response incorrectly states the plan was converted to PDF.
  > 💡 Regenerate the preparation plan as a PDF and update the response to match the delivered files.

### ✅ `6436ff9e…` — score 8/10
- File content appears truncated in preview.
- Instructor evaluation could be more specific.
- Marketing consent and media permissions may need clearer separation.
  > 💡 Add explicit rating scales and separate consent items for marketing, testimonials, and media use.

### ✅ `40a99a31…` — score 8/10
- Report preview is truncated; full section completeness is unverified.
- AMR payload claim may need validation against the 220 kg requirement.
- No explicit confirmation of six camera placements in the text response.
  > 💡 Verify the report and layout explicitly document all six cameras and the AMR payload.

### ❌ `b9665ca1…` — score 4/10
- Missing evidence the schematic matches all specified wiring details.
- Text response is generic and omits key circuit configuration specifics.
- No verification of correct relay pinout or button-box labeling shown.
  > 💡 Revise the schematic to explicitly show every required connection and label.

### ✅ `c6269101…` — score 6/10
- Requested PDF was not produced; a DOCX report was generated instead.
- Capability thresholds were not explicitly provided, yet capability indices were interpreted.
- The deck content cannot be verified from the preview for completeness.
  > 💡 Regenerate the report as PDF and ensure capability conclusions are clearly tied to provided criteria.

### ✅ `be830ca0…` — score 6/10
- No evidence the PPTX includes all required slide content.
- Text response is generic and lacks analysis results.
- Final timeline and tollgate status are not verified.
  > 💡 Verify slide contents and include explicit statistical findings in the presentation.

### ❌ `cd9efc18…` — score 4/10
- PDF is only 4 pages, not the requested 8-11 pages.
- Trustee/guardian provisions appear incomplete in the preview.
- Text response promises validation, but no validation evidence is shown.
  > 💡 Expand the will to include all requested trust and guardianship terms and meet the page target.

### ✅ `a97369c7…` — score 6/10
- Output is not a memo; it only describes producing files.
- No actual legal analysis is provided in the text response.
- The response omits the required brief primer content.
  > 💡 Provide the memo’s substantive analysis directly in the response and ensure it addresses all three issues.

### ✅ `3f625cb2…` — score 6/10
- The memo content is truncated in the preview, so completeness cannot be confirmed.
- No evidence the PDF stays within the three-page limit.
- The text response promises delivery but does not summarize the legal findings.
  > 💡 Provide the full three-page memo with clear legal conclusions and confirm page count.

### ✅ `aad21e4c…` — score 7/10
- Text response promises a file but omits substantive confirmation of completed drafting.
- Preview suggests the agreement may be incomplete or truncated.
- No explicit verification of all requested investor rights and consent provisions.
  > 💡 Confirm the document fully includes all requested terms and provide a complete content check.

### ✅ `8314d1b1…` — score 6/10
- Preview is truncated, so completeness and citations cannot be fully verified.
- No confirmation the memo stays within 3,500 words.
- March 2025 DGCL § 144 analysis may be incomplete or inaccurate.
  > 💡 Verify the full memo text, word count, and statutory analysis before delivery.

### ❌ `5e2b6aab…` — score 4/10
- No ZIP file is provided for STEP files over five components.
- Required sub-assembly PDF for the head module is missing.
- SCAD files are included, but the task requested STEP models and PDFs only.
  > 💡 Provide the missing head sub-assembly drawing and ensure all required STEP files are properly packaged.

### ❌ `46fc494e…` — score 4/10
- Back-face temperature is constant at 25 C, suggesting a likely modeling error.
- Required 20-minute node profile file is missing; only 200min appears produced.
- Mitigation guidance is unnecessary because the reported margin is far above 10 C.
  > 💡 Recompute the transient model and verify all requested time-point outputs and file names.

### ✅ `3940b7e7…` — score 6/10
- Report text is truncated in the preview, suggesting incomplete content.
- Boundary conditions and simulation environment lack specific numerical details.
- Extracted metrics sheet shows blank values for several key metrics.
  > 💡 Regenerate the report with complete, fully populated tables and explicit CFD setup details.

### ❌ `8077e700…` — score 4/10
- Report omits AISI 1045 results and comparison.
- Several key values are missing or blank in the PDF.
- Only one trend figure is produced, not all required graphs.
  > 💡 Revise the report to include complete 1018 and 1045 analyses, filled tables, and all supporting figures.

### ✅ `5a2d70da…` — score 6/10
- Only two Excel files were produced; the required emai is missing.
- Manufacturing steps workbook appears incomplete for the full task scope.
- No evidence the budget and sales tax were validated against the $7,500 limit.
  > 💡 Add the missing email and verify all deliverables, costs, and tax calculations.

### ✅ `61b0946a…` — score 6/10
- Output is truncated in the preview, so completeness is uncertain.
- The proposal may omit required detailed procedure estimates by participation scenario.
- No evidence the graph or document fully matches the original task's scope.
  > 💡 Verify the full document includes all requested analyses and complete, non-truncated content.

### ✅ `c9bf9801…` — score 6/10
- Guide appears only 3 pages and may be too brief.
- Linked template references are not verifiable in the guide.
- Evaluation forms are referenced but not produced as files.
  > 💡 Expand the guide and confirm all required linked documents and evaluation forms are included.

### ✅ `f1be6436…` — score 6/10
- Missing detailed flight and transportation specifics in the document.
- No discretionary-fund calculation or department coverage breakdown shown.
- Task text appears incomplete regarding return transportation arrangements.
  > 💡 Add full itemized totals, funding allocation, and complete travel details with dated screenshots.

### ❌ `6d2c8e55…` — score 4/10
- Missing one article PDF for each month.
- Schedule file content is not fully verifiable from preview.
- Output text does not confirm all task requirements were completed.
  > 💡 Provide all nine accessible article PDFs and verify the schedule against the source files.

### ✅ `4b98ccce…` — score 7/10
- No visible sign-off beneath the Excel tables.
- Letter content cannot be verified from the preview.
- Text response omits the employee name and ID details.
  > 💡 Verify the workbook sign-offs and letter text include all required template and HIPAA elements.

### ✅ `ef8719da…` — score 6/10
- File content appears truncated in the preview.
- No visible hyperlinks confirmed in the provided text.
- Need clearer evidence of draft timeline and source balance.
  > 💡 Verify the full document includes all required sections and working links.

### ✅ `3baa0009…` — score 6/10
- No evidence the article is 300-500 words.
- Chart data for 2024, 2025, and 2027 is not verified.
- Text response is a process note, not the deliverable itself.
  > 💡 Provide the final article text and confirm the chart matches the requested World Bank figures.

### ❌ `5d0feb24…` — score 4/10
- Response ignores the requested QA evaluation and only describes a deliverable.
- No assessment of file completeness, accuracy, or missing requirements is provided.
- The output is not a concise inspection result as required.
  > 💡 Provide a brief JSON verdict evaluating the deliverable against the task requirements.

### ✅ `6974adea…` — score 6/10
- Preview is truncated, so full word count and structure cannot be verified.
- No evidence the article meets the 1,000-1,500 word requirement.
- Word document content quality and Guardian style compliance are not fully confirmable.
  > 💡 Provide the full document text and verify length, headings, and style compliance.

### ✅ `1a78e076…` — score 6/10
- File content appears truncated in preview, so completeness is uncertain.
- No evidence of the required 10-15 page length or reference count.
- Text response is generic and does not confirm all requested analyses were completed.
  > 💡 Verify the full document includes all required sections, analyses, and reference limits.

### ✅ `0112fc9b…` — score 6/10
- Text response promises a DOCX but does not provide the SOAP note content.
- Plan appears incomplete in the preview and may omit full follow-up instructions.
- No clear confirmation that all required clinical details were fully addressed.
  > 💡 Provide the complete SOAP note content and verify all required sections are fully included.

### ❌ `772e7524…` — score 4/10
- Text response does not provide the SOAP note itself.
- Deliverables are files only, not a complete written response.
- Preview shows OCR-like errors and truncated content.
  > 💡 Provide a complete, polished SOAP note in the response and ensure clean file content.

### ✅ `e6429658…` — score 6/10
- Appeal letter is only 2 pages, not 2-4 pages long.
- AbbVie application was saved as XLSX, not a completed form file.
- Text response does not mention the required manufacturer assistance application completion.
  > 💡 Regenerate the assistance form in the correct format and verify all task requirements.

### ✅ `1137e2bb…` — score 6/10
- Word summary is truncated and contains an incomplete sentence.
- SKU-level summary lacks explicit PO-level drilldown detail.
- No evidence the workbook includes a true pivot or drilldown capability.
  > 💡 Complete the summary text and verify the summary tab supports PO-level drilldown.

### ✅ `664a42e5…` — score 6/10
- No side-by-side comparison is shown in the preview.
- The text response mentions a PDF handout, not just the requested presentation.
- The presentation content cannot be verified from the preview alone.
  > 💡 Add the missing comparison slide and ensure the deck fully covers every required ILIT topic.

### ✅ `feb5eefc…` — score 6/10
- PDF is only 3 pages, not the requested 12 or fewer with fuller analysis.
- Text response is a placeholder and does not summarize the actual recommendation.
- CRAT details appear truncated in the preview, risking incomplete coverage.
  > 💡 Revise the report to fully address all requirements and provide a substantive summary.

### ✅ `3600de06…` — score 8/10
- Preview is truncated, so full slide compliance cannot be fully verified.
- Text response promises a PDF, but no detailed content summary is provided.
- No explicit citation detail is visible for FINRA and NAIC source use.
  > 💡 Verify all 10 slides include sourced FINRA and NAIC guidance with clear advisor talking points.

### ✅ `f9f82549…` — score 6/10
- PDF title matches, but flowchart title requirement is inconsistent.
- PPTX content cannot be verified from preview.
- Text response promises validation not evidenced by files.
  > 💡 Align titles exactly and ensure the PPTX clearly maps each flowchart header to incident details.

### ✅ `84322284…` — score 6/10
- Text response only states intent, not the completed report.
- PDF content appears incomplete and may be truncated.
- Timeline and recommendations are present, but analysis is limited.
  > 💡 Provide a fully written report with clearer analysis and verified complete PDF content.

### ✅ `6241e678…` — score 5/10
- Missing required client tasks and approvals from the task list.
- Schedule appears to omit or alter required phase durations and revision counts.
- Text response claims extra files not requested and lacks deliverable-specific detail.
  > 💡 Align the schedule exactly to all listed tasks, durations, and client review periods.

### ✅ `e4f664ea…` — score 6/10
- Response promises file generation instead of delivering the screenplay content.
- Preview shows a truncated screenplay, suggesting incomplete output.
- Minor formatting error: 'CONTINUO' appears truncated.
  > 💡 Provide the complete screenplay in proper format and verify all files are fully generated.

### ❌ `02aa1805…` — score 2/10
- Workbook lacks extracted well data and required screening results.
- Potential Wells tab is empty, so no recommendations were identified.
- Email draft is generic and does not name top viable wells.
  > 💡 Populate the workbook with actual factsheet data and specific recommended wells.

### ✅ `fd6129bd…` — score 6/10
- SOP preview is truncated, so completeness cannot be fully verified.
- Change Request Form content appears minimal and may lack required fields.
- Text response is generic and does not confirm final deliverable completion.
  > 💡 Provide full document content and verify the form includes all required fields.

### ❌ `ce864f41…` — score 4/10
- No brief responses to the three questions were provided.
- The workbook content was not verified beyond the filename.
- The text response promises validation but gives no findings.
  > 💡 Include concise answers to all three questions and confirm workbook contents.

### ✅ `58ac1cc5…` — score 6/10
- Change control PDF content appears truncated in the preview.
- No explicit evidence the risk assessment is a separate Word document with required mitigation details.
- Internal summary note content was not previewed for completeness.
  > 💡 Verify the full documents include all required sections, actions, and final disposition language.

### ❌ `3c19c6d1…` — score 4/10
- Missing evidence that slide 4 uses the required tabular summary.
- No verification of required slide content or exact section titles.
- Text response is generic and does not confirm report completeness.
  > 💡 Review the deck against each required slide and confirm exact content.

### ✅ `55ddb773…` — score 6/10
- Preview is truncated, so completeness cannot be fully verified.
- No evidence the form includes every required violation detail from the attachment.
- Text response promises verification, but no verification result is shown.
  > 💡 Provide the full form content and confirm all required violation categories are included.

### ❌ `1e5a1d7f…` — score 4/10
- DOCX preview shows no table content.
- Required columns are not visible in the file preview.
- Text response promises a Python script not listed as produced.
  > 💡 Add the full table with all required columns and verify all deliverables are included.

### ✅ `0419f1c3…` — score 8/10
- Preview is truncated, so full completeness cannot be fully verified.
- PDF and DOCX were produced, but content quality beyond preview is uncertain.
  > 💡 Confirm the full document includes all required sections and complete signature lines.

### ✅ `ed2bc14c…` — score 6/10
- File content appears truncated in the preview.
- Communication plan details are incomplete in the visible document.
- Community event description is cut off before completion.
  > 💡 Verify the full Word document includes all required sections and complete details.

### ✅ `46bc7238…` — score 8/10
- Preview shows no obvious missing required sections.
- File content appears professional and on-task.
- Stock photo inclusion cannot be fully verified from preview.
  > 💡 Verify all pages include free stock photos and final PDF formatting.

### ✅ `2d06bc0a…` — score 9/10
- Minor typo in property address spelling may remain.
- Closing extension deposit wording is slightly awkward.
  > 💡 Verify the final document for address accuracy and polish the extension clause language.

### ❌ `0818571f…` — score 3/10
- No live June 2025 listings were sourced from Crexi or LoopNet.
- Files are templates with TBD placeholders, not completed acquisition opportunities.
- Required photos, maps, tenant mix, and transaction metrics are missing.
  > 💡 Populate the report with verified active listings and complete all property-level details.

### ❌ `11593a50…` — score 4/10
- Map PDF lacks visible property pins and spread details.
- Summary CSV shows wrong city and zip values.
- List date is N/A for all homes.
  > 💡 Correct the listing data and regenerate the map with clearly pinned properties.

### ❌ `94925f49…` — score 4/10
- Reports are only one page each, not clearly PDF reports with full required detail.
- No evidence of live reputable school or real estate source usage.
- Home listings appear placeholder-like and may not be verified current listings.
  > 💡 Regenerate the reports with sourced, current school data and verified nearby listings.

### ✅ `90f37ff3…` — score 8/10
- PDF preview is truncated, so full content cannot be fully verified.
- No explicit source citations or dates are visible in the preview.
- Recommendation wording varies slightly between $30.50 and $29.50 per SF.
  > 💡 Align the final recommended rate consistently and add clear comp source dates.

### ❌ `1bff4551…` — score 4/10
- Missing YouTube links for every song.
- Set list omits required research on collection representation.
- Output includes a DOCX file, not only the requested PDF.
  > 💡 Add song links and collection-based context, then deliver only the finalized PDF.

### ✅ `650adcb1…` — score 6/10
- No evidence the sixth time-off tab is included.
- Coverage gaps are not clearly summarized in the workbook.
- Text response is generic and omits validation of requested dates.
  > 💡 Add the missing request tab and a clear coverage summary with all understaffed dates.

### ✅ `116e791e…` — score 8/10
- File preview is truncated, so the third diagnosis cannot be fully verified.
- Text response is generic and does not confirm all required care plan elements.
- No obvious formatting or file-type errors were detected.
  > 💡 Verify the full PDF includes three complete diagnoses with all required outcomes, assessments, and interventions.

### ✅ `dd724c67…` — score 6/10
- TFU guide may not reflect the exact CMS methodology report wording.
- Facility list may be incomplete for all Long Island hospitals and rehabilitation facilities.
- Text response is generic and does not confirm research or completeness.
  > 💡 Verify all facilities and CMS timeframes against source documents, then update the workbook.

### ❌ `7151c60a…` — score 4/10
- Checklist lacks the required table format and document fields.
- Fax cover sheet is missing sender, recipient, date, subject, and page count fields.
- Text response is generic and does not confirm all required elements were included.
  > 💡 Revise both documents to include every required field and the checklist table format.

### ❌ `90edba97…` — score 3/10
- Output is only a narrative, not completed spreadsheet data entry.
- No patient-specific lab results or monthly treatment changes are shown.
- The response does not verify all required sheets and protocol actions were completed.
  > 💡 Populate the workbook with all patient monthly values and documented protocol-based changes.

### ✅ `8384083a…` — score 7/10
- PDF text is truncated in preview, so completeness cannot be fully verified.
- Ozempic days supply is presented as multiple values, which may confuse the standard package calculation.
- The response text is generic and does not confirm the required NDCs and formulas were included.
  > 💡 Revise the PDF to clearly show each medication’s exact NDC, package, formula, and single days-supply result.

### ✅ `045aba2e…` — score 8/10
- Monthly checklist preview is truncated, so full content cannot be verified.
- No explicit evidence of exact California lawbook or self-assessment citations.
- Text response promises validation, but validation details are not shown.
  > 💡 Provide full checklist content and cite the governing California references more explicitly.

### ❌ `f2986c1f…` — score 3/10
- No medications were identified from the image.
- Spreadsheet contains only NA values and one unknown type.
- MedlinePlus counseling links were not provided.
  > 💡 Identify each pill from the image and populate all required fields with source links.

### ✅ `b3573f20…` — score 7/10
- Preview is truncated, so page 3 completeness cannot be fully verified.
- Text response is generic and does not confirm the PDF content details.
- No explicit evidence of sufficient spacing or easy-completion layout.
  > 💡 Provide the full PDF text and confirm all three pages are complete and clearly formatted.

### ✅ `74ed1dc7…` — score 6/10
- File content appears truncated in the preview.
- Proposal details are incomplete in the visible content.
- Cannot verify all required order types and rationale are fully covered.
  > 💡 Provide the full document content and confirm all proposed order types are explicitly detailed.

### ❌ `d7cfae6f…` — score 4/10
- Text response is generic and does not confirm the workbook contents.
- The file appears to include duplicate brand rows without explanation.
- No evidence of a blank comments placeholder or correct Q1 2024 framing.
  > 💡 Verify the workbook matches all required sections, totals, and unique brand-level recaps.

### ❌ `105f8ad0…` — score 4/10
- Workbook appears to use placeholder benchmark values without source evidence.
- Rationale contains a concentration typo and repetitive wording.
- No proof of online research or September 2025 competitor pricing is included.
  > 💡 Add sourced competitor pricing, verify concentration labels, and document the benchmark calculations clearly.

### ❌ `b57efde3…` — score 2/10
- Only five records were reviewed, not the hundreds of exhibitors requested.
- Rows contain generic page text instead of real company leads and product details.
- The file appears to use placeholder/manual-review entries rather than verified exhibitor data.
  > 💡 Rebuild the spreadsheet from the official exhibitor list with verified company-specific leads and details.

### ❌ `15d37511…` — score 3/10
- Pricing values are missing, leaving the financial model incomplete.
- Spreadsheet contains placeholder zeros instead of required revenue and margin calculations.
- Memo notes missing source pricing details rather than delivering the requested analysis.
  > 💡 Rebuild the workbook using the exact email pricing and calculate all requested margins.

### ❌ `fe0d3941…` — score 4/10
- Physician questions contain text corruption and formatting errors.
- Survey pages are not clearly titled exactly as requested.
- Workflow presentation content cannot be verified from the preview.
  > 💡 Regenerate the survey with clean wording and verify the presentation includes all required slides.

### ✅ `9efbcd35…` — score 6/10
- Preview is truncated, so completeness cannot be fully verified.
- No evidence of source citations or MSCI data usage in the document.
- Text response is generic and does not confirm all required sections are included.
  > 💡 Verify the full DOCX includes all required sections, sources, and a concise four-page client-ready summary.

### ❌ `1d4672c8…` — score 4/10
- Fallback dataset used instead of MSCI website data.
- PDF content not verified from preview.
- Analysis may not reflect actual historical returns.
  > 💡 Replace fallback data with sourced MSCI data and regenerate both files.

### ❌ `4de6a529…` — score 4/10
- Text response promises a source script, but only the PDF is produced.
- Preview shows truncated content, so completeness cannot be verified.
- The deliverable may not fully satisfy the required detailed table formatting.
  > 💡 Provide the complete PDF content and include all requested deliverables.

### ✅ `bb499d9c…` — score 8/10
- Preview is truncated, so completeness cannot be fully verified.
- No explicit confirmation of the 25-page limit.
- Text response mentions a Python script, but only the DOCX file is listed.
  > 💡 Verify the full document length and include any promised supporting script if required.

### ✅ `5349dd7b…` — score 6/10
- FedEx extra large box is marked N/A, but analysis still needs explicit exclusion handling.
- Text response is generic and does not summarize findings or recommendations.
- Workbook appears complete, but the rate history row for FedEx has inconsistent formatting.
  > 💡 Revise the workbook notes and response to clearly document exclusions and key recommendations.

### ✅ `a4a9195c…` — score 6/10
- Document appears truncated in preview, so completeness cannot be fully verified.
- No explicit Word-format validation or page count confirmation is shown.
- Reference standard is cited, but alignment to IPC-A-610G is not demonstrated.
  > 💡 Verify the full DOCX content, page count, and compliance details before delivery.

### ❌ `76418a2c…` — score 3/10
- Excel manifest appears blank with no shipment data populated.
- No evidence of pick ticket processing or savings calculations.
- Text response promises a DOCX summary but does not confirm completed content.
  > 💡 Populate the manifest with all orders and verify calculated shipping methods and savings.

### ✅ `0e386e32…` — score 6/10
- Privacy logic is incomplete; zkSNARK unlinking is not fully evidenced.
- Yield generation via Aave is mentioned but not clearly verified in files.
- Cross-chain withdrawal implementation details are only described, not demonstrated.
  > 💡 Include explicit Aave, zkSNARK, and Connext implementation evidence in the codebase.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 1 file(s)
- `7d7fc9a7…` (Professional, Scientific, and Technical Services): 1 file(s)
- `43dc9778…` (Professional, Scientific, and Technical Services): 4 file(s)
- `ee09d943…` (Professional, Scientific, and Technical Services): 1 file(s)
- `f84ea6ac…` (Government): 2 file(s)
- `a328feea…` (Government): 2 file(s)
- `27e8912c…` (Government): 2 file(s)
- `17111c03…` (Government): 2 file(s)
- `c44e9b62…` (Government): 4 file(s)
- `99ac6944…` (Information): 5 file(s)
- `f9a1c16c…` (Information): 3 file(s)
- `38889c3b…` (Information): 6 file(s)
- `ff85ee58…` (Information): 2 file(s)
- `4b894ae3…` (Information): 2 file(s)
- `1b1ade2d…` (Manufacturing): 1 file(s)
- `93b336f3…` (Manufacturing): 1 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `24d1e93f…` (Manufacturing): 1 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `575f8679…` (Government): 1 file(s)
- `a74ead3b…` (Government): 4 file(s)
- `bbe0a93b…` (Government): 3 file(s)
- `76d10872…` (Government): 2 file(s)
- `36d567ba…` (Government): 2 file(s)
- `7bbfcfe9…` (Government): 1 file(s)
- `2696757c…` (Government): 2 file(s)
- `dfb4e0cd…` (Government): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `cebf301e…` (Professional, Scientific, and Technical Services): 2 file(s)
- `c2e8f271…` (Professional, Scientific, and Technical Services): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `c357f0e2…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a45bc83b…` (Professional, Scientific, and Technical Services): 5 file(s)
- `a10ec48c…` (Real Estate and Rental and Leasing): 1 file(s)
- `fccaa4a1…` (Real Estate and Rental and Leasing): 2 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 2 file(s)
- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
- `a0ef404e…` (Real Estate and Rental and Leasing): 1 file(s)
- `aa071045…` (Real Estate and Rental and Leasing): 2 file(s)
- `476db143…` (Real Estate and Rental and Leasing): 2 file(s)
- `61f546a8…` (Real Estate and Rental and Leasing): 1 file(s)
- `f3351922…` (Finance and Insurance): 2 file(s)
- `61717508…` (Finance and Insurance): 4 file(s)
- `0ed38524…` (Finance and Insurance): 2 file(s)
- `87da214f…` (Finance and Insurance): 1 file(s)
- `d025a41c…` (Finance and Insurance): 1 file(s)
- `401a07f1…` (Information): 1 file(s)
- `afe56d05…` (Information): 1 file(s)
- `9a8c8e28…` (Information): 7 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `ec2fccc9…` (Information): 1 file(s)
- `8c8fc328…` (Information): 1 file(s)
- `e222075d…` (Information): 2 file(s)
- `c94452e4…` (Information): 2 file(s)
- `75401f7c…` (Information): 1 file(s)
- `8079e27d…` (Finance and Insurance): 1 file(s)
- `e21cd746…` (Finance and Insurance): 3 file(s)
- `9e8607e7…` (Finance and Insurance): 5 file(s)
- `c7d83f01…` (Finance and Insurance): 5 file(s)
- `46b34f78…` (Finance and Insurance): 1 file(s)
- `a1963a68…` (Finance and Insurance): 5 file(s)
- `5f6c57dd…` (Finance and Insurance): 1 file(s)
- `b39a5aa7…` (Finance and Insurance): 1 file(s)
- `b78fd844…` (Finance and Insurance): 2 file(s)
- `4520f882…` (Finance and Insurance): 2 file(s)
- `ec591973…` (Wholesale Trade): 1 file(s)
- `62f04c2f…` (Wholesale Trade): 2 file(s)
- `3f821c2d…` (Wholesale Trade): 1 file(s)
- `e996036e…` (Wholesale Trade): 1 file(s)
- `327fbc21…` (Wholesale Trade): 1 file(s)
- `6dcae3f5…` (Health Care and Social Assistance): 2 file(s)
- `1aecc095…` (Health Care and Social Assistance): 4 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 3 file(s)
- `40a8c4b1…` (Health Care and Social Assistance): 1 file(s)
- `4d1a8410…` (Health Care and Social Assistance): 3 file(s)
- `8c823e32…` (Government): 2 file(s)
- `eb54f575…` (Government): 1 file(s)
- `11e1b169…` (Government): 2 file(s)
- `a95a5829…` (Government): 2 file(s)
- `22c0809b…` (Government): 2 file(s)
- `bf68f2ad…` (Manufacturing): 2 file(s)
- `efca245f…` (Manufacturing): 1 file(s)
- `9e39df84…` (Manufacturing): 1 file(s)
- `68d8d901…` (Manufacturing): 1 file(s)
- `1752cb53…` (Manufacturing): 1 file(s)
- `bd72994f…` (Retail Trade): 3 file(s)
- `211d0093…` (Retail Trade): 2 file(s)
- `d4525420…` (Retail Trade): 2 file(s)
- `45c6237b…` (Retail Trade): 2 file(s)
- `cecac8f9…` (Retail Trade): 4 file(s)
- `8f9e8bcd…` (Retail Trade): 1 file(s)
- `0fad6023…` (Retail Trade): 1 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `6436ff9e…` (Retail Trade): 1 file(s)
- `8a7b6fca…` (Manufacturing): 1 file(s)
- `40a99a31…` (Manufacturing): 3 file(s)
- `b9665ca1…` (Manufacturing): 2 file(s)
- `c6269101…` (Manufacturing): 5 file(s)
- `be830ca0…` (Manufacturing): 7 file(s)
- `cd9efc18…` (Professional, Scientific, and Technical Services): 2 file(s)
- `a97369c7…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3f625cb2…` (Professional, Scientific, and Technical Services): 2 file(s)
- `aad21e4c…` (Professional, Scientific, and Technical Services): 1 file(s)
- `8314d1b1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `5e2b6aab…` (Manufacturing): 21 file(s)
- `46fc494e…` (Manufacturing): 9 file(s)
- `3940b7e7…` (Manufacturing): 3 file(s)
- `8077e700…` (Manufacturing): 2 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `74d6e8b0…` (Health Care and Social Assistance): 2 file(s)
- `81db15ff…` (Health Care and Social Assistance): 1 file(s)
- `61b0946a…` (Health Care and Social Assistance): 2 file(s)
- `61e7b9c6…` (Health Care and Social Assistance): 1 file(s)
- `c9bf9801…` (Health Care and Social Assistance): 5 file(s)
- `f1be6436…` (Health Care and Social Assistance): 5 file(s)
- `41f6ef59…` (Health Care and Social Assistance): 2 file(s)
- `6d2c8e55…` (Health Care and Social Assistance): 11 file(s)
- `4b98ccce…` (Health Care and Social Assistance): 3 file(s)
- `60221cd0…` (Information): 1 file(s)
- `ef8719da…` (Information): 1 file(s)
- `3baa0009…` (Information): 4 file(s)
- `5d0feb24…` (Information): 1 file(s)
- `6974adea…` (Information): 1 file(s)
- `1a78e076…` (Health Care and Social Assistance): 1 file(s)
- `1b9ec237…` (Health Care and Social Assistance): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `772e7524…` (Health Care and Social Assistance): 2 file(s)
- `e6429658…` (Health Care and Social Assistance): 3 file(s)
- `b5d2e6f1…` (Wholesale Trade): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
- `47ef842d…` (Wholesale Trade): 1 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `c3525d4d…` (Wholesale Trade): 2 file(s)
- `9a0d8d36…` (Finance and Insurance): 1 file(s)
- `664a42e5…` (Finance and Insurance): 3 file(s)
- `feb5eefc…` (Finance and Insurance): 2 file(s)
- `3600de06…` (Finance and Insurance): 4 file(s)
- `c657103b…` (Finance and Insurance): 3 file(s)
- `ae0c1093…` (Retail Trade): 4 file(s)
- `f9f82549…` (Retail Trade): 4 file(s)
- `57b2cdf2…` (Retail Trade): 2 file(s)
- `84322284…` (Retail Trade): 2 file(s)
- `a46d5cd2…` (Retail Trade): 2 file(s)
- `6241e678…` (Information): 3 file(s)
- `e14e32ba…` (Information): 2 file(s)
- `b1a79ce1…` (Information): 1 file(s)
- `e4f664ea…` (Information): 2 file(s)
- `a079d38f…` (Information): 1 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `fd6129bd…` (Professional, Scientific, and Technical Services): 2 file(s)
- `ce864f41…` (Professional, Scientific, and Technical Services): 1 file(s)
- `58ac1cc5…` (Professional, Scientific, and Technical Services): 4 file(s)
- `3c19c6d1…` (Professional, Scientific, and Technical Services): 1 file(s)
- `a99d85fc…` (Real Estate and Rental and Leasing): 2 file(s)
- `55ddb773…` (Real Estate and Rental and Leasing): 2 file(s)
- `1e5a1d7f…` (Real Estate and Rental and Leasing): 1 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 2 file(s)
- `ed2bc14c…` (Real Estate and Rental and Leasing): 1 file(s)
- `46bc7238…` (Real Estate and Rental and Leasing): 2 file(s)
- `2d06bc0a…` (Real Estate and Rental and Leasing): 1 file(s)
- `fd3ad420…` (Real Estate and Rental and Leasing): 2 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 3 file(s)
- `6074bba3…` (Real Estate and Rental and Leasing): 4 file(s)
- `5ad0c554…` (Real Estate and Rental and Leasing): 4 file(s)
- `11593a50…` (Real Estate and Rental and Leasing): 3 file(s)
- `94925f49…` (Real Estate and Rental and Leasing): 8 file(s)
- `90f37ff3…` (Real Estate and Rental and Leasing): 3 file(s)
- `d3d255b2…` (Real Estate and Rental and Leasing): 2 file(s)
- `403b9234…` (Government): 1 file(s)
- `1bff4551…` (Government): 2 file(s)
- `650adcb1…` (Government): 1 file(s)
- `a73fbc98…` (Government): 2 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 1 file(s)
- `dd724c67…` (Health Care and Social Assistance): 1 file(s)
- `7151c60a…` (Health Care and Social Assistance): 2 file(s)
- `90edba97…` (Health Care and Social Assistance): 1 file(s)
- `91060ff0…` (Retail Trade): 4 file(s)
- `8384083a…` (Retail Trade): 3 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `b3573f20…` (Wholesale Trade): 1 file(s)
- `a69be28f…` (Wholesale Trade): 13 file(s)
- `788d2bc6…` (Wholesale Trade): 9 file(s)
- `74ed1dc7…` (Wholesale Trade): 1 file(s)
- `69a8ef86…` (Wholesale Trade): 2 file(s)
- `ab81b076…` (Wholesale Trade): 3 file(s)
- `d7cfae6f…` (Wholesale Trade): 1 file(s)
- `19403010…` (Wholesale Trade): 1 file(s)
- `7ed932dd…` (Wholesale Trade): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 1 file(s)
- `b57efde3…` (Wholesale Trade): 1 file(s)
- `15d37511…` (Wholesale Trade): 2 file(s)
- `bb863dd9…` (Wholesale Trade): 1 file(s)
- `fe0d3941…` (Wholesale Trade): 2 file(s)
- `9efbcd35…` (Finance and Insurance): 1 file(s)
- `1d4672c8…` (Finance and Insurance): 2 file(s)
- `4de6a529…` (Finance and Insurance): 1 file(s)
- `4c4dc603…` (Finance and Insurance): 1 file(s)
- `bb499d9c…` (Finance and Insurance): 1 file(s)
- `5349dd7b…` (Manufacturing): 1 file(s)
- `a4a9195c…` (Manufacturing): 1 file(s)
- `552b7dd0…` (Manufacturing): 3 file(s)
- `76418a2c…` (Manufacturing): 2 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 3 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
