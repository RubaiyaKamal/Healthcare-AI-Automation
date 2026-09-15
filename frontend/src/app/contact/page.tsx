"use client";

export default function ContactPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Contact Us</h1>
      <p className="mt-2 text-brand-muted">
        Questions about HealthFlow AI? Reach out — we would love to hear from you.
      </p>

      <form
        className="mt-10 space-y-4 rounded-xl border border-brand-line bg-white p-6 shadow-sm"
        onSubmit={(e) => e.preventDefault()}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-brand-brownDark">
            Name
          </label>
          <input
            type="text"
            className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            placeholder="Your name"
          />
        </div>

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
            Message
          </label>
          <textarea
            rows={4}
            className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
            placeholder="How can we help?"
          />
        </div>

        <button
          type="submit"
          className="rounded-lg bg-brand-yellow px-4 py-2 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight"
        >
          Send Message
        </button>
      </form>

      <div className="mt-8 rounded-xl border border-brand-line bg-white p-6 text-sm text-brand-muted shadow-sm">
        <p>
          <strong className="text-brand-brownDark">Email:</strong>{" "}
          hello@healthflow.ai
        </p>
        <p className="mt-2">
          <strong className="text-brand-brownDark">Phone:</strong> +1 (555) 010-2030
        </p>
      </div>
    </main>
  );
}