import { useState } from "react";
import { ClipboardCheck, Copy, Check, Lightbulb, PenLine } from "lucide-react";
import CircularGauge from "./CircularGauge.jsx";

export default function QualityPanel({ quality }) {
  const [copied, setCopied] = useState(-1);
  const copy = (text, i) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(i);
      setTimeout(() => setCopied(-1), 1500);
    });
  };
  return (
    <div className="card card-pad">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="text-brand-600 dark:text-brand-400" size={20} />
        <h3 className="section-title">Resume quality score</h3>
      </div>
      <div className="mt-4 grid gap-6 md:grid-cols-[auto_1fr]">
        <div className="flex flex-col items-center gap-2">
          <CircularGauge value={quality.score} size={130} stroke={12} label="/ 100" />
          <span className="chip-neutral font-semibold">{quality.label}</span>
        </div>
        <div className="space-y-2.5">
          {quality.breakdown.map((b) => (
            <div key={b.name}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="muted">{b.name}</span>
                <span className="font-semibold">{b.score}/{b.max}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-800">
                <div className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500 transition-all duration-700" style={{ width: `${(b.score / b.max) * 100}%` }} />
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2 pt-1 text-[11px]">
            <span className="chip-neutral">{quality.stats.bullets} bullets</span>
            <span className="chip-neutral">{quality.stats.quantified_pct}% quantified</span>
            <span className="chip-neutral">{quality.stats.action_verb_pct}% action verbs</span>
            <span className="chip-neutral">{quality.stats.word_count} words</span>
          </div>
        </div>
      </div>

      {quality.tips.length > 0 && (
        <div className="mt-6">
          <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Lightbulb size={16} className="text-amber-500" /> Improvement tips</h4>
          <ul className="space-y-2">
            {quality.tips.map((t, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" /> {t}
              </li>
            ))}
          </ul>
        </div>
      )}

      {quality.weak_bullets.length > 0 && (
        <div className="mt-6">
          <h4 className="mb-1 flex items-center gap-2 text-sm font-semibold"><PenLine size={16} /> Bullets to strengthen</h4>
          <p className="mb-3 text-xs muted">Template: <b>Action verb + task + tool + measurable result</b>. Replace the [brackets] with your real numbers.</p>
          <div className="space-y-3">
            {quality.weak_bullets.map((w, i) => (
              <div key={i} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800">
                <p className="text-rose-700 line-through decoration-rose-300 dark:text-rose-300">{w.original}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {w.issues.map((iss) => (
                    <span key={iss} className="chip-neutral !text-[10px]">{iss}</span>
                  ))}
                </div>
                <div className="mt-2 flex items-start gap-2 rounded-lg bg-emerald-50 p-2 text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-200">
                  <p className="flex-1">{w.suggestion}</p>
                  <button onClick={() => copy(w.suggestion, i)} className="no-pdf rounded p-1 hover:bg-emerald-100 dark:hover:bg-emerald-500/20" aria-label="Copy suggestion">
                    {copied === i ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
