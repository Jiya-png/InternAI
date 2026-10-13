import { useEffect, useState } from "react";

export function scoreColor(v) {
  if (v >= 75) return { stroke: "#10b981", text: "text-emerald-600 dark:text-emerald-400", label: "Strong match" };
  if (v >= 50) return { stroke: "#f59e0b", text: "text-amber-600 dark:text-amber-400", label: "Good match" };
  if (v >= 30) return { stroke: "#f97316", text: "text-orange-600 dark:text-orange-400", label: "Partial match" };
  return { stroke: "#f43f5e", text: "text-rose-600 dark:text-rose-400", label: "Low match" };
}

/** Animated circular percentage gauge (SVG). */
export default function CircularGauge({ value = 0, size = 96, stroke = 9, label, sublabel }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setShown(Math.max(0, Math.min(100, value))), 60);
    return () => clearTimeout(t);
  }, [value]);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = scoreColor(value);
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-slate-200 dark:stroke-slate-800" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color.stroke}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - shown / 100)}
          style={{ transition: "stroke-dashoffset 0.9s cubic-bezier(.2,.8,.2,1)" }}
        />
      </svg>
      <div className="absolute text-center leading-none">
        <div className={`font-extrabold ${color.text}`} style={{ fontSize: size * 0.24 }}>
          {Math.round(value)}
          <span style={{ fontSize: size * 0.13 }}>%</span>
        </div>
        {label && <div className="mt-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</div>}
        {sublabel && <div className="text-[10px] text-slate-400">{sublabel}</div>}
      </div>
    </div>
  );
}
