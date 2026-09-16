"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";

type Patient = {
  fhir_id: string;
  first_name: string;
  last_name: string;
  dob: string;
  gender?: string;
  mrn?: string;
  phone?: string;
  email?: string;
  address?: { line?: string[]; city?: string; state?: string; postalCode?: string };
  insurer?: string | null;
  member_id?: string | null;
};

type EligRow = {
  status: string;
  payer?: string | null;
  resolved_by: string;
  checked_at: string;
};

type ClaimRow = {
  claim_id: string;
  patient_fhir_id: string;
  payer?: string | null;
  total_amount?: number | null;
  codes: { system?: string; code?: string }[];
  status: string;
  resolved_by?: string | null;
  created_at?: string;
  submitted_at?: string | null;
  updated_at?: string | null;
  open_denial_reason?: string | null;
};

type CodingRow = {
  id: number;
  patient_fhir_id?: string;
  note_text?: string;
  accepted_codes?: { system?: string; code?: string; display?: string }[];
  rejected_codes?: { system?: string; code?: string; display?: string }[];
  resolved_by?: string;
  created_at?: string;
};

type DenialRow = {
  id: number;
  claim_id: string;
  reason_code?: string | null;
  reason_text?: string | null;
  suggested_fix?: string | null;
  fix_status: string;
  created_at: string;
};

type AuditRow = {
  actor: string;
  action: string;
  resource_type?: string | null;
  resource_id?: string | null;
  summary?: string | null;
  created_at: string;
};

type LabResult = {
  name: string;
  code: string;
  value: string;
  unit: string;
  range: string;
  flag: "Normal" | "Abnormal" | "Critical";
};

const CLAIM_STYLES: Record<string, string> = {
  PAID: "text-brand-brownDark bg-brand-yellowSoft border-brand-line",
  DENIED: "text-red-700 bg-red-50 border-red-200",
  PARTIALLY_PAID: "text-amber-700 bg-amber-50 border-amber-200",
  PENDING: "text-brand-brownDark bg-brand-yellow/20 border-brand-line",
  SUBMITTED: "text-brand-brownDark bg-brand-yellow/20 border-brand-line",
  DRAFT: "text-brand-muted bg-brand-cream border-brand-line",
};

const LABS_TEMPLATE: { name: string; code: string; unit: string; range: string; values: string[]; flags: string[] }[] = [
  { name: "Hemoglobin", code: "718-7", unit: "g/dL", range: "13.5–17.5", values: ["14.2", "11.8", "9.1"], flags: ["Normal", "Abnormal", "Critical"] },
  { name: "WBC Count", code: "6690-2", unit: "K/uL", range: "4.0–11.0", values: ["7.5", "14.8", "3.1"], flags: ["Normal", "Abnormal", "Critical"] },
  { name: "Glucose (fasting)", code: "2345-7", unit: "mg/dL", range: "70–99", values: ["92", "168", "310"], flags: ["Normal", "Abnormal", "Critical"] },
  { name: "HbA1c", code: "4548-4", unit: "%", range: "4.0–5.6", values: ["5.1", "7.8", "12.4"], flags: ["Normal", "Abnormal", "Critical"] },
  { name: "LDL Cholesterol", code: "13457-7", unit: "mg/dL", range: "<100", values: ["95", "142", "205"], flags: ["Normal", "Abnormal", "Critical"] },
  { name: "Thyroid Stimulating Hormone", code: "3016-3", unit: "mIU/L", range: "0.4–4.0", values: ["2.1", "7.9", "0.01"], flags: ["Normal", "Abnormal", "Critical"] },
];

function flagColor(flag: string) {
  switch (flag) {
    case "Critical":
      return "text-red-700 bg-red-50 border-red-200";
    case "Abnormal":
      return "text-amber-700 bg-amber-50 border-amber-200";
    default:
      return "text-brand-brownDark bg-brand-yellowSoft border-brand-line";
  }
}

