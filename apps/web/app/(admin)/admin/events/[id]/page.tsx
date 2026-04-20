import { notFound } from "next/navigation";
import { getEvent } from "@/lib/db/events";
import { readSession, isAuthenticated } from "@/lib/auth/session";
import { generateCsrfToken, getCsrfSessionId } from "@/lib/auth/csrf";

const FORMATS = ["in_person", "virtual", "hybrid", "unknown"];
const KINDS = [
  "fair",
  "seminar",
  "congress",
  "workshop",
  "webinar",
  "conference",
  "training",
  "other",
];
const LIFECYCLES = [
  "active",
  "postponed",
  "cancelled",
  "completed",
  "tentative",
];

export default async function EventEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const e = await getEvent(id);
  if (!e) notFound();

  const session = await readSession();
  const csrf = isAuthenticated(session)
    ? generateCsrfToken(getCsrfSessionId(session))
    : "";

  return (
    <div>
      <h1 className="text-2xl font-semibold">Edit event</h1>
      <p className="mt-1 font-mono text-xs text-slate-500">{e.id}</p>

      <form
        method="POST"
        action={`/admin/events/${e.id}/save`}
        className="mt-6 grid grid-cols-2 gap-4"
      >
        <input type="hidden" name="_csrf" value={csrf} />
        <Field name="title" label="Title" defaultValue={e.title} />
        <Field name="slug" label="Slug" defaultValue={e.slug} />
        <Field
          name="starts_on"
          label="Starts on (YYYY-MM-DD)"
          type="date"
          defaultValue={e.starts_on.toString().slice(0, 10)}
        />
        <Field
          name="ends_on"
          label="Ends on"
          type="date"
          defaultValue={e.ends_on ? e.ends_on.toString().slice(0, 10) : ""}
        />
        <Field
          name="timezone"
          label="Timezone"
          defaultValue={e.timezone ?? ""}
        />
        <Field name="city" label="City" defaultValue={e.city ?? ""} />
        <Field
          name="country_iso"
          label="Country (ISO-2)"
          defaultValue={e.country_iso ?? ""}
        />
        <Field
          name="venue_name"
          label="Venue"
          defaultValue={e.venue_name ?? ""}
        />
        <Select
          name="format"
          label="Format"
          defaultValue={e.format}
          options={FORMATS}
        />
        <Select
          name="event_kind"
          label="Kind"
          defaultValue={e.event_kind}
          options={KINDS}
        />
        <Select
          name="lifecycle_status"
          label="Lifecycle"
          defaultValue={e.lifecycle_status}
          options={LIFECYCLES}
        />
        <Field
          name="organizer_name"
          label="Organizer"
          defaultValue={e.organizer_name ?? ""}
        />
        <Field
          name="source_url"
          label="Source URL"
          defaultValue={e.source_url}
        />
        <Field
          name="registration_url"
          label="Registration URL"
          defaultValue={e.registration_url ?? ""}
        />
        <Field
          name="specialty_codes_csv"
          label="Specialty codes (comma-separated)"
          defaultValue={e.specialty_codes.join(",")}
        />
        <label className="col-span-2 block text-sm">
          Summary
          <textarea
            name="summary"
            rows={4}
            defaultValue={e.summary ?? ""}
            className="mt-1 block w-full rounded border border-slate-300 px-3 py-2"
          />
        </label>
        <label className="col-span-2 inline-flex items-center gap-2 text-sm">
          <input
            name="is_published"
            type="checkbox"
            defaultChecked={e.is_published}
          />
          Published
        </label>
        <div className="col-span-2 flex gap-3">
          <button
            type="submit"
            className="rounded bg-slate-900 px-4 py-2 text-white"
          >
            Save
          </button>
        </div>
      </form>

      <form
        method="POST"
        action={`/admin/events/${e.id}/unpublish`}
        className="mt-3"
      >
        <input type="hidden" name="_csrf" value={csrf} />
        <button
          type="submit"
          className="rounded border border-slate-300 px-4 py-2"
        >
          Unpublish
        </button>
      </form>
    </div>
  );
}

function Field({
  name,
  label,
  defaultValue,
  type = "text",
}: {
  name: string;
  label: string;
  defaultValue?: string;
  type?: string;
}) {
  return (
    <label className="block text-sm">
      {label}
      <input
        name={name}
        type={type}
        defaultValue={defaultValue}
        className="mt-1 block w-full rounded border border-slate-300 px-3 py-2"
      />
    </label>
  );
}

function Select({
  name,
  label,
  defaultValue,
  options,
}: {
  name: string;
  label: string;
  defaultValue: string;
  options: string[];
}) {
  return (
    <label className="block text-sm">
      {label}
      <select
        name={name}
        defaultValue={defaultValue}
        className="mt-1 block w-full rounded border border-slate-300 px-3 py-2"
      >
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
