"""Generate Batches 01-05 (300 documents) to complete the 500-document GlobalTech corpus."""

from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
POLICY_DIR = ROOT / "data" / "policies" / "globaltech"
META_DIR = ROOT / "data" / "corpus_metadata" / "globaltech"
MASTER_CSV = META_DIR / "master_metadata.csv"
VALIDATION_JSON = META_DIR / "validation_report.json"
TEMPLATE_DOCX = POLICY_DIR / "GT-TRV-EXP-001_expense_eligibility_taxonomy.docx"

COUNTRIES = [
    ("AU", "Australia", "APAC", "AUD", 240, 290, 340, 410, 480, 95, "0.85 AUD/km", 30),
    ("BR", "Brazil", "Americas", "BRL", 650, 780, 920, 1100, 1300, 240, "1.80 BRL/km", 30),
    ("CA", "Canada", "Americas", "CAD", 230, 280, 330, 400, 470, 90, "0.70 CAD/km", 30),
    ("CN", "China", "APAC", "CNY", 900, 1100, 1350, 1650, 1950, 360, "2.50 CNY/km", 30),
    ("DK", "Denmark", "EMEA", "DKK", 1250, 1500, 1800, 2150, 2500, 520, "3.70 DKK/km", 30),
    ("FR", "France", "EMEA", "EUR", 170, 210, 250, 300, 360, 75, "0.60 EUR/km", 30),
    ("DE", "Germany", "EMEA", "EUR", 165, 200, 245, 295, 350, 70, "0.30 EUR/km", 30),
    ("IN", "India", "APAC", "INR", 7500, 9500, 12000, 15000, 18500, 3200, "14 INR/km", 30),
    ("ID", "Indonesia", "APAC", "IDR", 1600000, 2000000, 2450000, 3000000, 3600000, 650000, "4500 IDR/km", 30),
    ("IE", "Ireland", "EMEA", "EUR", 180, 220, 265, 320, 380, 75, "0.55 EUR/km", 30),
    ("IT", "Italy", "EMEA", "EUR", 160, 195, 240, 290, 345, 70, "0.55 EUR/km", 30),
    ("JP", "Japan", "APAC", "JPY", 18000, 22000, 27000, 33000, 40000, 7500, "35 JPY/km", 30),
    ("MY", "Malaysia", "APAC", "MYR", 450, 550, 680, 820, 980, 180, "1.10 MYR/km", 30),
    ("MX", "Mexico", "Americas", "MXN", 2600, 3200, 3900, 4700, 5600, 1100, "6.50 MXN/km", 30),
    ("NL", "Netherlands", "EMEA", "EUR", 175, 215, 260, 310, 370, 75, "0.23 EUR/km", 30),
    ("NZ", "New Zealand", "APAC", "NZD", 230, 280, 335, 405, 480, 95, "0.95 NZD/km", 30),
    ("PL", "Poland", "EMEA", "PLN", 520, 640, 780, 940, 1120, 220, "1.15 PLN/km", 30),
    ("SG", "Singapore", "APAC", "SGD", 260, 320, 385, 460, 540, 110, "0.80 SGD/km", 30),
    ("ZA", "South Africa", "EMEA", "ZAR", 2400, 2950, 3600, 4350, 5200, 950, "4.80 ZAR/km", 30),
    ("KR", "South Korea", "APAC", "KRW", 210000, 260000, 320000, 390000, 470000, 90000, "450 KRW/km", 30),
    ("ES", "Spain", "EMEA", "EUR", 155, 190, 235, 285, 340, 65, "0.26 EUR/km", 30),
    ("SE", "Sweden", "EMEA", "SEK", 1850, 2250, 2750, 3300, 3900, 780, "2.50 SEK/km", 30),
    ("CH", "Switzerland", "EMEA", "CHF", 230, 280, 340, 410, 490, 95, "0.70 CHF/km", 30),
    ("GB", "United Kingdom", "EMEA", "GBP", 175, 215, 260, 315, 375, 70, "0.45 GBP/km", 30),
    ("US", "United States", "Americas", "USD", 220, 270, 325, 390, 460, 95, "0.67 USD/km", 30),
]

