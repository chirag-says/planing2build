// The notifications are derived from the API's own records only (decided 2026-10-08): next
// actions and recorded activity, no sample threads, and the bell counts only what needs the family.
import { describe, expect, it } from "vitest";

import { buildNotifications, dayGroup, unreadCount } from "@/lib/inbox";
import type { NextAction } from "@/lib/journey";
import type { ActivityItem } from "@/lib/project-overview";

const NOW = "2026-10-08T06:00:00.000Z";
const act: NextAction = { key: "requestQuotes", path: "/quotes", values: {}, kind: "act" };
const watch: NextAction = { key: "followFindings", path: "/construction", values: {}, kind: "watch" };
const activity: ActivityItem[] = [
  { id: "a1", kind: "planAccepted", at: "2026-10-01T10:00:00.000Z", values: {} },
  { id: "a2", kind: "inspectionPassed", at: "2026-10-05", values: {} },
];

describe("buildNotifications", () => {
  it("holds only next actions and activity, newest first", () => {
    const items = buildNotifications({ actions: [act, watch], activity }, NOW);
    expect(items.map((i) => i.source.type)).toEqual(["action", "action", "activity", "activity"]);
    expect(items.map((i) => i.kind)).toEqual(["action", "action", "inspection", "update"]);
    expect(items[2]?.path).toBe("/construction#inspections");
  });

  it("counts only the actions the family must take", () => {
    const items = buildNotifications({ actions: [act, watch], activity }, NOW);
    expect(unreadCount(items)).toBe(1);
  });

  it("is empty and counts nothing when the API records nothing", () => {
    const items = buildNotifications({ actions: [], activity: [] }, NOW);
    expect(items).toEqual([]);
    expect(unreadCount(items)).toBe(0);
  });
});

describe("dayGroup", () => {
  it("groups by the reader's day in India", () => {
    expect(dayGroup("2026-10-08T01:00:00.000Z", NOW)).toBe("today");
    expect(dayGroup("2026-10-07T01:00:00.000Z", NOW)).toBe("yesterday");
    expect(dayGroup("2026-10-01T01:00:00.000Z", NOW)).toBe("earlier");
  });
});
