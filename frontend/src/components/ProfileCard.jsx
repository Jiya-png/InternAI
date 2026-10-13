import { Briefcase, GraduationCap, Mail, Phone, Linkedin, Github, Award } from "lucide-react";

export default function ProfileCard({ profile }) {
  const skillsByCat = {};
  (profile.skill_details || []).forEach((s) => {
    (skillsByCat[s.category_label] ||= []).push(s);
  });
  return (
    <div className="card card-pad space-y-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-brand-600 dark:text-brand-400">Parsed profile</p>
        <h2 className="mt-1 text-xl font-bold">{profile.name || "Name not detected"}</h2>
        <div className="mt-2 space-y-1 text-sm muted">
          {profile.email && <p className="flex items-center gap-2 break-all"><Mail size={14} /> {profile.email}</p>}
          {profile.phone && <p className="flex items-center gap-2"><Phone size={14} /> {profile.phone}</p>}
          {profile.links?.linkedin && <p className="flex items-center gap-2 break-all"><Linkedin size={14} /> {profile.links.linkedin}</p>}
          {profile.links?.github && <p className="flex items-center gap-2 break-all"><Github size={14} /> {profile.links.github}</p>}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="chip-neutral">{profile.years_of_experience} yrs experience</span>
          <span className="chip-neutral">{profile.skills.length} skills</span>
          <span className="chip-neutral">{profile.word_count} words</span>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">Skills</h3>
        <div className="space-y-3">
          {Object.entries(skillsByCat).map(([cat, list]) => (
            <div key={cat}>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide muted">{cat}</p>
              <div className="flex flex-wrap gap-1.5">
                {list.map((s) => (
                  <span
                    key={s.name}
                    className={s.sections.includes("implied") ? "chip-neutral opacity-70" : "chip bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300"}
                    title={s.sections.includes("implied") ? "Implied by another skill you listed" : `Found in: ${s.sections.join(", ")}`}
                  >
                    {s.name}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {!profile.skills.length && <p className="text-sm muted">No skills detected - try adding a Skills section.</p>}
        </div>
      </div>

      {profile.education?.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><GraduationCap size={16} /> Education</h3>
          <ul className="space-y-2 text-sm">
            {profile.education.map((e, i) => (
              <li key={i}>
                <p className="font-medium">{e.degree || "Degree"}</p>
                <p className="muted">{[e.institution, e.year, e.score].filter(Boolean).join(" · ")}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {profile.experience?.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Briefcase size={16} /> Experience</h3>
          <ul className="space-y-2 text-sm">
            {profile.experience.map((e, i) => (
              <li key={i}>
                <p className="font-medium">
                  {e.title || "Role"} {e.is_internship && <span className="chip-amber ml-1 !py-0">Internship</span>}
                </p>
                <p className="muted">
                  {[e.company, e.duration_months ? `${e.duration_months} months` : null].filter(Boolean).join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {profile.projects?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Projects</h3>
          <ul className="list-inside list-disc space-y-1 text-sm">
            {profile.projects.map((p, i) => (
              <li key={i}>{p.title}</li>
            ))}
          </ul>
        </div>
      )}

      {profile.certifications?.length > 0 && (
        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold"><Award size={16} /> Certifications</h3>
          <ul className="space-y-1 text-sm muted">
            {profile.certifications.slice(0, 6).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
