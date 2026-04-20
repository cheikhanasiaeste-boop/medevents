import { notFound } from "next/navigation";
import { getSource } from "@/lib/db/sources";

export default async function SourceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const s = await getSource(id);
  if (!s) notFound();

  return (
    <div>
      <h1 className="text-2xl font-semibold">{s.name}</h1>
      <p className="font-mono text-sm text-slate-600">{s.code}</p>

      <dl className="mt-6 grid grid-cols-2 gap-3 rounded border border-slate-200 bg-white px-4 py-3 text-sm">
        <Field
          label="Homepage"
          value={
            <a href={s.homepage_url} className="text-blue-600 underline">
              {s.homepage_url}
            </a>
          }
        />
        <Field label="Type" value={s.source_type} />
        <Field label="Country" value={s.country_iso ?? "—"} />
        <Field label="Frequency" value={s.crawl_frequency} />
        <Field label="Parser" value={s.parser_name ?? "—"} />
        <Field label="Active" value={s.is_active ? "Yes" : "No"} />
        <Field
          label="Last crawled"
          value={
            s.last_crawled_at
              ? new Date(s.last_crawled_at).toLocaleString()
              : "—"
          }
        />
        <Field
          label="Last success"
          value={
            s.last_success_at
              ? new Date(s.last_success_at).toLocaleString()
              : "—"
          }
        />
        <Field
          label="Last error"
          value={
            s.last_error_at ? new Date(s.last_error_at).toLocaleString() : "—"
          }
        />
      </dl>

      {s.last_error_message && (
        <div className="mt-4 rounded bg-red-50 px-4 py-3 text-sm text-red-700">
          <strong>Last error:</strong> {s.last_error_message}
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <form method="POST" action={`/admin/sources/${s.id}/run`}>
          <button
            className="rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
            type="submit"
          >
            Run now (sync, ≤60s)
          </button>
        </form>
        <form method="POST" action={`/admin/sources/${s.id}/toggle-active`}>
          <button
            className="rounded border border-slate-300 px-4 py-2 hover:bg-slate-100"
            type="submit"
          >
            {s.is_active ? "Pause" : "Resume"}
          </button>
        </form>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}