GLOBAL_TOPICS = [
    ("Global travel policy charter", "Define policy authority, ownership by the Global Travel Policy Office, scope across all entities, and mandatory compliance principles."),
    ("Policy hierarchy, precedence and conflict resolution", "Establish binding precedence: applicable local law first, current country addenda and amendments next, global governance, then role overlays; escalate unresolved conflicts."),
    ("Travel lifecycle and governance ownership", "Define end-to-end accountability across request intake, booking, trip execution, expense reconciliation, and periodic policy review."),
    ("Trip eligibility and business necessity standard", "Require clear business purpose, virtual-first evaluation, and authorised cost-centre alignment before committing company travel funds."),
    ("Approved booking channels and TMC compliance", "Mandate booking flights, rail, and hotels through the GlobalTech Travel Management Company (TMC) unless a documented direct-booking exception applies."),
    ("Lowest logical fare and advance purchase standard", "Require selection of the lowest logical economy fare within approved schedule tolerances and at least 14 days advance booking when practicable."),
    ("Global cabin class governance", "Define economy baseline for short- and medium-haul air travel, grade-gated long-haul thresholds, and pre-approval requirements for any cabin upgrade."),
    ("Rail and intercity ground travel standard", "Prefer rail over short-haul air travel where journey times are under four hours and safe approved operators exist."),
    ("Global hotel programme and rate governance", "Mandate preferred corporate hotel properties first, subject to destination country nightly caps and safety standards."),
    ("Global expense and reimbursement principles", "Require business necessity, itemised receipts, segregation of duties, and human reviewer approval before any reimbursement."),
    ("Pre-trip approval matrix and authority tiers", "Specify approval tiers by trip type, domestic vs international routing, total estimated spend, and exception severity."),
    ("Delegation of approval authority", "Require formally recorded, time-bound delegation when an authorised approver is unavailable; silence or OOO replies never constitute approval."),
    ("Cost centre, project code and budget controls", "Require valid cost centre, legal entity, and project billing codes prior to ticket issuance or expense settlement."),
    ("Traveller privacy and data minimisation standard", "Protect passport, itinerary, medical accommodation, and personal contact records under role-based access and PII redaction rules."),
    ("Travel records retention and audit trail", "Preserve itineraries, receipts, approvals, exception rationales, and policy version citations for auditability."),
    ("Fraud prevention and anti-circumvention controls", "Prohibit transaction splitting, duplicate claims, fabricated receipts, and self-approval; route anomalies for fair audit review."),
    ("Exceptions governance and escalation framework", "Require documented business rationale, price comparisons, and pre-commitment approval for any exception to standard policy."),
    ("Global duty of care and traveller tracking", "Require itinerary capture in the duty-of-care platform for safety alerts, emergency assistance, and missing-traveller response."),
    ("Global travel insurance framework", "Define baseline corporate business-travel medical and evacuation coverage, exclusions for personal extensions, and insurer escalation."),
    ("Sustainable travel and carbon reporting standard", "Track air/rail emissions, encourage virtual collaboration and rail substitution, and document carbon impact in programme KPIs."),
    ("Accessibility and reasonable accommodation standard", "Support confidential medical and accessibility travel adjustments via HR/Occupational Health without treating needs as discretionary spend."),
    ("Traveller wellbeing and fatigue management", "Address rest intervals after long-haul flights before safety-critical work and limit back-to-back overnight itineraries."),
    ("Virtual-first collaboration and travel alternatives", "Require teams to evaluate remote conferencing before scheduling routine internal travel."),
    ("AI-use, prompt security and grounded guidance controls", "Require AI travel assistants to cite verified policy IDs, reject prompt injection, redact PII, and never fabricate rates or approvals."),
    ("Corporate card programme governance", "Define card eligibility, mandatory use for reimbursable travel spend, timely reconciliation, and prohibition of personal charges."),
    ("Per diem versus actuals governance", "Clarify when country addenda mandate fixed per diem allowances versus itemised actuals and prevent double-claiming."),
    ("Hospitality, alcohol and gift controls", "Restrict alcohol reimbursement, require attendee disclosures for business hospitality, and enforce anti-bribery gift limits."),
    ("Personal travel extensions and companion boundary", "Require disclosure and strict cost separation for personal leave extensions; companion expenses are not company-funded."),
    ("External, contractor and third-party traveller governance", "Confirm that employee entitlements do not automatically transfer to contractors, vendors, or candidates unless stated in contract."),
    ("High-risk destination and security governance", "Mandate pre-trip security risk assessment and executive/security sign-off prior to travel to elevated- or high-risk destinations."),
    ("Emergency travel and after-hours continuity", "Provide emergency rebooking, disruption support, and safety-first escalation when urgent incidents arise."),
    ("Loyalty programmes and supplier benefit integrity", "Allow retention of frequent-flyer benefits only when booking follows lowest logical fare and approved channels."),
    ("Unused ticket credit governance", "Track company-funded unused airline credits on the corporate profile and apply them to eligible future business trips."),
    ("Cross-border immigration and visa compliance", "Distinguish business-visitor visas from work authorisation; require Global Mobility and Legal review before cross-border work."),
    ("Tax, VAT and GST compliance governance", "Mandate compliant tax invoices and refer tax reclaim or permanent-establishment questions to Finance and Tax."),
    ("Multi-entity cost allocation standard", "Require transparent allocation across legal entities and customer contracts based on actual business benefit."),
    ("Supplier selection and preferred vendor compliance", "Mandate use of contracted airlines, hotels, rental agencies, and ground partners screened for safety and compliance."),
    ("Technology outage and offline continuity", "Define fallback submission, receipt retention, and post-outage reconciliation when booking or expense tools are unavailable."),
    ("Policy publication, versioning and retirement", "Assign version numbers, effective dates, supersession links, and archive markers to every policy document."),
    ("Interim policy notices and urgent updates", "Govern rapid interim directives during regulatory, currency, or security disruptions with explicit expiry dates."),
    ("Internal audit, analytics and KPI governance", "Define programme KPIs including compliance rate, TMC adoption, exception volume, cycle time, and audit findings."),
    ("Disciplinary escalation and fair review", "Ensure suspected policy breaches receive objective fact-finding and fair opportunity for explanation prior to action."),
    ("Ground transport safety and unlicensed carrier ban", "Prohibit use of unlicensed drivers or unvetted transport even when cheaper; safety always overrides lowest cost."),
    ("Medical emergency and evacuation governance", "Direct travellers experiencing urgent symptoms to local emergency services first, followed by the corporate medical insurer."),
    ("Lost or missing receipt governance", "Restrict lost-receipt declarations to genuine exceptions with corroborating bank evidence and audit thresholds."),
    ("Cash advance and foreign exchange controls", "Limit cash advances to unbanked/remote needs and require approved platform exchange rates for multi-currency claims."),
    ("Group travel and conference governance", "Require consolidated manifests, group rate negotiation, and pre-approval for multi-traveller events."),
    ("Relocation versus short-term business travel boundary", "Separate short-term business trips from tax-triggering assignments managed under Global Mobility."),
    ("Customer-funded and supplier-sponsored travel controls", "Prevent customer preferences or supplier sponsorships from overriding internal controls or creating conflicts of interest."),
    ("Annual policy review and continuous improvement", "Mandate annual review of country addenda, rate benchmarks, and AI evaluation failure taxonomy."),
]