export default function PatientRecordPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState("");
  const [patient, setPatient] = useState<Patient | null>(null);
  const [elig, setElig] = useState<EligRow[]>([]);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [coding, setCoding] = useState<CodingRow[]>([]);
  const [denials, setDenials] = useState<DenialRow[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [tab, setTab] = useState("overview");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/patients")
      .then((r) => r.json())
      .then((d: Patient[]) => {
        setPatients(d);
        if (d.length > 0) setSelected(d[0].fhir_id);
      })
      .catch(() => setError("Could not load patients. Is the backend running?"));
  }, []);

  const patientClaims = useMemo(
    () => claims.filter((c) => c.patient_fhir_id === selected),
    [claims, selected]
  );
  const patientClaimIds = useMemo(
    () => new Set(patientClaims.map((c) => c.claim_id)),
    [patientClaims]
  );
  const patientDenials = useMemo(
    () => denials.filter((d) => patientClaimIds.has(d.claim_id)),
    [denials, patientClaimIds]
  );
  const patientCoding = useMemo(
    () => coding.filter((c) => c.patient_fhir_id === selected),
    [coding, selected]
  );
  const patientAudit = useMemo(
    () =>
      audit.filter(
        (a) => a.resource_id === selected || (a.summary ?? "").includes(selected) || (a.resource_type ?? "") === "Patient"
      ),
    [audit, selected]
  );

  const labs = useMemo(() => {
    let h = 0;
    for (const ch of selected) h = (h * 31 + ch.charCodeAt(0)) % 997;
    return LABS_TEMPLATE.map((t, i) => ({
      name: t.name,
      code: t.code,
      value: t.values[(h + i * 2) % 3],
      unit: t.unit,
      range: t.range,
      flag: t.flags[(h + i) % 3] as LabResult["flag"],
    }));
  }, [selected]);

  useEffect(() => {
    if (!selected) return;
    setError("");
    Promise.all([
      fetch(`/api/patients/${selected}`).then((r) => r.json()),
      fetch(`/api/eligibility/${selected}`).then((r) => r.json()),
      fetch("/api/rcm/claims?limit=100").then((r) => r.json()),
      fetch("/api/rcm/coding?limit=100").then((r) => r.json()),
      fetch("/api/rcm/denials?limit=100").then((r) => r.json()),
      fetch("/api/audit?limit=200").then((r) => r.json()),
    ])
      .then(([p, e, c, co, dn, au]) => {
        setPatient(p);
        setElig(Array.isArray(e) ? e : []);
        setClaims(Array.isArray(c) ? c : []);
        setCoding(Array.isArray(co) ? co : []);
        setDenials(Array.isArray(dn) ? dn : []);
        setAudit(Array.isArray(au) ? au : []);
      })
      .catch(() => setError("Could not load the full record. Is the backend running?"));
  }, [selected]);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "eligibility", label: "Eligibility" },
    { id: "claims", label: "Claims & Denials" },
    { id: "coding", label: "Coding" },
    { id: "labs", label: "Labs" },
    { id: "audit", label: "Audit Trail" },
  ];

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-brand-ink">Patient Record</h1>
          <p className="text-sm text-brand-muted">
            One record, all 20 modules writing into it. Pick a patient below.
          </p>
        </div>
        <a href="/platform" className="text-sm font-semibold text-brand-brown hover:underline">
          ← Platform
        </a>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-brand-brownLight bg-brand-yellowSoft px-4 py-2 text-sm text-brand-brownDark">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-brand-brownDark">
          Select patient
        </label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
        >
          {patients.map((p) => (
            <option key={p.fhir_id} value={p.fhir_id}>
              {p.last_name}, {p.first_name} — b. {p.dob} ({p.insurer ?? "no insurer"})
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6 flex flex-wrap gap-1.5">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`rounded-full px-4 py-1.5 text-sm font-bold transition ${
              tab === t.id
                ? "bg-brand-brownDark text-brand-yellow"
                : "border border-brand-line bg-white text-brand-brown hover:bg-brand-yellowSoft"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-6">
        {tab === "overview" && patient && (
          <>
            <section className="grid gap-4 md:grid-cols-2">
              <Card title="Demographics & Insurance">
                <dl className="space-y-2 text-sm">
                  <Row k="Name" v={`${patient.first_name} ${patient.last_name}`} />
                  <Row k="DOB" v={patient.dob} />
                  <Row k="Gender" v={patient.gender ?? "—"} />
                  <Row k="MRN" v={patient.mrn ?? "—"} />
                  <Row k="Phone" v={patient.phone ?? "—"} />
                  <Row k="Email" v={patient.email ?? "—"} />
                  <Row k="Insurer" v={patient.insurer ?? "Self-Pay"} />
                  <Row k="Member ID" v={patient.member_id ?? "—"} />
                </dl>
              </Card>
              <Card title="Eligibility (latest)">
                {elig.length === 0 ? (
                  <p className="text-sm text-brand-muted">
                    No checks yet. Run Eligibility Check for this patient.
                  </p>
                ) : (
                  <dl className="space-y-2 text-sm">
                    <Row k="Status" v={elig[0].status} />
                    <Row k="Payer" v={elig[0].payer ?? "—"} />
                    <Row k="Resolved by" v={elig[0].resolved_by} />
                    <Row k="Checked" v={new Date(elig[0].checked_at).toLocaleString()} />
                  </dl>
                )}
              </Card>
            </section>
            <section className="grid gap-4 md:grid-cols-2">
              <Card title="Claims">
                <p className="text-3xl font-extrabold text-brand-brownDark">{patientClaims.length}</p>
                <p className="text-xs text-brand-muted">claims on file for this patient</p>
              </Card>
              <Card title="Audit">
                <p className="text-3xl font-extrabold text-brand-brownDark">{patientAudit.length}</p>
                <p className="text-xs text-brand-muted">recorded access events</p>
              </Card>
            </section>
          </>
        )}

        {tab === "eligibility" && (
          <Card title="Eligibility history">
            {elig.length === 0 ? (
              <p className="text-sm text-brand-muted">No eligibility checks recorded yet.</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-brand-line text-xs text-brand-muted">
                    <th className="py-1 pr-3">Status</th>
                    <th className="py-1 pr-3">Payer</th>
                    <th className="py-1 pr-3">By</th>
                    <th className="py-1">When</th>
                  </tr>
                </thead>
                <tbody>
                  {elig.map((h, i) => (
                    <tr key={i} className="border-b border-brand-line/50">
                      <td className="py-1.5 pr-3">{h.status}</td>
                      <td className="py-1.5 pr-3">{h.payer ?? "—"}</td>
                      <td className="py-1.5 pr-3">{h.resolved_by}</td>
                      <td className="py-1.5">{new Date(h.checked_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}

        {tab === "claims" && (
          <>
            <Card title="Claims">
              {patientClaims.length === 0 ? (
                <p className="text-sm text-brand-muted">
                  No claims yet. Run the Revenue Cycle agent for this patient.
                </p>
              ) : (
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-brand-line text-xs text-brand-muted">
                      <th className="py-1 pr-3">Claim</th>
                      <th className="py-1 pr-3">Payer</th>
                      <th className="py-1 pr-3">Codes</th>
                      <th className="py-1 pr-3">Amount</th>
                      <th className="py-1 pr-3">Status</th>
                      <th className="py-1">Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {patientClaims.map((c) => (
                      <tr key={c.claim_id} className="border-b border-brand-line/50">
                        <td className="py-1.5 pr-3 font-mono text-xs">{c.claim_id}</td>
                        <td className="py-1.5 pr-3">{c.payer ?? "—"}</td>
                        <td className="py-1.5 pr-3">
                          {c.codes.map((x) => x.code).join(", ") || "—"}
                        </td>
                        <td className="py-1.5 pr-3">
                          {c.total_amount != null ? `$${c.total_amount}` : "—"}
                        </td>
                        <td className="py-1.5 pr-3">
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[11px] font-bold ${
                              CLAIM_STYLES[c.status] ?? CLAIM_STYLES.DRAFT
                            }`}
                          >
                            {c.status}
                          </span>
                        </td>
                        <td className="py-1.5">
                          {c.updated_at ? new Date(c.updated_at).toLocaleDateString() : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
            <Card title="Open denials">
              {patientDenials.length === 0 ? (
                <p className="text-sm text-brand-muted">No open denials for this patient.</p>
              ) : (
                <ul className="space-y-3">
                  {patientDenials.map((d) => (
                    <li key={d.id} className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
                      <p className="font-bold text-red-700">
                        {d.reason_code ?? "DENIAL"} — {d.reason_text ?? "denied"}
                      </p>
                      {d.suggested_fix && (
                        <p className="mt-1 text-xs text-red-600">Fix: {d.suggested_fix}</p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </>
        )}

        {tab === "coding" && (
          <Card title="Coding suggestions">
            {patientCoding.length === 0 ? (
              <p className="text-sm text-brand-muted">
                No coding suggestions yet. Run the Revenue Cycle agent with a
                clinical note for this patient.
              </p>
            ) : (
              <ul className="space-y-3">
                {patientCoding.map((c) => (
                  <li key={c.id} className="rounded-lg border border-brand-line bg-brand-cream p-3 text-sm">
                    {c.note_text && <p className="text-xs italic text-brand-muted">"{c.note_text?.slice(0, 160)}…"</p>}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(c.accepted_codes ?? []).map((cd, i) => (
                        <span
                          key={i}
                          className="rounded-full border border-brand-line bg-brand-yellowSoft px-2 py-0.5 text-xs font-bold text-brand-brownDark"
                        >
                          {cd.code} {cd.display ? `· ${cd.display}` : ""}
                        </span>
                      ))}
                      {(c.rejected_codes ?? []).map((cd, i) => (
                        <span
                          key={i}
                          className="rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-bold text-red-500 line-through"
                        >
                          {cd.code}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 text-[11px] text-brand-muted">
                      resolved_by={c.resolved_by} · {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        {tab === "labs" && (
          <>
            <Card title="Recent lab results">
              <div className="mb-3 rounded-lg border border-brand-line bg-brand-yellowSoft p-3 text-xs text-brand-brownDark">
                <strong>Preview — simulated.</strong> Lab automation (#15) is on
                the roadmap; these rows are deterministically generated to show
                the color-coded normal / abnormal / critical UX that a LOINC
                feed will populate.
              </div>
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-brand-line text-xs text-brand-muted">
                    <th className="py-1 pr-3">Test</th>
                    <th className="py-1 pr-3">LOINC</th>
                    <th className="py-1 pr-3">Result</th>
                    <th className="py-1 pr-3">Ref range</th>
                    <th className="py-1">Flag</th>
                  </tr>
                </thead>
                <tbody>
                  {labs.map((l) => (
                    <tr key={l.code} className="border-b border-brand-line/50">
                      <td className="py-1.5 pr-3 font-medium text-brand-ink">{l.name}</td>
                      <td className="py-1.5 pr-3 font-mono text-xs text-brand-muted">{l.code}</td>
                      <td className="py-1.5 pr-3 font-bold">{l.value} {l.unit}</td>
                      <td className="py-1.5 pr-3 text-brand-muted">{l.range}</td>
                      <td className="py-1.5">
                        <span className={`rounded-full border px-2 py-0.5 text-[11px] font-bold ${flagColor(l.flag)}`}>
                          {l.flag}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-3 text-xs text-brand-muted">
                Critical values are intended to trigger immediate provider
                notification via a deterministic rule — never gated behind an LLM.
              </p>
            </Card>
          </>
        )}

        {tab === "audit" && (
          <Card title="Audit trail">
            <p className="mb-3 text-xs text-brand-muted">
              Every access to this patient&apos;s record — visible to
              compliance/admin roles only.
            </p>
            {patientAudit.length === 0 ? (
              <p className="text-sm text-brand-muted">No audit events recorded for this patient yet.</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-brand-line text-xs text-brand-muted">
                    <th className="py-1 pr-3">When</th>
                    <th className="py-1 pr-3">Actor</th>
                    <th className="py-1 pr-3">Action</th>
                    <th className="py-1 pr-3">Resource</th>
                    <th className="py-1">Summary</th>
                  </tr>
                </thead>
                <tbody>
                  {patientAudit.map((a, i) => (
                    <tr key={i} className="border-b border-brand-line/50">
                      <td className="py-1.5 pr-3 whitespace-nowrap">
                        {new Date(a.created_at).toLocaleString()}
                      </td>
                      <td className="py-1.5 pr-3">{a.actor}</td>
                      <td className="py-1.5 pr-3 font-mono text-xs">{a.action}</td>
                      <td className="py-1.5 pr-3">
                        {a.resource_type ?? "—"}{a.resource_id ? ` / ${a.resource_id}` : ""}
                      </td>
                      <td className="py-1.5 text-xs text-brand-muted">{a.summary ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}
      </div>
    </main>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
      <h2 className="mb-3 text-base font-bold text-brand-ink">{title}</h2>
      {children}
    </section>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-brand-line/40 pb-1 last:border-0">
      <span className="text-brand-muted">{k}</span>
      <span className="font-semibold text-brand-ink">{v}</span>
    </div>
  );
}