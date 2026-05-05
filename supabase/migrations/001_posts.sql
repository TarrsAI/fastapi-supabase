create table if not exists posts (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  body text not null,
  author_id uuid references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table posts enable row level security;

create policy "posts: read for authed users"
  on posts for select
  using (auth.uid() is not null);

create policy "posts: insert own"
  on posts for insert
  with check (auth.uid() = author_id);
