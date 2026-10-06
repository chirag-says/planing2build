# Plan2Build: requirement questions, version 1 (LOCKED implementation version)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/REQUIREMENT_QUESTIONS_V1.md` |
| Version | 2.0, LOCKED 2026-10-04 by Chirag's final rulings. The locked set is section L. Sections 0 to 7 are the history that led to it |
| Date | 2026-10-04 |
| Status | LOCKED. Section L is the implementation version: the seeded question set (`requirement_question_sets` version 1) must equal it. A change is a new question set version with Chirag's approval, never an edit in place |
| Purpose | The question set for the homeowner requirement (J06) in slice 1, traced to the sources, without inventing options |
| Implementation | Seeded as `requirement_question_sets` version 1 by migration `0004_handover1_projects` from `apps/api/migrations/data/requirement_questions_v1.json`. `apps/api/tests/test_questions.py` fails if the seeded keys or options differ from the L.2 table below. The web form renders from `GET /api/v1/public/requirement-questions` (2026-10-04) |
| Sources read for this document | `IHB_FLOW.md` sections 8.6, 8.7, 12.2 (F-020 to F-043), 24, 25, 26, 32, 33; `PROFESSIONALS_FLOW.md` 44.7; `RECOMMENDATION_ENGINE.md` sections 4, 5, 12; `DATA_ARCHITECTURE.md` 4.3; and, read directly on 2026-10-04: S05 (`Plan2Build_MVP_Build_Plan.docx` sections 5, 6, 9), S06 (`Plan2Build_Technology_Product_Blueprint_with_Journey_Maps.docx` sections 6, 7, 10), S07 (`Plan2Build_Client_Product_and_Implementation_Blueprint.docx` 4.1, 4.2), S14 (prototype calculator), S23c (Post Your Requirement mockup), S24 page 3 (pitchboard requirement page) |

## L. Locked question set, version 1 (implementation version)

Provenance column: R-n is Chirag's final ruling number n (2026-10-04); "round 1" is his first spoken answers; "delegated" is Sakha's design under Chirag's delegation (section 0.1), carried into the locked document when he instructed it to be locked, and not separately confirmed by him; "default" is a choice Sakha made where no ruling exists, listed in L.4 so each can be changed.

### L.1 Entry (before the form, on the public site)

| Key | Screen wording | Answers | Provenance | Behaviour |
|---|---|---|---|---|
| `entry_new_home` | "Are you building a new home?" | Yes; No | R-1; CD-03 | No opens the "Need help?" path (L.3) |
| `entry_in_raipur` | "Is your plot in Raipur?" | Yes; No | R-2 (the message); the question itself is default D-1 | No opens the other-city capture (L.3) |

### L.2 The requirement form

| Key | Screen wording | Type | Options (stored value: label) | Required | Provenance |
|---|---|---|---|---|---|
| `location` | "Mark your plot on the map" | Map pin (latitude, longitude) | | Yes | Round 1 (Q04) |
| `locality` | "Locality" (filled from the pin; the family can correct it) | Short text, up to 120 characters | | Yes | R-3 |
| `property_type` | "What are you building?" | One choice | `INDEPENDENT_HOUSE`: Independent house; `VILLA`: Villa; `MULTI_FLAT_OWN_PLOT`: Apartment / multi-flat building on your own plot; `OTHER`: Other | Yes | R-4 |
| `property_type_other` | "Tell us what you are building" | Short text, up to 200 characters; shown only for Other | | Yes when Other | R-4 |
| `plot_is_rectangular` | "Is your plot a rectangle?" | Yes / No | | Yes | Delegated (Q06) |
| `plot_width_ft` | "Plot width (feet)" | Number, 5 to 1,000; shown when rectangular | | Yes when rectangular | Delegated (Q06); bounds default D-2 |
| `plot_depth_ft` | "Plot depth (feet)" | Number, 5 to 1,000; shown when rectangular | | Yes when rectangular | Delegated (Q06); bounds default D-2 |
| `plot_area_sqft` | "Total plot area (sq ft)" | Number, 100 to 200,000; shown when not rectangular. For a rectangle the system computes width x depth | | Yes when not rectangular | Delegated (Q06); bounds default D-2 |
| `built_up_area_sqft` | "Total built-up area across all floors (sq ft)" | Number, 300 to 12,000, or "Not sure yet" | | Yes (a number or Not sure yet) | Delegated (Q07) |
| `floors` | "How many floors?" | One choice | `G`: Ground only; `G_PLUS_1`: Ground + 1; `G_PLUS_2`: Ground + 2; `G_PLUS_3`: Ground + 3 | Yes | Delegated (Q08) |
| `basement` | "Will the house have a basement?" | Yes / No | | Yes | Round 1 (Q09) |
| `quality_tier` | "Construction quality tier" (help: "How the house is built and finished: materials and specifications.") | One choice | `STANDARD`: Standard; `PREMIUM`: Premium; `LUXURY`: Luxury | Yes | Delegated (Q10); help text R-11 |
| `style` | "Style of the house" (help: "How the house looks. This guides the illustrative 3D images; it does not change the quality tier.") | One choice | `MODERN`: Modern; `CONTEMPORARY`: Contemporary; `TRADITIONAL`: Traditional; `MINIMALIST`: Minimalist; `LUXURY`: Luxury | No | R-11; optional default D-3 |
| `bedrooms` | "Bedrooms" | One choice | `1`, `2`, `3`, `4`, `5_PLUS`: 5+ | Yes | R-13 |
| `bathrooms` | "Bathrooms" | One choice | `1`, `2`, `3`, `4`, `5_PLUS`: 5+ | Yes | R-13 |
| `pooja_room` | "Pooja room" | Yes / No | | Yes | R-13 |
| `car_parking` | "Car parking" | Yes / No | | Yes | R-13 |
| `facing` | "Which way does the plot face?" | One choice | `N`: North; `S`: South; `E`: East; `W`: West; `NE`: North-East; `NW`: North-West; `SE`: South-East; `SW`: South-West; `NOT_SURE`: Not sure | Yes | R-13 |
| `setbacks` | "Setbacks (open space to leave on each side), in feet" | Front, Back, Left, Right: each a number 0 to 200, or Not sure | | Yes (each side a number or Not sure) | R-13; bounds default D-2 |
| `vastu` | "Vastu" | One choice | `MUST_FOLLOW`: Must follow; `WHERE_POSSIBLE`: Where possible; `NOT_NEEDED`: Not needed | Yes | R-13 |
| `services_needed` | "Which services do you need?" (several allowed) | Several choices | `CONSTRUCTION`: Full home construction; `ARCHITECTURAL_DESIGN`: Architectural design; `STRUCTURAL_DESIGN`: Structural design (by a registered structural engineer); `CIVIL_WORK`: Civil work; `MEP`: Electrical, plumbing and HVAC; `INTERIOR_DESIGN`: Interior design and execution; `PROJECT_MANAGEMENT`: Project management; `APPROVALS`: Approvals and legal support | No | Round 1 (Q17); optional default D-4 |
| `budget_band` | "Your construction budget (excluding land)" | One choice | `UNDER_40L`: Under ₹40L; `40L_60L`: ₹40L to ₹60L; `60L_80L`: ₹60L to ₹80L; `80L_1CR`: ₹80L to ₹1Cr; `1CR_1_5CR`: ₹1Cr to ₹1.5Cr; `ABOVE_1_5CR`: Above ₹1.5Cr | Yes | R-5 |
| `start_timeline` | "When do you plan to start building?" | One choice | `WITHIN_3M`: Within 3 months; `3_6M`: 3 to 6 months; `6_12M`: 6 to 12 months; `OVER_12M`: More than 12 months; `ALREADY_STARTED`: Already started | Yes | R-6 |
| `construction_started` | "Has construction started?" | Yes / No | | Yes | R-8 |
| `has_contractor` | "Does your family already have a contractor you want to use?" | Yes / No | | Yes | R-9 |
| `has_quote` | "Do you already have a quote from any contractor?" | Yes / No | | Yes | R-10 |
| `priorities` | "Rank what matters most to you (1 = most important)" | A ranking of all four | `QUALITY`: Quality of work; `ON_TIME`: Finishing on time; `WITHIN_BUDGET`: Staying within budget; `SIMILAR_HOMES`: Experience with similar homes | Yes (all four ranked) | R-12 |
| `notes` | "Anything else we should know?" | Text, up to 500 characters | | No | R-14 |
| `uploads` | "Drawings, a sanctioned plan or site photos" | Files: JPG, PNG, PDF; up to 10 MB each; up to 10 files | | No | R-15 |

