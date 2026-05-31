-- Run in Supabase SQL Editor if columns are missing.

create table if not exists file_logs (
    id uuid primary key default gen_random_uuid(),
    original_filename text not null,
    output_format text not null,
    uploaded_file_url text,
    processed_file_url text,
    processed_storage_path text,
    processed_filename text,
    created_at timestamptz not null default now()
);

alter table file_logs
    add column if not exists processed_storage_path text,
    add column if not exists processed_filename text,
    add column if not exists created_at timestamptz default now();

create index if not exists idx_file_logs_created_at on file_logs (created_at desc);
