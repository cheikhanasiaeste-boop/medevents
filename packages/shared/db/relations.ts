import { relations } from "drizzle-orm/relations";
import { sources, source_pages, events, event_sources, review_items } from "./schema";

export const source_pagesRelations = relations(source_pages, ({one, many}) => ({
	source: one(sources, {
		fields: [source_pages.source_id],
		references: [sources.id]
	}),
	event_sources: many(event_sources),
	review_items: many(review_items),
}));

export const sourcesRelations = relations(sources, ({many}) => ({
	source_pages: many(source_pages),
	event_sources: many(event_sources),
	review_items: many(review_items),
}));

export const event_sourcesRelations = relations(event_sources, ({one}) => ({
	event: one(events, {
		fields: [event_sources.event_id],
		references: [events.id]
	}),
	source: one(sources, {
		fields: [event_sources.source_id],
		references: [sources.id]
	}),
	source_page: one(source_pages, {
		fields: [event_sources.source_page_id],
		references: [source_pages.id]
	}),
}));

export const eventsRelations = relations(events, ({many}) => ({
	event_sources: many(event_sources),
	review_items: many(review_items),
}));

export const review_itemsRelations = relations(review_items, ({one}) => ({
	source: one(sources, {
		fields: [review_items.source_id],
		references: [sources.id]
	}),
	source_page: one(source_pages, {
		fields: [review_items.source_page_id],
		references: [source_pages.id]
	}),
	event: one(events, {
		fields: [review_items.event_id],
		references: [events.id]
	}),
}));