Removed from version 1: funding source (R-7). Not in version 1: target completion, first-time builder, readiness, household members (section 4).

### L.3 The two capture paths

| Path | Screen wording | Captured | Result | Provenance |
|---|---|---|---|---|
| Need help? (coming soon) | "Need help with renovation, interiors or repairs? Tell us." | Type of work (`RENOVATION`: Renovation; `INTERIORS`: Interiors; `REPAIRS`: Repairs) and email | An enquiry for Plan2Build operations; no Phase-2 workflow | R-1 |
| Other city | "We're starting in Raipur. Leave your email and we'll let you know when we reach your city." | Email only | An enquiry for Plan2Build operations | R-2 |

### L.4 Rules applied at submission, and the defaults Sakha chose

| ID | Rule or default | Provenance |
|---|---|---|
| Rule | Budget never rejects a homeowner; it feeds the estimator, qualification and the recommendation | R-5 |
| Rule | `property_type = OTHER` adds the review flag `PROPERTY_TYPE_OTHER`; the project is not treated as qualified for the normal workflow until operations review it | R-4 |
| Rule | `construction_started = Yes` adds the review flag `CONSTRUCTION_STARTED`; the answer is recorded; no automatic pre-construction workflow | R-8 |
| Rule | Every submission goes to operations review (SUBMITTED); nothing qualifies automatically (IHB_FLOW 33.1 step 8) | B-01 |
| Rule | The family's ranking is stored as given; no universal ranking overrides it. Expert weights live in the recommendation engine, which blends them with the family's weights (RECOMMENDATION_ENGINE section 5) | R-12 |
| D-1 | The Raipur question on the entry path ("Is your plot in Raipur?") is how "other city" is detected | Default |
| D-2 | Number bounds (plot sides 5 to 1,000 ft, plot area 100 to 200,000 sq ft, setbacks 0 to 200 ft) only catch typing mistakes | Default |
| D-3 | Style is optional (S23c marks it optional; the rulings say one choice but not whether it is required) | Default |
| D-4 | Services needed is optional (S23c marks it neither required nor optional, AMB-063) | Default |
| D-5 | `start_timeline = ALREADY_STARTED` also adds the `CONSTRUCTION_STARTED` flag. The two questions overlap; both are kept as ruled and the overlap is listed as open point O-2 | Default |

### L.5 Open points that do not block version 1

| ID | Point |
|---|---|
| O-1 | CD-03 also names kitchens and extensions as phase-2 types; R-1 lists renovation, interiors and repairs only. The "Need help?" path offers the three ruled types |
| O-2 | `start_timeline = Already started` and `construction_started` overlap; the form records both |
| O-3 | A pin outside Raipur on the map is recorded as placed; whether the system should stop it is not decided. Operations see the locality at review |
| O-4 | The email captured on the two capture paths has no consent text yet; the privacy notice is launch blocker D-17 |

