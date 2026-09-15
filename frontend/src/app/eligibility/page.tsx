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

type CheckResult = {
  status: string;
  detail: string;
  plan?: string | null;
  resolved_by: string;
  payer?: string | null;
  check_id: string;
  checked_at: string;
};

type HistoryRow = {
  status: string;
  payer?: string | null;
  resolved_by: string;
  checked_at: string;
};

const STATUS_STYLES: Record<string, string> = {
  Covered: "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  "Not Covered": "bg-brand-brownDark text-brand-yellowLight border-brand-brownDark",
  "Needs Prior Auth": "bg-brand-yellow text-brand-ink border-brand-yellow",
  Unknown: "bg-brand-yellowSoft border-brand-line text-brand-brownDark",
};

export default function EligibilityPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [result, setResult] = useState<CheckResult | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/patients")
      .then((r) => r.json())
      .then((data: Patient[]) => {
        setPatients(data);
        if (data.length > 0) setSelected(data[0].fhir_id);
      })
      .catch(() => setError("Could not load patients. Is the backend running?"));
  }, []);

  const loadHistory = useCallback(async (fhirId: string) => {
    try {
      const r = await fetch(`/api/eligibility/${fhirId}`);
      const data = await r.json();
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setHistory([]);
    }
  }, []);

  async function check() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const r = await fetch("/api/eligibility/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_fhir_id: selected, actor: "frontend-demo" }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${r.status}`);
      }
      const data: CheckResult = await r.json();
      setResult(data);
      await loadHistory(selected);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const selPatient = patients.find((p) => p.fhir_id === selected);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brand-black">Insurance Eligibility Check</h1>
          <p className="text-sm text-brand-muted">
            Rule-based classification — LLM only used for unrecognized responses.
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

      <div className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-brand-brownDark">
          Select patient
        </label>
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            setResult(null);
            loadHistory(e.target.value);
          }}
          className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
        >
          {patients.map((p) => (
            <option key={p.fhir_id} value={p.fhir_id}>
              {p.last_name}, {p.first_name} — b. {p.dob} ({p.insurer ?? "no insurer"})
            </option>
          ))}
        </select>

        <button
          onClick={check}
          disabled={busy || !selected}
          className="mt-4 w-full rounded-lg bg-brand-yellow px-4 py-2 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight disabled:opacity-40"
        >
          {busy ? "Checking…" : "Check Eligibility"}
        </button>
      </div>

      {result && (
        <div
          className={`mt-6 rounded-xl border p-5 shadow-sm ${STATUS_STYLES[result.status] ?? STATUS_STYLES.Unknown}`}
        >
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">{result.status}</h2>
            <span className="rounded-full bg-black/10 px-2 py-0.5 text-xs">
              resolved_by={result.resolved_by}
            </span>
          </div>
          <p className="mt-1 text-sm">{result.detail}</p>
          {result.plan && <p className="mt-1 text-xs opacity-80">Plan: {result.plan}</p>}
          {result.payer && <p className="mt-1 text-xs opacity-80">Payer: {result.payer}</p>}
        </div>
      )}

      {history.length > 0 && (
        <div className="mt-8">
          <h3 className="mb-2 text-sm font-semibold text-brand-brownDark">
            Recent checks ({selPatient ? `${selPatient.first_name} ${selPatient.last_name}` : "this patient"})
          </h3>
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
              {history.map((h, i) => (
                <tr key={i} className="border-b border-brand-line/50">
                  <td className="py-1.5 pr-3">{h.status}</td>
                  <td className="py-1.5 pr-3">{h.payer ?? "—"}</td>
                  <td className="py-1.5 pr-3">{h.resolved_by}</td>
                  <td className="py-1.5">{new Date(h.checked_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}