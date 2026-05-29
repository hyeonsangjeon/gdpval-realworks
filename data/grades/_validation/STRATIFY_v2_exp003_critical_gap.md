# Critical-Item Disagreement Stratification — Sign-Aware (Probe Y₁ v2)

- hybrid: `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json`
- mini  : `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json`
- task pairs: 220
- critical definition: `|max_score| >= 4` (covers high-positive AND high-negative items)
- 'model_did_right' = `verdict=='pass'` for positive items, `verdict!='pass'` for negative items

## Headline (sign-aware)
- total critical (rubric item) pairs: **483**
- overall hybrid_right_rate: **0.468**
- overall mini_right_rate  : **0.596**
- overall gap: **-12.84pp**  (positive = hybrid more lenient overall; negative = hybrid stricter overall)

## Where does the disagreement come from?
- total hybrid-stricter pairs (hybrid=wrong, mini=right): **78**
- total mini-stricter   pairs (mini=wrong, hybrid=right): **16**
- net directional gap: **+62**  (positive = hybrid strict more often)

### Share of hybrid-stricter pairs by bucket
- formatting:  60.3%
- content   :  17.9%
- penalty   :  21.8%

### Share of mini-stricter pairs by bucket
- formatting:  37.5%
- content   :  25.0%
- penalty   :  37.5%

> Interpretation:
> - **hybrid-stricter ≫ mini-stricter, concentrated in formatting** → Scenario B (hybrid over-rejects, extraction artifact)
> - **hybrid-stricter ≫ mini-stricter, concentrated in content/penalty** → Scenario A (hybrid catches real failures)
> - **mini-stricter > hybrid-stricter in penalty** → mini catches anti-criteria hybrid misses (a separate, opposite signal)
> - **roughly balanced everywhere** → noise; neither is meaningfully better

## Bucket: `formatting`  (pairs: 161)
- hybrid_right_rate: 0.429  |  mini_right_rate: 0.683  |  gap: **-25.5pp**
- agreement: both_right=63  both_wrong=45  hybrid_stricter=47  mini_stricter=6
- net directional (h - m): **+41**
- hybrid-stricter decided by tier: {'judge': 47}

### Top hybrid-stricter criteria (hybrid wrong / mini right)
| count | criterion (first 120 chars) |
|---:|---|
| 45 | `overall formatting and style of the deliverable` |
| 1 | `includes a table for flat rate shipping costs for 2025 that contains information for the following package sizes: pak, s` |
| 1 | `overall formatting and style of the deliverable.` |

### Top mini-stricter criteria (mini wrong / hybrid right)
| count | criterion (first 120 chars) |
|---:|---|
| 5 | `overall formatting and style of the deliverable` |
| 1 | `structures the briefing note so that it fits within one page.` |

