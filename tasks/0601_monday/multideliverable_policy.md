# MULTI-DELIVERABLE POLICY

## 한 줄 결론

Set-diff(reference 제외) 후 생성 후보가 2개 이상인 task는 **79 / 220**이다. 그중 진짜 복수 primary deliverable로 봐야 하는 `separate_equivalent`는 **43개**, `main_plus_support`는 **27개**, `format_variants`는 **2개**, `ambiguous`는 **7개**, set-diff가 놓친 reference성 `spurious_echo`는 **0개**로 분류했다. 전체 critical `Overall formatting and style` **140개** 중 다중 후보 task에 걸린 것은 **45개**이고, 그중 **26개**가 진짜 복수 primary deliverable에 걸린다. 권고 정책은 **hybrid**: file-specific criterion은 해당 파일로, `main_plus_support`의 task-level style은 primary만, `separate_equivalent`의 task-level style은 primary deliverable별로 split 후 엄격 집계, cross-file consistency criterion은 bundle로 평가한다. 정책 확정 후 selector를 그 형태로 한 번에 구현하고, audit 필드와 인증 복구 후 재채점은 한 번만 가는 순서가 맞다.

## PHASE 1 - 다중 산출물 범위 + 분류

### 방법

- Source metadata: `batch-runner/results/exp003_GPT52Chat_baseline_runner_exec/report/report_data.json`
- Reference source of truth: `reference_file_urls` URL-decoded basename.
- Generated candidate rule: `deliverable_files` minus exact normalized reference basenames.
- Classification evidence: post-set-diff filenames, prompt delivery wording, and rubric file/existence criteria in `data/gdpval-local/data/train-00000-of-00001.parquet`.
- This is a policy analysis, not a grade. If the generated files fail the requested type, that is noted as ambiguity/primary-absent; no quality score is inferred.

### Class 집계

| class | tasks |
|---|---:|
| `separate_equivalent` | 43 |
| `main_plus_support` | 27 |
| `format_variants` | 2 |
| `spurious_echo` | 0 |
| `ambiguous` | 7 |

Interpretation:

- `separate_equivalent`: multiple independent primary outputs are requested. They may differ in type and weight, but they are not mere embedded support files.
- `main_plus_support`: one primary output is requested or dominates the rubric; extra images/workbooks/text are support artifacts, embedded assets, scratch analyses, or leaked companion files.
- `format_variants`: same substantive deliverable emitted in multiple formats, usually while rubric asks for one required format.
- `spurious_echo`: set-diff missed a reference/input residual. None were provable by basename/rubric review in this 79-task set.
- `ambiguous`: required primary deliverable is absent or the file set cannot be deterministically interpreted without owner/pipeline policy.

### 다중 task 목록

