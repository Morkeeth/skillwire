begin;
-- Additive, not yet applied. Fail closed if a same-named table already exists.
create table public.skillwire_directions (
 namespace text not null check(namespace ~ '^[a-zA-Z0-9:_-]{1,110}$'),
 voter_hash text not null check(voter_hash ~ '^[a-f0-9]{64}$'),
 network_hash text not null check(network_hash ~ '^[a-f0-9]{64}$'),
 skill text not null check(skill ~ '^[a-f0-9]{16}$'),
 value smallint not null check(value in (-1,1)),
 primary key(namespace,voter_hash,skill)
);
create index skillwire_direction_network_skill on public.skillwire_directions(namespace,network_hash,skill);
create table public.skillwire_direction_budget (
 namespace text not null, day date not null, scope text not null check(scope in ('person','network','mint')),
 budget_hash text not null check(budget_hash ~ '^[a-f0-9]{64}$'), used integer not null check(used between 1 and 120),
 primary key(namespace,day,scope,budget_hash)
);
-- Materialized JSON counts, maintained in the same transaction as each preference.
-- GET reads this row, never a full GROUP BY over the voter table.
create table public.skillwire_direction_totals (
 namespace text primary key, counts jsonb not null default '{}'::jsonb check(jsonb_typeof(counts)='object'),
 total bigint not null default 0 check(total>=0), updated_at timestamptz not null default now()
);
alter table public.skillwire_directions enable row level security;
alter table public.skillwire_direction_budget enable row level security;
alter table public.skillwire_direction_totals enable row level security;
revoke all on public.skillwire_directions,public.skillwire_direction_budget,public.skillwire_direction_totals from public,anon,authenticated;
grant select,insert,update,delete on public.skillwire_directions,public.skillwire_direction_budget,public.skillwire_direction_totals to service_role;
create function public.skillwire_direction_mint(p_namespace text,p_day date,p_network_hash text)
returns boolean language plpgsql security invoker set search_path='' as $$
begin
 if p_namespace is null or p_namespace !~ '^[a-zA-Z0-9:_-]{1,110}$' or p_day is null or p_network_hash is null or p_network_hash !~ '^[a-f0-9]{64}$' then raise exception 'Invalid browser request'; end if;
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':network:'||p_network_hash,0));
 if coalesce((select used from public.skillwire_direction_budget where namespace=p_namespace and day=p_day and scope='mint' and budget_hash=p_network_hash),0)>=3 then return false; end if;
 insert into public.skillwire_direction_budget values(p_namespace,p_day,'mint',p_network_hash,1)
 on conflict(namespace,day,scope,budget_hash) do update set used=public.skillwire_direction_budget.used+1;
 delete from public.skillwire_direction_budget where namespace=p_namespace and day<p_day-2;
 return true;
end; $$;
create function public.skillwire_direction_status(p_namespace text,p_voter_hash text)
returns jsonb language sql security invoker set search_path='' as $$
 select jsonb_build_object('counts',coalesce((select counts from public.skillwire_direction_totals where namespace=p_namespace),'{}'::jsonb),
 'total',coalesce((select total from public.skillwire_direction_totals where namespace=p_namespace),0),
 'updated_at',(select updated_at from public.skillwire_direction_totals where namespace=p_namespace),
 'mine',coalesce((select jsonb_object_agg(skill,value) from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash),'{}'::jsonb));
$$;
create function public.skillwire_direction_set(p_namespace text,p_day date,p_voter_hash text,p_network_hash text,p_skill text,p_value integer)
returns integer language plpgsql security invoker set search_path='' as $$
declare previous integer; cached jsonb; ups bigint; downs bigint;
begin
 if p_namespace is null or p_namespace !~ '^[a-zA-Z0-9:_-]{1,110}$' or p_day is null or p_voter_hash is null or p_voter_hash !~ '^[a-f0-9]{64}$' or p_network_hash is null or p_network_hash !~ '^[a-f0-9]{64}$' or p_skill is null or p_skill !~ '^[a-f0-9]{16}$' or p_value is null or p_value not in (-1,0,1) then raise exception 'Invalid preference'; end if;
 -- Stable network lock: caps cannot race at the UTC day boundary.
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':network:'||p_network_hash,0));
 perform pg_advisory_xact_lock(hashtextextended(p_namespace||':person:'||p_voter_hash,0));
 select value into previous from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash and skill=p_skill;
 if coalesce(previous,0)=p_value then return 0; end if;
 if p_value<>0 then
  -- At most three active browser preferences on one skill from one network,
  -- even with pre-issued or cookie-reset identities; this cap does not reset daily.
  if previous is null and (select count(*) from public.skillwire_directions where namespace=p_namespace and network_hash=p_network_hash and skill=p_skill)>=3 then return -1; end if;
  if coalesce((select used from public.skillwire_direction_budget where namespace=p_namespace and day=p_day and scope='network' and budget_hash=p_network_hash),0)>=120
  or coalesce((select used from public.skillwire_direction_budget where namespace=p_namespace and day=p_day and scope='person' and budget_hash=p_voter_hash),0)>=60 then return -1; end if;
  insert into public.skillwire_direction_budget values(p_namespace,p_day,'network',p_network_hash,1),(p_namespace,p_day,'person',p_voter_hash,1)
  on conflict(namespace,day,scope,budget_hash) do update set used=public.skillwire_direction_budget.used+1;
 end if;
 insert into public.skillwire_direction_totals(namespace) values(p_namespace) on conflict do nothing;
 select counts into cached from public.skillwire_direction_totals where namespace=p_namespace for update;
 ups=coalesce((cached->p_skill->>'up')::bigint,0)+(case when p_value=1 then 1 else 0 end)-(case when previous=1 then 1 else 0 end);
 downs=coalesce((cached->p_skill->>'down')::bigint,0)+(case when p_value=-1 then 1 else 0 end)-(case when previous=-1 then 1 else 0 end);
 if ups<0 or downs<0 then raise exception 'Invalid preference totals'; end if;
 if ups+downs=0 then cached=cached-p_skill;
 else cached=jsonb_set(cached,array[p_skill],jsonb_build_object('up',ups,'down',downs,'score',ups-downs),true); end if;
 if p_value=0 then delete from public.skillwire_directions where namespace=p_namespace and voter_hash=p_voter_hash and skill=p_skill;
 else insert into public.skillwire_directions values(p_namespace,p_voter_hash,p_network_hash,p_skill,p_value)
 on conflict(namespace,voter_hash,skill) do update set value=excluded.value; end if;
 update public.skillwire_direction_totals set counts=cached,total=total+(case when p_value<>0 then 1 else 0 end)-(case when previous is not null then 1 else 0 end),updated_at=clock_timestamp() where namespace=p_namespace;
 delete from public.skillwire_direction_budget where namespace=p_namespace and day<p_day-2;
 return 1;
end; $$;
revoke execute on function public.skillwire_direction_mint(text,date,text),public.skillwire_direction_status(text,text),public.skillwire_direction_set(text,date,text,text,text,integer) from public,anon,authenticated;
grant execute on function public.skillwire_direction_mint(text,date,text),public.skillwire_direction_status(text,text),public.skillwire_direction_set(text,date,text,text,text,integer) to service_role;
commit;