### Sample hybrid-stricter (top 12)
- task `0818571f…` rubric `adeb1380…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Retail Shopping Center Acquisition Shortlist Prepared for Investment Group | June 2025 This report presents a shortlist of Florida retail shopping center opportunities_
- task `0e4fe8cd…` rubric `3d96a5b6…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _[Sheet: June 1 – Departure] Time,Action,Location,Details,Provider / Contact,Link_
- task `0fad6023…` rubric `4023c456…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _How to Use the 24ft FSC Planogram Tab:
1. Each row equals one pan in the FSC.
2. Enter the Pan Width in inches (typically 6 or 8 inches)._
- task `105f8ad0…` rubric `0df310cf…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=3.75 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Gender,Fragrance Name,Size_oz,COGS,Current_MSRP,Current_Price_per_oz,Size_Tier,Competitor_Avg_Price_per_oz,Target_Price_per_oz,Recommended_MSRP,Pricing_Rationale_
- task `11dcc268…` rubric `46fcfb7d…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=3.25 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Date ____________,,,Location Report,,,,,,,,,,
P21-L44S38-30,Switch, Front Panel,200,RECEIVING DOCK,UNASSIGNED,200,0,,,,,,,_
- task `27e8912c…` rubric `8e5445d2…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Checklist (Based on NIH Workstation Ergonomics Guidance)
n Chair: Feet rest flat on the floor or footrest; thighs are parallel to the floor._
- task `3940b7e7…` rubric `27eb86e8…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=3.5 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Preliminary Flow Simulation Report – Experimental X Wing Assembly Objective ... experimental XnWing assembly ... impact liftntondrag performance_
- task `3a4c347c…` rubric `de9cb74c…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Aims of the Season
- Deliver high-quality, in-depth journalism on enterprise technology innovation across Asia._
- task `403b9234…` rubric `9e7a1046…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Why Community Partnerships Matter
Public recreation thrives when connected to the broader community
Partnerships expand resources without expanding tax burden_
- task `4520f882…` rubric `b871ca80…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Weekly Musician Payroll Model – Instructions
1. Enter all weekly musician information on the 'Weekly_Roster_Input' sheet.
2. Yellow cells indicate contractor input._
- task `4d1a8410…` rubric `6be9d58e…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=3.5 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Nu Arc Medical Center – MTP Interview Day Schedule [Table 1] Room | Interviewer | Time Block | Applicants / Notes_
- task `4d61a19a…` rubric `c2e72d1d…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Promotion Overview,,,
Product & Pricing,,,
Historical Context,,,
Store Input (To Be Completed by Store),,,_

### Sample mini-stricter (top 12)
- task `02aa1805…` rubric `3c1ecd45…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.5
  - mini evidence: _Subject: Preliminary Screening of Potential Water Wells for Green Hydrogen Facility
Hi [REDACTED],_
- task `57b2cdf2…` rubric `32109b91…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=4.0
  - mini evidence: _"Final Surveillance Investigation Report
Case Number: SERC-1410PI-2025
Date of Surveillance: July 3, 2025
Summary"_
- task `68d8d901…` rubric `734c2bba…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.0
  - mini evidence: _"Work Schedule\nProduction target – 250,000 lbs of bulk output\nShift length – 12 hours\nNumber of shifts per day – 2 shifts per day"_
- task `8f9e8bcd…` rubric `f585843f…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.5
  - mini evidence: _Overcoming Sales Objections in Bridal Sales
Overview
Types of Objections
1. Price Objections (Cost or Budget Constraints)_
- task `c44e9b62…` rubric `6bd38559…`  (max_score=5)  `Structures the Briefing note so that it fits within one page.`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**fail** awarded=0.0
  - mini evidence: _"Briefing Note: FTE Reductions
Background
As part of the annual government budget planning cycle..."_
- task `f2986c1f…` rubric `22d6fd3e…`  (max_score=5)  `Overall formatting and style of the deliverable`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.0
  - mini evidence: _[Sheet: Medication Identification]
Markings,Color,Shape,Dose form,Name of medication,Strength of medication,Type of medication,MedlinePlus.gov counseling link_

## Bucket: `content`  (pairs: 236)
- hybrid_right_rate: 0.458  |  mini_right_rate: 0.500  |  gap: **-4.2pp**
- agreement: both_right=104  both_wrong=114  hybrid_stricter=14  mini_stricter=4
- net directional (h - m): **+10**
- hybrid-stricter decided by tier: {'judge': 14}

### Top hybrid-stricter criteria (hybrid wrong / mini right)
| count | criterion (first 120 chars) |
|---:|---|
| 1 | `public listing indicates the asset is for sale (not lease-only, and not pad/outparcel-only) for each property listing` |
| 1 | `each formulary line item contains the 'brand name' column populated without factual error.` |
| 1 | `each row specifies dosage form (e.g., tablet/patch/gel/ring/cream) and active ingredient(s)` |
| 1 | `an estimated one-month cost without insurance is provided for each medication.` |
| 1 | `all included products are fda-approved prescription drugs (no compounded preparations or non-fda-approved products), eve` |
| 1 | `spreadsheet includes the template’s core data fields needed to meet the prompt (medication name(s), formulation/dosage f` |
| 1 | `each row includes the generic active ingredient name(s).` |
| 1 | `kickoff call is scheduled on monday, 2025-07-07.` |
| 1 | `final delivery is scheduled no later than friday, 2025-08-29 and occurs after audio mixing, color grading, and the clien` |
| 1 | `each date shows all scheduled tasks without any hidden overflow indicators (e.g., no '+n more' on any date).` |