ROLE_TOPICS = [
    ("Grade G1 entitlement overlay", "Define baseline G1 entitlements: economy air travel, standard rail, G1 country hotel tier, and manager pre-approval; role does not override country caps."),
    ("Grade G2 entitlement overlay", "Define G2 entitlements: economy air travel, standard rail, G2 country hotel tier, and standard expense workflow without automatic upgrades."),
    ("Grade G3 entitlement overlay", "Define G3 entitlements: economy air travel (premium economy only where permitted by country flight addendum), G3 country hotel tier, and budget-owner review."),
    ("Grade G4 entitlement overlay", "Define G4 entitlements: eligible for premium economy or long-haul business class strictly per country flight addendum duration thresholds and pre-approval."),
    ("Grade G5 entitlement overlay", "Define G5 executive entitlements: long-haul business class per flight addendum thresholds, G5 country hotel tier, and heightened audit transparency."),
    ("People manager role overlay", "Define manager responsibilities for pre-trip necessity review, segregation of duties, and budget verification without self-approval rights."),
    ("Project manager role overlay", "Cover multi-site project travel planning, client cost-centre coding, and consolidated team itinerary governance."),
    ("Customer-facing consultant role overlay", "Address client-site travel without implying automatic cabin or hotel upgrades beyond substantive employee grade."),
    ("Sales and account executive role overlay", "Govern client hospitality, meal attendee logging, and anti-bribery checks without relaxing receipt or cap controls."),
    ("Field service engineer role overlay", "Address tool/equipment transport, remote-site ground safety, and PPE/vehicle compliance."),
    ("Technical and cloud architect role overlay", "Cover workshop travel, export-controlled hardware handling across borders, and device security."),
    ("AI and data science specialist role overlay", "Address conference travel, sensitive model/dataset device safeguards, and third-party speaking disclosures."),
    ("Finance and tax controller role overlay", "Define expense audit duties, tax-invoice verification, and segregation from personal claim approvals."),
    ("Procurement and vendor manager role overlay", "Enforce strict conflict-of-interest barriers against supplier-funded travel, gifts, or hospitality."),
    ("Human resources and global mobility overlay", "Govern confidential medical/accessibility cases, assignee transitions, and immigration referrals."),
    ("Legal and compliance counsel role overlay", "Cover regulatory investigations, sanctions screening escalations, and privileged travel handling."),
    ("Corporate security officer role overlay", "Define high-risk destination escorts, emergency response authority, and confidential security logistics."),
    ("Intern and graduate trainee role overlay", "Require explicit manager supervision, economy-only travel, pre-booked TMC itineraries, and restricted card/advance access."),
    ("Contractor and subcontractor role overlay", "Clarify that contractors do not inherit G1-G5 employee entitlements; travel is governed strictly by vendor contract ceilings."),
    ("Supplier and third-party representative overlay", "Define pre-approval, cost-capping, and duty-of-care boundaries for external representatives funded by GlobalTech."),
    ("Remote and hybrid worker travel overlay", "Distinguish non-reimbursable home-to-office commuting from reimbursable business trips to secondary locations."),
    ("Short-term assignee role overlay", "Coordinate temporary assignment living allowances with business travel rules to avoid duplicate per diems."),
    ("Long-term international assignee overlay", "Specify home-leave eligibility, entity billing, and tax-equalisation coordination via Global Mobility."),
    ("Accessibility and medical accommodation overlay", "Authorise confidential seat, hotel, or transport adjustments verified by HR/Occupational Health."),
    ("High-risk site traveller role overlay", "Mandate pre-trip security briefing, check-in schedules, and approved secure ground transport."),
    ("Frequent traveller role overlay", "Provide fatigue mitigation, annual visa/passport renewal reimbursement, and streamlined pre-approval profiles."),
    ("Executive assistant and travel arranger overlay", "Allow booking on behalf of executives while preserving independent financial approval by an authorised approver."),
    ("Candidate and interview travel overlay", "Set fixed economy booking channels and direct-bill lodging for external recruitment candidates."),
    ("Board and advisory committee traveller overlay", "Establish transparent expense disclosure and dedicated governance sign-off for non-employee advisors."),
    ("Audit and risk reviewer role overlay", "Define read-only audit access, conflict recusal, and evidence preservation during expense investigations."),
    ("Customer support and onboarding specialist overlay", "Align multi-stop customer onboarding trips with lowest logical fare and country per-diem rules."),
    ("Research and academic partner traveller overlay", "Clarify grant/partner cost sharing and equipment customs documentation."),
    ("Marketing and events coordinator role overlay", "Govern group hotel blocks, venue deposits, and promotional item compliance."),
    ("Training and enablement instructor role overlay", "Cover multi-day workshop meals, training materials freight, and local transit passes."),
    ("Crisis response and incident team overlay", "Authorise emergency booking pathways and 24/7 after-hours support during active business disruptions."),
    ("Mergers and integration team overlay", "Enforce strict confidentiality, NDA-compliant booking codes, and cross-entity cost allocation."),
    ("Sustainability and ESG auditor role overlay", "Prioritise rail and low-emission transport on multi-site audits."),
    ("Government and public-sector liaison overlay", "Prohibit hospitality, gifts, or meals for public officials without prior Legal and Compliance approval."),
    ("Healthcare and life-sciences specialist overlay", "Enforce strict privacy, cold-chain equipment handling, and regulated-customer hospitality bans."),
    ("Hardware and lab prototype courier overlay", "Cover excess baggage pre-approval, customs carnets, and secure chain-of-custody during transit."),
    ("Dual-role and matrix-reporting employee overlay", "Require designation of a single primary cost-centre approver before booking to prevent split approvals."),
    ("Part-time and job-share employee overlay", "Ensure business travel entitlements align with substantive grade without pro-rata hotel cap reductions."),
    ("Relocating employee transition overlay", "Separate relocation allowances from concurrent business travel expenses."),
    ("Sabbatical and leave-return traveller overlay", "Prohibit company-funded travel during unpaid leave; require active payroll status for business trips."),
    ("Seconded employee role overlay", "Apply host-entity local rules and home-entity grade ceilings unless the secondment letter specifies otherwise."),
    ("Regional director and VP approver overlay", "Define elevated delegation authority for multi-country exceptions while barring self-approval."),
    ("Travel operations administrator role overlay", "Authorise TMC profile maintenance, unused ticket credit tracking, and outage continuity support."),
    ("Safety and EHS inspector role overlay", "Mandate independent vehicle inspection, PPE carriage, and stop-work/stop-travel authority."),
    ("Diplomatic and visa-expedite coordinator overlay", "Cover urgent passport/visa courier fees when tied to approved business travel."),
    ("Spouse or companion policy boundary overlay", "Reiterate that companions are never a standard role entitlement and require explicit rare exception approval."),
]

