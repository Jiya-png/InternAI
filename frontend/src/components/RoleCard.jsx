import CircularGauge, { scoreColor } from "./CircularGauge.jsx";

export default function RoleCard({ role, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`card group flex w-full flex-col items-center gap-2 p-4 text-center transition hover:-translate-y-0.5 hover:shadow-md
        ${active ? "!border-brand-500 ring-2 ring-brand-500/30" : ""}`}
      aria-pressed={active}
    >
      <span className="self-start text-[11px] font-bold text-slate-400">#{role.rank}</span>
      <CircularGauge value={role.match} size={88} />
      <p className="text-sm font-semibold leading-tight">{role.title}</p>
      <p className={`text-[11px] font-medium ${scoreColor(role.match).text}`}>{scoreColor(role.match).label}</p>
      <span className="chip-neutral !text-[10px] capitalize">{role.experience_level} · {role.domain}</span>
    </button>
  );
}
