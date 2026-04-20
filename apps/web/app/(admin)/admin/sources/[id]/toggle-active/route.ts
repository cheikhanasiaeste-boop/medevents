import { NextResponse, type NextRequest } from "next/server";
import { getSource, toggleActive } from "@/lib/db/sources";
import { writeAudit } from "@/lib/db/audit";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const before = await getSource(id);
  if (!before) {
    return NextResponse.json({ error: "source not found" }, { status: 404 });
  }
  await toggleActive(id);
  await writeAudit({
    actor: "owner",
    action: "source.toggle",
    targetKind: "source",
    targetId: id,
    details: { from: before.is_active, to: !before.is_active },
  });
  return NextResponse.redirect(new URL(`/admin/sources/${id}`, req.url), 303);
}