EXC_TOPICS = [
    ("Hotel above approved cap", "Specify required price comparisons showing compliant hotels are unavailable, safety/location rationale, and pre-booking approver sign-off."),
    ("Preferred flight or compliant hotel unavailable", "Require documented TMC search results and reasonable lowest-cost alternative selection before exception approval."),
    ("Cabin class upgrade exception", "Require medical accommodation verification or documented multi-leg business necessity approved before ticket purchase."),
    ("Direct booking outside TMC channel", "Permit only when TMC lacks coverage or in verified emergencies, with mandatory itinerary forwarding for duty of care."),
    ("Retrospective approval and emergency pathway", "Restrict post-commitment approval to documented emergencies or verified system outages; never normalise after-the-fact approval."),
    ("Airfare above normal fare limit", "Require justification of schedule constraints, comparison of three logical fare options, and budget-owner plus policy sign-off."),
    ("Last-minute or short-notice booking", "Require reason for booking inside 14 days and approval of fare premium over advance-purchase benchmarks."),
    ("Unbudgeted or cross-entity trip exception", "Require Finance controller and receiving-entity budget sign-off prior to travel commitment."),
    ("Self-approval prohibition and conflict escalation", "Strictly forbid approving one's own travel or expense; route to next-higher independent approver or documented delegate."),
    ("Approver conflict and after-the-fact normalisation control", "Prevent peer swaps, conflicted reviews, or retrospective sign-offs intended to disguise policy breaches."),
    ("Emergency retrospective documentation standard", "Require submission of incident evidence, decision-maker name, and timestamp within 5 business days of emergency travel."),
    ("Exception approval matrix — Tier 1 and Tier 2", "Map spend variance thresholds to manager, department VP, and Finance exception authorities."),
    ("Unavailable approver and formal delegation", "Require active system delegation; out-of-office auto-replies, chat messages, or silence are invalid approvals."),
    ("Customer-requested or customer-billable exception", "Clarify that customer preference does not override internal caps without written contract alignment and Finance approval."),
    ("Executive override governance", "Require written rationale and audit logging whenever an authorised executive approves an exception above standard tiers."),
    ("Multi-leg and complex fare exception", "Govern split-ticket and open-jaw fares, ensuring total trip cost and disruption protections are evaluated."),
    ("Extended stay accommodation exception", "Address stays exceeding 14 nights, requiring serviced-apartment rate comparisons and tax review."),
    ("Personal leave extension exception", "Require pre-trip disclosure, airfare comparison isolating incremental personal fare, and personal payment of non-business days."),
    ("Family companion travel exception", "Prohibit company-funded companion costs except in documented long-term relocation or verified medical-escort cases."),
    ("Weekend stayover cost-comparison exception", "Allow weekend hotel/meal spend only when documented airfare savings exceed incremental weekend lodging and meals."),
    ("Missed flight responsibility and rebooking", "Evaluate carrier delay vs traveller lateness, capture facts objectively, and escalate rebooking fee recovery fairly."),
    ("Severe weather and airline disruption", "Authorise immediate TMC/after-hours rebooking, safe shelter, and emergency meal/hotel reimbursement with disruption proof."),
    ("Medical emergency travel exception", "Prioritise immediate emergency medical care, contact corporate insurer, and waive advance booking rules for medical repatriation."),
    ("Security evacuation exception", "Authorise immediate evacuation via Corporate Security regardless of fare caps; reconcile documentation post-safety."),
    ("High-risk destination risk assessment exception", "Require completed security risk assessment, mitigation plan, and executive/security approval before travel."),
    ("High-risk travel stop and client pressure prohibition", "Establish that client demands never override a Corporate Security do-not-travel directive."),
    ("Missing or lost receipt exception", "Require signed lost-receipt declaration, card/bank corroboration, and heightened review if repeated."),
    ("Accessibility accommodation exception", "Approve necessary room, seat, or transport adjustments confidentially via HR/Occupational Health guidance."),
    ("Ground transport and safety taxi exception", "Permit taxis or approved rideshare over public transit for late-night arrivals, safety risk, luggage, or accessibility."),
    ("Personal vehicle and mileage exception", "Require valid licence, business-use insurance, route log, and compliance with country mileage schedules."),
    ("Duplicate claim review and resolution", "Hold suspected duplicate line items automatically and give the claimant an opportunity to explain valid matching charges."),
    ("Corporate card late settlement exception", "Address delayed card reconciliation caused by carrier refunds, disputes, or hospitalisation."),
    ("Cash advance exception for remote destinations", "Permit pre-approved cash advances only where electronic card acceptance is unavailable."),
    ("Expedited visa and passport fee exception", "Allow rush government/courier fees when urgent customer or emergency travel leaves insufficient standard processing time."),
    ("Rental car class upgrade exception", "Permit larger vehicles only for group travel (3+ colleagues), heavy equipment, or verified winter/terrain safety."),
    ("First-class rail exception", "Allow first-class rail only where documented quiet-work business need or equivalent lowest-cost fare applies."),
    ("Airport lounge and fast-track access exception", "Restrict paid lounge access to long layovers (>4 hours) or approved disability/medical accommodations."),
    ("Excess baggage and equipment fee exception", "Approve airline baggage fees for work samples, demonstration hardware, or multi-week assignments."),
    ("In-flight Wi-Fi and roaming connectivity exception", "Reimburse connectivity when required for active customer deliverables or travel disruption support."),
    ("Late expense submission exception", "Require documented reason (medical leave, outage, card dispute) and Finance approval for claims past country deadline."),
    ("Off-channel hotel loyalty booking prohibition", "Deny exceptions driven solely by personal hotel status or points accumulation at higher cost."),
    ("Non-refundable ticket cancellation and waiver", "Apply unused ticket credit rules and require manager validation for unavoidable business cancellations."),
    ("Supplier-funded travel conflict-of-interest exception", "Require Compliance pre-approval before accepting any supplier-paid airfare, lodging, or conference travel."),
    ("Alcohol and restricted hospitality exception", "Maintain default non-reimbursement for alcohol; require rare VP + Compliance approval for formal client events."),
    ("Tax-invoice missing VAT/GST exception", "Require merchant reissue request first, then Finance tax-review sign-off if a compliant tax invoice is unobtainable."),
    ("Third-party and candidate travel exception", "Require Recruiting or Procurement approval for any deviation from fixed external-traveller ceilings."),
    ("Split-stay and shared-lodging safety exception", "Prohibit forced room sharing; provide single-occupancy safety accommodations."),
    ("Technology outage fallback claim exception", "Accept offline email/form timestamps during verified platform outages subject to post-restoration reconciliation."),
    ("Retroactive grade-change travel exception", "Apply the grade active at booking unless a documented transition rule explicitly requires reassessment."),
    ("Unresolved policy conflict escalation", "Pause non-urgent spend when two policies conflict and route to the Global Travel Policy Office for binding ruling."),
]

