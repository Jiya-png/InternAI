import { useState } from "react";
import { HelpCircle } from "lucide-react";

/** Accessible tooltip: opens on hover, focus or tap. */
export default function InfoTooltip({ label = "How was this calculated?", children, align = "left" }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        aria-expanded={open}
      >
        <HelpCircle size={14} /> {label}
      </button>
      {open && (
        <span
          role="tooltip"
          className={`absolute top-6 z-40 w-80 max-w-[85vw] rounded-xl border border-slate-200 bg-white p-4 text-left text-xs leading-relaxed text-slate-700 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 ${align === "right" ? "right-0" : "left-0"}`}
        >
          {children}
        </span>
      )}
    </span>
  );
}
