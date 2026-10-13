import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, Legend, ResponsiveContainer, Tooltip } from "recharts";
import { CheckCircle2, XCircle } from "lucide-react";
import CircularGauge from "./CircularGauge.jsx";
import InfoTooltip from "./InfoTooltip.jsx";

const SHORT = {
  "Programming Languages": "Languages", "Machine Learning & AI": "ML & AI", "Web Development": "Web",
  "Mobile Development": "Mobile", "Data & Analytics": "Data", "Cloud & DevOps": "Cloud/DevOps",
  "Security & Networking": "Security", "IoT & Embedded": "IoT/Embedded", "Testing & QA": "Testing",
  "Tools & Productivity": "Tools", "CS Fundamentals": "CS Basics", "Design & Creative": "Design",
  "Marketing & Content": "Marketing", "Business, Finance & HR": "Business", "Blockchain, Games & XR": "Emerging",
  "Soft Skills": "Soft skills",
};

const SIGNALS = [
  ["weighted_overlap", "Required skills (weighted by importance)"],
  ["pct_required", "Share of required skills you have"],
  ["nice_ratio", "Nice-to-have skills"],
  ["semantic_similarity", "Resume ↔ job description similarity"],
  ["classifier_prob", "Role classifier confidence"],
  ["experience_fit", "Experience level fit"],
];

function Bar({ label, value }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="muted">{label}</span>
        <span className="font-semibold">{Math.round(value * 100)}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-200 dark:bg-slate-800">
        <div className="h-full rounded-full bg-brand-500 transition-all duration-700" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

export default function RoleDetail({ role, howCalculated }) {
  const weightDots = (w) => "●".repeat(w) + "○".repeat(5 - w);
  return (
    <div className="card card-pad animate-fade-up">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
        <CircularGauge value={role.match} size={120} stroke={11} label="match" />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-extrabold tracking-tight">{role.title}</h2>
            <span className="chip-neutral capitalize">{role.experience_level}</span>
            <span className="chip-neutral">{role.domain}</span>
          </div>
          <p className="mt-2 text-sm leading-relaxed muted">{role.description}</p>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">
              {role.matched_skills.length}/{role.required_total} required skills matched
            </span>
            <InfoTooltip>
              <p className="font-semibold text-slate-900 dark:text-white">How was this calculated?</p>
              <p className="mt-1">{howCalculated}</p>
              <p className="mt-2">
                The model was trained on 5,400 synthetic resumes, so treat the number as a helpful estimate, not a verdict.
              </p>
            </InfoTooltip>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-5">
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 size={16} /> Matched skills
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {role.matched_skills.map((s) => (
                <span key={s.skill} className="chip-green" title={`Importance ${s.weight}/5`}>
                  {s.skill} <span className="text-[9px] tracking-tighter opacity-70">{weightDots(s.weight)}</span>
                </span>
              ))}
              {role.matched_nice.map((s) => (
                <span key={s} className="chip-green opacity-80" title="Nice-to-have">{s} ★</span>
              ))}
              {!role.matched_skills.length && <p className="text-sm muted">None of the required skills yet.</p>}
            </div>
          </div>
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-rose-700 dark:text-rose-400">
              <XCircle size={16} /> Missing required skills <span className="font-normal muted">(most important first)</span>
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {role.missing_required.map((s) => (
                <span key={s.skill} className="chip-red" title={`Importance ${s.weight}/5 · demand ${Math.round(s.demand * 100)}%`}>
                  {s.skill} <span className="text-[9px] tracking-tighter opacity-70">{weightDots(s.weight)}</span>
                  {s.gain > 0 && <span className="font-bold">+{s.gain}%</span>}
                </span>
              ))}
              {!role.missing_required.length && <p className="text-sm text-emerald-600">You have every required skill 🎉</p>}
            </div>
          </div>
          {role.missing_nice.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold text-amber-700 dark:text-amber-400">Nice-to-have skills to add</h3>
              <div className="flex flex-wrap gap-1.5">
                {role.missing_nice.slice(0, 10).map((s) => (
                  <span key={s.skill} className="chip-amber">
                    {s.skill} {s.gain > 0 && <span className="font-bold">+{s.gain}%</span>}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-2.5 rounded-xl bg-slate-50 p-4 dark:bg-slate-800/50">
            <p className="text-xs font-semibold uppercase tracking-wide muted">Signals used by the model</p>
            {SIGNALS.map(([k, label]) => (
              <Bar key={k} label={label} value={role.breakdown[k] ?? 0} />
            ))}
          </div>
        </div>

        <div>
          <h3 className="mb-1 text-sm font-semibold">Skill categories: you vs role requirement</h3>
          <p className="mb-2 text-xs muted">100% = you cover everything this role asks for in that category.</p>
          <div className="h-80 w-full">
            <ResponsiveContainer>
              <RadarChart data={role.radar.map((d) => ({ ...d, category: SHORT[d.category] || d.category }))} outerRadius="68%">
                <PolarGrid className="stroke-slate-300 dark:stroke-slate-700" />
                <PolarAngleAxis dataKey="category" tick={{ fontSize: 11, fill: "currentColor" }} />
                <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="Role requirement" dataKey="role" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.15} />
                <Radar name="You" dataKey="you" stroke="#6366f1" fill="#6366f1" fillOpacity={0.45} isAnimationActive />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Tooltip formatter={(v) => `${v}%`} contentStyle={{ borderRadius: 12, fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