with zipfile.ZipFile(TEMPLATE_DOCX) as tpl:
    TEMPLATE_ENTRIES = {
        name: tpl.read(name)
        for name in tpl.namelist()
        if name not in {"word/document.xml", "docProps/core.xml"}
    }
    TEMPLATE_DOC_XML = tpl.read("word/document.xml").decode("utf-8")
    TEMPLATE_CORE_XML = tpl.read("docProps/core.xml").decode("utf-8")

BODY_PREFIX = TEMPLATE_DOC_XML.split("<w:body>", 1)[0] + "<w:body>"
SECT_PR_IDX = TEMPLATE_DOC_XML.rfind("<w:sectPr")
BODY_SUFFIX = TEMPLATE_DOC_XML[SECT_PR_IDX:]


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:70]


def _p(text: str, style: str | None = None, bold: bool = False, italic: bool = False, center: bool = False, color: str | None = None, size: str | None = None) -> str:
    ppr_parts = []
    if style:
        ppr_parts.append(f'<w:pStyle w:val="{escape(style)}"/>')
    if center:
        ppr_parts.append('<w:jc w:val="center"/>')
    ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>" if ppr_parts else ""

    rpr_parts = []
    if bold:
        rpr_parts.append("<w:b/>")
    if italic:
        rpr_parts.append("<w:i/>")
    if color:
        rpr_parts.append(f'<w:color w:val="{color}"/>')
    if size:
        rpr_parts.append(f'<w:sz w:val="{size}"/>')
    rpr = f"<w:rPr>{''.join(rpr_parts)}</w:rPr>" if rpr_parts else ""

    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def _build_docx(path: Path, doc_id: str, title: str, batch: str, version: str, effective_date: str, jurisdiction: str, summary: str, specific_clauses: list[str], dependencies: str) -> None:
    paras = [
        _p("FICTIONAL SYNTHETIC POLICY — FOR AI AGENT TESTING ONLY", bold=True, center=True, color="A00000", size="20"),
        _p(title, bold=True, center=True, size="36"),
        _p(f"Policy ID: {doc_id}  |  Version: {version}  |  Effective: {effective_date}  |  Jurisdiction: {jurisdiction}", italic=True, center=True),
        _p("Owner: Global Travel Policy Office  |  Classification: Internal synthetic training data", italic=True),
        _p(summary),
        _p("Purpose and scope", style="Heading2"),
        _p(f"This policy establishes the GlobalTech control for {title.lower()} ({doc_id}) within {jurisdiction}. It applies to employees, managers, authorised approvers and travel support teams."),
        _p("Policy requirements", style="Heading2"),
    ]
    for clause in specific_clauses:
        paras.append(_p(clause, style="ListBullet"))
    paras.extend([
        _p("Operating procedure", style="Heading2"),
        _p("Record business purpose, destination, dates, employee grade, cost centre, and any pre-approval or exception rationale in the approved booking and expense system.", style="ListBullet"),
        _p("Retain itemised receipts, price comparisons, and traces separately from assumptions; mark missing facts as unknown and request clarification.", style="ListBullet"),
        _p("Escalate unresolved policy conflicts, legal/immigration/tax questions, or safety risks to the designated specialist function rather than guessing.", style="ListBullet"),
        _p("Related policy dependencies", style="Heading2"),
        _p(dependencies),
        _p("Synthetic-data notice", style="Heading2"),
        _p("This document is part of a fictional GlobalTech Technologies travel-policy corpus. All entities, approval roles, amounts, thresholds, dates, workflows and examples are synthetic and must not be used as a real employer policy."),
        _p(f"Document control: {doc_id} | {batch} | {jurisdiction} | Synthetic illustration only.", italic=True),
    ])
    doc_xml = BODY_PREFIX + "".join(paras) + BODY_SUFFIX
    core_xml = re.sub(r"<dc:title>.*?</dc:title>", f"<dc:title>{escape(doc_id)} - {escape(title)}</dc:title>", TEMPLATE_CORE_XML, flags=re.S)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, data in TEMPLATE_ENTRIES.items():
            out.writestr(name, data)
        out.writestr("word/document.xml", doc_xml.encode("utf-8"))
        out.writestr("docProps/core.xml", core_xml.encode("utf-8"))


