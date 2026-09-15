export default function AboutPage() {
  const stats = [
    { value: "0", label: "Duplicate Records" },
    { value: "100%", label: "Audit Coverage" },
    { value: "3s", label: "Eligibility Check" },
    { value: "24/7", label: "AI Intake Access" },
  ];

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">About HealthFlow AI</h1>
      <p className="mt-4 max-w-2xl text-brand-muted">
        HealthFlow AI is an AI-powered platform that automates the most
        repetitive parts of healthcare administration — patient intake and
        insurance eligibility — so clinics can process more patients faster
        with fewer errors.
      </p>

      {/* Stats */}
      <div className="mt-10 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-brand-line bg-white p-5 text-center shadow-sm"
          >
            <p className="text-2xl font-extrabold text-brand-yellow">{s.value}</p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-brand-brown">
              {s.label}
            </p>
          </div>
        ))}
      </div>

      {/* For Patients */}
      <section className="mt-14">
        <h2 className="text-xl font-bold text-brand-ink">What It Means for Patients</h2>

        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <Card
            title="Instant Registration"
            desc="No more long waiting-room forms. A conversational AI walks patients through intake, capturing every detail accurately before they even arrive."
          />
          <Card
            title="No Duplicate Confusion"
            desc="Fuzzy-match + LLM duplicate checking stops mixed-up records before they are created — so patient history is never lost or merged with someone else's."
          />
          <Card
            title="Real-Time Eligibility"
            desc="Patients know their coverage status within seconds instead of waiting days. No surprise bills from incorrect assumptions."
          />
          <Card
            title="Mobile Access"
            desc="A dedicated mobile app lets patients check in, chat with the intake agent, and verify eligibility — all from their phone."
          />
        </div>
      </section>

      {/* For Clinics */}
      <section className="mt-14">
        <h2 className="text-xl font-bold text-brand-ink">What It Means for Clinics</h2>

        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <Card
            title="Front-Desk Time Back"
            desc="Intake chat handles repetitive registration conversations automatically, freeing staff for higher-value patient care."
          />
          <Card
            title="Eligibility Checks in Seconds"
            desc="A rules-first classifier resolves most checks instantly. The AI only steps in for edge cases — deterministic when it can be, intelligent when it must be."
          />
          <Card
            title="Full Audit Trail"
            desc="Every action — intake, duplicate check, eligibility result — is logged with actor, timestamp, and context. Compliance-ready from day one."
          />
          <Card
            title="Clean Patient Records"
            desc="FHIR-native patient data stays consistent across systems. Registration, lookup, and search all pull from the same source of truth."
          />
        </div>
      </section>

      <p className="mt-12 text-xs text-brand-muted">
        Local sandbox only — synthetic data. Not HIPAA-compliant for production use.
      </p>
    </main>
  );
}

function Card({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
      <h3 className="text-base font-semibold text-brand-ink">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-brand-muted">{desc}</p>
    </div>
  );
}