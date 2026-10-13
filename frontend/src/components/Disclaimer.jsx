import { Info } from "lucide-react";

export default function Disclaimer({ text, compact = false }) {
  return (
    <div className={`flex gap-3 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200 ${compact ? "p-3 text-xs" : "p-4 text-sm"}`}>
      <Info className="mt-0.5 shrink-0" size={compact ? 14 : 18} />
      <p>
        {text ||
          "Match percentages are estimates from a model trained on synthetic (computer-generated) resumes and a hand-built skills catalog. Use them as guidance, not as a hiring decision."}
      </p>
    </div>
  );
}
