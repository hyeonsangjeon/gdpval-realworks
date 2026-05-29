# Critical-Item Disagreement Stratification (Probe Y₁)

- hybrid: `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json`
- mini  : `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json`
- task pairs: 220
- total critical (rubric item) pairs: 397

## Headline split of the −10pp gap
- total hybrid-fail / mini-pass disagreements (the gap): **61**
- of which **formatting bucket**: 47 (77.0%)
- of which **content bucket**:    14 (22.9%)

> Interpretation:
> - **formatting >> content** → Scenario B (hybrid penalizes flattened extraction; mini is closer to truth)
> - **content >> formatting** → Scenario A (pro tier catching real critical fails; mini too lenient)
> - **roughly equal** → both effects present; need probe Y₂ to disentangle

## Bucket: `formatting`
- pairs: 161  | hybrid_pass: 0.429  | mini_pass: 0.683  | gap: **-25.5pp**
- agreement: both_pass=63  both_fail=45  hybrid_fail_only=47  mini_fail_only=6
- hybrid fails decided by tier (precheck vs judge): {'judge': 47}

### Top disagreement criteria (hybrid fail / mini pass)
| count | criterion (first 120 chars) |
|---:|---|
| 45 | `overall formatting and style of the deliverable` |
| 1 | `includes a table for flat rate shipping costs for 2025 that contains information for the following package sizes: pak, s` |
| 1 | `overall formatting and style of the deliverable.` |

### Sample disagreements (top 12 for inspection)
- task `0818571f…` rubric `adeb1380…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Retail Shopping Center Acquisition Shortlist Prepared for Investment Group | June 2025 This report presents a shortlist of Florida retail shopping center opportunities_
  - mini evidence  : _"Retail Shopping Center Acquisition Shortlist\nPrepared for Investment Group | June 2025\nThis report presents a shortlist of Florida retail shopping center opportunities"_
- task `0e4fe8cd…` rubric `3d96a5b6…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _[Sheet: June 1 – Departure] Time,Action,Location,Details,Provider / Contact,Link_
  - mini evidence  : _[Sheet: June 2 – Arrival & Touring] Time,Action,Location,Details,Provider / Contact,Link_
- task `0fad6023…` rubric `4023c456…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _How to Use the 24ft FSC Planogram Tab:
1. Each row equals one pan in the FSC.
2. Enter the Pan Width in inches (typically 6 or 8 inches)._
  - mini evidence  : _"Meat & Seafood 24-Foot FSC Planogram – Instructions" ... "1. Each row equals one pan in the FSC."_
- task `105f8ad0…` rubric `0df310cf…`  `Overall formatting and style of the deliverable`
  - hybrid: **3.75/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Gender,Fragrance Name,Size_oz,COGS,Current_MSRP,Current_Price_per_oz,Size_Tier,Competitor_Avg_Price_per_oz,Target_Price_per_oz,Recommended_MSRP,Pricing_Rationale_
  - mini evidence  : _[Sheet: MSRP_Model]
Gender,Fragrance Name,Size_oz,COGS,Current_MSRP,Current_Price_per_oz,Size_Tier,Competitor_Avg_Price_per_oz,Target_Price_per_oz,Recommended_MSRP,Pricing_Rationale_
- task `11dcc268…` rubric `46fcfb7d…`  `Overall formatting and style of the deliverable`
  - hybrid: **3.25/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Date ____________,,,Location Report,,,,,,,,,,
P21-L44S38-30,Switch, Front Panel,200,RECEIVING DOCK,UNASSIGNED,200,0,,,,,,,_
  - mini evidence  : _PO#,Supplier,Item #,Item Description,Qty ordered,Qty Rec'd,Qty B/O,On time (Y/N)_
- task `27e8912c…` rubric `8e5445d2…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Checklist (Based on NIH Workstation Ergonomics Guidance)
n Chair: Feet rest flat on the floor or footrest; thighs are parallel to the floor._
  - mini evidence  : _Workstation Ergonomics Checklist
Goal: To ensure office workstations are set up to minimize neck and back strain, support neutral postures, and improve employee comfort and performance._
- task `3940b7e7…` rubric `27eb86e8…`  `Overall formatting and style of the deliverable`
  - hybrid: **3.5/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Preliminary Flow Simulation Report – Experimental X Wing Assembly Objective ... experimental XnWing assembly ... impact liftntondrag performance_
  - mini evidence  : _"Fluid Flow Simulation Report
Table of Contents
1 General Information ..."_
- task `3a4c347c…` rubric `de9cb74c…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Aims of the Season
- Deliver high-quality, in-depth journalism on enterprise technology innovation across Asia._
  - mini evidence  : _"Asia in Focus: Enterprise Technology\nIntroduction\nThis proposal outlines a four-week themed season of editorial coverage focused on enterprise technology innovation across Asia."_
- task `403b9234…` rubric `9e7a1046…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Why Community Partnerships Matter
Public recreation thrives when connected to the broader community
Partnerships expand resources without expanding tax burden_
  - mini evidence  : _[Slide 1]
