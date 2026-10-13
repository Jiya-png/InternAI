import { BookOpen, ExternalLink, Clock, PlayCircle, GraduationCap, Dumbbell, FileText } from "lucide-react";

const TYPE_ICON = { video: PlayCircle, course: GraduationCap, practice: Dumbbell, tutorial: FileText };
const DIFF = {
  Beginner: "chip-green",
  Intermediate: "chip-amber",
  Advanced: "chip-red",
};

export default function CoursesList({ role }) {
  const required = new Set(role.missing_required.map((m) => m.skill));
  const weight = Object.fromEntries(role.missing_required.map((m) => [m.skill, m.weight]));
  return (
    <div className="card card-pad">
      <div className="flex items-center gap-2">
        <BookOpen className="text-brand-600 dark:text-brand-400" size={20} />
        <h3 className="section-title">Skill gap & recommended courses</h3>
      </div>
      <p className="mt-1 text-sm muted">Ordered by how important each missing skill is for {role.title}. Links open a search on that platform.</p>
      {role.courses.length === 0 && <p className="mt-4 text-sm text-emerald-600">No gaps for this role - great job!</p>}
      <div className="mt-4 space-y-4">
        {role.courses.map((c, idx) => (
          <div key={c.skill} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-slate-900 text-xs font-bold text-white dark:bg-white dark:text-slate-900">{idx + 1}</span>
              <h4 className="font-semibold">{c.skill}</h4>
              <span className={required.has(c.skill) ? "chip-red" : "chip-amber"}>
                {required.has(c.skill) ? `Required · importance ${weight[c.skill]}/5` : "Nice to have"}
              </span>
              <span className="chip-neutral">{c.category}</span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {c.resources.map((r) => {
                const Icon = TYPE_ICON[r.type] || BookOpen;
                return (
                  <a
                    key={r.url}
                    href={r.url}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex flex-col gap-1.5 rounded-lg bg-slate-50 p-3 text-sm transition hover:bg-brand-50 dark:bg-slate-800/60 dark:hover:bg-brand-500/10"
                  >
                    <span className="flex items-center justify-between font-semibold">
                      <span className="flex items-center gap-1.5"><Icon size={15} /> {r.platform}</span>
                      <ExternalLink size={13} className="opacity-50 group-hover:opacity-100" />
                    </span>
                    <span className="text-xs muted line-clamp-2">{r.title}</span>
                    <span className="flex flex-wrap items-center gap-1.5 text-[11px]">
                      <span className="flex items-center gap-1 muted"><Clock size={11} /> {r.duration}</span>
                      <span className={`${DIFF[r.difficulty] || "chip-neutral"} !px-1.5 !py-0 !text-[10px]`}>{r.difficulty}</span>
                    </span>
                    <span className="text-[10px] muted">{r.cost}</span>
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