## 0. Answers received from Chirag (2026-10-04, spoken, transcribed)

Status words in this section:

| Status | Meaning |
|---|---|
| DECIDED | Chirag stated the answer. His words are paraphrased in the row. |
| DELEGATED | Chirag asked Sakha to decide. The row gives Sakha's design. It counts as a proposal until Chirag confirms it. |
| CLARIFY | The answer was missing, or answered a different question. The follow-up is in section 0.2. |

### 0.1 Question by question

| # | Question | Chirag's answer (paraphrase) | Status | Resulting question and options |
|---|---|---|---|---|
| Q01 | Building a new home? | New homes are the product. Renovation, interiors, repairs and the rest are not excluded for good: they appear as "coming soon", promised on demand, not by default | DECIDED | Entry asks "Are you building a new home?". Yes opens the form. Other types go to a "coming soon" page that offers help on demand (consistent with CD-03 and CD-12). How a visitor asks for that help: F-01 |
| Q02 | City | Raipur for the POC; the product is for all of India; other cities in phase 2 | DECIDED | Raipur only in the POC; `city` stays a field so phase 2 adds cities as data. Visitors from other cities: F-02 |
| Q03 | Locality | Not clear what was meant | CLARIFY | F-03 |
| Q04 | Plot location on the map | Use the pin | DECIDED | Map pin |
| Q05 | Property type | The product is for independent house builders. Offer villa, apartment and other as well, so that the AI-generated images match what the family wants | DECIDED, one meaning to confirm | Independent house, Villa, Apartment, Other. Meaning of "Apartment" and whether "Other" takes text: F-04 |
| Q06 | Plot size and unit | Sakha to decide a standard that can be shared with contractors and professionals and used for the images | DELEGATED | Plot width and plot depth in feet; area computed in sq ft. "My plot is not a rectangle" lets the family enter the total plot area in sq ft instead. Feet and sq ft are the one standard everywhere (form, leads, drawings brief, image inputs). Number entry departs from CD-02 by necessity; checks guard only against typos |
| Q07 | Built-up area | Sakha to decide | DELEGATED | Total built-up area across all floors, in sq ft, as a number (300 to 12,000, the estimator bounds), or "Not sure yet", in which case Plan2Build's team settles it at the review (J07). A number, because the estimator and the class limits at about 2,500 and 5,000 sq ft need one |
| Q08 | Floors | Sakha to decide; "G+1, G+2 is fine" | DELEGATED, one point to confirm | Ground only, G+1, G+2, G+3 (the estimator's range). Whether to offer only G+1 and G+2: F-05 |
| Q09 | Basement | Yes or no | DECIDED | Yes / No |
| Q10 | Quality tier | Sakha to decide. The customers care about their house and want a good one; the market is ₹40 lakh and above | DELEGATED | Standard, Premium, Luxury, the three tiers the estimator already uses. What each tier includes is defined later with the specification lines, not invented here |
| Q11 | Budget band | Keep the cheaper bands, but the focus is ₹40 lakh and above | DECIDED (direction); band values DELEGATED | Under ₹40 lakh; ₹40 to 60 lakh; ₹60 to 80 lakh; ₹80 lakh to 1 crore; ₹1 to 1.5 crore; above ₹1.5 crore. Each band includes its lower bound. No family is turned away by budget. Land in or out: F-06 |
| Q12 | When do you plan to start? | "Within three to six months" | CLARIFY | That is one option; the form needs the full list: F-07 |
| Q13 | Funding source | Answered about Plan2Build raising investor funding after the POC | CLARIFY | The question is about how the family pays for its house: F-08 |
| Q14 | Current construction stage | Asked for an explanation | CLARIFY | F-09 |
| Q15 | Does the family already have a contractor? | Answered about Plan2Build onboarding contractors by showing them the website | CLARIFY | The question is about the family's own contractor: F-10 |
| Q16 | Already hold a contractor's quote? | Contractors are not onboarded yet, so there are no quotes | CLARIFY | The question is about a quote the family already holds from any contractor: F-10 |
| Q17 | Services needed | Everything needed to build a house except material supply: contractor, structural engineer, civil engineer, architect and design, interior design, project manager | DECIDED | Full home construction; Architectural design; Structural design (by a registered structural engineer, BR-055); Civil work; Electrical, plumbing and HVAC (MEP); Interior design and execution; Project management; Approvals and legal support. Excluded: Material supply (CD-13); Renovation or demolition (not part of a new home; CD-03) |
| Q18 | Style | Asked whether it means the website or the house | CLARIFY | F-11 |
| Q19 | Rank what matters most | Quality of work and finishing on time are the main motto | CLARIFY (one point) | F-12 |
| Q20 | Design inputs | Yes: facing, setbacks and the rest belong in the form | DECIDED (include); options DELEGATED | Facing: North, South, East, West, North-East, North-West, South-East, South-West, Not sure. Setbacks: front, rear, left, right in feet, or "Not sure" (the team checks the local rules). Vastu: Must follow; Follow where possible; Not needed. Rooms: F-13 |
| Q21 | Anything else (optional text) | Not answered | CLARIFY | F-14 |
| Q22 | Upload drawings or photos | Not answered | CLARIFY | F-14 |

### 0.2 Follow-up questions (with Sakha's recommendation)

| ID | Question | Recommendation |
|---|---|---|
| F-01 | On the "coming soon" page, how does a visitor ask for help with renovation, interiors or repairs? | A short request: type of work and email, received by the team as an enquiry; no account needed |
| F-02 | What does a visitor from outside Raipur see? | "We start in Raipur. Leave your email and we will tell you when we reach your city"; no form beyond that |
| F-03 | Locality means the neighbourhood inside Raipur (for example a colony or ward), not the city. Contractors see it on a lead instead of the exact address until they accept (CD-26 design). | Do not ask it; take it from the map pin automatically and let the family correct it |
| F-04 | Does "Apartment" mean a family building a multi-flat building on its own plot (in scope), or buying a flat (out of scope)? Does "Other" need a short text box? | Apartment = a multi-flat building on the family's own plot. "Other" with a short text box, used for the image brief only |
| F-05 | Floors: offer Ground only to G+3, or only G+1 and G+2? | Ground only to G+3, so single-storey and G+3 houses are not turned away |
| F-06 | Is the budget for construction only, or does it include the land? | Construction only, the same basis as the estimator |
| F-07 | Start timeline options | Within 3 months; 3 to 6 months; 6 to 12 months; more than 12 months; already started |
| F-08 | How the family will pay for the house (not Plan2Build's funding). Keep the question? | Keep it, optional: Own savings; Home loan; Both; Prefer not to say. Plan2Build only records it (no loans, S05 section 9) |
| F-09 | Current construction stage: some families come after work has begun (foundation poured, walls up). Plan2Build's flow assumes it starts before construction. Do we take such families in the POC? | Ask "Has construction started?" Yes / No. A "Yes" is handled by the team at review; no automatic stage logic in the POC |
| F-10 | Q15: does the family already have a contractor it wants to use (CD-07, own contractor route)? Q16: does the family already hold a quote from any contractor (CD-04, quote review)? Both are about the family, not about Plan2Build's onboarding. | Keep both as Yes / No |
| F-11 | Style is the look of the house (modern, contemporary, traditional, minimalist), used to guide the AI-generated 3D views; not the website. Which options, and one or several? | Modern, Contemporary, Traditional, Minimalist; one choice; drop "Luxury" (already a quality tier) and "Other" |
| F-12 | Keep all four priorities for the family to rank (the ranking sets the recommendation weights), with quality of work and finishing on time as Plan2Build's own emphasis in its expert weights? | Yes: four items ranked by the family; Plan2Build's emphasis goes into the expert weights |
| F-13 | Which rooms should the form ask about? | Number of bedrooms (1, 2, 3, 4, 5 or more) and number of bathrooms, plus yes/no for pooja room and car parking; Chirag to add or remove |
| F-14 | Keep the optional "anything else" note (500 characters) and the optional upload of drawings or photos? Uploads need the file storage module in slice 1 | Keep the note. Uploads: yes, optional, JPG, PNG, PDF up to 10 MB each, at most 10 files |

### 0.3 Second round of answers (2026-10-04, spoken, transcribed)

| ID | Chirag's answer (paraphrase) | Status | Result |
|---|---|---|---|
| F-01 | Accepts the recommendation | DECIDED | Coming-soon page: "Need help with renovation, interiors or repairs? Tell us." Type of work and email, received by the team as an enquiry |
| F-02 | Accepts | DECIDED | Other cities see the Raipur message and can leave an email |
| F-03 | Go with the recommendation | DECIDED | Locality is not asked; it comes from the map pin and the family can correct it |
| F-04 | Apartment means building a multi-flat building on the family's own plot (in scope); buying a flat is out of scope | DECIDED | Option label to make that plain. The text box for "Other" was not addressed: F-15 |
| F-05 | Not addressed this round (first round: "Sakha decides; G+1, G+2 is fine") | DELEGATED | Ground only, G+1, G+2, G+3, as designed in 0.1 |
| F-06 | Construction budget excludes land | DECIDED | Budget is for construction only |
| F-07 | Answered about delivery: the website goes to the client in 1 to 1.5 months for the POC, improved from the POC's results | CLARIFY | The start-timeline options are still open: F-16. The delivery date is recorded in the baseline as a project constraint |
| F-08 | How a family pays is its own business; Plan2Build sponsors no loans and handles no payments between homeowners and contractors | CLARIFY | Whether the form asks the question at all: F-17 |
| F-09 | Agreed. If construction has started, the team visits, prepares a report and starts the process from where the house is | DECIDED | "Has construction started?" Yes / No. Yes is handled by the team (visit and report) outside the system in the POC; the system records the answer and flags it at review |
| F-10 | Keep "Does your family already have a contractor you want to use?" | DECIDED (Q15) | Yes / No. The quote question (Q16) was not addressed: F-18 |
| F-11 | Let the homeowner choose the look of the house: Modern, Contemporary, Traditional, Minimalist, Luxury, so the images follow the family's taste | DECIDED | Those five options. "Luxury" here means the look; the quality tier "Luxury" means the finish level; screen labels make the difference plain. One choice or several: F-19 |
| F-12 | Keep all four | DECIDED | The family ranks quality of work, finishing on time, staying within budget, experience with similar homes |
| F-13 | Go as recommended | DECIDED (from Sakha's recommendation) | Facing (8 directions, Not sure); setbacks in feet or Not sure; Vastu (must follow, where possible, not needed); bedrooms 1, 2, 3, 4, 5 or more; bathrooms 1, 2, 3, 4, 5 or more; pooja room Yes / No; car parking Yes / No |
| F-14 | Keep the notes option | DECIDED (Q21) | Optional note, 500 characters. Uploads (Q22) not addressed: F-20 |

### 0.4 Still open after round two

| ID | Question the homeowner would see, and what is needed | Recommendation |
|---|---|---|
| F-15 | Property type "Other": should a short text box appear ("Tell us what you are building")? | Yes, used only for the image brief |
| F-16 | "When do you plan to start building?" Which options? | Within 3 months; 3 to 6 months; 6 to 12 months; more than 12 months; already started |
| F-17 | "How will you pay for the construction?" Ask it (optional, recorded only), or drop it? | Drop it from version 1, since Plan2Build has no part in payments; add later if the cash-flow plan needs it |
| F-18 | "Do you already have a quote from any contractor?" Yes / No. Keep? A Yes leads to Plan2Build's quote review (CD-04) | Keep |
| F-19 | Style: one choice or several? | One choice |
| F-20 | Optional upload of drawings, a sanctioned plan or photos (JPG, PNG, PDF, 10 MB each, up to 10 files). Keep? | Keep; a sanctioned plan saves a design step (IHB_FLOW 33.6) |

### 0.5 Final rulings (2026-10-04, written)

Chirag's written rulings R-1 to R-15 settled F-01 to F-20: coming-soon capture (R-1), other cities (R-2), locality from the pin with correction (R-3), property types with Other as a review signal (R-4), budget bands without rejection (R-5), start timeline (R-6), funding removed (R-7), construction started as a review flag (R-8), existing contractor (R-9), existing quote (R-10), style as one choice with help text separating it from quality tier (R-11), all four priorities ranked by the family (R-12), design inputs (R-13), notes (R-14), uploads (R-15). He then instructed that this document be locked as the implementation version; section L is the result.

Sections 1 to 7 below are the version 1 analysis, unchanged, kept for traceability.

## 1. How to read this document

Source ranks (baseline section 4): client decisions, then the flows, then the architecture, then the Source of Truth. Inside the Source of Truth, the D2 written specifications (S05 governs build scope; S06, S07) define behaviour; the D3 mockups (S23c, S24) add detail where they do not contradict D2 (IHB_FLOW 3.2, rules 1, 4, 5). Mockup sample values are evidence of format, not requirements (rule 7).

| Status | Meaning |
|---|---|
| APPROVED | Settled by a recorded client decision from the client's own notes (CD-01 to CD-24). Cited. |
| PROPOSED | Supported by a source and not in conflict, or by a design Chirag delegated (CD-25 to CD-28 are "Proposed answer" until he reviews them, IHB_FLOW 32.1 rule 2). Needs Chirag's approval. |
| CONFLICTING | Sources disagree with each other or with a client decision. Needs a ruling. |
| EXCLUDED | Removed by a client decision. Listed so the exclusion is visible. |

"GAP" marks an option list that no source provides. Gaps are not filled here.

"Required by" names the source that makes a question required. "D2" sources (S05, S06, S07) carry more weight than the "D3" mockup asterisks (S23c).

Format: CD-02 (APPROVED) says the requirement form uses multiple-choice boxes "so the homeowner picks answers instead of typing". Questions that need a number or a map pin are flagged where they depart from that.

## 2. Summary

| # | Question | Required by | Question status | Options status |
|---|---|---|---|---|
| Q01 | Are you building a new home? (entry routing) | CD-03; client flow decision "Building a new home?" | APPROVED | Yes: APPROVED; other types: EXCLUDED to "coming soon" |
| Q02 | City | S05 section 5 (`city` reference data); S07 4.2 ("location") | APPROVED for Raipur only | Raipur: APPROVED (CD-07); other cities: EXCLUDED for the POC |
| Q03 | Locality | S06 section 7 and 6B ("city/locality"); 44.7 lead brief | PROPOSED | GAP |
| Q04 | Plot location on the map | Architecture decision (map pin primary, Chirag 2026-10-03); S02 4.2 "coordinates where available" | PROPOSED | Not a choice question |
| Q05 | Property type | S02 4.2 (D1); S23c asterisk; no D2 source | CONFLICTING | Mixed |
| Q06 | Plot size and unit | S05 section 5 ("plot"); S06 section 7; S07 4.2; S23c asterisk; 44.7 lead brief | CONFLICTING (format) | Unit: one option known, rest GAP |
| Q07 | Built-up area | S05 F2 and section 5 ("area per floor"); S06 section 7; S07 4.2; 44.7 lead brief and class table | CONFLICTING (number or band) | Bands from S24 conflict with the class thresholds |
| Q08 | Floors | S05 section 5 and P2 inputs; S07 4.2; S05 F1 (repeating stages) | PROPOSED | From S14 prototype; above G+3 is a GAP |
| Q09 | Basement | 44.7 class table (CD-26 design) | PROPOSED | Yes / No |
| Q10 | Quality tier (finish level) | S05 section 5, P2 inputs, F2 | PROPOSED | From S14 prototype |
| Q11 | Budget band | S05 section 5 ("budget"); S06 section 7 and S07 4.2 ("budget band"); S23c asterisk; 44.7 lead brief | CONFLICTING (segment threshold) | From S24 |
| Q12 | When you plan to start | S05 section 5 ("target start"); S06; S07 4.2; S23c asterisk; 44.7 "start window" | PROPOSED | GAP (two sample values only) |
| Q13 | Funding source | S05 section 5; S07 4.2 | PROPOSED | GAP |
| Q14 | Current construction stage | S07 4.2; S06 6B ("stage") | CONFLICTING (OQ-028) | GAP |
| Q15 | Does the family already have a contractor? | S06 6B ("contractor status"); client flow decision node (CD-07) | PROPOSED | Yes / No |
| Q16 | Do you already hold a contractor's quote? | Client flow decision node "Already holding contractor quotes?" (CD-04) | PROPOSED (timing open) | Yes / No |
| Q17 | Services needed | S23c only (D3); 44.7 lead brief shows "services needed" | CONFLICTING | Two EXCLUDED, four CONFLICTING, three PROPOSED |
| Q18 | Style preference | S23c (optional); IHB_FLOW 33.6 (style for 3D views) | PROPOSED | Four PROPOSED, two CONFLICTING |
| Q19 | Rank what matters most | CD-28 (delegated design); RECOMMENDATION_ENGINE section 5 | PROPOSED | Four items from CD-28 |
| Q20 | Design inputs: plot shape, facing, setbacks, rooms, Vastu | IHB_FLOW 33.6 (proposed method for CD-25) | PROPOSED, timing open | GAP for every input |
| Q21 | Anything else (optional text) | S23c, S24 (optional) | PROPOSED, in tension with CD-02 | Free text, 500 characters |
| Q22 | Upload drawings, sanctioned plan, photos | S06 6B and S07 4.2 ("drawings"); S05 P2 ("documents"); S23c | PROPOSED | File types from S23c |

Candidates considered and not proposed are in section 4.

## 3. Questions in detail

### Q01. Are you building a new home? (entry routing, J05)

| Option | Source | Status | Notes |
|---|---|---|---|
| Yes, a new home | CD-03 ("The MVP covers new homes only"); S23c "Build New Home"; S24 "Build a New Home"; S18 "Build a new home" | APPROVED | Leads to the requirement form |
| Renovation; Interiors; Repair and Upgrade (S23c); Kitchen; Others (S24); Renovate my home; Do interiors; Add a floor or room; Repairs and maintenance (S18, S01 6.1) | as listed | EXCLUDED | CD-03: these move to phase 2 and appear as "coming soon". They are not options of the requirement. Which of them the coming-soon page names is website content, not this form |
| Not sure (help me decide) | S18, S01 6.1 (D1) | CONFLICTING | Not covered by CD-03. The D1 "decision assistant" is unspecified anywhere. Needs a ruling: drop, or route to "Talk to an expert" (whose channel is itself open, OQ-025) |

Recommendation: the form does not ask the project type; the entry page asks Q01 and only "Yes" opens the form, as in the client flow (IHB_FLOW 33.2).

### Q02. City

| Option | Source | Status | Notes |
|---|---|---|---|
| Raipur | CD-07 ("Raipur, the fixed pilot market"); S05 section 9 ("One city in the pilot") | APPROVED | |
| Bilaspur, Bhubaneswar, Nagpur, Indore, Jaipur, Pune, Bengaluru | S14 calculator list | EXCLUDED for the POC | AMB-012; prototype list only |

Open: what a visitor outside Raipur sees (OQ-002, AMB-012). Not answered by any source.

### Q03. Locality

| Item | Source | Status |
|---|---|---|
| Question | S06 section 7 (`city, locality`), 6B ("city/locality"); S07 4.2 ("location"); 44.7 lead brief shows "the locality (not the exact address)" | PROPOSED |
| Options | S03 section 7: the pilot covers "one city, two localities", which are not named. GAP | GAP |

Recommendation: do not ask it as a list. Derive the locality name from the map pin by reverse geocoding (INTEGRATION_ARCHITECTURE section 5) and show it for confirmation. Whether only two localities are eligible during the pilot is OQ-002 and AMB-012.

### Q04. Plot location on the map

| Item | Source | Status |
|---|---|---|
| Question | Architecture decision by Chirag, 2026-10-03: map pin is the primary plot input (ADR-015, ADR-020); S02 4.2 "address and coordinates where available"; S02 section 20: manual address entry when the map fails | PROPOSED |
| Format | A pin, not a choice: departs from CD-02 by necessity | PROPOSED |

Dependency: map tiles need a provider key (AQ-19). Address text as fallback (S02 section 20).

### Q05. Property type

| Option | Source | Status | Notes |
|---|---|---|---|
| Independent house | S23c dropdown (only value visible); S24 page 3; S02 4.2 "Independent house" | PROPOSED | Matches the segment "Standalone homes on your own or controlled plot" (S20 to S22) |
| Villa | S24 page 3 | CONFLICTING | May or may not be a standalone home on the family's own or controlled plot (AMB-002) |
| Apartment | S24 page 3; S02 4.2 | CONFLICTING | Conflicts with the segment (C-007) and with "new home" construction on a plot |
| Plot construction | S24 page 3 | CONFLICTING | Meaning unclear; overlaps "Independent house" |
| Land | S02 4.2 ("Independent house, apartment, land") | CONFLICTING | Meaning unclear |

No D2 source asks property type. Whether the question is needed depends on OQ-002 (who qualifies). Ruling needed.

### Q06. Plot size and unit

| Item | Source | Status | Notes |
|---|---|---|---|
| Question | S05 section 5 ("plot"); S06 section 7 ("plot"); S07 4.2 ("plot and built-up area"); S23c "Plot or Home Size" (asterisk); 44.7 lead brief ("plot size") | CONFLICTING (format) | S23c merges plot and home size in one field; S07 separates them. A number departs from CD-02 |
| Unit: Sq. ft. | S23c (only unit visible in the dropdown) | PROPOSED | |
| Other units | none | GAP | Not filled |
| Bounds | S02 4.2: "numeric bounds" without values | GAP | |

### Q07. Built-up area

| Option | Source | Status | Notes |
|---|---|---|---|
| A number in sq ft | S05 F2 (estimator input); S06 section 10; S07 4.1; S14 (300 to 12,000); API_ARCHITECTURE section 3 (300 to 12,000) | CONFLICTING | Needed as a number by the estimator and by the proposed class table (thresholds at about 2,500 and 5,000 sq ft, 44.7) |
| Bands: under 1,000 sq ft; 1,000 to 2,000; 2,000 to 3,000; over 3,000 | S24 page 3 (read from the image on 2026-10-04) | CONFLICTING | Bands cannot apply the class thresholds at 2,500 and 5,000; 2,000 and 3,000 sit in two bands each |
| Area per floor | S05 section 5 (`project`: "area per floor") | CONFLICTING | Total built-up or per floor: S05 and S06 differ |

Ruling needed: number or band; total or per floor.

### Q08. Floors

| Option | Source | Status | Notes |
|---|---|---|---|
| Ground only | S14 ("Ground only") | PROPOSED | S14 is a prototype; S05 requires floors (section 5, P2 inputs) without listing values |
| Ground + 1 | S14 | PROPOSED | |
| Ground + 2 | S14 | PROPOSED | |
| Ground + 3 | S14 | PROPOSED | |
| More than ground + 3 | none | GAP | Class A in 44.7 covers "larger than class B", so taller houses may exist; no source gives an option |

Required: S05 section 5 and P2; S07 4.2; floors drive the repeated stages 5, 6 and 9 (S05 F1). S23c and S24 have no floors field; D2 governs (IHB_FLOW 3.2 rule 5).

### Q09. Basement

| Option | Source | Status | Notes |
|---|---|---|---|
| Yes | 44.7 class table ("or with a basement"); DATA `projects.has_basement` | PROPOSED | The class table is a delegated design (CD-26) and CQ-07 may replace it |
| No | same | PROPOSED | |

### Q10. Quality tier (finish level)

| Option | Source | Status | Notes |
|---|---|---|---|
| Standard | S14 finish buttons; S06 section 10 and S07 4.1 call the input "finish level" | PROPOSED | S05 requires "quality tier" (section 5, P2, F2) and rate cards "per quality tier" without naming the tiers |
| Premium | S14 | PROPOSED | |
| Luxury | S14 | PROPOSED | S23c uses "Luxury" as a style (Q18); the same word in two questions needs a ruling |

S23c and S24 have no quality field; D2 governs.

### Q11. Budget band

| Option | Source | Status | Notes |
|---|---|---|---|
| Under ₹25 lakh | S24 page 3 | CONFLICTING | The segment is "₹40 lakh+" (S20 to S22) and "houses above ₹50 lakh" (S03 section 7): C-049, OQ-002 |
| ₹25 to 50 lakh | S24 page 3 | CONFLICTING | Straddles the ₹40 lakh segment line; ₹25 and ₹50 each sit in two bands |
| ₹50 lakh to 1 crore | S24 page 3; S23c (the only value visible) | PROPOSED | |
| Over ₹1 crore | S24 page 3 | PROPOSED | |

Also open: whether the budget includes land (the estimator excludes land and approvals, AMB-071). Required by S05 section 5 ("budget"), S06 section 7 and S07 4.2 ("budget band"), S23c asterisk.

### Q12. When do you plan to start?

| Item | Source | Status | Notes |
|---|---|---|---|
| Question | S05 section 5 ("target start"); S06 section 7 ("target dates"); S07 4.2 ("target start"); S23c "Preferred Start Timeline" (asterisk); 44.7 "start window"; RECOMMENDATION_ENGINE section 4 (capacity in the start window) | PROPOSED | S05 may mean a date; S23c offers a window: format to rule |
| "Within 3 to 6 months" | S23c (only value visible) | PROPOSED | |
| "6 to 12 months" | S18 sample (D1) | PROPOSED | Sample value only |
| Full list | none (S24 shows "Select timeline" with no values) | GAP | Not filled |

### Q13. Funding source

| Item | Source | Status | Notes |
|---|---|---|---|
| Question | S05 section 5 (`project`: "funding source"); S07 4.2 | PROPOSED | Used for the cash-flow plan |
| Options | none; D1 says "financing preference" without values | GAP | Lending is excluded (S05 section 9), so options must not imply a loan offer |

### Q14. Current construction stage

| Item | Source | Status | Notes |
|---|---|---|---|
| Question | S07 4.2 ("current construction stage"); S06 6B ("stage") | CONFLICTING | Joining mid-construction is open (OQ-028, EC-009); S06 "stage" may mean readiness, not construction stage |
| Options | none | GAP | |

Recommendation: leave out of version 1 until OQ-028 is decided.

### Q15. Does the family already have a contractor?

| Option | Source | Status | Notes |
|---|---|---|---|
| Yes | Client flow decision node "Family already has a contractor?" (IHB_FLOW 33.2); CD-07 keeps both routes; S06 6B "contractor status" | PROPOSED | Asking it in the requirement is the proposal; the routes themselves are APPROVED (CD-07) |
| No | same | PROPOSED | |

### Q16. Do you already hold a contractor's quote?

| Option | Source | Status | Notes |
|---|---|---|---|
| Yes | Client flow decision node "Already holding contractor quotes?" (CD-04) | PROPOSED | The client flow asks it after the workspace (step 8); asking it in the requirement is a timing change for Chirag to decide |
| No | same | PROPOSED | What follows a "Yes" is CQ-02 |

### Q17. Services needed

| Option | Source | Status | Notes |
|---|---|---|---|
| Full home construction | S23c | PROPOSED | |
| Structural and civil work | S23c | PROPOSED | Structural design itself stays with the registered engineer (BR-055) |
| MEP (electrical, plumbing, HVAC) | S23c | PROPOSED | |
| Architectural design and planning | S23c | CONFLICTING | CD-25: Plan2Build's concept design is in the package by default and an architect is on request; a separate "service" may mislead |
| Interior design and execution | S23c | CONFLICTING | Interiors as a project type moved to phase 2 (CD-03); interiors inside a new home are not decided |
| Approvals and legal support | S23c | CONFLICTING | Permit drawings and approvals scope is CQ-22 |
| Project management | S23c | CONFLICTING | S05 section 9 excludes project management execution tooling ("We do not take the construction contract") |
| Material supply | S23c | EXCLUDED | CD-13 |
| Renovation / demolition | S23c | EXCLUDED | CD-03 |

The question exists only in S23c (D3), unmarked as required or optional (AMB-063). The 44.7 lead brief (CD-26 design) shows "services needed" to contractors. Ruling needed on the question and on each CONFLICTING option.

### Q18. Style preference (optional)

| Option | Source | Status | Notes |
|---|---|---|---|
| Modern | S23c | PROPOSED | Style words guide the illustrative 3D views (IHB_FLOW 33.6; AI_AND_RECOMMENDATION A3) |
| Contemporary | S23c | PROPOSED | |
| Traditional | S23c | PROPOSED | |
| Minimalist | S23c | PROPOSED | |
| Luxury | S23c | CONFLICTING | Same word as the quality tier "Luxury" (Q10) |
| Other | S23c | CONFLICTING | Would need typed text: against CD-02, and the image prompt has no slot for free text (AI_AND_RECOMMENDATION A6) |

Single or multiple choice: AMB-062 (the S23c summary shows "Modern Contemporary").

### Q19. Rank what matters most to you

| Item | Source | Status |
|---|---|---|
| Quality of work | CD-28; IHB_FLOW 33.1 J06; RECOMMENDATION_ENGINE section 4 | PROPOSED |
| Finishing on time | same | PROPOSED |
| Staying within budget | same | PROPOSED |
| Experience with similar homes | same | PROPOSED |

All four are ranked (rank-order centroid needs a full ranking, RECOMMENDATION_ENGINE section 5). CD-28 is a delegated design awaiting Chirag's review, and the question's wording is for Plan2Build's team to set (RECOMMENDATION_ENGINE section 12).

### Q20. Design inputs: plot shape, facing, setbacks, rooms, Vastu preference

| Item | Source | Status | Notes |
|---|---|---|---|
| Questions | IHB_FLOW 33.6 (Sakha's proposed method for CD-25: "The requirement form (plot size and shape, facing, setbacks, floors, rooms, Vastu preference)"); DATA `project_requirements` columns; S23c placeholder text mentions "number of bedrooms" | PROPOSED | The concept design starts after the package is paid (J10), so these may belong to a design intake rather than the first requirement |
| Options for each | none | GAP | Not filled. Bedrooms: S20 to S22 price by BHK, but no option list exists |

Recommendation: leave out of version 1 and take them at the design intake once CD-25's method is reviewed.

### Q21. Anything else (optional)

| Item | Source | Status | Notes |
|---|---|---|---|
| Free text, up to 500 characters | S23c ("Additional Information", counter 0/500); S24 ("Any other details? (optional)") | PROPOSED | In tension with CD-02 ("picks answers instead of typing"), which does not forbid an optional note. Free text is personal data (P2) |

### Q22. Upload drawings, a sanctioned plan, photos (optional)

| Item | Source | Status | Notes |
|---|---|---|---|
| Upload | S06 6B and S07 4.2 ("drawings"); S05 P2 ("documents"); IHB_FLOW 33.6 (sanctioned plan used as is); S23c | PROPOSED | |
| File types and size | S23c: JPG, PNG, PDF, 10 MB each | PROPOSED | Maximum number of files: GAP |

Dependency: the file storage module is designed, not built (FOUNDATION_PLAN section 2, J). Including uploads in slice 1 adds that module to the slice.

## 4. Candidates not proposed for version 1

| Candidate | Source | Why not proposed |
|---|---|---|
| Target completion date | S01 6.2 (D1, optional); S06 section 7 "target dates" | Not among S07's core facts; optional in D1. Chirag may add it |
| First-time builder (yes, no, unknown) | S02 4.2, S18 (D1) | D1 only; no D2 source uses it |
| Stage of readiness | S02 4.2, S18 (D1; only sample "Just exploring") | D1 only; options GAP |
| Household members and stakeholders | S05 P2 | Belongs to the workspace (J08), after acceptance |
| Name | S01 4.1 (D1) | Account data, not a requirement; D2 identifies by contact |
| Lead source ("how did you hear about us") | S06 6B, S07 section 7 | Measured by the system (F-001), never asked as a question in any source |

## 5. Conflicts that need a ruling

| ID | Conflict | Sources | Questions |
|---|---|---|---|
| R-01 | Who qualifies as a homeowner: segment ₹40 lakh+ standalone homes versus form options below ₹25 lakh and apartments | S20 to S22, S03 versus S24, S02; C-007, C-049, OQ-002 | Q05, Q11 |
| R-02 | Built-up area as a number or as bands; total or per floor | S05, S06, S14 versus S24; 44.7 class thresholds | Q06, Q07 |
| R-03 | Form shape: three-step wizard (S24) or five-step long form (S23c) | C-042, AMB-058 | All |
| R-04 | "Luxury" as quality tier and as style | S14 versus S23c | Q10, Q18 |
| R-05 | Services options against CD-03, CD-13, CD-25, CQ-22, S05 section 9 | S23c | Q17 |
| R-06 | Typed answers (plot size, built-up area, optional note) against CD-02 | CD-02 versus S05, S23c | Q06, Q07, Q21 |
| R-07 | Start as a date or a window | S05 versus S23c | Q12 |

## 6. Gaps that only Chirag or the client can fill

Option lists missing from every source: locality (Q03), plot-size units other than sq ft and bounds (Q06), floors above G+3 (Q08), start windows (Q12), funding source (Q13), current construction stage (Q14), design inputs (Q20), maximum number of uploads (Q22).

## 7. What Sakha recommends Chirag approves or rules on

1. Q01, Q02 as written (they restate CD-03 and CD-07).
2. Rulings R-01, R-02 and R-07, because floors, built-up area, budget and start window feed the estimator, the class table and the lead brief.
3. The option lists for Q12 and Q13 (gaps), or a decision to leave Q13 out of version 1.
4. Q08, Q09, Q10, Q19 as proposed.
5. Whether version 1 includes Q15, Q16, Q17, Q18, Q21, Q22, and the rulings on their CONFLICTING options.
6. Leaving Q14 and Q20 out of version 1.

Until then the requirement form is not built and no question set is stored.
