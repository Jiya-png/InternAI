import { AlertTriangle } from "lucide-react";

export default function ErrorBox({ message, onRetry }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200">
      <AlertTriangle className="mt-0.5 shrink-0" size={18} />
      <div className="flex-1">
        <p className="font-semibold">Something went wrong</p>
        <p className="mt-0.5">{message}</p>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="btn-ghost !py-1 text-xs">
          Try again
        </button>
      )}
    </div>
  );
}