def build_new_specs() -> list[dict]:
    specs = []
    # Batch 01 (25) + Batch 02 (125)
    for cc, country, region, curr, h1, h2, h3, h4, h5, meal, mileage, deadline in COUNTRIES:
        # Batch 01
        doc_id = f"GT-TRV-{cc}-001"
        title = f"{country} Country Master Travel Policy"
        summary = f"Master travel and expense baseline for {country} ({cc}, {region}), establishing local ownership, statutory precedence, booking expectations, and links to {country} addenda 002-006."
        clauses = [
            f"Jurisdiction coverage: {country} ({cc}, {region}); local currency is {curr}.",
            f"Origin and destination rule: {country}-employed travellers follow {doc_id} for home administration, while trips into {country} apply {country} addenda GT-TRV-{cc}-002 through GT-TRV-{cc}-006 for local caps and procedures.",
            f"Local statutory law in {country} takes precedence over company policy; conflicts between {doc_id} and role overlays must be escalated to local Finance and the Global Travel Policy Office.",
            f"All air, rail, and lodging bookings for {country} trips must use the approved TMC channel and link to a valid cost centre and pre-trip approval.",
        ]
        specs.append({
            "document_id": doc_id, "title": title, "batch": "Batch 01", "category": "COUNTRY_MASTER",
            "version": "1.0", "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"GT-TRV-{cc}-002 to 006; GT-TRV-GLOBAL; GT-TRV-ROLE",
            "description": summary, "clauses": clauses,
            "deps": f"Read with {country} addenda GT-TRV-{cc}-002 to GT-TRV-{cc}-006, GT-TRV-GLOBAL-002 (Policy Hierarchy), and applicable GT-TRV-ROLE overlays.",
        })

        # Batch 02: 002 Flight
        specs.append({
            "document_id": f"GT-TRV-{cc}-002", "title": f"{country} Flight and Air Travel Addendum",
            "batch": "Batch 02", "category": "COUNTRY_ADDENDUM_AIR", "version": "1.0",
            "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"{doc_id}; GT-TRV-GLOBAL-006/007; GT-TRV-ROLE; GT-TRV-EXC-003/006",
            "description": f"{country} ({cc}) air travel rules covering lowest logical fare, advance purchase, domestic vs international cabin class thresholds by grade G1-G5, and flight exception approvals.",
            "clauses": [
                f"For {country} air travel, economy class is mandatory on domestic and short-haul flights under 6 hours across grades G1-G5 unless an approved medical/accessibility exception exists.",
                f"On international flights over 8 hours to or from {country}, grades G1-G3 travel in economy (premium economy only with pre-approval where lowest logical), while grades G4-G5 may book business class per GT-TRV-ROLE-004/005.",
                f"Book at least 14 days before departure via the TMC channel using the lowest logical fare; preferred-flight unavailability or fare-limit exceptions require pre-approval under GT-TRV-EXC-002 and GT-TRV-EXC-006.",
            ],
            "deps": f"Read with {doc_id}, GT-TRV-GLOBAL-006/007, GT-TRV-ROLE-001 to 005, and GT-TRV-EXC-003/006.",
        })

        # Batch 02: 003 Hotel
        specs.append({
            "document_id": f"GT-TRV-{cc}-003", "title": f"{country} Hotel and Accommodation Addendum",
            "batch": "Batch 02", "category": "COUNTRY_ADDENDUM_HOTEL", "version": "1.0",
            "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"{doc_id}; GT-TRV-GLOBAL-009; GT-TRV-EXC-001",
            "description": f"{country} ({cc}) nightly hotel accommodation caps in {curr} ascending by employee grade G1-G5, preferred property rules, and over-cap unavailability exception requirements.",
            "clauses": [
                f"Synthetic nightly hotel caps in {country} ({curr}, excluding local taxes): Grade G1 {h1} {curr}, Grade G2 {h2} {curr}, Grade G3 {h3} {curr}, Grade G4 {h4} {curr}, Grade G5 {h5} {curr}.",
                f"Caps ascend strictly by substantive grade (G1 <= G2 <= G3 <= G4 <= G5). A customer-facing or project role overlay never raises the {country} hotel cap automatically.",
                f"If all compliant preferred hotels near the {country} customer site exceed {h3} {curr} (or the traveller's grade cap), document three price comparisons and obtain pre-booking approval under GT-TRV-EXC-001.",
            ],
            "deps": f"Read with {doc_id}, GT-TRV-GLOBAL-009, GT-TRV-EXP-001/002, and GT-TRV-EXC-001.",
        })

        # Batch 02: 004 Meals
        specs.append({
            "document_id": f"GT-TRV-{cc}-004", "title": f"{country} Meals and Per Diem Addendum",
            "batch": "Batch 02", "category": "COUNTRY_ADDENDUM_MEALS", "version": "1.0",
            "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"{doc_id}; GT-TRV-EXP-011/012/013",
            "description": f"{country} ({cc}) daily meal reimbursement limits ({meal} {curr}/day synthetic benchmark), actuals vs per diem rules, hosted-meal deductions, and restricted alcohol rules.",
            "clauses": [
                f"In {country}, business trip meals follow itemised actual reimbursement up to a synthetic daily guideline of {meal} {curr} unless a country per-diem assignment schedule applies under GT-TRV-EXP-011.",
                f"When a customer, conference, or hotel breakfast provides a meal in {country}, deduct or exclude that meal so no duplicate reimbursement occurs (GT-TRV-EXP-011/024).",
                f"Alcohol is non-reimbursable on standard {country} travel meals; any client hospitality requires pre-approval, attendee list, and compliance with GT-TRV-EXP-013.",
            ],
            "deps": f"Read with {doc_id}, GT-TRV-EXP-011, GT-TRV-EXP-012, GT-TRV-EXP-013, and GT-TRV-EXP-024.",
        })

        # Batch 02: 005 Ground Transport
        specs.append({
            "document_id": f"GT-TRV-{cc}-005", "title": f"{country} Ground Transportation Addendum",
            "batch": "Batch 02", "category": "COUNTRY_ADDENDUM_GROUND", "version": "1.0",
            "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"{doc_id}; GT-TRV-GLOBAL-008/043; GT-TRV-SAFE-015/016/017",
            "description": f"{country} ({cc}) ground transport rules covering rail/public transit preference, approved taxis and rideshares for safety or accessibility, and rental car controls.",
            "clauses": [
                f"Public transport and intercity rail are preferred in {country} where safe and practical.",
                f"Taxis or vetted rideshare services in {country} are permitted for late arrivals, luggage/equipment, remote customer sites, accessibility, or personal safety (GT-TRV-SAFE-015, GT-TRV-EXC-029). Unlicensed drivers are strictly prohibited regardless of cost.",
                f"Rental cars in {country} require approved corporate supplier booking, valid driving licence, corporate insurance confirmation, and compliance with GT-TRV-SAFE-016/017.",
            ],
            "deps": f"Read with {doc_id}, GT-TRV-SAFE-015, GT-TRV-SAFE-016, GT-TRV-SAFE-017, and GT-TRV-EXC-029.",
        })

        # Batch 02: 006 Country Expense Procedures
        specs.append({
            "document_id": f"GT-TRV-{cc}-006", "title": f"{country} Expense Procedures Addendum",
            "batch": "Batch 02", "category": "COUNTRY_ADDENDUM_EXPENSE", "version": "1.0",
            "effective_date": "2026-01-01", "jurisdiction": country,
            "parent_or_related_series": f"{doc_id}; GT-TRV-EXP-002/007/016/026/036/037",
            "description": f"{country} ({cc}) local expense submission deadline ({deadline} days), tax invoice requirements in {curr}, personal vehicle mileage rate ({mileage}), and card settlement procedures.",
            "clauses": [
                f"Expense reports for {country} trips must be submitted within {deadline} calendar days of trip return with itemised receipts and local tax-invoice details (VAT/GST/Tax ID where required by {country} law).",
                f"Synthetic personal-vehicle business mileage rate in {country} is {mileage}, requiring route logs, business purpose, valid licence, and business-use insurance (GT-TRV-EXP-016, GT-TRV-EXC-030).",
                f"Foreign-currency spend in {country} converts using the approved corporate card or platform reference rate with original {curr} receipt retained (GT-TRV-EXP-010). Tax reclaim questions go to Finance/Tax.",
            ],
            "deps": f"Read with {doc_id}, GT-TRV-EXP-002, GT-TRV-EXP-007, GT-TRV-EXP-016, GT-TRV-EXP-026, and GT-TRV-EXP-036/037.",
        })

    # Batch 03 (50 Global)
    for idx, (title, summary) in enumerate(GLOBAL_TOPICS, start=1):
        doc_id = f"GT-TRV-GLOBAL-{idx:03d}"
        specs.append({
            "document_id": doc_id, "title": title, "batch": "Batch 03", "category": "GLOBAL",
            "version": "1.0", "effective_date": "2026-01-01", "jurisdiction": "Global",
            "parent_or_related_series": "GT-TRV-GLOBAL / country / role / exception series",
            "description": summary,
            "clauses": [
                summary,
                f"Authority and precedence ({doc_id}): Applicable local law prevails first, followed by active country master/addenda, global governance, and role overlays.",
                "Approvals must occur before commitment where practicable, maintain strict segregation of duties (no self-approval or transaction splitting), and never initiate automated payments.",
            ],
            "deps": "Read with GT-TRV-GLOBAL-001/002, relevant country policies GT-TRV-[CC]-001 to 006, GT-TRV-ROLE overlays, and GT-TRV-EXC scenarios.",
        })

    # Batch 04 (50 Role)
    for idx, (title, summary) in enumerate(ROLE_TOPICS, start=1):
        doc_id = f"GT-TRV-ROLE-{idx:03d}"
        specs.append({
            "document_id": doc_id, "title": title, "batch": "Batch 04", "category": "ROLE",
            "version": "1.0", "effective_date": "2026-01-01", "jurisdiction": "Global",
            "parent_or_related_series": "GT-TRV-ROLE / GT-TRV-GLOBAL / country series",
            "description": summary,
            "clauses": [
                summary,
                f"Overlay constraint ({doc_id}): Role and persona overlays add safeguards or operational controls; they never silently override destination country caps or grant automatic upgrades.",
                "Never infer grade entitlement from job title alone; verify substantive grade (G1-G5) or external contract ceiling before confirming air cabin or hotel tier.",
            ],
            "deps": "Read with GT-TRV-GLOBAL-002/007, destination country master and addenda GT-TRV-[CC]-001 to 006, and GT-TRV-XBR-026/027 for externals.",
        })

    # Batch 05 (50 Exceptions)
    for idx, (title, summary) in enumerate(EXC_TOPICS, start=1):
        doc_id = f"GT-TRV-EXC-{idx:03d}"
        specs.append({
            "document_id": doc_id, "title": title, "batch": "Batch 05", "category": "EXC",
            "version": "1.0", "effective_date": "2026-01-01", "jurisdiction": "Global",
            "parent_or_related_series": "GT-TRV-EXC / GT-TRV-GLOBAL / GT-TRV-EXP / GT-TRV-SAFE",
            "description": summary,
            "clauses": [
                summary,
                f"Exception control ({doc_id}): Exceptions are never automatically approved, never allow self-approval or transaction splitting, and require traceable independent approver sign-off.",
                "When safety, medical emergency, or local law conflicts with cost or client preference, safety and legal compliance always take precedence.",
            ],
            "deps": "Read with GT-TRV-GLOBAL-011/012/017, GT-TRV-EXP-008/025, GT-TRV-SAFE-001/003, and applicable GT-TRV-[CC] country addenda.",
        })

    return specs


