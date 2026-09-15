"use client";

import { useState } from "react";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "signup">("login");

  return (
    <main className="mx-auto max-w-md px-6 py-16">
      <h1 className="text-center text-3xl font-bold text-brand-ink">
        {mode === "login" ? "Welcome Back" : "Create Account"}
      </h1>
      <p className="mt-2 text-center text-brand-muted">
        {mode === "login"
          ? "Sign in to your HealthFlow AI account."
          : "Get started with HealthFlow AI."}
      </p>

      <div className="mt-6 flex rounded-lg border border-brand-line bg-white p-1">
        {(["login", "signup"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-bold transition ${
              mode === m
                ? "bg-brand-yellow text-brand-ink"
                : "text-brand-brown"
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
              Full Name
            </label>
            <input
              type="text"
              className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
              placeholder="Jane Doe"
            />
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
      </form>
    </main>
  );
}