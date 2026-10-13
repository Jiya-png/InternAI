import { useEffect, useState } from "react";
import { Map, Rocket, Clock, ExternalLink } from "lucide-react";
import { friendlyError, getRoadmap } from "../api.js";
import { Bone } from "./Skeleton.jsx";

export default function Roadmap({ analysisId, roles, defaultRole }) {
  const [role, setRole] = useState(defaultRole);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => setRole(defaultRole), [defaultRole]);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    getRoadmap(analysisId, role)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(friendlyError(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [analysisId, role]);

  return (
    <div className="card card-pad">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Map className="text-brand-600 dark:text-brand-400" size={20} />
          <h3 className="section-title">Your 4-week learning roadmap</h3>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="muted">Target role</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900"
          >
            {roles.map((r) => (
              <option key={r.role_id} value={r.role_id}>
                {r.title} ({r.match}%)
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      {loading && !data && <Bone className="mt-4 h-64 w-full" />}

      {data && (
        <div className={`transition-opacity ${loading ? "opacity-50" : ""}`}>
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-gradient-to-r from-brand-50 to-violet-50 p-4 text-sm dark:from-brand-500/10 dark:to-violet-500/10">
            <Rocket size={18} className="text-brand-600 dark:text-brand-400" />
            <span>
              {data.mode === "gap" ? "Focus skills" : "You already have all required skills - level up with"}:{" "}
              <b>{data.focus_skills.join(", ")}</b>
            </span>
            {data.projected_match != null && (
              <span className="ml-auto font-semibold">
                Match {data.current_match}% → <span className="text-emerald-600 dark:text-emerald-400">{data.projected_match}%</span>
              </span>
            )}
            <span className="chip-neutral"><Clock size={11} /> ~{data.total_hours} h total</span>
          </div>

          <ol className="relative mt-6 space-y-6 border-l-2 border-brand-200 pl-6 dark:border-brand-500/30">
            {data.weeks.map((w) => (
              <li key={w.week} className="relative">
                <span className="absolute -left-[35px] grid h-7 w-7 place-items-center rounded-full bg-brand-600 text-xs font-bold text-white ring-4 ring-white dark:ring-slate-900">
                  {w.week}
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className="font-semibold">{w.title}</h4>
                  <span className="chip-neutral"><Clock size={11} /> ~{w.estimated_hours} h</span>
                </div>
                <ul className="mt-2 list-inside list-disc space-y-1 text-sm muted">
                  {w.goals.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
                <div className="mt-3 rounded-xl border border-dashed border-brand-300 p-3 text-sm dark:border-brand-500/40">
                  <p className="font-semibold">🛠 Mini project: {w.mini_project.title}</p>
                  <p className="mt-0.5 muted">{w.mini_project.description}</p>
                </div>
                {w.resources.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {w.resources.map((r) => (
                      <a key={r.url} href={r.url} target="_blank" rel="noreferrer" className="chip-neutral hover:bg-brand-50 dark:hover:bg-brand-500/10">
                        {r.platform} · {r.duration} <ExternalLink size={10} />
                      </a>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
