import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileSearch, Target, GraduationCap, FlaskConical, ClipboardCheck, Map, ShieldCheck, Cpu } from "lucide-react";
import Dropzone from "../components/Dropzone.jsx";
import ErrorBox from "../components/ErrorBox.jsx";
import Disclaimer from "../components/Disclaimer.jsx";
import { friendlyError, uploadResume } from "../api.js";

const STEPS = [
  { icon: FileSearch, title: "Upload", text: "Drop your PDF or DOCX resume. It is parsed and then deleted." },
  { icon: Cpu, title: "Parse & understand", text: "NLP extracts skills, education, experience and projects - even from bullet points." },
  { icon: Target, title: "Match", text: "ML models score you against 30 roles and explain every match." },
  { icon: Map, title: "Grow", text: "Get courses, a what-if simulator and a 4-week roadmap to close the gap." },
];

const FEATURES = [
  { icon: Target, title: "Top 5 role matches", text: "Match % for internships and entry roles across tech, data, design, marketing, finance and HR." },
  { icon: FileSearch, title: "Explained, not a black box", text: "See matched vs missing skills with importance weights and a skills radar." },
  { icon: GraduationCap, title: "Courses for every gap", text: "YouTube, Coursera, NPTEL, Kaggle and more - with duration and difficulty." },
  { icon: FlaskConical, title: "What-if simulator", text: "Pick skills you plan to learn and watch your match % update instantly." },
  { icon: ClipboardCheck, title: "Resume quality score", text: "A 0-100 score with concrete tips and rewritten bullet points." },
  { icon: Map, title: "4-week roadmap", text: "Weekly goals and a mini project for your chosen target role." },
];

export default function Landing() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("uploading");
  const [error, setError] = useState("");

  const submit = async (file) => {
    setBusy(true);
    setError("");
    setProgress(0);
    setStage("uploading");
    try {
      const res = await uploadResume(file, (p) => {
        setProgress(p);
        if (p >= 100) setStage("analysing");
      });
      navigate(`/results/${res.analysis_id}`);
    } catch (e) {
      setError(friendlyError(e));
      setBusy(false);
    }
  };

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 left-1/2 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-gradient-to-r from-brand-300/40 via-violet-300/30 to-sky-300/30 blur-3xl dark:from-brand-700/30 dark:via-violet-700/20 dark:to-sky-700/20" />
        <div className="relative mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-2 lg:py-20">
          <div className="animate-fade-up">
            <span className="chip bg-brand-100 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
              <ShieldCheck size={14} /> Free · runs locally · no paid AI APIs
            </span>
            <h1 className="mt-4 text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
              Find the internships your resume is{" "}
              <span className="bg-gradient-to-r from-brand-600 to-violet-500 bg-clip-text text-transparent">ready for</span>
            </h1>
            <p className="mt-4 max-w-xl text-lg muted">
              InternAI reads your resume, recommends your top 5 roles with a match score, explains exactly which skills you
              are missing, and builds a personalised plan to close the gap.
            </p>
            <ul className="mt-6 grid max-w-xl gap-2 text-sm sm:grid-cols-2">
              {["Match % for 30 roles", "Matched vs missing skills", "Courses for each gap", "4-week roadmap"].map((t) => (
                <li key={t} className="flex items-center gap-2">
                  <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300">✓</span>
                  {t}
                </li>
              ))}
            </ul>
          </div>
          <div className="animate-fade-up space-y-3" style={{ animationDelay: "120ms" }} id="upload">
            <Dropzone onSubmit={submit} busy={busy} progress={progress} stage={stage} />
            <ErrorBox message={error} />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
        <h2 className="text-center text-3xl font-extrabold tracking-tight">How it works</h2>
        <p className="mx-auto mt-2 max-w-2xl text-center muted">From resume to plan in about 5 seconds.</p>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <div key={s.title} className="card card-pad relative">
              <span className="absolute right-4 top-4 text-4xl font-black text-slate-100 dark:text-slate-800">{i + 1}</span>
              <s.icon className="text-brand-600 dark:text-brand-400" />
              <h3 className="mt-3 font-bold">{s.title}</h3>
              <p className="mt-1 text-sm muted">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-7xl px-4 pb-14 sm:px-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="card card-pad">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/10 dark:text-brand-300">
                <f.icon size={20} />
              </div>
              <h3 className="mt-3 font-bold">{f.title}</h3>
              <p className="mt-1 text-sm muted">{f.text}</p>
            </div>
          ))}
        </div>
        <div className="mt-8">
          <Disclaimer />
        </div>
      </section>
    </div>
  );
}
