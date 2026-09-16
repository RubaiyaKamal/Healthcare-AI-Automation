"use client";

import { useCallback, useEffect, useState } from "react";

type Patient = {
  fhir_id: string;
  first_name: string;
  last_name: string;
  dob: string;
  mrn?: string;
  insurer?: string | null;
  member_id?: string | null;
};

type Metrics = {
  funnel: {
    total: number;
    paid: number;
    denied: number;
    partially_paid: number;
    pending: number;
    error: number;
  };
  open_denials: number;
  denial_rate: number;
};

type ClaimRow = {
  claim_id: string;
  patient_fhir_id: string;
  payer?: string | null;
  total_amount?: number | null;
  codes: { system?: string; code?: string }[];
  status: string;
  resolved_by?: string | null;
  submitted_at?: string | null;
  updated_at?: string | null;
  open_denial_reason?: string | null;
};

type DenialRow = {
  id: number;
  claim_id: string;
  reason_code?: string | null;
  reason_text?: string | null;
  suggested_fix?: string | null;
  fix_status: string;
  patient_name?: string | null;
  created_at: string;
};

type CodingRow = {
  id: number;
  patient_fhir_id?: string;
  note_excerpt?: string;
  accepted_codes?: { system?: string; code?: string; display?: string }[];
  rejected_codes?: { system?: string; code?: string; display?: string }[];
  resolved_by?: string;
  created_at?: string;
};

type PriorAuthRow = {
  id?: number;
  request_id: string;
  patient_fhir_id: string;
  payer: string;
  procedure_code: string;
  procedure_display?: string | null;
  status: string;
  narrative?: string | null;
  created_at: string;
  submitted_at?: string | null;
};

type ToolCall = {
  tool: string;
  args: Record<string, unknown>;
};