| task | class | generated candidates after reference set-diff | evidence basis |
|---|---|---|---|
| `27e8912c` | `separate_equivalent` | Organizational_Ergonomic_Action_Items.docx, Workstation_Ergonomics_Checklist.pdf, chair_setup.png, key... | two primary requested files + support images |
| `17111c03` | `separate_equivalent` | Administrative Services Memo – Tentative Cleanup Schedule.pdf, Tentative_Cleanup_Schedule.xlsx | memo PDF + Excel schedule both requested |
| `c44e9b62` | `separate_equivalent` | Briefing_Note_FTE_Reductions_Administrative_Support_Services.docx, Revised_Org_Chart_Administrative_Su... | briefing note + org chart + FTE report |
| `99ac6944` | `main_plus_support` | IEM_Budget_Breakdown.png, IEM_Budget_Breakdown.xlsx, IEM_Signal_Flow.png, West_Coast_Tour_IEM_Mobile_S... | single PDF required; xlsx/png are embedded/support artifacts |
| `ff85ee58` | `ambiguous` | Tavarua_Mix_Reconstruction_Report.docx, Tavarua_Sax_Timing_Grid.xlsx | required WAV/audio primary absent; only reconstruction docs |
| `05389f78` | `separate_equivalent` | Model_A_Headlamp_Supplier_Replacement_CPO_Report.docx, Model_A_Juvoxa_Termination_Email.docx | two separate docx files explicitly required |
| `a74ead3b` | `separate_equivalent` | Session_13_Nurturing_Parenting_Recovery.pptx, Session_14_Nurturing_Parenting_Recovery.pptx, neutral_ba... | Session 13 and Session 14 decks both required; background image support |
| `bbe0a93b` | `separate_equivalent` | Kent_County_Community_Resource_Guide.pdf, Kent_County_Needs_Assessment_English.pdf, Kent_County_Needs_... | English assessment + Spanish assessment + resource guide |
| `4c18ebae` | `main_plus_support` | SAR_Bluehaven_Silverleaf_Tavery_Curcun.docx, SAR_Supporting_Transactions.xlsx | SAR narrative primary + supporting transactions workbook |
| `a45bc83b` | `separate_equivalent` | GCP_POC_Implementation_Guide.docx, Proposed_GCP_Architecture_Diagram.pdf, Proposed_GCP_Architecture_Su... | summary doc + architecture diagram + POC guide |
| `fccaa4a1` | `main_plus_support` | Early_Access_Statue_of_Liberty_Ellis_Island_Tour.pdf, statue_of_liberty_illustration.png | single tour PDF; illustration asset |
| `f5d428fd` | `main_plus_support` | Seven_Day_Bahamas_Yacht_Itinerary.pdf, eleuthera.png, harbour_island.png, highbourne_cay.png, nassau.p... | single itinerary PDF; image assets |
| `2fa8e956` | `main_plus_support` | Napa_Valley_Vineyards.png, Napa_Valley_Wineries_Within_One_Hour.docx | single Word document; vineyard image asset |
| `aa071045` | `separate_equivalent` | Damage_Revenue_Report_ORD_2025-09-17.xlsx, Service_Request_Form_Vehicle_Maintenance_ORD_2025-09-18.docx | service request form + damage revenue report |
| `476db143` | `separate_equivalent` | September_2025_Move-Out_Inspection_Email.pdf, September_2025_Move-Out_Inspection_Schedule.pdf | email template + inspection schedule |
| `61717508` | `separate_equivalent` | Elder_Abuse_and_Financial_Exploitation_Quick_Guide.pdf, Mock_Elder_Exploitation_Role_Play_Accounts.pdf | two PDFs explicitly required |
| `0ed38524` | `separate_equivalent` | ECID_Board_Meeting_Talking_Points.pdf, ECID_Constituent_Feedback_Summary_By_District.pdf | summary + board talking points |
| `9a8c8e28` | `separate_equivalent` | Accessibility_Framework_Guide_for_Online_Journalism.pdf, Editorial_Accessibility_Knowledge_Quiz.pdf, E... | guide + checklist + quiz PDFs |
| `e222075d` | `ambiguous` | Graphic_Renewable_Reliable_Green_Energy.png, Graphic_Urge_Your_Legislator.png, Support_Green_Energy_30... | required MP4 absent; planning/graphics artifacts only |
| `c94452e4` | `ambiguous` | Care_Not_Cutbacks_Animatic.pptx, Care_Not_Cutbacks_Stock_and_Music_References.docx, Care_Not_Cutbacks_... | required MP4 absent; storyboard/timing/assets only |
| `75401f7c` | `ambiguous` | Goodsin_Studios_Showreel_Edit_Plan_2025.docx, Goodsin_Studios_Showreel_Storyboard.pdf, Goodsin_Studios... | required MP4 absent; storyboard/timeline artifacts only |
| `a941b6d8` | `ambiguous` | Teleportation_Compositing_Workflow.pdf, Teleportation_Shot_Timing.xlsx, Teleportation_VFX_Shot_Plan.do... | required composited video absent; planning/mock assets only |
| `e21cd746` | `format_variants` | Last_Mile_Logistics_MA_Overview_April2025.pdf, Last_Mile_Logistics_MA_Overview_April2025.pptx | same M&A overview in PPTX and PDF; rubric requires single PDF |
| `c7d83f01` | `ambiguous` | convergence_binomial.png, pricing_comparison.png, runtime_benchmark.png | required ipynb absent; plots only |
| `b78fd844` | `format_variants` | Tiny-Rod Hit Inc – FY2025 Investment Evaluation Report.docx, Tiny-Rod Hit Inc – FY2025 Investment Eval... | same investment report in docx and PDF; rubric requires PDF |
| `62f04c2f` | `separate_equivalent` | Gravon_Shoes_Exchange_Authorization_Form.xlsx, Gravon_Shoes_Exchange_Program_Overview.docx | Word overview + Excel authorization form |
| `6dcae3f5` | `separate_equivalent` | Chief Key Indicator 5-Year.xlsx, Email_to_PD_Key_Indicator_Analysis.docx | Excel analytical workbook + email/briefing document |
| `1aecc095` | `separate_equivalent` | MA_Telehealth_Email.docx, Telehealth Roadmap.docx, Telehealth Workflow.docx | workflow + roadmap + email/comm document |
| `4d1a8410` | `separate_equivalent` | Allen_GroupA_Itinerary.docx, Isabelle_GroupB_Itinerary.docx, NAMC_MTP_Interview_Schedule.docx | master schedule + two applicant itineraries |
| `a95a5829` | `ambiguous` | General_Order_Training_Request_Process.docx, Training_Request_Log.xlsx | rubric says single PDF; generated docx + log workbook |
| `bf68f2ad` | `main_plus_support` | MIG_Welding_Catch_Up_Plan.xlsx, MIG_Welding_Catch_Up_Summary.txt | Excel plan primary + text summary |
| `efca245f` | `main_plus_support` | Running_Board_Recovery_Plan.xlsx, Running_Board_Recovery_Summary.docx | Excel recovery plan primary + summary doc |
| `bd72994f` | `separate_equivalent` | Client_Appointment_Outreach_Template.docx, Luxury_Brand_Resort_2025_Styled_Looks.pdf | styled-look deck + outreach template |
| `cecac8f9` | `separate_equivalent` | Black_Friday_2024_8_Week_Preparation_Plan.pdf, Black_Friday_2024_Team_Launch_Deck.pdf | 8-week plan + launch deck |
| `4d61a19a` | `separate_equivalent` | Promo Projection Form.pptx, Promotion Projection Form Template.xlsx | Excel template + PowerPoint training deck |
| `40a99a31` | `separate_equivalent` | CNC_Cell_Safety_and_Visibility_Layout.png, Hardware_Selection_and_Costs.xlsx, Robotic_CNC_Cell_Design_... | report + hardware workbook; diagram image support |
| `c6269101` | `main_plus_support` | Brightland_Process_Capability_Review.pptx, failure_rate_trend.png, system_error_trend.png, task_durati... | PowerPoint primary + chart images |
| `be830ca0` | `main_plus_support` | ANOVA_Interval_Plot.png, IMR_Control_Chart_Baseline.png, IMR_Control_Chart_Full.png, LLS_Processing_Ra... | PowerPoint primary + analysis images |
| `5e2b6aab` | `separate_equivalent` | Toasty_Assembly_Drawings.pdf, Toasty_STEP_Models.zip | assembly drawings PDF + STEP model zip |
| `46fc494e` | `main_plus_support` | Backface_Temperature_Summary.xlsx, C_SiC_Heat_Shield_Thermal_Screening_Report.docx, Isotherms_20min.pn... | report primary + workbook/plots supporting analysis |
| `8077e700` | `main_plus_support` | AISI1018_Hardness_vs_Time.png, Heat_Treatment_Analysis_Report.pdf | single PDF report + plot image |
| `5a2d70da` | `separate_equivalent` | Cover_Plate_Manufacturing_Steps.xlsx, Cover_Plate_Master_Tool_List.xlsx | two required Excel workbooks |
| `61b0946a` | `main_plus_support` | Collaborative Cadaver Program Proposal.docx, Collaborative_Cadaver_Cost_Savings.png | Word proposal primary + savings chart image |
| `c9bf9801` | `separate_equivalent` | DGHT_Formal_Mentorship_Program_Guide.docx, DGHT_Mentor_Mentee_Application.docx, DGHT_Mentorship_Roadma... | multiple mentorship Word templates/guides |
| `f1be6436` | `main_plus_support` | 2026 ACP-IMM Estimated Costs.docx, flights.png, lodging.png, registration.png, transport.png | Word cost estimate primary + image assets |
| `41f6ef59` | `separate_equivalent` | June 2025 Declined Payments Outreach.xlsx, Third Declined Payment Email Template.docx | outreach workbook + email template |
| `6d2c8e55` | `separate_equivalent` | December_Journal_Club_Dietitians_in_Preventive_Medicine.pdf, December_Journal_Club_Interdisciplinary_P... | schedule + review email + article PDFs |
| `4b98ccce` | `separate_equivalent` | DECEASED CORRESPONDENCE 2025.docx, GENERAL CORRESPONDENCE 2025.docx, PATIENT INCIDENT 007.xlsx | two correspondence docs + incident workbook |
| `3baa0009` | `main_plus_support` | World_Bank_Global_Economic_Prospects_June_2025.docx, World_Bank_Global_Growth_Forecast.jpg | article primary + chart image; generated primary is wrong format |
| `1b9ec237` | `main_plus_support` | BP_Measurement_Illustration.png, Hypertension_Lecture_Nursing_Students.pptx | presentation primary + illustration image |
| `e6429658` | `separate_equivalent` | RP Financial Assistance Application.pdf, Vraylar Appeal for RP.docx | appeal letter + assistance application |
| `47ef842d` | `main_plus_support` | Out_of_Stock_Rate_by_UPC.png, Top5_UPC_Inventory_Summary.xlsx | single workbook primary + plot image |
| `1137e2bb` | `separate_equivalent` | Wholesale_PO_Error_Audit.xlsx, Wholesale_PO_Error_Audit_Summary.docx | audit workbook + summary Word doc |
| `c3525d4d` | `separate_equivalent` | Draft_Email_Floorstand_Budget_Update.docx, Holiday_Floorstand_Budget_Comparison.xlsx | budget workbook + draft email |
| `c657103b` | `separate_equivalent` | 8_Year_Roth_Conversion_Strategy_Overview.pptx, Roth_Conversion_8_Year_Tax_and_Estate_Analysis.xlsx | strategy deck + analysis spreadsheet |
| `ae0c1093` | `separate_equivalent` | Undercover_Observation_Form.pdf, Undercover_Operations_Guide_Employee_Evaluation.pdf | guide PDF + observation form PDF |
| `f9f82549` | `separate_equivalent` | Missing Bank Deposits Investigation.pdf, Missing_Bank_Deposits_Incident_Details.pptx | incident details + flowchart deliverables |
| `02aa1805` | `separate_equivalent` | Illinois_Water_Well_Screening.xlsx, Water_Source_Screening_Email.docx | screening workbook + recommendation email |
| `fd6129bd` | `separate_equivalent` | Change_Control_SOP.docx, Change_Request_Form.xlsx | SOP + change request form |
| `ce864f41` | `main_plus_support` | Workload_Analysis_Responses_March_2025.docx, Workload_Distribution_Tracker_March_2025.xlsx | workload tracker primary + response doc |
| `58ac1cc5` | `separate_equivalent` | Change_Control_Request_QY_GEL_Antifoam.pdf, Internal_Summary_QY_GEL_Antifoam.txt, QA_Escalation_Email_... | change request + risk assessment + email + internal summary |
| `46bc7238` | `main_plus_support` | QSR_Tenant_Outreach_Playbook_123_Dade_County_Rd.pdf, stock_image_1.jpg, stock_image_2.jpg, stock_image... | single PDF playbook + stock images |
| `0818571f` | `main_plus_support` | Daytona_Retail_Plaza_map.png, Daytona_Retail_Plaza_photo.png, Fort_Myers_Neighborhood_Center_map.png, ... | consolidated report primary + underwriting/images support |
| `6074bba3` | `main_plus_support` | CMA_112_Pine_Crest_Ln_Adairsville_GA.pdf, days_on_market.png, list_vs_sale_price.png | CMA PDF primary + chart images |
| `5ad0c554` | `main_plus_support` | Buyer_Broker_Agreement_and_Homebuying_Guide_Sarasota.docx, homebuyer_banner.png | single Word brochure + banner image |
| `11593a50` | `separate_equivalent` | Weekend_Showings_Map.pdf, Weekend_Showings_Selection.pdf | property selection PDF + one-page map PDF |
| `94925f49` | `separate_equivalent` | Floral_Park_Bellerose_School_Report.pdf, Garden_City_Park_School_Report.pdf, Hillside_Grade_School_Rep... | five school PDF reports |
| `a73fbc98` | `separate_equivalent` | Spring_Bazaar_2025_Table_Assignment_Summary.pdf, Spring_Bazaar_2025_Vendor_Assignments.xlsx | vendor spreadsheet + layout PDFs expected |
| `7151c60a` | `separate_equivalent` | Facility_Admission_Pre_Screening_Checklist.docx, Fax_Cover_Sheet.docx | fax cover sheet + pre-screening checklist |
| `90edba97` | `main_plus_support` | Monthly_Lab_Review_Nursing_Summary.docx, Monthly_Tracker_Patient_Lab_Results_Completed.xlsx | single workbook primary + nursing summary doc |
| `045aba2e` | `separate_equivalent` | Daily_Compliance_Checklist_CA_Pharmacy.pdf, Quarterly_Annual_Compliance_Checklist_CA_Pharmacy.pdf, Wee... | three separate compliance checklist PDFs |
| `a69be28f` | `main_plus_support` | Exec_Men_Units.png, Exec_Women_Units.png, Midwest_Men_Revenue.png, Midwest_Men_Units.png, Midwest_Wome... | presentation PDF primary + chart images |
| `69a8ef86` | `separate_equivalent` | External_Return_Authorization_Guidelines_for_Key_Accounts.docx, Internal_Return_Authorization_Process.... | internal process + external guidelines |
| `ab81b076` | `main_plus_support` | Dealer_Parts_Order_Check-In_Procedure.pdf, visual_checkin_flow.png, visual_damage_documentation.png | single procedure PDF + visual assets |
| `fe0d3941` | `separate_equivalent` | Instant_non-invasive_blood_analysis_Survey.pdf, Workflows.pptx | survey PDF + workflows PPTX |
| `1d4672c8` | `separate_equivalent` | NexVen_Correlation_Analysis_Report.pdf, NexVen_International_Correlation_Analysis.xlsx | analysis report + workbook |
| `bb499d9c` | `main_plus_support` | Asset_Issuer_Sales_Process_Flowchart.png, Retail_Investor_Sales_Process_Flowchart.png, Sales_Operation... | single Word process doc + flowchart images |
| `552b7dd0` | `main_plus_support` | Inventory_Incident_Analysis_2025.pptx, avg_duration_by_type.png, incident_percentage_per_supplier.png,... | PowerPoint primary + chart images |
| `4122f866` | `main_plus_support` | README.md, contact_form_backend.zip | single zip primary; README leaked outside zip |

