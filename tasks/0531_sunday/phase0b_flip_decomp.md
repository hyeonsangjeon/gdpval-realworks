# PHASE 0(b) — fail->pass / partial->pass flip decomposition (mini vs standard)

Shared exp003 tasks: 10
Total leniency flips (mini > standard): 38
  judge-decided side (either): 38 (rest involve precheck)
  type counts: {'fail->partial': 8, 'partial->pass': 21, 'fail->pass': 9}
  modality totals: {'text': 32, 'formatting': 3, 'visual': 3}

## Modality breakdown by flip type

| type | total | visual | audio | formatting | text |
|---|---:|---:|---:|---:|---:|
| partial->pass | 21 | 0 | 0 | 1 | 20 |
| fail->pass | 9 | 2 | 0 | 1 | 6 |
| fail->partial | 8 | 1 | 0 | 1 | 6 |

Evidence similarity (loose char-overlap >=70% or substring): 32/38 flips look like *same evidence, different verdict* (consistent with leniency rather than mini reading differently).

## All flips (detailed)

| task | type | modality | max | criterion | std evidence | mini evidence |
|---|---|---|---:|---|---|---|
| 17111c03 | fail->partial | text | 1 | The memo states that an Excel version of the schedule is attached or … | "Please use the attached tentative schedule when responding to inquir… | “Please use the attached tentative schedule” |
| 27e8912c | partial->pass | text | 1 | The checklist includes a distinctly labeled section or grouping for W… | n Work Surface: Desk height allows relaxed shoulders and neutral arm … | "n Work Surface: Desk height allows relaxed shoulders and neutral arm… |
| 43dc9778 | fail->pass | text | 2 | Provides a PDF of IRS Form 1040 (tax year 2024) containing pages 1 an… | 2024 Individual Income Tax Return – Form 1040 (Draft) | "page_count": 2; "2024 Individual Income Tax Return – Form 1040" |
| 43dc9778 | fail->pass | text | 2 | Form 1040 line 25a (federal income tax withheld from Forms W‑2) is $2… | "- Federal income tax withheld per Wn2s" | "Federal income tax withheld per Wn2s" |
| 43dc9778 | partial->pass | text | 2 | Form 1040 line 26 (estimated tax payments and amount applied from 202… | - 2024 estimated tax payments totaling $13,685 | "2024 estimated tax payments totaling $13,685" |
| 7b08cd4d | partial->pass | text | 2 | For each tour stop, no revenue is attributed to the production compan… | Date,City,Country,Gross Revenue USD,Withholding Rate,Withholding Tax … | Date,City,Country,Gross Revenue USD,Withholding Rate,Withholding Tax … |
| 7d7fc9a7 | fail->pass | formatting | 2 | Delivers a single Excel workbook file in .xlsx format. | "kind": "pdf", "filename": "Aurisic_Prepaid_Expenses_Apr25.pdf" | "kind": "xlsx", "filename": "Aurisic_Prepaid_Amortization_Schedule_Th… |
| 7d7fc9a7 | partial->pass | text | 2 | On 1250, each line’s Monthly Expense is calculated on a straight-line… | Global Services,2025-04-01 00:00:00,81000,Apr-2025,13500,67500 Global… | ADOBE MAGENTO,2025-01-01 00:00:00,10377.75,Jan-2025,1729.62,8648.12 A… |
| 7d7fc9a7 | partial->pass | text | 1 | The 1250 detailed schedule is organized by vendor (grouped and/or sor… | "CDW,2025-02-01 00:00:00,3968.47...Jul-2025,661.41,0\nExpertek,2025-0… | "ADOBE MAGENTO... ALTAIR... AMESITE... CDW... Expertek..." |
| 83d10b06 | partial->pass | text | 2 | The first worksheet contains the selected sample data copied from the… | No,Division,Sub-Division,Country,Legal Entity,KRIs,Q3 2024 KRI,Q2 202… | No,Division,Sub-Division,Country,Legal Entity,KRIs,Q3 2024 KRI,Q2 202… |
| 83d10b06 | fail->pass | text | 2 | For every row included on the first worksheet, the values in columns … | "sheets": [{"name": "Sheet1", "max_row": null, "max_col": null}] | 1,AM,Asset Management,Australia,Willett Bank Australia Investments,To… |
| 83d10b06 | fail->pass | text | 1 | The header for column J clearly indicates it represents quarter‑on‑qu… | "No,Division,Sub-Division,Country,Legal Entity,KRIs,Q3 2024 KRI,Q2 20… | "No,Division,Sub-Division,Country,Legal Entity,KRIs,Q3 2024 KRI,Q2 20… |
| 83d10b06 | fail->partial | formatting | 5 | Overall formatting and style of the deliverable | "fill": "00000000", "bold": false, "font_color": "Values must be of t… | "merged_ranges": [], "column_widths": {}, "has_charts": false |
| a328feea | fail->pass | text | 2 | Document is one page or less in length. | "kind": "docx", "paragraph_count": 9, "table_count": 0, "section_coun… | "paragraph_count": 9, "char_count": 1732 |
| a328feea | partial->pass | text | 1 | Includes within the 'Definitions' section 'MFA' (Medical or Family As… | “• MFA Case File: An approved Medical or Family Assistance case requi… | “MFA Case File: An approved Medical or Family Assistance case requiri… |
| a328feea | fail->partial | text | 1 | Includes within the 'Procedure' section additional reporting guidance… | "e) Any information related to an MFA case file must be communicated … | "Any information related to an MFA case file must be communicated by … |
| c44e9b62 | fail->partial | text | 3 | Mentions the updated FTE report is targeting Administrative Support S… | "Position Title,FTE(s),Planned FTE Reduction,Planned FTE Next Fiscal … | ADMINISTRATIVE SUPPORT SERVICES BRANCH, CENTRAL SERVICES DIVISION |
| c44e9b62 | partial->pass | text | 2 | Shows the planned reduction figures for 2025-26 in the updated FTE re… | Position Title,FTE(s),Planned FTE Reduction,Planned FTE Next Fiscal Y… | "FTE(s),Planned FTE Reduction,Planned FTE Next Fiscal Year\nSuperviso… |
| c44e9b62 | fail->partial | text | 2 | Removes one Clerk II and two Data Clerks FTE under the IT Support Ser… | "Clerk II: 51 FTE (Reduced by 1)\nData Clerk: 30 FTE (Reduced by 5)" | "Clerk II: 51 FTE (Reduced by 1)... Data Clerk: 30 FTE (Reduced by 5)" |
| c44e9b62 | partial->pass | text | 2 | Explains the 10% reduction for the “Regional Support Services Supervi… | "the reduction of Regional Offices from 10 to 9 allows for a proporti… | “the reduction of Regional Offices from 10 to 9 allows for a proporti… |
| c44e9b62 | fail->pass | visual | 1 | Assumes each box in the organizational chart equals one FTE unless a … | "Supervisor: 5 FTE (Reduced by 1)" | "Policy Advisor (2)" and "Service Leads (10)" |
| c44e9b62 | fail->pass | visual | 1 | Matches the FTE report’s Branch totals (Current and Planned) with the… | "Total FTEs,237,0,237" and "Data Clerk: 30 FTE (Reduced by 5)" | "Total FTEs,237,0,237" |
| c44e9b62 | fail->partial | text | 2 | Classifies impacted reductions by service area (e.g., Regional Suppor… | "the reduction of Regional Offices from 10 to 9 allows for a proporti… | "Regional Offices from 10 to 9 allows for a proportional 10% reductio… |
| c44e9b62 | fail->pass | text | 5 | Omits contradictory revised FTE counts (no position is shown as both … | "the reduction of Regional Offices from 10 to 9 allows for a proporti… | Supervisor,6,1,5 Supervisor: 5 FTE (Reduced by 1) |
| c44e9b62 | fail->partial | visual | 5 | Adopts the layout style of the reference chart sufficiently to allow … | "Administrative Services Manager: 1 FTE\nSupervisor: 5 FTE (Reduced b… | "Revised Organizational Chart (FTE Reductions Highlighted)\nAdministr… |
| ee09d943 | partial->pass | text | 1 | The Table of Contents lists, as distinct entries, every sheet from th… | 11,Accrued Interest #2402,COMPLETE | "3a,TB convert,COMPLETE" ... "Accrual – Misc #2410,April 2025 source … |
| ee09d943 | partial->pass | text | 1 | The April Corporate Funding Sources tab indicates funding from seven … | "Aurisic UK,450155" ... "Aurisic US,338488" ... "Aurisic UK,197280" .… | Aurisic UK,450155,,,, Aurisic US,338488,,,, Aurisic UK,197280,,,, Aur… |
| ee09d943 | partial->pass | text | 1 | The Professional Fees Accrual schedule (GL 2404; name contains 'Prof … | GLAcctno,Gltitle... 2404,Accrued Legal/Audit Fees ... "Balance at 4-3… | "Balance at 4-30-25,,,,-160270.21999999997" |
| ee09d943 | partial->pass | text | 1 | The Legal/Audit Expense schedule (GL 6200; name contains 'Legal Audit… | "Balance #6200 at 3-31-25,870569.3800000001" | "Balance #6200 at 3-31-25,870569.3800000001" |
| ee09d943 | partial->pass | text | 1 | The A/R Accruals schedule (GL 1101; name contains 'AR Accruals' and '… | "Aurisic A/R Accrual #1101" ... "as of 4-30-25" ... "Total Accrued #1… | "Aurisic A/R Accrual #1101" ... "as of 4-30-25" ... "Total Accrued #1… |
| ee09d943 | partial->pass | text | 1 | The Accrual for Uninvoiced (Aurisic Glob Accrual #2011; name contains… | [Sheet: Aurisic Global Accrual #2011] as of 4-30-25,, Total,304169.11, | "as of 4-30-25,," ... "Total,304169.11," |
| ee09d943 | partial->pass | text | 1 | The Miscellaneous Accruals schedule (GL 2410; name contains 'Misc Acc… | [Sheet: Misc Accruals #2410] ...Balance at 4-30-25,,146796.7599999999… | "Balance at 4-30-25,,146796.75999999998," |
| ee09d943 | partial->pass | formatting | 1 | The workbook uses March's template styling and tab sequence for share… | "name": "Table of Contents" ... "name": "#15) Vendor Rebates #2005" | "Table of Contents", "#3a) TB convert 3-31-25", "#4) Cash Availabilit… |
| f84ea6ac | partial->pass | text | 2 | Reviews five academic articles on the topic of AI and automation in g… | "OECD (2021) “The Impact of AI on the Public Sector Workforce”" | [REDACTED] (2021)... [REDACTED] (2021)... [REDACTED] (2022)... [REDAC… |
| f84ea6ac | partial->pass | text | 3 | Reviews academic articles published in a peer-reviewed journal or aca… | "Wirtz, B. W., Weyerer, J. C., & Geyer, C. (2021) ‘Artificial Intelli… | “This table summarizes recent academic research (published after 2020… |
| f84ea6ac | fail->partial | text | 5 | Structures the final Scan of Research so that it fits within one page. | "char_count": 2668, "truncated": false | "paragraph_count": 2, "table_count": 1, "section_count": 1 |
| f84ea6ac | partial->pass | text | 3 | Reviews five academic articles in the deliverable. | "OECD (2021) “The Impact of AI on the Public Sector Workforce”" | [REDACTED] (2021) ... [REDACTED] (2021) ... [REDACTED] (2022) ... OEC… |
| f84ea6ac | partial->pass | text | 1 | Includes the setting (country/region, government level, specific agen… | "OECD (2021) ... Cross-national public sector workforce study" | "Cross-national public sector workforce study" |

## Hypothesis verdict (Phase 0b)

REJECTED: 32/38 flips are pure text criteria. Leniency is not a modality-blindness symptom; perception wiring is unlikely to recover these. Investigate judge strictness drift independently.
