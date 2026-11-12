begin;
-- Dedicated SkillWire project only. Anonymous clients have no direct table/RPC access.
create table if not exists public.skillwire_vote_counts (
 namespace text not null, skill text not null check (skill ~ '^[a-f0-9]{16}$'),
 votes bigint not null check (votes > 0), primary key(namespace,skill)
);
create table if not exists public.skillwire_daily_votes (
 namespace text not null, day date not null, voter_hash text not null check(length(voter_hash)=64),
 network_hash text not null check(length(network_hash)=64), skill text not null,
 primary key(namespace,day,voter_hash)
);
create table if not exists public.skillwire_daily_networks (
 namespace text not null, day date not null, network_hash text not null,
 used integer not null check(used between 1 and 3), primary key(namespace,day,network_hash)
);
create table if not exists public.skillwire_x_poll_cache (namespace text primary key, result jsonb not null);
create table if not exists public.skillwire_x_poll_attempts (namespace text not null, day date not null, primary key(namespace,day));
alter table public.skillwire_vote_counts enable row level security;
alter table public.skillwire_daily_votes enable row level security;
alter table public.skillwire_daily_networks enable row level security;
alter table public.skillwire_x_poll_cache enable row level security;
alter table public.skillwire_x_poll_attempts enable row level security;
revoke all on public.skillwire_vote_counts,public.skillwire_daily_votes,public.skillwire_daily_networks,public.skillwire_x_poll_cache,public.skillwire_x_poll_attempts from public,anon,authenticated;
grant select,insert,update,delete on public.skillwire_vote_counts,public.skillwire_daily_votes,public.skillwire_daily_networks,public.skillwire_x_poll_cache,public.skillwire_x_poll_attempts to service_role;

create or replace function public.skillwire_vote_status(p_namespace text,p_day date,p_voter_hash text)
returns jsonb language sql security invoker set search_path='' as $$
 select jsonb_build_object('counts',coalesce((select jsonb_object_agg(skill,votes) from public.skillwire_vote_counts where namespace=p_namespace),'{}'::jsonb),
 'selected_today',(select skill from public.skillwire_daily_votes where namespace=p_namespace and day=p_day and voter_hash=p_voter_hash));
$$;
create or replace function public.skillwire_cast_vote(p_namespace text,p_day date,p_voter_hash text,p_network_hash text,p_skill text)
returns integer language plpgsql security invoker set search_path='' as $$
begin
 if p_namespace !~ '^[a-zA-Z0-9:_-]{1,110}$' or p_voter_hash !~ '^[a-f0-9]{64}$' or p_network_hash !~ '^[a-f0-9]{64}$' or p_skill !~ '^[a-f0-9]{16}$' then raise exception 'Invalid vote'; end if;
 -- One transaction locks both budgets; concurrent cookie resets cannot overspend a network.
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':network:'||p_day::text||':'||p_network_hash,0));
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':person:'||p_day::text||':'||p_voter_hash,0));
 if exists(select 1 from public.skillwire_daily_votes where namespace=p_namespace and day=p_day and voter_hash=p_voter_hash) then return 0; end if;
 if coalesce((select used from public.skillwire_daily_networks where namespace=p_namespace and day=p_day and network_hash=p_network_hash),0)>=3 then return -1; end if;
 insert into public.skillwire_daily_votes values(p_namespace,p_day,p_voter_hash,p_network_hash,p_skill);
 insert into public.skillwire_daily_networks values(p_namespace,p_day,p_network_hash,1)
 on conflict(namespace,day,network_hash) do update set used=public.skillwire_daily_networks.used+1;
 insert into public.skillwire_vote_counts values(p_namespace,p_skill,1)
 on conflict(namespace,skill) do update set votes=public.skillwire_vote_counts.votes+1;
 return 1;
end;
$$;
create or replace function public.skillwire_x_poll_get(p_namespace text)
returns jsonb language sql security invoker set search_path='' as $$
 select result from public.skillwire_x_poll_cache where namespace=p_namespace;
$$;
create or replace function public.skillwire_x_poll_set(p_namespace text,p_result jsonb)
returns void language sql security invoker set search_path='' as $$
 insert into public.skillwire_x_poll_cache values(p_namespace,p_result)
 on conflict(namespace) do update set result=excluded.result;
$$;
create or replace function public.skillwire_x_poll_claim(p_namespace text,p_day date)
returns boolean language plpgsql security invoker set search_path='' as $$
declare n integer;
begin
 insert into public.skillwire_x_poll_attempts values(p_namespace,p_day) on conflict do nothing;
 get diagnostics n = row_count; return n=1;
end;
$$;
create or replace function public.skillwire_keepalive()
returns jsonb language plpgsql security invoker set search_path='' as $$
declare cutoff date := (current_timestamp at time zone 'UTC')::date-1;
begin
 delete from public.skillwire_daily_votes where day<cutoff;
 delete from public.skillwire_daily_networks where day<cutoff;
 delete from public.skillwire_x_poll_attempts where day<cutoff;
 return jsonb_build_object('ok',true,'checked_at',current_timestamp);
end;
$$;
revoke execute on function public.skillwire_vote_status(text,date,text),public.skillwire_cast_vote(text,date,text,text,text),public.skillwire_x_poll_get(text),public.skillwire_x_poll_set(text,jsonb),public.skillwire_x_poll_claim(text,date),public.skillwire_keepalive() from public,anon,authenticated;
grant execute on function public.skillwire_vote_status(text,date,text),public.skillwire_cast_vote(text,date,text,text,text),public.skillwire_x_poll_get(text),public.skillwire_x_poll_set(text,jsonb),public.skillwire_x_poll_claim(text,date),public.skillwire_keepalive() to service_role;
commit;