### Top mini-stricter criteria (mini wrong / hybrid right)
| count | criterion (first 120 chars) |
|---:|---|
| 1 | `the formulary clearly differentiates fda-approved menopause hormone therapies from medications commonly used off-label f` |
| 1 | `references community safety as a key emphasis.` |
| 1 | `states under "purpose" that uas will enhance community safety.` |
| 1 | `writes andy as being shy, awkward, and lonely.` |

### Sample hybrid-stricter (top 12)
- task `0818571f…` rubric `0121dd26…`  (max_score=5)  `Public listing indicates the asset is for sale (not lease-only, and not pad/outparcel-only) for each property listing`
  - hybrid: verdict=**fail** awarded=0.0 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _This report presents a shortlist of Florida retail shopping center opportunities that align with the investor’s acquisition criteria_
- task `61e7b9c6…` rubric `1fbcf6ff…`  (max_score=4)  `Each formulary line item contains the 'Brand Name' column populated without factual error.`
  - hybrid: verdict=**partial** awarded=3.2 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _,Bijuva,estradiol/bazedoxifene,Capsules,Oral,1mg/100mg,250,_
- task `61e7b9c6…` rubric `ef63e6fb…`  (max_score=4)  `Each row specifies dosage form (e.g., tablet/patch/gel/ring/cream) and active ingredient(s)`
  - hybrid: verdict=**partial** awarded=3.0 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _ESTROGEN (ORAL),,,,,,,
,Estrace,estradiol,Tablet,Oral,1 mg,40,
ESTROGEN (TRANSDERMAL),,,,,,,
,Vivelle-Dot,estradiol,Patch,Transdermal,0.05 mg/day,60,_
- task `61e7b9c6…` rubric `adfc1f1e…`  (max_score=5)  `An estimated one-month cost without insurance is provided for each medication.`
  - hybrid: verdict=**partial** awarded=3.75 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Group,Brand Name,Generic Name,Formulation,Route,Drug Strength,Estimated cost without insurance,
,Bijuva,estradiol / progesterone,Capsule,Oral,1 mg / 100 mg,250,_
- task `61e7b9c6…` rubric `82f3fd1b…`  (max_score=4)  `All included products are FDA-approved prescription drugs (no compounded preparations or non-FDA-approved products), even when listed for off-label menopause sy`
  - hybrid: verdict=**partial** awarded=3.0 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _Bijuva,estradiol/bazedoxifene,Capsules,Oral,1mg/100mg,250_
- task `61e7b9c6…` rubric `a196ee80…`  (max_score=4)  `Spreadsheet includes the template’s core data fields needed to meet the prompt (medication name(s), formulation/dosage form, route, strength, FDA-approved vs of`
  - hybrid: verdict=**partial** awarded=3.32 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _Group,Brand Name,Generic Name,Formulation,Route,Drug Strength,Estimated cost without insurance,_
- task `61e7b9c6…` rubric `fc36f035…`  (max_score=4)  `Each row includes the generic active ingredient name(s).`
  - hybrid: verdict=**partial** awarded=2.4 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _ESTROGEN (ORAL),,,,,,,
,Estrace,estradiol,Tablet,Oral,1 mg,40,_
- task `6241e678…` rubric `4dfb92b5…`  (max_score=8)  `Kickoff call is scheduled on Monday, 2025-07-07.`
  - hybrid: verdict=**fail** awarded=0.0 (judge)  vs mini: verdict=**pass** awarded=8.0 (judge)
  - hybrid evidence: _60 Second B2B Video Full Production Schedule