const STATUS_STYLES: Record<string, string> = {
  PAID: "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  PARTIALLY_PAID: "bg-brand-yellowSoft text-brand-brownDark border-brand-brownLight",
  DENIED: "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  PENDING: "bg-brand-yellow text-brand-ink border-brand-yellow",
  SUBMITTED: "bg-brand-yellow text-brand-ink border-brand-yellow",
  DRAFT: "bg-brand-yellowSoft border-brand-line text-brand-brownDark",
  ERROR: "bg-brand-yellow text-brand-ink border-brand-yellow",
  RESOLVED: "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  OPEN: "bg-brand-yellow text-brand-ink border-brand-yellow",
  APPROVED: "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  PENDING_REVIEW: "bg-brand-yellowSoft border-brand-line text-brand-brownDark",
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${
        STATUS_STYLES[status] ?? "bg-brand-yellowSoft border-brand-line text-brand-brownDark"
      }`}
    >
      {status}
    </span>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div className="rounded-xl border border-brand-line bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-brand-black">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-brand-muted">{hint}</p>}
    </div>
  );
}

export default function RCMPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState("");
  const [payer, setPayer] = useState("");
  const [note, setNote] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [claims, setClaims] = useState<ClaimRow[]>([]);
  const [denials, setDenials] = useState<DenialRow[]>([]);
  const [coding, setCoding] = useState<CodingRow[]>([]);
  const [priorAuth, setPriorAuth] = useState<PriorAuthRow[]>([]);

  const [output, setOutput] = useState("");
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [running, setRunning] = useState(false);
  const [fixingId, setFixingId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const loadAll = useCallback(async () => {
    const fetchers: [Promise<Response>, (d: unknown) => void][] = [
      [fetch("/api/rcm/metrics"), (d) => setMetrics(d && typeof d === "object" && "funnel" in d ? (d as Metrics) : null)],
      [fetch("/api/rcm/claims"), (d) => setClaims(Array.isArray(d) ? (d as ClaimRow[]) : [])],
      [fetch("/api/rcm/denials"), (d) => setDenials(Array.isArray(d) ? (d as DenialRow[]) : [])],
      [fetch("/api/rcm/coding"), (d) => setCoding(Array.isArray(d) ? (d as CodingRow[]) : [])],
      [fetch("/api/rcm/prior-auth"), (d) => setPriorAuth(Array.isArray(d) ? (d as PriorAuthRow[]) : [])],
    ];
    await Promise.all(
      fetchers.map(async ([p, setter]) => {
        try {
          setter(await (await p).json());
        } catch {
          /* endpoint unavailable */
        }
      })
    );
  }, []);

  useEffect(() => {
    fetch("/api/patients")
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setPatients(list);
        if (list.length > 0) {
          setSelected(list[0].fhir_id);
          setPayer(list[0].insurer ?? "");
        }
      })
      .catch(() => setError("Could not load patients. Is the backend running?"));
    loadAll();
  }, [loadAll]);

  async function runCycle() {
    if (!selected || !note.trim()) return;
    setRunning(true);
    setError("");
    setOutput("");
    setToolCalls([]);
    try {
      const r = await fetch("/api/rcm/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_fhir_id: selected,
          clinical_note: note,
          payer,
          actor: "frontend-demo",
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      setOutput(data.output ?? "");
      setToolCalls(Array.isArray(data.tool_calls) ? data.tool_calls : []);
      await loadAll();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  }

  async function suggestFix(id: number) {
    setFixingId(id);
    try {
      const r = await fetch("/api/rcm/suggest-denial-fix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ denial_id: id }),
      });
      if (!r.ok) throw new Error("request failed");
      await loadAll();
    } catch {
      setError("Could not generate denial fix suggestion.");
    } finally {
      setFixingId(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brand-black">Revenue Cycle</h1>
          <p className="text-sm text-brand-muted">
            Eligibility → coding → prior auth → claims → denials.
          </p>
        </div>
        <a href="/" className="text-sm font-semibold text-brand-brown hover:underline">
          ← Home
        </a>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-brand-brownLight bg-brand-yellowSoft px-4 py-2 text-sm text-brand-brownDark">
          {error}
        </div>
      )}

      {/* Run the full cycle */}
      <section className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-semibold text-brand-brownDark">
          Run full revenue cycle agent
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm text-brand-muted">
            Patient
            <select
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                const p = patients.find((x) => x.fhir_id === e.target.value);
                if (p?.insurer) setPayer(p.insurer);
              }}
              className="mt-1 w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            >
              {patients.map((p) => (
                <option key={p.fhir_id} value={p.fhir_id}>
                  {p.last_name}, {p.first_name} — b. {p.dob} ({p.insurer ?? "no insurer"})
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-brand-muted">
            Payer
            <input
              value={payer}
              onChange={(e) => setPayer(e.target.value)}
              placeholder="e.g. Acme Health"
              className="mt-1 w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            />
          </label>
        </div>
        <label className="mt-3 block text-sm text-brand-muted">
          Clinical note
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={4}
            placeholder="e.g. 48yo established patient with 3-month right knee pain, MRI confirmed meniscal tear. Plan: arthroscopic meniscectomy. Comorbid: type 2 diabetes, hypertension."
            className="mt-1 w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
          />
        </label>
        <button
          onClick={runCycle}
          disabled={running || !selected}
          className="mt-4 rounded-lg bg-brand-yellow px-4 py-2 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight disabled:opacity-40"
        >
          {running ? "Running…" : "Run Revenue Cycle"}
        </button>
      </section>

      {output && (
        <div className="mt-6 rounded-xl border border-brand-brownDark bg-brand-brownDark p-5 text-brand-yellowLight shadow-sm">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide">Agent output</h3>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{output}</p>
          {toolCalls.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-semibold text-brand-yellowLight/80">
                {toolCalls.length} tool call{toolCalls.length > 1 ? "s" : ""}
              </summary>
              <ul className="mt-2 space-y-1 text-xs">
                {toolCalls.map((t, i) => (
                  <li key={i} className="rounded bg-black/20 px-2 py-1">
                    <span className="font-mono">{t.tool}</span>
                    {Object.keys(t.args).length > 0 && (
                      <span className="text-brand-yellowLight/70"> — {JSON.stringify(t.args)}</span>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Metrics */}
      {metrics && metrics.funnel && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-brand-brownDark">Claim funnel</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <MetricCard label="Submitted" value={metrics.funnel.total ?? 0} />
            <MetricCard label="Paid" value={metrics.funnel.paid ?? 0} />
            <MetricCard label="Partially Paid" value={metrics.funnel.partially_paid ?? 0} />
            <MetricCard label="Denied" value={metrics.funnel.denied ?? 0} hint={`${metrics.denial_rate ?? 0}% denial rate`} />
            <MetricCard label="Pending" value={metrics.funnel.pending ?? 0} />
            <MetricCard label="Errors" value={metrics.funnel.error ?? 0} />
            <MetricCard label="Open denials" value={metrics.open_denials ?? 0} />
          </div>
        </section>
      )}

      {/* Claims */}
      <section className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-brand-brownDark">Claims</h2>
        {claims.length === 0 ? (
          <p className="text-sm text-brand-muted">No claims yet — run the cycle above.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-brand-line text-xs text-brand-muted">
                <th className="py-1 pr-3">Claim</th>
                <th className="py-1 pr-3">Patient</th>
                <th className="py-1 pr-3">Payer</th>
                <th className="py-1 pr-3">Codes</th>
                <th className="py-1 pr-3">Amount</th>
                <th className="py-1 pr-3">Status</th>
                <th className="py-1">Resolved by</th>
              </tr>
            </thead>
            <tbody>
              {claims.map((c) => (
                <tr key={c.claim_id} className="border-b border-brand-line/50">
                  <td className="py-1.5 pr-3 font-mono text-xs">{c.claim_id}</td>
                  <td className="py-1.5 pr-3">{c.patient_fhir_id}</td>
                  <td className="py-1.5 pr-3">{c.payer ?? "—"}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs">
                    {(c.codes ?? []).map((x) => x.code).join(", ") || "—"}
                  </td>
                  <td className="py-1.5 pr-3">
                    {c.total_amount != null ? `$${c.total_amount.toFixed(2)}` : "—"}
                  </td>
                  <td className="py-1.5 pr-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="py-1.5">{c.resolved_by ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Denials */}
      <section className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-brand-brownDark">Denial queue</h2>
        {denials.length === 0 ? (
          <p className="text-sm text-brand-muted">No denials.</p>
        ) : (
          <div className="space-y-3">
            {denials.map((d) => (
              <div
                key={d.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-brand-line bg-white p-4 shadow-sm"
              >
                <div className="max-w-xl">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={d.fix_status} />
                    <span className="font-mono text-xs text-brand-muted">{d.claim_id}</span>
                  </div>
                  <p className="mt-1 text-sm font-semibold text-brand-black">
                    {d.reason_code ? `${d.reason_code} — ` : ""}
                    {d.reason_text ?? "Denied"}
                  </p>
                  {d.patient_name && <p className="text-xs text-brand-muted">{d.patient_name}</p>}
                  {d.suggested_fix && (
                    <p className="mt-1 rounded bg-brand-cream px-2 py-1 text-xs text-brand-brownDark">
                      Suggested fix: {d.suggested_fix}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => suggestFix(d.id)}
                  disabled={fixingId === d.id || d.fix_status === "RESOLVED"}
                  className="rounded-lg border border-brand-brown bg-white px-3 py-1.5 text-xs font-bold text-brand-brown transition hover:bg-brand-yellowLight disabled:opacity-40"
                >
                  {fixingId === d.id ? "Suggesting…" : "Suggest fix"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Coding suggestions + prior auth */}
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-brand-brownDark">Recent coding suggestions</h2>
          {coding.length === 0 ? (
            <p className="text-sm text-brand-muted">No coding activity yet.</p>
          ) : (
            <ul className="space-y-2">
              {coding.map((c) => (
                <li key={c.id} className="rounded-xl border border-brand-line bg-white p-3 text-sm shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-brand-muted">
                      {c.patient_fhir_id ?? "?"} · {new Date(c.created_at ?? "").toLocaleString()}
                    </span>
                    <span className="rounded-full bg-brand-yellowSoft border border-brand-line px-2 py-0.5 text-xs text-brand-brownDark">
                      accepted {c.accepted_codes?.length ?? 0}
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {(c.accepted_codes ?? []).map((s, j) => (
                      <span
                        key={`acc-${j}`}
                        className="rounded bg-brand-brownDark px-1.5 py-0.5 font-mono text-xs text-brand-yellowLight"
                        title={s.display}
                      >
                        {s.code}
                      </span>
                    ))}
                    {(c.rejected_codes ?? []).map((s, j) => (
                      <span
                        key={`rej-${j}`}
                        className="rounded bg-brand-yellow px-1.5 py-0.5 font-mono text-xs text-brand-ink line-through"
                        title={`rejected · ${s.display ?? ""}`}
                      >
                        {s.code}
                      </span>
                    ))}
                  </div>
                  {c.note_excerpt && (
                    <p className="mt-1 truncate text-xs text-brand-muted" title={c.note_excerpt}>
                      “{c.note_excerpt}”
                    </p>
                  )}
                  {c.resolved_by && (
                    <p className="mt-0.5 text-xs text-brand-muted">resolved by {c.resolved_by}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold text-brand-brownDark">Prior authorization</h2>
          {priorAuth.length === 0 ? (
            <p className="text-sm text-brand-muted">No prior-auth requests.</p>
          ) : (
            <ul className="space-y-2">
              {priorAuth.map((p) => (
                <li key={p.request_id} className="rounded-xl border border-brand-line bg-white p-3 text-sm shadow-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-brand-muted">{p.request_id}</span>
                    <StatusBadge status={p.status} />
                  </div>
                  <p className="mt-1 font-semibold text-brand-black">
                    {p.procedure_code} {p.procedure_display ? `— ${p.procedure_display}` : ""}
                  </p>
                  <p className="text-xs text-brand-muted">
                    {p.payer} · {p.patient_fhir_id}
                  </p>
                  {p.narrative && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs font-semibold text-brand-brown">
                        Narrative
                      </summary>
                      <p className="mt-1 whitespace-pre-wrap text-xs text-brand-brownDark">{p.narrative}</p>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}