## PHASE 2 - rubric 참조 수준

### Criterion-level distribution in the 79 multi-candidate tasks

There are **3717** rubric items across the 79 tasks. The following is a heuristic reference-level classification from criterion text. It is meant to expose selector/routing shape, not to grade correctness.

| reference level | items | meaning |
|---|---:|---|
| task-level generic/content | 2003 | rubric criteria not tied to a named file; often substantive content checks |
| file-specific content | 1255 | names a file type, sheet, slide, document, form, chart, email, etc. |
| count/existence/format | 414 | file count, extension, openability, submitted-as checks |
| task-level overall style | 45 | exact `Overall formatting and style of the deliverable` |

### By task class

| task class | overall-style | count/existence | file-specific | task-level generic/content |
|---|---:|---:|---:|---:|
| `separate_equivalent` | 26 | 228 | 908 | 870 |
| `main_plus_support` | 14 | 124 | 276 | 934 |
| `format_variants` | 2 | 12 | 41 | 24 |
| `ambiguous` | 3 | 50 | 30 | 175 |

### Critical Overall Style collision

- Whole benchmark exact `Overall formatting and style of the deliverable`: **140** items.
- Critical subset `abs(max_score) >= 4`: **140** items.
- Multi-candidate tasks containing that criterion: **45** items across **45** tasks.
- By class: `separate_equivalent` **26**, `main_plus_support` **14**, `format_variants` **2**, `ambiguous` **3**.

