"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const mainLinks = [
  { href: "/", label: "Home" },
  { href: "/solutions", label: "Solutions" },
  { href: "/platform", label: "Platform" },
  { href: "/patients", label: "Patients" },
  { href: "/about", label: "About" },
  { href: "/security", label: "Security" },
  { href: "/contact", label: "Contact" },
];

const portals = [
  { href: "/login?portal=staff", label: "Staff Login", desc: "Front desk, clinicians, billers" },
  { href: "/login?portal=patient", label: "Patient Login", desc: "My Health portal" },
  { href: "/portal", label: "Portal Chatbot", desc: "Patient assistant demo (scoped)" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [portalOpen, setPortalOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-50 border-b border-brand-line bg-brand-cream/90 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-yellow">
            <span className="text-sm">●</span>
          </span>
          <span className="text-lg font-extrabold tracking-tight text-brand-ink">
            HealthFlow AI
          </span>
        </Link>

        {/* Desktop nav */}
        <ul className="hidden items-center gap-0.5 lg:flex">
          {mainLinks.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition hover:bg-brand-yellow hover:text-brand-ink ${
                  isActive(l.href) ? "text-brand-ink" : "text-brand-brown"
                }`}
              >
                {l.label}
              </Link>
            </li>
          ))}

          {/* Login portal dropdown */}
          <li
            className="relative"
            onMouseEnter={() => setPortalOpen(true)}
            onMouseLeave={() => setPortalOpen(false)}
          >
            <button
              onClick={() => setPortalOpen((v) => !v)}
              className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold transition hover:bg-brand-yellow hover:text-brand-ink ${
                pathname.startsWith("/login") ? "text-brand-ink" : "text-brand-brown"
              }`}
            >
              Login
              <span className="text-[10px]">▼</span>
            </button>
            {portalOpen && (
              <div className="absolute right-0 mt-1 w-56 rounded-xl border border-brand-line bg-white p-1 shadow-lg">
                {portals.map((p) => (
                  <Link
                    key={p.href}
                    href={p.href}
                    onClick={() => setPortalOpen(false)}
                    className="block rounded-lg px-3 py-2 transition hover:bg-brand-yellowSoft"
                  >
                    <span className="text-sm font-bold text-brand-ink">{p.label}</span>
                    <span className="block text-xs text-brand-muted">{p.desc}</span>
                  </Link>
                ))}
              </div>
            )}
          </li>
        </ul>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen((v) => !v)}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-brand-line text-brand-brown bg-white lg:hidden"
          aria-label="Toggle menu"
        >
          {mobileOpen ? "✕" : "☰"}
        </button>
      </nav>

      {/* Mobile nav */}
      {mobileOpen && (
        <div className="border-t border-brand-line bg-brand-cream px-4 py-3 lg:hidden">
          <ul className="flex flex-col gap-1">
            {mainLinks.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  onClick={() => setMobileOpen(false)}
                  className={`block rounded-lg px-3 py-2 text-sm font-semibold ${
                    isActive(l.href) ? "bg-brand-yellowSoft text-brand-ink" : "text-brand-brown"
                  }`}
                >
                  {l.label}
                </Link>
              </li>
            ))}
            <li className="mt-2 border-t border-brand-line pt-2">
              <p className="px-3 pb-1 text-xs font-bold uppercase tracking-wider text-brand-muted">
                Login
              </p>
              {portals.map((p) => (
                <Link
                  key={p.href}
                  href={p.href}
                  onClick={() => setMobileOpen(false)}
                  className="block rounded-lg px-3 py-2 text-sm font-semibold text-brand-brown hover:bg-brand-yellowSoft"
                >
                  {p.label}
                </Link>
              ))}
            </li>
          </ul>
        </div>
      )}
    </header>
  );
}