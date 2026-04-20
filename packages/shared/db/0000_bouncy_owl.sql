-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TABLE IF NOT EXISTS "alembic_version" (
	"version_num" varchar(32) PRIMARY KEY NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "sources" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"code" "citext" NOT NULL,
	"homepage_url" text NOT NULL,
	"source_type" text NOT NULL,
	"country_iso" char(2),
	"is_active" boolean DEFAULT true NOT NULL,
	"parser_name" text,
	"crawl_frequency" text NOT NULL,
	"crawl_config" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"last_crawled_at" timestamp with time zone,
	"last_success_at" timestamp with time zone,
	"last_error_at" timestamp with time zone,
	"last_error_message" text,
	"notes" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "sources_code_key" UNIQUE("code"),
	CONSTRAINT "sources_source_type_check" CHECK (source_type = ANY (ARRAY['society'::text, 'sponsor'::text, 'aggregator'::text, 'venue'::text, 'government'::text, 'other'::text])),
	CONSTRAINT "sources_crawl_frequency_check" CHECK (crawl_frequency = ANY (ARRAY['daily'::text, 'weekly'::text, 'biweekly'::text, 'monthly'::text]))
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "source_pages" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"source_id" uuid NOT NULL,
	"url" text NOT NULL,
	"page_kind" text NOT NULL,
	"content_hash" text,
	"last_seen_at" timestamp with time zone,
	"last_fetched_at" timestamp with time zone,
	"fetch_status" text,
	"parser_name" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "source_pages_source_id_url_key" UNIQUE("source_id","url"),
	CONSTRAINT "source_pages_page_kind_check" CHECK (page_kind = ANY (ARRAY['listing'::text, 'detail'::text, 'pdf'::text, 'unknown'::text]))
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "events" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"slug" text NOT NULL,
	"title" text NOT NULL,
	"summary" text,
	"starts_on" date NOT NULL,
	"ends_on" date,
	"timezone" text,
	"city" text,
	"country_iso" char(2),
	"venue_name" text,
	"format" text DEFAULT 'unknown' NOT NULL,
	"event_kind" text DEFAULT 'other' NOT NULL,
	"lifecycle_status" text DEFAULT 'active' NOT NULL,
	"specialty_codes" text[] DEFAULT '{""}' NOT NULL,
	"organizer_name" text,
	"source_url" text NOT NULL,
	"registration_url" text,
	"source_count" integer DEFAULT 1 NOT NULL,
	"last_checked_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_changed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"is_published" boolean DEFAULT true NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "events_slug_key" UNIQUE("slug"),
	CONSTRAINT "events_format_check" CHECK (format = ANY (ARRAY['in_person'::text, 'virtual'::text, 'hybrid'::text, 'unknown'::text])),
	CONSTRAINT "events_event_kind_check" CHECK (event_kind = ANY (ARRAY['fair'::text, 'seminar'::text, 'congress'::text, 'workshop'::text, 'webinar'::text, 'conference'::text, 'training'::text, 'other'::text])),
	CONSTRAINT "events_lifecycle_status_check" CHECK (lifecycle_status = ANY (ARRAY['active'::text, 'postponed'::text, 'cancelled'::text, 'completed'::text, 'tentative'::text]))
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "event_sources" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"event_id" uuid NOT NULL,
	"source_id" uuid NOT NULL,
	"source_page_id" uuid,
	"source_url" text NOT NULL,
	"first_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"last_seen_at" timestamp with time zone DEFAULT now() NOT NULL,
	"is_primary" boolean DEFAULT false NOT NULL,
	"raw_title" text,
	"raw_date_text" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "review_items" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"kind" text NOT NULL,
	"source_id" uuid,
	"source_page_id" uuid,
	"event_id" uuid,
	"status" text DEFAULT 'open' NOT NULL,
	"details_json" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"resolved_at" timestamp with time zone,
	"resolved_by" text,
	"resolution_note" text,
	CONSTRAINT "review_items_kind_check" CHECK (kind = ANY (ARRAY['duplicate_candidate'::text, 'parser_failure'::text, 'suspicious_data'::text, 'source_blocked'::text])),
	CONSTRAINT "review_items_status_check" CHECK (status = ANY (ARRAY['open'::text, 'resolved'::text, 'ignored'::text]))
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "audit_log" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"actor" text NOT NULL,
	"action" text NOT NULL,
	"target_kind" text,
	"target_id" uuid,
	"details_json" jsonb DEFAULT '{}'::jsonb NOT NULL,
	"occurred_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "source_pages" ADD CONSTRAINT "source_pages_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "public"."sources"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "event_sources" ADD CONSTRAINT "event_sources_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "event_sources" ADD CONSTRAINT "event_sources_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "public"."sources"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "event_sources" ADD CONSTRAINT "event_sources_source_page_id_fkey" FOREIGN KEY ("source_page_id") REFERENCES "public"."source_pages"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "review_items" ADD CONSTRAINT "review_items_source_id_fkey" FOREIGN KEY ("source_id") REFERENCES "public"."sources"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "review_items" ADD CONSTRAINT "review_items_source_page_id_fkey" FOREIGN KEY ("source_page_id") REFERENCES "public"."source_pages"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "review_items" ADD CONSTRAINT "review_items_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "sources_active_crawled" ON "sources" USING btree ("is_active" timestamptz_ops,"last_crawled_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "source_pages_content_hash" ON "source_pages" USING btree ("content_hash" text_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "source_pages_source_kind" ON "source_pages" USING btree ("source_id" uuid_ops,"page_kind" text_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "events_country_starts_on" ON "events" USING btree ("country_iso" date_ops,"starts_on" bpchar_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "events_lifecycle" ON "events" USING btree ("lifecycle_status" text_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "events_published_starts_on" ON "events" USING btree ("is_published" date_ops,"starts_on" date_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "events_specialty_codes_gin" ON "events" USING gin ("specialty_codes" array_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "events_title_trgm" ON "events" USING gin ("title" gin_trgm_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "event_sources_event" ON "event_sources" USING btree ("event_id" uuid_ops);--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "event_sources_event_page_uniq" ON "event_sources" USING btree ("event_id" uuid_ops,"source_page_id" uuid_ops) WHERE (source_page_id IS NOT NULL);--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "event_sources_event_url_uniq" ON "event_sources" USING btree ("event_id" text_ops,"source_url" uuid_ops) WHERE (source_page_id IS NULL);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "event_sources_page" ON "event_sources" USING btree ("source_page_id" uuid_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "event_sources_source" ON "event_sources" USING btree ("source_id" uuid_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "review_items_status_kind" ON "review_items" USING btree ("status" text_ops,"kind" timestamptz_ops,"created_at" text_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "audit_log_actor_time" ON "audit_log" USING btree ("actor" text_ops,"occurred_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "audit_log_target" ON "audit_log" USING btree ("target_kind" text_ops,"target_id" timestamptz_ops,"occurred_at" text_ops);
*/