These **45** are the policy pressure point. A single-string criterion says “the deliverable” while the selected target may be two primary decks, three PDFs, or one main report plus asset PNGs. Leaving this to the judge creates nondeterministic file choice; forcing every case into one bundle makes support assets over-visible; splitting every case makes single-primary tasks noisy. That is why the data points to hybrid.

## PHASE 3 - 정책 권고

### Recommended policy: hybrid

1. **Manifest / count / extension criteria** use the selected file manifest, not an LLM guess. Example: “Provides two distinct .pptx files” or “single PDF file is delivered”.
2. **File-specific criteria** route to the named or inferred file target. Example: workbook tab checks go to the workbook; slide checks go to the specified deck; layout PDF checks go to the layout PDF.
3. **Cross-file consistency criteria** get a bundle, but only of the relevant primary targets. Example: spreadsheet-to-layout agreement in `a73fbc98` needs workbook plus layout PDFs.
4. **`main_plus_support` task-level style** grades the primary deliverable only. Support PNGs/XLSX/text files should be hidden from generic style unless the criterion explicitly asks about them or they are embedded in the primary rendered output.
5. **`separate_equivalent` task-level style** should be split by primary deliverable, with child evaluations preserved. Recommended strict aggregation: if any child has a blocking defect or is absent, cap/fail the parent; otherwise use an unweighted mean or minimum depending on owner tolerance. My recommendation for GDPVal strictness: **blocking-defect min, non-blocking mean**.
6. **`format_variants`** chooses the rubric-required format as primary. Extra variant is audit-only unless the rubric explicitly asks for both.
7. **`ambiguous` / no matching primary** returns `selection_error`, not an arbitrary first file and not a reference fallback.

