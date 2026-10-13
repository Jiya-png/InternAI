import { useEffect, useMemo, useRef, useState } from "react";
import { FlaskConical, Plus, Search, Loader2 } from "lucide-react";
import { friendlyError, searchSkills, whatIf } from "../api.js";

/** What-if simulator: toggle skills you plan to learn and watch the match % update. */
export default function WhatIf({ analysisId, role }) {
  const [selected, setSelected] = useState([]);
  const [custom, setCustom] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const reqId = useRef(0);

  useEffect(() => {
    setSelected([]);
    setCustom([]);
    setResult(null);
  }, [role.role_id]);

  const options = useMemo(() => {
    const req = role.missing_required.map((m) => ({ skill: m.skill, gain: m.gain, kind: "required" }));
    const nice = role.missing_nice.slice(0, 8).map((m) => ({ skill: m.skill, gain: m.gain, kind: "nice" }));
    const extra = custom.filter((c) => ![...req, ...nice].some((o) => o.skill === c)).map((c) => ({ skill: c, gain: null, kind: "custom" }));
    return [...req, ...nice, ...extra];
  }, [role, custom]);

  // debounced API call whenever the selection changes
  useEffect(() => {
    if (!selected.length) {
      setResult(null);
      return;
    }
    const id = ++reqId.current;
    setLoading(true);
    setError("");
    const t = setTimeout(() => {
      whatIf(analysisId, role.role_id, selected)
        .then((r) => id === reqId.current && setResult(r))
        .catch((e) => id === reqId.current && setError(friendlyError(e)))
        .finally(() => id === reqId.current && setLoading(false));
    }, 250);
    return () => clearTimeout(t);
  }, [selected, analysisId, role.role_id]);

  // skill search for custom additions
  useEffect(() => {
    if (query.trim().length < 2) return setSuggestions([]);
    const t = setTimeout(() => searchSkills(query).then(setSuggestions).catch(() => setSuggestions([])), 200);
    return () => clearTimeout(t);
  }, [query]);

  const toggle = (s) => setSelected((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));
  const addCustom = (name) => {
    if (!custom.includes(name)) setCustom((c) => [...c, name]);
    if (!selected.includes(name)) setSelected((c) => [...c, name]);
    setQuery("");
    setSuggestions([]);
  };

  const base = role.match;
  const next = result ? Math.round(result.new_match) : base;
  const delta = next - base;

  return (
    <div className="card card-pad">
      <div className="flex items-center gap-2">
        <FlaskConical className="text-brand-600 dark:text-brand-400" size={20} />
        <h3 className="section-title">What-if simulator</h3>
      </div>
      <p className="mt-1 text-sm muted">
        Select the skills you plan to learn for <b className="text-slate-800 dark:text-slate-200">{role.title}</b> and see how your match changes.
      </p>

      <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-800/50">
        <div className="flex items-end justify-between">
          <div>
            <p className="text-xs muted">Current → with selected skills</p>
            <p className="text-3xl font-extrabold">
              {base}% <span className="text-slate-400">→</span>{" "}
              <span className="text-brand-600 dark:text-brand-400">{next}%</span>
            </p>
          </div>
          <div className={`text-right text-2xl font-extrabold ${delta > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-400"}`}>
            {loading ? <Loader2 className="animate-spin" /> : `${delta > 0 ? "+" : ""}${delta}%`}
          </div>
        </div>
        <div className="relative mt-3 h-4 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-brand-500 to-violet-500 transition-all duration-700 ease-out" style={{ width: `${next}%` }} />
          <div className="absolute inset-y-0 left-0 rounded-full bg-slate-400/70 dark:bg-slate-500" style={{ width: `${base}%` }} />
        </div>
        {result?.per_skill?.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {result.per_skill.map((p) => (
              <li key={p.skill}>
                Learning <b>{p.skill}</b>: <span className="font-semibold text-emerald-600 dark:text-emerald-400">+{p.delta}%</span>
              </li>
            ))}
          </ul>
        )}
        {result?.unknown_skills?.length > 0 && (
          <p className="mt-2 text-xs text-amber-600">Not in our skills list: {result.unknown_skills.join(", ")}</p>
        )}
        {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {options.map((o) => {
          const on = selected.includes(o.skill);
          return (
            <button
              key={o.skill}
              onClick={() => toggle(o.skill)}
              aria-pressed={on}
              className={`chip !px-3 !py-1.5 ring-1 transition ${
                on
                  ? "bg-brand-600 text-white ring-brand-600"
                  : o.kind === "required"
                  ? "bg-rose-50 text-rose-700 ring-rose-200 hover:bg-rose-100 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-500/30"
                  : "bg-white text-slate-700 ring-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700"
              }`}
            >
              {on ? "✓ " : "+ "}
              {o.skill}
              {o.gain > 0 && <span className={`ml-1 text-[10px] ${on ? "text-white/80" : "opacity-70"}`}>+{o.gain}%</span>}
            </button>
          );
        })}
        {!options.length && <p className="text-sm muted">No missing skills for this role - try adding any skill below.</p>}
      </div>

      <div className="relative mt-4">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 dark:border-slate-700">
          <Search size={16} className="text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Add any other skill (e.g. Docker, Figma, AWS)..."
            className="w-full bg-transparent py-2.5 text-sm outline-none"
            aria-label="Search skills"
          />
        </div>
        {suggestions.length > 0 && (
          <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
            {suggestions.map((s) => (
              <li key={s.name}>
                <button onClick={() => addCustom(s.name)} className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800">
                  <span className="flex items-center gap-2"><Plus size={14} /> {s.name}</span>
                  <span className="text-xs muted">{s.category}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
