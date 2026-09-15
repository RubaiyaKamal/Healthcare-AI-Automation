import Link from "next/link";

const links = [
  { href: "/", label: "Home" },
  { href: "/services", label: "Services" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
  { href: "/login", label: "Login/Signup" },
];

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-brand-line bg-brand-cream/90 backdrop-blur">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-6 py-3">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-yellow">
            <span className="text-sm">●</span>
          </span>
          <span className="text-lg font-extrabold tracking-tight text-brand-ink">
            HealthFlow AI
          </span>
        </Link>

        <ul className="flex items-center gap-1">
          {links.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                className="rounded-lg px-3 py-2 text-sm font-semibold text-brand-brown transition hover:bg-brand-yellow hover:text-brand-ink"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}