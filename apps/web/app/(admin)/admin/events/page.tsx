import Link from "next/link";
import { parseEventsFilter } from "@/lib/search/events";
import { searchEventsForAdmin } from "@/lib/db/events";

export default async function EventsListPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const filter = parseEventsFilter(sp);
  const { rows, total } = await searchEventsForAdmin(filter);
  const totalPages = Math.max(1, Math.ceil(total / filter.per_page));

  return (
    <div>
      <h1 className="text-2xl font-semibold">Events</h1>

      <form className="mt-4 flex flex-wrap items-end gap-3" method="GET">
        <label className="text-sm">
          Search title
          <input
            name="q"
            defaultValue={filter.q ?? ""}
            placeholder="fuzzy match (pg_trgm)"
            className="mt-1 block rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          Lifecycle
          <select
            name="lifecycle"
            defaultValue={filter.lifecycle ?? ""}
            className="mt-1 block rounded border border-slate-300 px-3 py-2"
          >
            <option value="">any</option>
            <option value="active">active</option>
            <option value="postponed">postponed</option>
            <option value="cancelled">cancelled</option>
            <option value="completed">completed</option>
            <option value="tentative">tentative</option>
          </select>
        </label>
        <label className="text-sm">
          Published
          <select
            name="is_published"
            defaultValue={filter.is_published ?? ""}
            className="mt-1 block rounded border border-slate-300 px-3 py-2"
          >
            <option value="">any</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </label>
        <button
          type="submit"
          className="rounded bg-slate-900 px-4 py-2 text-white"
        >
          Filter
        </button>
      </form>

      <p className="mt-3 text-sm text-slate-500">{total} result(s)</p>

      <table className="mt-3 w-full divide-y divide-slate-200 rounded border border-slate-200 bg-white text-sm">
        <thead className="bg-slate-50 text-left">
          <tr>
            <th className="px-3 py-2">Title</th>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">City</th>
            <th className="px-3 py-2">Country</th>
            <th className="px-3 py-2">Lifecycle</th>
            <th className="px-3 py-2">Pub.</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-2">{r.title}</td>
              <td className="px-3 py-2 font-mono text-xs">
                {r.starts_on.toString().slice(0, 10)}
                {r.ends_on ? ` – ${r.ends_on.toString().slice(0, 10)}` : ""}
              </td>
              <td className="px-3 py-2">{r.city ?? "—"}</td>
              <td className="px-3 py-2">{r.country_iso ?? "—"}</td>
              <td className="px-3 py-2">{r.lifecycle_status}</td>
              <td className="px-3 py-2">{r.is_published ? "✅" : "—"}</td>
              <td className="px-3 py-2 text-right">
                <Link
                  className="text-blue-600 hover:underline"
                  href={`/admin/events/${r.id}`}
                >
                  Edit
                </Link>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                No events match.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {totalPages > 1 && (
        <nav className="mt-4 flex gap-2 text-sm">
          {Array.from({ length: totalPages }).map((_, i) => {
            const page = i + 1;
            const params = new URLSearchParams(sp as Record<string, string>);
            params.set("page", String(page));
            return (
              <Link
                key={page}
                href={`/admin/events?${params.toString()}`}
                className={`rounded px-3 py-1 ${page === filter.page ? "bg-slate-900 text-white" : "bg-white border border-slate-300"}`}
              >
                {page}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}