### Selector return type required by this policy

The selector should not return a bare path. It should return a structured selection object:

```json
{
  "selection_status": "ok|ambiguous|no_matching_primary|no_generated_candidate",
  "task_id": "...",
  "task_class": "separate_equivalent|main_plus_support|format_variants|ambiguous",
  "primary_targets": [
    {"target_id": "checklist_pdf", "paths": ["...pdf"], "kind": "pdf", "role": "primary", "evidence_rule": "rubric_filename_or_kind"}
  ],
  "support_artifacts": ["...png", "...xlsx"],
  "reference_files_excluded": ["..."],
  "selection_rule": "set_diff_then_rubric_kind",
  "selection_error": null
}
```

For item grading, grade JSON needs item-level target audit:

```json
{
  "rubric_item_id": "...",
  "target_scope": "manifest|file_target|primary_bundle|split_children|selection_error",
  "target_ids": ["..."],
  "child_grades": [
    {"target_id": "...", "score": 4.0, "evidence": "..."}
  ],
  "aggregation_rule": "blocking_min_else_mean|null",
  "selected_paths": ["..."],
  "support_paths_visible": []
}
```

This preserves the original rubric item while making the selected file(s) auditable. It also prevents future Bug2 investigations from having to infer the file path from evidence.

### Gold examples under hybrid

