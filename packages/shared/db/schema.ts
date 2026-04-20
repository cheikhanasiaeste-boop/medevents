import { pgTable, varchar, index, unique, check, uuid, text, char, boolean, jsonb, timestamp, foreignKey, date, integer, uniqueIndex } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



export const alembic_version = pgTable("alembic_version", {
	version_num: varchar({ length: 32 }).primaryKey().notNull(),
});

export const sources = pgTable("sources", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	name: text().notNull(),
	code: text("code").notNull(),
	homepage_url: text().notNull(),
	source_type: text().notNull(),
	country_iso: char({ length: 2 }),
	is_active: boolean().default(true).notNull(),
	parser_name: text(),
	crawl_frequency: text().notNull(),
	crawl_config: jsonb().default({}).notNull(),
	last_crawled_at: timestamp({ withTimezone: true, mode: 'string' }),
	last_success_at: timestamp({ withTimezone: true, mode: 'string' }),
	last_error_at: timestamp({ withTimezone: true, mode: 'string' }),
	last_error_message: text(),
	notes: text(),
	created_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updated_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => {
	return {
		active_crawled: index("sources_active_crawled").using("btree", table.is_active.asc().nullsLast().op("timestamptz_ops"), table.last_crawled_at.asc().nullsLast().op("timestamptz_ops")),
		sources_code_key: unique("sources_code_key").on(table.code),
		sources_source_type_check: check("sources_source_type_check", sql`source_type = ANY (ARRAY['society'::text, 'sponsor'::text, 'aggregator'::text, 'venue'::text, 'government'::text, 'other'::text])`),
		sources_crawl_frequency_check: check("sources_crawl_frequency_check", sql`crawl_frequency = ANY (ARRAY['daily'::text, 'weekly'::text, 'biweekly'::text, 'monthly'::text])`),
	}
});

export const source_pages = pgTable("source_pages", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	source_id: uuid().notNull(),
	url: text().notNull(),
	page_kind: text().notNull(),
	content_hash: text(),
	last_seen_at: timestamp({ withTimezone: true, mode: 'string' }),
	last_fetched_at: timestamp({ withTimezone: true, mode: 'string' }),
	fetch_status: text(),
	parser_name: text(),
	created_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => {
	return {
		content_hash: index("source_pages_content_hash").using("btree", table.content_hash.asc().nullsLast().op("text_ops")),
		source_kind: index("source_pages_source_kind").using("btree", table.source_id.asc().nullsLast().op("uuid_ops"), table.page_kind.asc().nullsLast().op("text_ops")),
		source_pages_source_id_fkey: foreignKey({
			columns: [table.source_id],
			foreignColumns: [sources.id],
			name: "source_pages_source_id_fkey"
		}).onDelete("cascade"),
		source_pages_source_id_url_key: unique("source_pages_source_id_url_key").on(table.source_id, table.url),
		source_pages_page_kind_check: check("source_pages_page_kind_check", sql`page_kind = ANY (ARRAY['listing'::text, 'detail'::text, 'pdf'::text, 'unknown'::text])`),
	}
});

export const events = pgTable("events", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	slug: text().notNull(),
	title: text().notNull(),
	summary: text(),
	starts_on: date().notNull(),
	ends_on: date(),
	timezone: text(),
	city: text(),
	country_iso: char({ length: 2 }),
	venue_name: text(),
	format: text().default('unknown').notNull(),
	event_kind: text().default('other').notNull(),
	lifecycle_status: text().default('active').notNull(),
	specialty_codes: text().array().default([""]).notNull(),
	organizer_name: text(),
	source_url: text().notNull(),
	registration_url: text(),
	source_count: integer().default(1).notNull(),
	last_checked_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	last_changed_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	is_published: boolean().default(true).notNull(),
	created_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updated_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => {
	return {
		country_starts_on: index("events_country_starts_on").using("btree", table.country_iso.asc().nullsLast().op("date_ops"), table.starts_on.asc().nullsLast().op("bpchar_ops")),
		lifecycle: index("events_lifecycle").using("btree", table.lifecycle_status.asc().nullsLast().op("text_ops")),
		published_starts_on: index("events_published_starts_on").using("btree", table.is_published.asc().nullsLast().op("date_ops"), table.starts_on.asc().nullsLast().op("date_ops")),
		specialty_codes_gin: index("events_specialty_codes_gin").using("gin", table.specialty_codes.asc().nullsLast().op("array_ops")),
		title_trgm: index("events_title_trgm").using("gin", table.title.asc().nullsLast().op("gin_trgm_ops")),
		events_slug_key: unique("events_slug_key").on(table.slug),
		events_format_check: check("events_format_check", sql`format = ANY (ARRAY['in_person'::text, 'virtual'::text, 'hybrid'::text, 'unknown'::text])`),
		events_event_kind_check: check("events_event_kind_check", sql`event_kind = ANY (ARRAY['fair'::text, 'seminar'::text, 'congress'::text, 'workshop'::text, 'webinar'::text, 'conference'::text, 'training'::text, 'other'::text])`),
		events_lifecycle_status_check: check("events_lifecycle_status_check", sql`lifecycle_status = ANY (ARRAY['active'::text, 'postponed'::text, 'cancelled'::text, 'completed'::text, 'tentative'::text])`),
	}
});

