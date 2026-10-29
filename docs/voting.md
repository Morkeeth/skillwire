# Daily community voting

One vote across the catalog per signed anonymous browser identity per UTC day. The website cannot prove one human without login. A shared-network budget permits three identities each day (IPv4 address or IPv6 /64), making cookie resets inconvenient while allowing some household use. Shared networks can still hit this limit; proxies, new networks and devices can still game it. No-login preference is not measured usage or skill effectiveness. The harmless catalog Easter egg is not eligible to vote.

Votes and the identity/network claims are committed in one Postgres transaction. Raw IPs and cookie identities never enter the vote store: per-day keyed hashes are pruned by the daily maintenance job after the day plus a recovery window. Aggregate counts persist. No executable skills, private files, model requests or uploads are accepted. Duplicate/uncertain responses require a readback; the API never guesses a second vote succeeded.

## Deployment

Existing Vercel project, allowlisted source export only. Configure server-only `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and a random `SKILLWIRE_VOTE_SECRET` of at least 32 characters in both preview and production. No ephemeral filesystem fallback is provided. A durable store must be approved and available; missing configuration returns 503.

Preview data uses a deployment-specific prefix. Production uses `production-v1`. Preserve the production signing secret across deployments. Preview test votes are not production community votes. Use existing project hosting and the dedicated approved free Supabase skillwire-votes project in EU (never another project); provisioning or paid plans require their own authorization. This code does not create a store or discover credentials.

The public API is GET `/api/votes` (signed HttpOnly/Secure/SameSite cookie and CSRF token), POST `/api/vote` (same-origin JSON with skill_id,csrf,website). Size capped at 1024 bytes. Browser counts refresh on entry, after voting, manually, or every 30 seconds while the Community votes tab is visible. Errors keep the last shown counts visibly stale; no fake seed votes. Aggregate counts are separate from research picks and task evaluations.

Vercel overwrites `x-forwarded-for`; the endpoint uses `x-vercel-forwarded-for` on Vercel, never a request-body identity. https://vercel.com/docs/headers/request-headers . A custom proxy deployment requires revisiting this trust boundary. Local HTTP tests use the actual socket peer.

## X poll: built, OFF

`SKILLWIRE_X_POLL_ENABLED` defaults OFF. With OFF, the X job never accesses the datastore or X. The separate daily maintenance still reads Postgres and prunes expired identity/network claims. To enable later, Oscar must supply an approved X developer app bearer token as `X_API_BEARER_TOKEN`, a public poll Post ID as `SKILLWIRE_X_POLL_POST_ID`, and a random `CRON_SECRET` (at least 16 characters). This is read access only; there is no X post implementation or visitor OAuth flow. The once-daily Vercel cron calls authenticated `/api/vote-maintenance` at 06:17 UTC for datastore keepalive/cleanup, then invokes the X mirror only if its flag is enabled. `/api/x-poll-sync` also supports an authenticated manual read with the same daily attempt constraint. Only a matching cron bearer secret can run enabled work. Set the flag only after access and credits are explicitly available.

The X job makes at most one attempt per UTC day, including failed reads, without paid retries. It requests the poll expansion from the known Post lookup and caches aggregate counts with the true fetch time. Failures preserve the previous dated result. X and on-site votes are never combined. It does not create a poll, buy credits or enable itself.

Official pricing checked 29 October 2026: Post reads $0.005 per resource; repeated same-resource reads normally deduplicate within a UTC day, a soft guarantee. One daily lookup is normally $0.005/day; thirty daily reads $0.15 as arithmetic, excluding other endpoints and platform changes. Do not assume the $0.001 owned-read discount for direct Post lookup. Actual entitlement, available credits and billing remain unverified. https://docs.x.com/x-api/getting-started/pricing . Access: https://docs.x.com/x-api/getting-started/getting-access . Poll fields: https://docs.x.com/x-api/fundamentals/data-dictionary#poll . Cron authentication: https://vercel.com/docs/cron-jobs/manage-cron-jobs .

## Verification

Run `python3 -m unittest discover -s tests -p 'test_voting*.py' -v` and `python3 -m unittest discover -s tests -p test_x_poll.py -v`. These tests start their own local Postgres with no persistence and exercise the exact deployed SQL rules, concurrent retries, daily boundaries, cookie resets, privacy keys and real HTTP. Set `PG_BINDIR` to installed Postgres server binaries if needed (default Homebrew postgresql@18). HTTP tests patch only storage configuration, not the rule. X tests replace only external network effects. No paid API is used. Test preview end-to-end with real HTTP votes and fresh browser sessions before production; production readback must not create fake popularity.

## Supabase isolation and free plan

Apply `migrations/20261029_daily_votes.sql` only to the dedicated project. All five tables have RLS enabled and no anon/authenticated permissions or write policies. RPC execute is revoked from PUBLIC/anon/authenticated and granted only to service_role. Only the API function receives the service key in Vercel; no key appears in site files, browser requests, source packs or logs. The primary key(namespace,day,voter_hash) prevents voting across different skills on the same day. Transaction-scoped advisory locks protect both browser and shared-network budgets, with aggregate counts updated in the same transaction.

The approved free project can pause after inactivity. Authenticated daily maintenance reads it and cleans transient claims, reducing inactivity risk without claiming a guaranteed uptime plan. If paused, resume skillwire-votes in the existing Supabase Dashboard, then read `/api/votes` and verify counts. Do not replace/reset the database or signing secret. Aggregate votes survive app deployments; hosted free-plan restoration/availability follows Supabase terms. Missing/offline storage fails closed with no fake counts or votes. Official guidance: https://supabase.com/docs/guides/deployment/going-into-prod .
