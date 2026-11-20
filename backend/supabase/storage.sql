-- Supabase Storage setup for Azentmart Finance AI (run once in the SQL editor).
-- Replace 'finance-documents' with the value of SUPABASE_STORAGE_BUCKET.

-- 1. Private bucket (public = false), 10 MB per-object cap.
insert into storage.buckets (id, name, public, file_size_limit)
values ('finance-documents', 'finance-documents', false, 10485760)
on conflict (id) do update set public = false, file_size_limit = 10485760;

-- 2. storage.objects has RLS enabled by Supabase. Create NO policies for this
--    bucket: anon/authenticated browser clients then cannot read or write it.
--    The FastAPI backend uses the service-role key, which bypasses RLS, and
--    authorises every request itself before touching Storage.

-- 3. Verify: expect public = false.
select id, public, file_size_limit from storage.buckets where id = 'finance-documents';
