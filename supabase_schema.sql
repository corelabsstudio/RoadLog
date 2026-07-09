-- 운행일지 AI v2 — Supabase 스키마
-- SQL Editor에서 실행하세요.

-- 사용자 프로필 (앱 자체 인증 해시 사용)
create table if not exists public.profiles (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  name text,
  plan text not null default 'free',  -- free | pro
  password_hash text not null,
  salt text not null,
  created_at timestamptz default now()
);

-- 사용자별 설정 (JSON)
create table if not exists public.user_settings (
  email text primary key references public.profiles(email) on delete cascade,
  settings jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

-- 월별 사용량 (month = 'YYYY-MM' → 매월 1일 자연 리셋)
create table if not exists public.usage (
  email text not null,
  month text not null,
  count int not null default 0,
  updated_at timestamptz default now(),
  primary key (email, month)
);

-- 결제 기록
create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  amount int not null default 0,
  plan text default 'pro',
  note text,
  paid_at timestamptz default now(),
  month text not null
);

create index if not exists idx_payments_month on public.payments(month);
create index if not exists idx_usage_month on public.usage(month);

-- 개발 편의: service_role 키 사용 시 RLS 우회.
-- anon 키만 쓸 경우 아래 정책을 환경에 맞게 조정하세요.
alter table public.profiles enable row level security;
alter table public.user_settings enable row level security;
alter table public.usage enable row level security;
alter table public.payments enable row level security;

-- 데모/MVP: 인증된 서비스 키 권장. 임시로 전체 허용 정책 예시:
create policy "allow_all_profiles" on public.profiles for all using (true) with check (true);
create policy "allow_all_settings" on public.user_settings for all using (true) with check (true);
create policy "allow_all_usage" on public.usage for all using (true) with check (true);
create policy "allow_all_payments" on public.payments for all using (true) with check (true);
