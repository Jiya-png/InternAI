export function Bone({ className = "" }) {
  return <div className={`animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800 ${className}`} />;
}

export default function ResultsSkeleton() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6" aria-busy="true" aria-label="Loading results">
      <Bone className="h-8 w-64" />
      <Bone className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-8 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="card card-pad space-y-3">
          <Bone className="h-6 w-40" />
          <Bone className="h-4 w-56" />
          <div className="flex flex-wrap gap-2 pt-2">
            {Array.from({ length: 12 }).map((_, i) => (
              <Bone key={i} className="h-6 w-16 rounded-full" />
            ))}
          </div>
          <Bone className="h-24 w-full" />
        </div>
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="card card-pad flex flex-col items-center gap-3">
                <Bone className="h-20 w-20 rounded-full" />
                <Bone className="h-4 w-24" />
              </div>
            ))}
          </div>
          <div className="card card-pad space-y-3">
            <Bone className="h-6 w-48" />
            <Bone className="h-64 w-full" />
          </div>
        </div>
      </div>
    </div>
  );
}