Exploring a Community Partnership
with the County Chamber of Commerce
Parks & Recreation Advisory Board Discussion_
- task `4520f882…` rubric `b871ca80…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Weekly Musician Payroll Model – Instructions
1. Enter all weekly musician information on the 'Weekly_Roster_Input' sheet.
2. Yellow cells indicate contractor input._
  - mini evidence  : _Weekly Musician Payroll Model – Instructions

1. Enter all weekly musician information on the 'Weekly_Roster_Input' sheet._
- task `4d1a8410…` rubric `6be9d58e…`  `Overall formatting and style of the deliverable`
  - hybrid: **3.5/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Nu Arc Medical Center – MTP Interview Day Schedule [Table 1] Room | Interviewer | Time Block | Applicants / Notes_
  - mini evidence  : _Nu Arc Medical Center – MTP Interview Day Schedule

[Table 1]
Room | Interviewer | Time Block | Applicants / Notes_
- task `4d61a19a…` rubric `c2e72d1d…`  `Overall formatting and style of the deliverable`
  - hybrid: **4.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Promotion Overview,,,
Product & Pricing,,,
Historical Context,,,
Store Input (To Be Completed by Store),,,_
  - mini evidence  : _"Promotion Projection Form\nTraining for Meat Team Leaders"_

## Bucket: `content`
- pairs: 236  | hybrid_pass: 0.458  | mini_pass: 0.500  | gap: **-4.2pp**
- agreement: both_pass=104  both_fail=114  hybrid_fail_only=14  mini_fail_only=4
- hybrid fails decided by tier (precheck vs judge): {'judge': 14}

### Top disagreement criteria (hybrid fail / mini pass)
| count | criterion (first 120 chars) |
|---:|---|
| 1 | `public listing indicates the asset is for sale (not lease-only, and not pad/outparcel-only) for each property listing` |
| 1 | `spreadsheet includes the template’s core data fields needed to meet the prompt (medication name(s), formulation/dosage f` |
| 1 | `each row includes the generic active ingredient name(s).` |
| 1 | `an estimated one-month cost without insurance is provided for each medication.` |
| 1 | `each row specifies dosage form (e.g., tablet/patch/gel/ring/cream) and active ingredient(s)` |
| 1 | `all included products are fda-approved prescription drugs (no compounded preparations or non-fda-approved products), eve` |
| 1 | `each formulary line item contains the 'brand name' column populated without factual error.` |
| 1 | `final delivery is scheduled no later than friday, 2025-08-29 and occurs after audio mixing, color grading, and the clien` |
| 1 | `each date shows all scheduled tasks without any hidden overflow indicators (e.g., no '+n more' on any date).` |
| 1 | `the calendar contains only the project tasks listed in the prompt and no unrelated events.` |

### Sample disagreements (top 12 for inspection)
- task `0818571f…` rubric `0121dd26…`  `Public listing indicates the asset is for sale (not lease-only, and not pad/outparcel-only) for each property listing`
  - hybrid: **0.0/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _This report presents a shortlist of Florida retail shopping center opportunities that align with the investor’s acquisition criteria_
  - mini evidence  : _Sunshine Plaza,Orlando, FL,82000,1998 / 2016,Grocery, QSR, Medical, Local Retail,18500000,1250000,6.75%,Value‑add via rent growth_
- task `61e7b9c6…` rubric `a196ee80…`  `Spreadsheet includes the template’s core data fields needed to meet the prompt (medication name(s), formulation/dosage form, route, strength, FDA-approved vs of`
  - hybrid: **3.32/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _Group,Brand Name,Generic Name,Formulation,Route,Drug Strength,Estimated cost without insurance,_
  - mini evidence  : _Brand Name, Generic Name, Formulation, Route, Drug Strength, Estimated cost without insurance, NON-HORMONAL (OFF-LABEL, FDA-APPROVED)_
- task `61e7b9c6…` rubric `fc36f035…`  `Each row includes the generic active ingredient name(s).`
  - hybrid: **2.4/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _ESTROGEN (ORAL),,,,,,,
,Estrace,estradiol,Tablet,Oral,1 mg,40,_
  - mini evidence  : _,Estrace,estradiol,Tablet,Oral,1 mg,40,
,Vivelle-Dot,estradiol,Patch,Transdermal,0.05 mg/day,60,
,Prometrium,progesterone,Capsule,Oral,100 mg,45,_
- task `61e7b9c6…` rubric `adfc1f1e…`  `An estimated one-month cost without insurance is provided for each medication.`
  - hybrid: **3.75/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Group,Brand Name,Generic Name,Formulation,Route,Drug Strength,Estimated cost without insurance,
,Bijuva,estradiol / progesterone,Capsule,Oral,1 mg / 100 mg,250,_
  - mini evidence  : _,Bijuva,estradiol / progesterone,Capsule,Oral,1 mg / 100 mg,250,\n,Estrace,estradiol,Tablet,Oral,1 mg,40,\n,Vivelle-Dot,estradiol,Patch,Transdermal,0.05 mg/day,60,_
- task `61e7b9c6…` rubric `ef63e6fb…`  `Each row specifies dosage form (e.g., tablet/patch/gel/ring/cream) and active ingredient(s)`
  - hybrid: **3.0/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _ESTROGEN (ORAL),,,,,,,
,Estrace,estradiol,Tablet,Oral,1 mg,40,
ESTROGEN (TRANSDERMAL),,,,,,,
,Vivelle-Dot,estradiol,Patch,Transdermal,0.05 mg/day,60,_
  - mini evidence  : _Brand Name,Generic Name,Formulation,Route,Drug Strength,... ,Estrace,estradiol,Tablet,Oral,1 mg,40,_
- task `61e7b9c6…` rubric `82f3fd1b…`  `All included products are FDA-approved prescription drugs (no compounded preparations or non-FDA-approved products), even when listed for off-label menopause sy`
  - hybrid: **3.0/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _Bijuva,estradiol/bazedoxifene,Capsules,Oral,1mg/100mg,250_
  - mini evidence  : _"NON-HORMONAL (OFF-LABEL, FDA-APPROVED),,,,,,,\n,Effexor XR,venlafaxine,Extended-release capsule,Oral,75 mg,15,\n,Neurontin,gabapentin,Capsule,Oral,300 mg,10,"_
- task `61e7b9c6…` rubric `1fbcf6ff…`  `Each formulary line item contains the 'Brand Name' column populated without factual error.`
  - hybrid: **3.2/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _,Bijuva,estradiol/bazedoxifene,Capsules,Oral,1mg/100mg,250,_
  - mini evidence  : _"Bijuva,estradiol / progesterone,Capsule,Oral,1 mg / 100 mg,250,"_
- task `6241e678…` rubric `842391b9…`  `Final Delivery is scheduled no later than Friday, 2025-08-29 and occurs after Audio Mixing, Color Grading, and the client review of audio and color.`
  - hybrid: **4.0/8** (judge)  vs mini: **8.0/8** (judge)
  - hybrid evidence: _Audio Mixing
Color Grading
*Client Review of Audio & Color
Final Delivery_
  - mini evidence  : _60 Second B2B Video Full Production Schedule (July 7 Aug 29, 2025)
Audio Mixing
Color Grading
*Client Review of Audio & Color
Final Delivery_
- task `6241e678…` rubric `a2aa0e6f…`  `Each date shows all scheduled tasks without any hidden overflow indicators (e.g., no '+n more' on any date).`
  - hybrid: **0.0/4** (judge)  vs mini: **4.0/4** (judge)
  - hybrid evidence: _Final Delivery
8 5 2 1 8 5 2 1
0 1 2 0 0 1 2 0
7- 7- 7- 8- 8- 8- 8- 9-_
  - mini evidence  : _"60 Second B2B Video Full Production Schedule ... Kickoff Call Internal Creative Workshopping Internal Creative Review *Client Pitch Meeting"_
- task `6241e678…` rubric `21d90796…`  `The calendar contains only the project tasks listed in the prompt and no unrelated events.`
  - hybrid: **2.5/5** (judge)  vs mini: **5.0/5** (judge)
  - hybrid evidence: _Kickoff Call
Internal Creative Workshopping
Internal Creative Review
*Client Pitch Meeting
*Client Pitch Review_
  - mini evidence  : _"Kickoff Call\nInternal Creative Workshopping\nInternal Creative Review\n*Client Pitch Meeting"_
- task `6241e678…` rubric `4dfb92b5…`  `Kickoff call is scheduled on Monday, 2025-07-07.`
  - hybrid: **0.0/8** (judge)  vs mini: **8.0/8** (judge)
  - hybrid evidence: _60 Second B2B Video Full Production Schedule
(July 7 Aug 29, 2025)
Kickoff Call_
  - mini evidence  : _"60 Second B2B Video Full Production Schedule (July 7 Aug 29, 2025) Kickoff Call"_
- task `c94452e4…` rubric `e685a428…`  `Each super is on a unique shot.`
  - hybrid: **0.0/6** (judge)  vs mini: **6.0/6** (judge)
  - hybrid evidence: _judge_json_parse_failed:truncated_at_max_tokens_
  - mini evidence  : _2,2,2.5,4.5,In a year of record profits,,Slow push-in. Darken/desaturate.
3,4.5,2.5,7,VitalNet Health Plans,Hold for legibility._

