export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const params = await searchParams;
  return (
    <main className="mx-auto max-w-sm px-6 py-16">
      <h1 className="text-2xl font-semibold">Admin login</h1>
      <p className="mt-2 text-sm text-slate-600">MedEvents operator surface.</p>

      {params.error && (
        <p className="mt-4 rounded bg-red-50 px-3 py-2 text-sm text-red-700">
          {params.error === "invalid"
            ? "Wrong password."
            : "Sign-in failed. Try again."}
        </p>
      )}

      <form method="POST" action="/admin/login" className="mt-6 space-y-3">
        <input type="hidden" name="next" value={params.next ?? "/admin"} />
        <label className="block text-sm font-medium text-slate-700">
          Password
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            required
            className="mt-1 block w-full rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          className="w-full rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700"
        >
          Sign in
        </button>
      </form>
    </main>
  );
}