(July 7 Aug 29, 2025)
Kickoff Call_
- task `6241e678…` rubric `842391b9…`  (max_score=8)  `Final Delivery is scheduled no later than Friday, 2025-08-29 and occurs after Audio Mixing, Color Grading, and the client review of audio and color.`
  - hybrid: verdict=**partial** awarded=4.0 (judge)  vs mini: verdict=**pass** awarded=8.0 (judge)
  - hybrid evidence: _Audio Mixing
Color Grading
*Client Review of Audio & Color
Final Delivery_
- task `6241e678…` rubric `a2aa0e6f…`  (max_score=4)  `Each date shows all scheduled tasks without any hidden overflow indicators (e.g., no '+n more' on any date).`
  - hybrid: verdict=**fail** awarded=0.0 (judge)  vs mini: verdict=**pass** awarded=4.0 (judge)
  - hybrid evidence: _Final Delivery
8 5 2 1 8 5 2 1
0 1 2 0 0 1 2 0
7- 7- 7- 8- 8- 8- 8- 9-_
- task `6241e678…` rubric `21d90796…`  (max_score=5)  `The calendar contains only the project tasks listed in the prompt and no unrelated events.`
  - hybrid: verdict=**partial** awarded=2.5 (judge)  vs mini: verdict=**pass** awarded=5.0 (judge)
  - hybrid evidence: _Kickoff Call
Internal Creative Workshopping
Internal Creative Review
*Client Pitch Meeting
*Client Pitch Review_
- task `c94452e4…` rubric `e685a428…`  (max_score=6)  `Each super is on a unique shot.`
  - hybrid: verdict=**judge_error** awarded=0.0 (judge)  vs mini: verdict=**pass** awarded=6.0 (judge)
  - hybrid evidence: _judge_json_parse_failed:truncated_at_max_tokens_

### Sample mini-stricter (top 12)
- task `61e7b9c6…` rubric `22d319ec…`  (max_score=4)  `The formulary clearly differentiates FDA-approved menopause hormone therapies from medications commonly used off-label for perimenopause or menopause symptoms.`
  - hybrid: verdict=**pass** awarded=4.0  vs mini: verdict=**fail** awarded=0.0
  - mini evidence: _"NON-HORMONAL (OFF-LABEL, FDA-APPROVED),,,,,,,"_
- task `8c823e32…` rubric `25dbd728…`  (max_score=5)  `References community safety as a key emphasis.`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.0
  - mini evidence: _"The purpose of this policy is to enhance public safety, improve officer safety, and increase operational efficiency"_
- task `8c823e32…` rubric `b064af31…`  (max_score=5)  `States under "Purpose" that UAS will enhance community safety.`
  - hybrid: verdict=**pass** awarded=5.0  vs mini: verdict=**partial** awarded=3.0
  - mini evidence: _“The purpose of this policy is to enhance public safety, improve officer safety, and increase operational efficiency...”_
- task `e4f664ea…` rubric `0d00bce5…`  (max_score=6)  `Writes Andy as being shy, awkward, and lonely.`
  - hybrid: verdict=**pass** awarded=6.0  vs mini: verdict=**partial** awarded=4.0200000000000005
  - mini evidence: _"ANDY (20s), awkward and stiff, steps out. He hesitates, then moves toward the office. ... Loneliness and desire drive Andy"_

## Bucket: `penalty`  (pairs: 86)
- hybrid_right_rate: 0.570  |  mini_right_rate: 0.698  |  gap: **-12.8pp**
- agreement: both_right=43  both_wrong=20  hybrid_stricter=17  mini_stricter=6
- net directional (h - m): **+11**
- hybrid-stricter decided by tier: {'judge': 17}

