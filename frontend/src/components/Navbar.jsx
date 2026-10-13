import { Link } from "react-router-dom";
import { Moon, Sun, Sparkles } from "lucide-react";
import useTheme from "../hooks/useTheme.js";

export default function Navbar() {
  const [theme, toggle] = useTheme();
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2 font-extrabold tracking-tight">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-500 text-white shadow">
            <Sparkles size={18} />
          </span>
          <span className="text-lg">
            Intern<span className="text-brand-600 dark:text-brand-400">AI</span>
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <a href="/#how" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white sm:block">
            How it works
          </a>
          <a href="/docs" target="_blank" rel="noreferrer" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white sm:block">
            API
          </a>
          <button onClick={toggle} className="btn-ghost h-10 w-10 !p-0" aria-label="Toggle dark mode" title="Toggle dark mode">
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </div>
      </nav>
    </header>
  );
}
