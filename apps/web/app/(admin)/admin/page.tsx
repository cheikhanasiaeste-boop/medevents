import { sql } from "@/lib/db/client";

async function getDashboardCounts() {
  const [sources, events, openReviews, recentAudits] = await Promise.all([
    sql<{ count: string }[]>`SELECT count(*) FROM sources`,
    sql<
      { count: string }[]
    >`SELECT count(*) FROM events WHERE is_published = true`,
    sql<
      { count: string }[]
    >`SELECT count(*) FROM review_items WHERE status = 'open'`,
    sql<{ actor: string; action: string; occurred_at: Date }[]>`
      SELECT actor, action, occurred_at FROM audit_log ORDER BY occurred_at DESC LIMIT 10
    `,
  ]);
  return {
    sourcesCount: Number(sources[0].count),
    publishedEventsCount: Number(events[0].count),
    openReviewsCount: Number(openReviews[0].count),
    recentAudits,
  };
}

export default async function DashboardPage() {
  const data = await getDashboardCounts();
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <div className="mt-6 grid grid-cols-3 gap-4">
        <Stat label="Sources" value={data.sourcesCount} />
        <Stat label="Published events" value={data.publishedEventsCount} />
        <Stat label="Open reviews" value={data.openReviewsCount} />
      </div>

      <h2 className="mt-10 text-lg font-semibold">Recent activity</h2>
      <ul className="mt-3 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
        {data.recentAudits.length === 0 && (
          <li className="px-4 py-3 text-sm text-slate-500">No activity yet.</li>
        )}
        {data.recentAudits.map((row, i) => (
          <li
            key={i}
            className="flex items-center justify-between px-4 py-3 text-sm"
          >
            <span>
              <span className="font-mono text-slate-600">{row.actor}</span>{" "}
              <span className="text-slate-900">{row.action}</span>
            </span>
            <span className="text-slate-500">
              {new Date(row.occurred_at).toLocaleString()}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-slate-200 bg-white px-4 py-3">
      <div className="text-sm text-slate-600">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
