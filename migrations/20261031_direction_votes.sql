begin;
-- Additive anonymous up/down preferences. Historical daily votes remain untouched.
create table if not exists public.skillwire_directions (
 namespace text not null check(namespace ~ '^[a-zA-Z0-9:_-]{1,110}$'),
 voter_hash text not null check(voter_hash ~ '^[a-f0-9]{64}$'),
 skill text not null check(skill ~ '^[a-f0-9]{16}$'),
 value smallint not null check(value in (-1,1)),
 primary key(namespace,voter_hash,skill)
);
create table if not exists public.skillwire_direction_budget (
 namespace text not null, day date not null, scope text not null check(scope in ('person','network')),
 budget_hash text not null check(budget_hash ~ '^[a-f0-9]{64}$'), used integer not null check(used between 1 and 120),
 primary key(namespace,day,scope,budget_hash)
);
alter table public.skillwire_directions enable row level security;
alter table public.skillwire_direction_budget enable row level security;
revoke all on public.skillwire_directions,public.skillwire_direction_budget from public,anon,authenticated;
grant select,insert,update,delete on public.skillwire_directions,public.skillwire_direction_budget to service_role;
create or replace function public.skillwire_direction_status(p_namespace text,p_voter_hash text)
returns jsonb language sql security invoker set search_path='' as $$
 select jsonb_build_object('counts',coalesce((select jsonb_object_agg(skill,jsonb_build_object('up',up,'down',down,'score',up-down)) from
 (select skill,count(*) filter(where value=1) up,count(*) filter(where value=-1) down from public.skillwire_directions where namespace=p_namespace group by skill) t),'{}'::jsonb),
 'mine',coalesce((select jsonb_object_agg(skill,value) from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash),'{}'::jsonb));
$$;
create or replace function public.skillwire_direction_set(p_namespace text,p_day date,p_voter_hash text,p_network_hash text,p_skill text,p_value integer)
returns integer language plpgsql security invoker set search_path='' as $$
declare previous integer;
begin
 if p_namespace is null or p_namespace !~ '^[a-zA-Z0-9:_-]{1,110}$' or p_day is null or p_voter_hash is null or p_voter_hash !~ '^[a-f0-9]{64}$' or p_network_hash is null or p_network_hash !~ '^[a-f0-9]{64}$' or p_skill is null or p_skill !~ '^[a-f0-9]{16}$' or p_value is null or p_value not in (-1,0,1) then raise exception 'Invalid preference'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':network:'||p_day::text||':'||p_network_hash,0));
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':person:'||p_voter_hash,0));
 select value into previous from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash and skill=p_skill;
 -- Explicit desired state makes request retries idempotent, not a second toggle.
 if coalesce(previous,0)=p_value then return 0; end if;
 -- Removing a preference must remain possible even after the change budget is spent.
 if p_value=0 then delete from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash and skill=p_skill; return 1; end if;
 if coalesce((select used from public.skillwire_direction_budget where namespace=p_namespace and day=p_day and scope='network' and budget_hash=p_network_hash),0)>=120
 or coalesce((select used from public.skillwire_direction_budget where namespace=p_namespace and day=p_day and scope='person' and budget_hash=p_voter_hash),0)>=60 then return -1; end if;
 insert into public.skillwire_direction_budget values(p_namespace,p_day,'network',p_network_hash,1),(p_namespace,p_day,'person',p_voter_hash,1)
 on conflict(namespace,day,scope,budget_hash) do update set used=public.skillwire_direction_budget.used+1;
 if p_value=0 then delete from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash and skill=p_skill;
 else insert into public.skillwire_directions values(p_namespace,p_voter_hash,p_skill,p_value)
 on conflict(namespace,voter_hash,skill) do update set value=excluded.value; end if;
 delete from public.skillwire_direction_budget where namespace=p_namespace and day<p_day-2;
 return 1;
end; $$;
revoke execute on function public.skillwire_direction_status(text,text),public.skillwire_direction_set(text,date,text,text,text,integer) from public,anon,authenticated;
grant execute on function public.skillwire_direction_status(text,text),public.skillwire_direction_set(text,date,text,text,text,integer) to service_role;
commit;
