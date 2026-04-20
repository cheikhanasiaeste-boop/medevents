import { notFound } from "next/navigation";
import { getReview } from "@/lib/db/reviews";
import { readSession, isAuthenticated } from "@/lib/auth/session";
import { generateCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";

export default async function ReviewDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const r = await getReview(id);
  if (!r) notFound();

  const session = await readSession();
  const csrf = isAuthenticated(session)
    ? generateCsrfToken(getCsrfSessionId(session))
    : "";

  return (
    <div>
      <h1 className="text-2xl font-semibold">Review item</h1>
      <p className="mt-1 text-sm text-slate-600">
        <span className="font-mono">{r.kind}</span> · status {r.status}
      </p>

      <pre className="mt-4 overflow-auto rounded bg-slate-100 p-3 text-xs">
        {JSON.stringify(r.details_json, null, 2)}
      </pre>

      {r.status === "open" ? (
        <form
          method="POST"
          action={`/admin/review/${r.id}/resolve`}
          className="mt-6 space-y-3"
        >
          <input type="hidden" name="_csrf" value={csrf} />
          <label className="block text-sm">
            Resolution note
            <textarea
              name="note"
              rows={3}
              required
              className="mt-1 block w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
          <div className="flex gap-2">
            <button
              name="status"
              value="resolved"
              type="submit"
              className="rounded bg-slate-900 px-4 py-2 text-white"
            >
              Mark resolved
            </button>
            <button
              name="status"
              value="ignored"
              type="submit"
              className="rounded border border-slate-300 px-4 py-2"
            >
              Ignore
            </button>
          </div>
        </form>
      ) : (
        <div className="mt-6 rounded bg-slate-50 px-4 py-3 text-sm">
          Resolved by <strong>{r.resolved_by}</strong> · {r.resolution_note}
        </div>
      )}
    </div>
  );
}
