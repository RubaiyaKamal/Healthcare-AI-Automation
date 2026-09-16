import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";

type Automation = {
  n: number;
  title: string;
  desc: string;
  status: "Live" | "Demo" | "In Progress" | "Roadmap";
  href?: string;
};

type Domain = {
  id: string;
  icon: string;
  title: string;
  blurb: string;
  roi: string;
  items: Automation[];
};

const domains: Domain[] = [
  {
    id: "front-desk",
    icon: "🗂",
    title: "Front Desk & Patient Access",
    blurb:
      "The patient's first touchpoints — capture the record once, schedule right, verify coverage before the visit.",
    roi: "Less registration re-entry, fewer no-shows, no surprise denials at the door.",
    items: [
      {
        n: 3,
        title: "Patient Intake & Registration",
        desc: "Conversational AI captures demographics, insurance, and contacts with duplicate-check guardrails before any record is created.",
        status: "Live",
        href: "/intake",
      },
      {
        n: 12,
        title: "Insurance Eligibility Verification",
        desc: "Rules-first coverage classification with a deterministic layer — LLM only for edge cases. Every check audited.",
        status: "Live",
        href: "/eligibility",
      },
      {
        n: 1,
        title: "Appointment & Scheduling",
        desc: "Reads the patient record, checks availability, writes a FHIR Appointment — and reconciles across locations.",
        status: "Roadmap",
      },
      {
        n: 10,
        title: "Patient No-Show Prediction",
        desc: "Scores upcoming appointments from history + demographics to prioritize reminders and overbooking.",
        status: "Roadmap",
      },
      {
        n: 7,
        title: "Patient Follow-Up",
        desc: "Reminder half: automated appointment, lab, and billing reminders through the patient's preferred channel.",
        status: "Roadmap",
      },
    ],
  },
  {
    id: "revenue-cycle",
    icon: "◆",
    title: "Revenue Cycle",
    blurb:
      "From clinical note to paid claim — coding, prior auth, submission, and denial handling run on one pipeline.",
    roi: "Lower denial rate and days-in-A/R; every clinical and financial action gated behind human approval.",
    items: [
      {
        n: 13,
        title: "Healthcare Revenue Cycle Automation",
        desc: "The umbrella agent: orchestrates coding, prior auth, claims, and denials for a single patient encounter.",
        status: "Live",
        href: "/rcm",
      },
      {
        n: 5,
        title: "AI-Powered Medical Coding",
        desc: "Reads the clinical note, suggests ICD-10/CPT codes with validated vs. rejected sets logged for audit.",
        status: "Live",
        href: "/rcm",
      },
      {
        n: 6,
        title: "Prior Authorization Automation",
        desc: "Cross-references coded procedures against payer-specific rules and flags what needs a prior auth.",
        status: "Live",
        href: "/rcm",
      },
      {
        n: 2,
        title: "Medical Billing & Claims Automation",
        desc: "Assembles FHIR Claims, submits through a simulated clearinghouse, and classifies the response rules-first.",
        status: "Live",
        href: "/rcm",
      },
      {
        n: 9,
        title: "Healthcare Fraud Detection",
        desc: "Scores claims patterns across all patients for anomaly, duplicate, and abuse signals for compliance review.",
        status: "Roadmap",
      },
    ],
  },
  {
    id: "clinical",
    icon: "✚",
    title: "Clinical Workflow",
    blurb:
      "Clinician-facing automation: write it once, and preparation, extraction, and orders flow from the same note.",
    roi: "Less documentation burnout; coded, med-checked, and lab-routed notes with zero re-keying.",
    items: [
      {
        n: 11,
        title: "Electronic Health Record (EHR) Automation",
        desc: "The FHIR backbone — not a feature but the plumbing every module reads and writes through. Single patient identity.",
        status: "Live",
        href: "/platform/patient-record",
      },
      {
        n: 4,
        title: "Clinical Documentation",
        desc: "Voice or text note captured into a FHIR DocumentReference with draft/final status for clinical review.",
        status: "Roadmap",
      },
      {
        n: 19,
        title: "Medical Records Data Extraction",
        desc: "Pulls medications, diagnoses, and allergies out of notes and incoming referral documents into structured FHIR.",
        status: "In Progress",
      },
      {
        n: 15,
        title: "Lab Result Processing & Notifications",
        desc: "LOINC-based results with normal/abnormal/critical color coding; critical values trigger immediate, deterministic alerts.",
        status: "Roadmap",
      },
      {
        n: 8,
        title: "Prescription & Medication Management",
        desc: "Reads extracted meds, checks interactions, writes a FHIR MedicationRequest — physician approves before send.",
        status: "Roadmap",
      },
    ],
  },
  {
    id: "engagement",
    icon: "◉",
    title: "Patient Engagement",
    blurb:
      "The same record that serves staff also powers honest, helpful patient-facing communication.",
    roi: "Patients feel informed instead of surprised; support load drops when routine answers are automated.",
    items: [
      {
        n: 14,
        title: "Patient Triage & Symptom Assessment",
        desc: "Patient-reported symptoms become FHIR Observations. Never a diagnosis — urgency flags route to a clinician queue.",
        status: "Roadmap",
      },
      {
        n: 20,
        title: "Patient Communication & Support Automation",
        desc: "Appointment, lab, and billing status messages across email/SMS — with a clear human handoff for anything urgent.",
        status: "Roadmap",
      },
      {
        n: 18,
        title: "Patient Referral Management",
        desc: "Packs the clinical summary and sends a structured referral to an external provider; ingests their records on return.",
        status: "Roadmap",
      },
    ],
  },
  {
    id: "operations",
    icon: "⚙",
    title: "Operations",
    blurb:
      "The room to run — staffing and inventory live independently of the patient record but feed the same dashboard.",
    roi: "Right-sized staff and stocked meds reduce both cost and the risk of a canceled or delayed procedure.",
    items: [
      {
        n: 16,
        title: "Hospital Staff Scheduling Automation",
        desc: "Roster, shift coverage, and skill-fit scheduling against forecasted patient volume.",
        status: "Roadmap",
      },
      {
        n: 17,
        title: "Healthcare Inventory Management",
        desc: "Supply and medication stock with min/max reordering — links back to #8 for medication availability.",
        status: "Roadmap",
      },
    ],
  },
];

