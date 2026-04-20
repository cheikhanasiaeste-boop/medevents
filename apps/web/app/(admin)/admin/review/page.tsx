import Link from "next/link";
import { listOpenReviews } from "@/lib/db/reviews";

const KINDS = [
  "duplicate_candidate",
  "parser_failure",
  "suspicious_data",
  "source_blocked",
];

export default async function ReviewListPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string }>;
}) {
  const { kind } = await searchParams;
  const items = await listOpenReviews(kind);
  return (
    <div>
      <h1 className="text-2xl font-semibold">Review queue</h1>

      <nav className="mt-4 flex gap-2 text-sm">
        <Link
          className={`rounded px-3 py-1 ${!kind ? "bg-slate-900 text-white" : "bg-white border border-slate-300"}`}
          href="/admin/review"
        >
          All
        </Link>
        {KINDS.map((k) => (
          <Link
            key={k}
            className={`rounded px-3 py-1 ${kind === k ? "bg-slate-900 text-white" : "bg-white border border-slate-300"}`}
            href={`/admin/review?kind=${k}`}
          >
            {k}
          </Link>
        ))}
      </nav>

      <ul className="mt-6 divide-y divide-slate-200 rounded border border-slate-200 bg-white">
        {items.length === 0 && (
          <li className="px-4 py-6 text-center text-sm text-slate-500">
            No open items{kind ? ` for ${kind}` : ""}.
          </li>
        )}
        {items.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between px-4 py-3 text-sm"
          >
            <span>
              <span className="font-mono text-slate-600">{r.kind}</span>
              {r.event_id && (
                <>
                  {" "}
                  · event{" "}
                  <span className="font-mono">{r.event_id.slice(0, 8)}</span>
                </>
              )}
              {r.source_id && (
                <>
                  {" "}
                  · source{" "}
                  <span className="font-mono">{r.source_id.slice(0, 8)}</span>
                </>
              )}
            </span>
            <Link
              className="text-blue-600 hover:underline"
              href={`/admin/review/${r.id}`}
            >
              Open
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
