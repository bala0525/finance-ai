-- Idempotent: enable Row Level Security on every public table.
-- Run in the Supabase SQL editor after adding tables outside Alembic.
-- No policies are created on purpose: the FastAPI backend (database owner)
-- bypasses RLS, while Supabase's anon/authenticated REST access is denied.
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END $$;