export default function SolutionsPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Solutions</h1>
      <p className="mt-2 max-w-2xl text-brand-muted">
        HealthFlow AI spans 20 automations across five domains — all reading and
        writing the same FHIR patient record, so nothing is ever entered twice.
        Status badges show what is live today vs. planned.
      </p>

      <div className="mt-8 flex flex-wrap gap-2">
        {domains.map((d) => (
          <a
            key={d.id}
            href={`#${d.id}`}
            className="rounded-full border border-brand-line bg-white px-4 py-1.5 text-sm font-semibold text-brand-brown transition hover:bg-brand-yellow"
          >
            {d.icon} {d.title}
          </a>
        ))}
      </div>

      <div className="mt-10 space-y-16">
        {domains.map((d) => (
          <section key={d.id} id={d.id} className="scroll-mt-24">
            <div className="grid gap-6 md:grid-cols-[1fr_1.6fr]">
              <div>
                <div className="flex items-center gap-3">
                  <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand-yellow text-lg">
                    {d.icon}
                  </span>
                  <h2 className="text-xl font-bold text-brand-ink">{d.title}</h2>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-brand-muted">{d.blurb}</p>
                <p className="mt-3 rounded-lg border border-brand-line bg-white p-3 text-sm text-brand-brownDark">
                  <strong className="text-brand-brown">Focus:</strong> {d.roi}
                </p>
              </div>

              <div className="space-y-3">
                {d.items.map((it) => (
                  <div
                    key={it.n}
                    className="flex items-start gap-4 rounded-xl border border-brand-line bg-white p-4 shadow-sm"
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-yellowSoft text-sm font-bold text-brand-brownDark">
                      {it.n}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-brand-ink">{it.title}</h3>
                        <StatusBadge status={it.status} />
                      </div>
                      <p className="mt-1 text-sm leading-relaxed text-brand-muted">{it.desc}</p>
                      {it.href && (
                        <Link
                          href={it.href}
                          className="mt-2 inline-block text-sm font-bold text-brand-brown transition group-hover:translate-x-1 hover:underline"
                        >
                          See it live →
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}