import Link from "next/link";

export default function Home() {
  const cards = [
    {
      href: "/intake",
      title: "Patient Intake",
      desc: "AI-driven registration chat with duplicate-check guardrails",
    },
    {
      href: "/eligibility",
      title: "Eligibility Check",
      desc: "Deterministic insurance verification with audit trail",
    },
  ];

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold">Healthcare AI — Phase 1</h1>
      <p className="mt-2 text-slate-600">
        FHIR + OpenAI Agents SDK automation demo: patient intake and
        insurance eligibility.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {cards.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-sky-400 hover:shadow"
          >
            <h2 className="text-lg font-semibold">{c.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{c.desc}</p>
          </Link>
        ))}
      </div>

      <p className="mt-12 text-xs text-slate-400">
        Local sandbox only — synthetic data. No production PHI.
      </p>
    </main>
  );
}