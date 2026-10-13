import { useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";

const MAX_MB = 5;
const ACCEPT = [".pdf", ".docx"];

/**
 * Drag & drop resume picker with client-side validation.
 * Props: onSubmit(file), busy, progress (0-100), stage ("uploading" | "analysing")
 */
export default function Dropzone({ onSubmit, busy, progress, stage }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState("");

  const pick = (f) => {
    setError("");
    if (!f) return;
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ACCEPT.includes(ext)) return setError("Please choose a PDF or DOCX file.");
    if (f.size > MAX_MB * 1024 * 1024) return setError(`That file is over ${MAX_MB} MB. Please upload a smaller file.`);
    if (f.size === 0) return setError("That file is empty.");
    setFile(f);
  };

  return (
    <div className="card card-pad">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload resume"
        onClick={() => !busy && inputRef.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !busy && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) pick(e.dataTransfer.files?.[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition
          ${drag ? "border-brand-500 bg-brand-50 dark:bg-brand-500/10" : "border-slate-300 hover:border-brand-400 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800/50"}
          ${busy ? "pointer-events-none opacity-70" : ""}`}
      >
        <div className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
          <UploadCloud size={28} />
        </div>
        <p className="mt-4 font-semibold">
          Drag & drop your resume here, or <span className="text-brand-600 dark:text-brand-400">browse</span>
        </p>
        <p className="mt-1 text-xs muted">PDF or DOCX · max {MAX_MB} MB · deleted right after parsing</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0])}
        />
      </div>

      {error && <p className="mt-3 text-sm font-medium text-rose-600 dark:text-rose-400">{error}</p>}

      {file && (
        <div className="mt-4 flex items-center gap-3 rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
          <FileText className="text-brand-600 dark:text-brand-400" size={22} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{file.name}</p>
            <p className="text-xs muted">{(file.size / 1024).toFixed(0)} KB</p>
          </div>
          {!busy && (
            <button onClick={() => setFile(null)} className="rounded-lg p-1 text-slate-400 hover:text-slate-700" aria-label="Remove file">
              <X size={16} />
            </button>
          )}
        </div>
      )}

      {busy && (
        <div className="mt-4" aria-live="polite">
          <div className="mb-1 flex justify-between text-xs font-medium">
            <span>{stage === "uploading" ? "Uploading..." : "Analysing your resume with AI..."}</span>
            {stage === "uploading" && <span>{progress}%</span>}
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            {stage === "uploading" ? (
              <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
            ) : (
              <div className="h-full w-2/5 animate-indeterminate rounded-full bg-gradient-to-r from-brand-500 to-violet-500" />
            )}
          </div>
        </div>
      )}

      <button className="btn-primary mt-4 w-full !py-3" disabled={!file || busy} onClick={() => onSubmit(file)}>
        {busy ? "Working..." : "Analyse my resume"}
      </button>
    </div>
  );
}
