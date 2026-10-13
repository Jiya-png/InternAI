import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Download, RotateCcw, Trash2, Cpu } from "lucide-react";
import { deleteAnalysis, friendlyError, getAnalysis } from "../api.js";
import ResultsSkeleton from "../components/Skeleton.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import Disclaimer from "../components/Disclaimer.jsx";
import ProfileCard from "../components/ProfileCard.jsx";
import RoleCard from "../components/RoleCard.jsx";
import RoleDetail from "../components/RoleDetail.jsx";
import WhatIf from "../components/WhatIf.jsx";
import CoursesList from "../components/CoursesList.jsx";
import QualityPanel from "../components/QualityPanel.jsx";
import Roadmap from "../components/Roadmap.jsx";
import { scoreColor } from "../components/CircularGauge.jsx";
import { exportElementToPdf } from "../pdf.js";

export default function Results() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    setError("");
    setData(null);
    getAnalysis(id)
      .then((d) => {
        setData(d);
        setSelected(d.top_roles[0]?.role_id);
      })
      .catch((e) => setError(friendlyError(e)));
  }, [id]);

  useEffect(load, [load]);

  const downloadPdf = async () => {
    setExporting(true);
    const root = document.documentElement;
    const wasDark = root.classList.contains("dark");
    try {
      if (wasDark) root.classList.remove("dark"); // print in light theme
      await new Promise((r) => setTimeout(r, 300));
      const name = (data.profile.name || "resume").replace(/\s+/g, "_");
      await exportElementToPdf(document.getElementById("report"), `InternAI_report_${name}.pdf`);
    } catch (e) {
      setError("Could not create the PDF: " + (e?.message || e));
    } finally {
      if (wasDark) root.classList.add("dark");
      setExporting(false);
    }
  };

  const remove = async () => {
    if (!window.confirm("Delete this analysis from the server? This cannot be undone.")) return;
    try {
      await deleteAnalysis(id);
      navigate("/");
    } catch (e) {
      setError(friendlyError(e));
    }
  };

  if (error && !data)
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <ErrorBox message={error} onRetry={load} />
        <Link to="/" className="btn-ghost mt-4">Upload a resume</Link>
      </div>
    );
  if (!data) return <ResultsSkeleton />;

  const role = data.top_roles.find((r) => r.role_id === selected) || data.top_roles[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="no-pdf mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link to="/" className="btn-ghost"><RotateCcw size={16} /> Analyse another resume</Link>
        <div className="flex flex-wrap gap-2">
          <button onClick={remove} className="btn-ghost text-rose-600"><Trash2 size={16} /> Delete my data</button>
          <button onClick={downloadPdf} disabled={exporting} className="btn-primary">
            <Download size={16} /> {exporting ? "Preparing PDF..." : "Download report as PDF"}
          </button>
        </div>
      </div>

      <div id="report" className="space-y-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">
            Results for {data.profile.name || "your resume"}
          </h1>
          <p className="mt-1 text-sm muted">
            {data.filename} · analysed {new Date(data.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="flex-1"><Disclaimer text={data.disclaimer} compact /></div>
          <span className="chip-neutral self-start md:self-auto" title="Models in use">
            <Cpu size={12} /> {data.model_info.trained_models ? `${data.model_info.classifier} + ${data.model_info.regressor}` : "Heuristic scoring (models not trained)"} · {data.model_info.embedding_backend}
          </span>
        </div>

        <div className="grid gap-6 lg:grid-cols-[330px_1fr]">
          <aside className="lg:sticky lg:top-20 lg:self-start">
            <ProfileCard profile={data.profile} />
          </aside>

          <div className="min-w-0 space-y-6">
            <section>
              <h2 className="section-title mb-3">Your top 5 matches</h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                {data.top_roles.map((r) => (
                  <RoleCard key={r.role_id} role={r} active={r.role_id === role.role_id} onClick={() => setSelected(r.role_id)} />
                ))}
              </div>
              <details className="no-pdf mt-3 text-sm">
                <summary className="cursor-pointer font-medium text-brand-600 dark:text-brand-400">See all {data.all_roles.length} roles</summary>
                <div className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
                  {data.all_roles.map((r) => (
                    <div key={r.role_id} className="flex items-center gap-3">
                      <span className="w-48 truncate">{r.title}</span>
                      <div className="h-2 flex-1 rounded-full bg-slate-200 dark:bg-slate-800">
                        <div className="h-full rounded-full" style={{ width: `${r.match}%`, background: scoreColor(r.match).stroke }} />
                      </div>
                      <span className="w-10 text-right font-semibold">{r.match}%</span>
                    </div>
                  ))}
                </div>
              </details>
            </section>

            <RoleDetail role={role} howCalculated={data.how_calculated} />
            <div className="no-pdf"><WhatIf analysisId={id} role={role} /></div>
            <CoursesList role={role} />
            <Roadmap analysisId={id} roles={data.all_roles} defaultRole={role.role_id} />
            <QualityPanel quality={data.quality} />
          </div>
        </div>
      </div>
      {error && <div className="mt-4"><ErrorBox message={error} /></div>}
    </div>
  );
}