### Top hybrid-stricter criteria (hybrid wrong / mini right)
| count | criterion (first 120 chars) |
|---:|---|
| 1 | `fails to identify the bathrooms for any sold comp in the “2. comparable sales (sold properties)” table.` |
| 1 | `fails to identify the lot size for any sold comp in the “2. comparable sales (sold properties)” table.` |
| 1 | `fails to state the lowest sold price in the “5. overview of closed properties” section.` |
| 1 | `fails to state a mid-tier price as a dollar amount in the “6. pricing recommendations” section.` |
| 1 | `fails to identify the bedrooms for any sold comp in the “2. comparable sales (sold properties)” table.` |
| 1 | `fails to identify the property type for any sold comp in the “2. comparable sales (sold properties)” table.` |
| 1 | `fails to state a recommended list price range as two dollar amounts in the “6. pricing recommendations” section.` |
| 1 | `includes an empty address for any active or pending listing in the “3. active & pending listings” table.` |
| 1 | `fails to identify the bathrooms for any active or pending listing in the “3. active & pending listings” table.` |
| 1 | `fails to state the lowest active listing price in the “4. overview of active properties” section.` |

### Top mini-stricter criteria (mini wrong / hybrid right)
| count | criterion (first 120 chars) |
|---:|---|
| 1 | `fails to include details about what week each activity under the "activity" or "details/tracker" column should take plac` |
| 1 | `inspection schedule deliverable identifies any room other than the following as having a move-out date in september 2025` |
| 1 | `includes an empty address for any sold comp in the “2. comparable sales (sold properties)” table.` |
| 1 | `fails to reference at least one active or pending listing in the “6. pricing recommendations” section.` |
| 1 | `schedules clever carpet or carpet work in any unit on a date other than on of the following: july 3, 2025; july 7, 2025;` |
| 1 | `schedules sam williams or paint work in any unit on a date other than on of the following: july 2, 2025; july 8, 2025; j` |

