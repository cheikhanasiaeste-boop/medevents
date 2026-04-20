import Link from "next/link";
import { listSources } from "@/lib/db/sources";

export default async function SourcesListPage() {
  const sources = await listSources();
  return (
    <div>
      <h1 className="text-2xl font-semibold">Sources</h1>
      <table className="mt-6 w-full divide-y divide-slate-200 rounded border border-slate-200 bg-white text-sm">
        <thead className="bg-slate-50 text-left">
          <tr>
            <th className="px-3 py-2">Code</th>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Frequency</th>
            <th className="px-3 py-2">Last crawled</th>
            <th className="px-3 py-2">Active</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {sources.map((s) => (
            <tr key={s.id}>
              <td className="px-3 py-2 font-mono">{s.code}</td>
              <td className="px-3 py-2">{s.name}</td>
              <td className="px-3 py-2">{s.source_type}</td>
              <td className="px-3 py-2">{s.crawl_frequency}</td>
              <td className="px-3 py-2 text-slate-600">
                {s.last_crawled_at
                  ? new Date(s.last_crawled_at).toLocaleString()
                  : "—"}
              </td>
              <td className="px-3 py-2">{s.is_active ? "✅" : "⏸"}</td>
              <td className="px-3 py-2 text-right">
                <Link
                  className="text-blue-600 hover:underline"
                  href={`/admin/sources/${s.id}`}
                >
                  Open
                </Link>
              </td>
            </tr>
          ))}
          {sources.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                No sources yet. Run{" "}
                <code>
                  make ingest CMD=&quot;seed-sources --path
                  ../../config/sources.yaml&quot;
                </code>
                .
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
