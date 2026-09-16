const styles: Record<string, string> = {
  Live: "bg-brand-yellowSoft text-brand-brownDark border-brand-line",
  Demo: "bg-brand-yellow text-brand-ink border-brand-yellow",
  "In Progress": "bg-brand-yellow/30 text-brand-brownDark border-brand-line",
  Roadmap: "bg-brand-cream text-brand-muted border-brand-line",
};

const dots: Record<string, string> = {
  Live: "bg-brand-brownDark",
  Demo: "bg-brand-ink",
  "In Progress": "bg-brand-yellow",
  Roadmap: "bg-brand-brownLight",
};

export default function StatusBadge({ status }: { status: string }) {
  const dot = dots[status] ?? dots.Roadmap;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide ${
        styles[status] ?? styles.Roadmap
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}