### Sample hybrid-stricter (top 12)
- task `6074bba3…` rubric `54a83730…`  (max_score=-10)  `Fails to identify the bathrooms for any sold comp in the “2. Comparable Sales (Sold Properties)” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _2. Comparable Sales (Closed)
Sold Comp 1: Sold at $275,000 (DOM: 32)
Sold Comp 2: Sold at $290,000 (DOM: 28)
Sold Comp 3: Sold at $270,000 (DOM: 45)_
- task `6074bba3…` rubric `04bd4043…`  (max_score=-10)  `Fails to identify the lot size for any sold comp in the “2. Comparable Sales (Sold Properties)” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _2. Comparable Sales (Closed)
Sold Comp 1: Sold at $275,000 (DOM: 32)
Sold Comp 2: Sold at $290,000 (DOM: 28)_
- task `6074bba3…` rubric `a9ad9ad3…`  (max_score=-10)  `Fails to state the lowest sold price in the “5. Overview of Closed Properties” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _5. Pricing Recommendations
Average Price: $292,909
Median Price: $295,000
High Price: $315,000
Low Price: $270,000_
- task `6074bba3…` rubric `03ff6769…`  (max_score=-10)  `Fails to state a mid-tier price as a dollar amount in the “6. Pricing Recommendations” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _5. Pricing Recommendations
Average Price: $292,909
Median Price: $295,000
High Price: $315,000
Low Price: $270,000_
- task `6074bba3…` rubric `90c99ba8…`  (max_score=-10)  `Fails to identify the bedrooms for any sold comp in the “2. Comparable Sales (Sold Properties)” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _2. Comparable Sales (Closed)
Sold Comp 1: Sold at $275,000 (DOM: 32)
Sold Comp 2: Sold at $290,000 (DOM: 28)_
- task `6074bba3…` rubric `0f1f96a9…`  (max_score=-10)  `Fails to identify the property type for any sold comp in the “2. Comparable Sales (Sold Properties)” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _2. Comparable Sales (Closed)
Sold Comp 1: Sold at $275,000 (DOM: 32)
Sold Comp 2: Sold at $290,000 (DOM: 28)_
- task `6074bba3…` rubric `62a55de5…`  (max_score=-10)  `Fails to state a recommended list price range as two dollar amounts in the “6. Pricing Recommendations” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _5. Pricing Recommendations
Average Price: $292,909
... Suggested List Price Range: $285,000 – $310,000_
- task `6074bba3…` rubric `0b51f393…`  (max_score=-10)  `Includes an empty address for any active or pending listing in the “3. Active & Pending Listings” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _3. Active & Pending Listings
Active Comp 1: Listed at $310,000 (DOM: 18)_
- task `6074bba3…` rubric `a3334cd1…`  (max_score=-10)  `Fails to identify the bathrooms for any active or pending listing in the “3. Active & Pending Listings” table.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _3. Active & Pending Listings
Active Comp 1: Listed at $310,000 (DOM: 18)
Active Comp 2: Listed at $299,000 (DOM: 25)_
- task `6074bba3…` rubric `b3898981…`  (max_score=-10)  `Fails to state the lowest active listing price in the “4. Overview of Active Properties” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _6. Overview of Active Properties
7. Overview of Closed Properties
8. Pricing Recommendations_
- task `6074bba3…` rubric `c55bb75a…`  (max_score=-10)  `Fails to state the average days on market for sold listings in the “5. Overview of Closed Properties” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _7. Overview of Closed Properties
8. Pricing Recommendations_
- task `6074bba3…` rubric `cd70a16b…`  (max_score=-10)  `Fails to state the average days on market for active listings in the “4. Overview of Active Properties” section.`
  - hybrid: verdict=**pass** awarded=-10.0 (judge)  vs mini: verdict=**fail** awarded=-0.0 (judge)
  - hybrid evidence: _6. Overview of Active Properties
7. Overview of Closed Properties_

### Sample mini-stricter (top 12)
- task `1e5a1d7f…` rubric `462267a8…`  (max_score=-10)  `Fails to include details about what week each activity under the "Activity" or "Details/Tracker" column should take place`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-10.0
  - mini evidence: _8:00 – 9:00 AM | Move-Ins | ... | Weekly (As Needed)
11:00 AM – 12:00 PM | Renewals | ... | Weeks 1–3_
- task `476db143…` rubric `f180e77f…`  (max_score=-5)  `Inspection schedule deliverable identifies any room other than the following as having a move-out date in September 2025: 302, 308, 411, 415, 617`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-5.0
  - mini evidence: _302 | [REDACTED] | 9/30/25 | 9/25/25
308 | [REDACTED] | 9/29/25 | 9/23/25
411 | [REDACTED] | 9/25/25 | 9/23/25
415 | [REDACTED] | 9/30/25 | 9/23/25
617 | [REDACTED] | 9/30/25 | 9/28/25_
- task `6074bba3…` rubric `b53589db…`  (max_score=-10)  `Includes an empty address for any sold comp in the “2. Comparable Sales (Sold Properties)” table.`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-10.0
  - mini evidence: _"Sold Comp 1: Sold at $275,000 (DOM: 32)
Sold Comp 2: Sold at $290,000 (DOM: 28)"_
- task `6074bba3…` rubric `6b89dde8…`  (max_score=-10)  `Fails to reference at least one active or pending listing in the “6. Pricing Recommendations” section.`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-10.0
  - mini evidence: _“Based on current active and closed comparables, pricing near the median supports strong buyer interest while maintaining defensible value.”_
- task `61f546a8…` rubric `a48535eb…`  (max_score=-10)  `Schedules Clever Carpet or carpet work in any unit on a date other than on of the following: July 3, 2025; July 7, 2025; July 8, 2025; July 9, 2025; July 10, 20`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-10.0
  - mini evidence: _Clever Carpet Cleaning M24 Carpet Replacement Refrigerator 7/3/25 No_
- task `61f546a8…` rubric `968e284b…`  (max_score=-10)  `Schedules Sam Williams or paint work in any unit on a date other than on of the following: July 2, 2025; July 8, 2025; July 9, 2025; July 10, 2025; July 11, 202`
  - hybrid: verdict=**fail** awarded=-0.0  vs mini: verdict=**pass** awarded=-10.0
  - mini evidence: _[REDACTED] Paint M17 Partial Paint Hot Water Tank 7/2/25 No; [REDACTED] Paint M30 Full Paint None 7/8/25 No_

