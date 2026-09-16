"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

function LoginForm() {
  const params = useSearchParams();
  const initial = params.get("portal") === "patient" ? "patient" : "staff";
  const [portal, setPortal] = useState<"staff" | "patient">(initial);
  const [mode, setMode] = useState<"login" | "signup">("login");

  const isPatient = portal === "patient";

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-center text-3xl font-bold text-brand-ink">
        {isPatient ? "My Health Portal" : "Staff Portal"}
      </h1>
      <p className="mt-2 text-center text-brand-muted">
        {isPatient
          ? "Appointments, lab results, and messages."
          : "Front desk, clinical, and billing access."}
      </p>

      <div className="mt-6 flex rounded-lg border border-brand-line bg-white p-1">
        {(["staff", "patient"] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPortal(p)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-bold transition ${
              portal === p ? "bg-brand-yellow text-brand-ink" : "text-brand-brown"
            }`}
          >
            {p === "staff" ? "Staff" : "Patient"}
          </button>
        ))}
      </div>

      <div className="mt-4 flex rounded-lg border border-brand-line bg-white p-1">
        {(["login", "signup"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-bold transition ${
              mode === m ? "bg-brand-yellow text-brand-ink" : "text-brand-brown"
            }`}
          >
            {m === "login" ? "Login" : "Signup"}
          </button>
        ))}
      </div>

      <form
        className="mt-6 space-y-4 rounded-xl border border-brand-line bg-white p-6 shadow-sm"
        onSubmit={(e) => e.preventDefault()}
      >
        {mode === "signup" && (
          <div>
            <label className="mb-1 block text-sm font-medium text-brand-brownDark">
              {isPatient ? "Full Name" : "Staff Name"}
            </label>
            <input
              type="text"
              className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
              placeholder="Jane Doe"
            />
          </div>
        )}

        {!isPatient && mode === "signup" && (
          <div>
            <label className="mb-1 block text-sm font-medium text-brand-brownDark">
              Role
            </label>
            <select className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown">
              <option>Front Desk</option>
              <option>Clinician</option>
              <option>Billing</option>
              <option>Compliance / Admin</option>
            </select>
          </div>
        )}

        <div>
          <label className="mb-1 block text-sm font-medium text-brand-brownDark">
            Email
          </label>
          <input
            type="email"
            className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-brand-brownDark">
            Password
          </label>
          <input
            type="password"
            className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            placeholder="••••••••"
          />
        </div>

        <button
          type="submit"
          className="w-full rounded-lg bg-brand-yellow px-4 py-2 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight"
        >
          {mode === "login" ? "Login" : "Create Account"}
        </button>

        {isPatient && (
          <p className="text-xs text-brand-muted">
            Patient portal is a demo placeholder — this website does not hold
            real patient accounts.
          </p>
        )}
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}