| task | observed class | hybrid behavior for generic Overall Style | why |
|---|---|---|---|
| `27e8912c` | `separate_equivalent` with support images | split into checklist PDF and action-items DOCX; images are support unless embedded | prompt/rubric explicitly ask for one checklist PDF and one action-items DOCX |
| `a74ead3b` | `separate_equivalent` with support image | split Session 13 deck and Session 14 deck; aggregate child style scores | two distinct `.pptx` files are explicitly required |
| `bbe0a93b` | `separate_equivalent` | split English assessment, Spanish assessment, and resource guide PDFs | rubric says each is a standalone PDF |
| `6dcae3f5` | `separate_equivalent` | split analytical workbook and email/briefing document, or route file-specific items individually | workbook is primary analytical deliverable, but the email doc is also a requested output |
| `99ac6944` | `main_plus_support` | do not split PNG/XLSX; grade required single PDF, use support only if checking embedded cost/signal-flow images | rubric says a single PDF is delivered |
| `b78fd844` | `format_variants` | choose PDF as primary; DOCX is audit-only extra | rubric requires a single PDF |

## owner 결정 필요

1. Confirm hybrid as the selector policy.
2. Confirm aggregation for split overall-style children. Recommended: blocking defect in any required child caps/fails parent; otherwise average child scores.
3. Confirm that `selection_error` is a harness/audit error, not automatic rubric fail, unless the rubric item itself is a file existence criterion.
4. Then implement selector once with structured return type, persist audit fields, restore authenticated artifact access, and run one recalculation/regrade pass. The expensive mistake would be implementing a path-only selector now and changing bundle/split semantics later.