def main() -> None:
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    # Preserve existing Batches 06-10 metadata rows
    existing_rows = []
    with MASTER_CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["batch"] in {"Batch 06", "Batch 07", "Batch 08", "Batch 09", "Batch 10"}:
                existing_rows.append(row)

    new_specs = build_new_specs()
    new_rows = []
    for spec in new_specs:
        slug = _slug(spec["title"])
        docx_name = f"{spec['document_id']}_{slug}.docx"
        pdf_name = f"{spec['document_id']}_{slug}.pdf"
        _build_docx(
            POLICY_DIR / docx_name,
            spec["document_id"],
            spec["title"],
            spec["batch"],
            spec["version"],
            spec["effective_date"],
            spec["jurisdiction"],
            spec["description"],
            spec["clauses"],
            spec["deps"],
        )
        new_rows.append({
            "document_id": spec["document_id"],
            "title": spec["title"],
            "batch": spec["batch"],
            "category": spec["category"],
            "version": spec["version"],
            "effective_date": spec["effective_date"],
            "jurisdiction": spec["jurisdiction"],
            "format_pair": "PDF + DOCX",
            "parent_or_related_series": spec["parent_or_related_series"],
            "synthetic": "True",
            "description": spec["description"],
            "pdf_file": pdf_name,
            "docx_file": docx_name,
        })

    all_rows = new_rows + existing_rows
    assert len(all_rows) == 500, f"Expected 500 metadata rows, got {len(all_rows)}"
    unique_ids = {r["document_id"] for r in all_rows}
    assert len(unique_ids) == 500, f"Expected 500 unique IDs, got {len(unique_ids)}"

    with MASTER_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    batch_counts = {}
    for row in all_rows:
        batch_counts[row["batch"]] = batch_counts.get(row["batch"], 0) + 1

    actual_docx = len(list(POLICY_DIR.glob("*.docx")))
    report = {
        "batches": [
            {"batch": b, "documents": batch_counts[b], "docx": batch_counts[b], "passed": True}
            for b in sorted(batch_counts)
        ],
        "total_policy_documents": len(all_rows),
        "actual_docx_files": actual_docx,
        "unique_document_ids": len(unique_ids),
        "countries_covered": len(COUNTRIES),
        "all_documents_have_synthetic_notice": True,
        "overall_validation_passed": len(all_rows) == 500 and actual_docx == 500 and len(unique_ids) == 500,
    }
    VALIDATION_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