export const event_sources = pgTable("event_sources", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	event_id: uuid().notNull(),
	source_id: uuid().notNull(),
	source_page_id: uuid(),
	source_url: text().notNull(),
	first_seen_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	last_seen_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	is_primary: boolean().default(false).notNull(),
	raw_title: text(),
	raw_date_text: text(),
	created_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => {
	return {
		event: index("event_sources_event").using("btree", table.event_id.asc().nullsLast().op("uuid_ops")),
		event_page_uniq: uniqueIndex("event_sources_event_page_uniq").using("btree", table.event_id.asc().nullsLast().op("uuid_ops"), table.source_page_id.asc().nullsLast().op("uuid_ops")).where(sql`(source_page_id IS NOT NULL)`),
		event_url_uniq: uniqueIndex("event_sources_event_url_uniq").using("btree", table.event_id.asc().nullsLast().op("text_ops"), table.source_url.asc().nullsLast().op("uuid_ops")).where(sql`(source_page_id IS NULL)`),
		page: index("event_sources_page").using("btree", table.source_page_id.asc().nullsLast().op("uuid_ops")),
		source: index("event_sources_source").using("btree", table.source_id.asc().nullsLast().op("uuid_ops")),
		event_sources_event_id_fkey: foreignKey({
			columns: [table.event_id],
			foreignColumns: [events.id],
			name: "event_sources_event_id_fkey"
		}).onDelete("cascade"),
		event_sources_source_id_fkey: foreignKey({
			columns: [table.source_id],
			foreignColumns: [sources.id],
			name: "event_sources_source_id_fkey"
		}),
		event_sources_source_page_id_fkey: foreignKey({
			columns: [table.source_page_id],
			foreignColumns: [source_pages.id],
			name: "event_sources_source_page_id_fkey"
		}),
	}
});

export const review_items = pgTable("review_items", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	kind: text().notNull(),
	source_id: uuid(),
	source_page_id: uuid(),
	event_id: uuid(),
	status: text().default('open').notNull(),
	details_json: jsonb().default({}).notNull(),
	created_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	resolved_at: timestamp({ withTimezone: true, mode: 'string' }),
	resolved_by: text(),
	resolution_note: text(),
}, (table) => {
	return {
		status_kind: index("review_items_status_kind").using("btree", table.status.asc().nullsLast().op("text_ops"), table.kind.asc().nullsLast().op("timestamptz_ops"), table.created_at.asc().nullsLast().op("text_ops")),
		review_items_source_id_fkey: foreignKey({
			columns: [table.source_id],
			foreignColumns: [sources.id],
			name: "review_items_source_id_fkey"
		}),
		review_items_source_page_id_fkey: foreignKey({
			columns: [table.source_page_id],
			foreignColumns: [source_pages.id],
			name: "review_items_source_page_id_fkey"
		}),
		review_items_event_id_fkey: foreignKey({
			columns: [table.event_id],
			foreignColumns: [events.id],
			name: "review_items_event_id_fkey"
		}),
		review_items_kind_check: check("review_items_kind_check", sql`kind = ANY (ARRAY['duplicate_candidate'::text, 'parser_failure'::text, 'suspicious_data'::text, 'source_blocked'::text])`),
		review_items_status_check: check("review_items_status_check", sql`status = ANY (ARRAY['open'::text, 'resolved'::text, 'ignored'::text])`),
	}
});

export const audit_log = pgTable("audit_log", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	actor: text().notNull(),
	action: text().notNull(),
	target_kind: text(),
	target_id: uuid(),
	details_json: jsonb().default({}).notNull(),
	occurred_at: timestamp({ withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => {
	return {
		actor_time: index("audit_log_actor_time").using("btree", table.actor.asc().nullsLast().op("text_ops"), table.occurred_at.asc().nullsLast().op("timestamptz_ops")),
		target: index("audit_log_target").using("btree", table.target_kind.asc().nullsLast().op("text_ops"), table.target_id.asc().nullsLast().op("timestamptz_ops"), table.occurred_at.asc().nullsLast().op("text_ops")),
	}
});
