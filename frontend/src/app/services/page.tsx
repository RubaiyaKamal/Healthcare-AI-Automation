import Link from "next/link";

export default function ServicesPage() {
  const services = [
    {
      href: "/intake",
      title: "Patient Intake",
      desc: "AI-driven registration chat with duplicate-check guardrails before any record is created.",
      icon: "✚",
    },
    {
      href: "/eligibility",
      title: "Eligibility Check",
      desc: "Rules-first insurance verification with a full audit trail.",
      icon: "✓",
    },
  ];

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Our Services</h1>
      <p className="mt-2 text-brand-muted">
        Automated workflows built for the front desk.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {services.map((s) => (
          <Link
            key={s.href}
            href={s.href}
            className="group rounded-xl border border-brand-line bg-white p-6 shadow-sm transition hover:border-brand-brown hover:shadow-md"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-yellow text-xl">
              {s.icon}
            </div>
            <h2 className="mt-4 text-lg font-semibold text-brand-ink">{s.title}</h2>
            <p className="mt-1 text-sm text-brand-muted">{s.desc}</p>
            <span className="mt-4 inline-block text-sm font-bold text-brand-brown transition group-hover:translate-x-1">
              Open →
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}