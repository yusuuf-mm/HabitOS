#!/usr/bin/env bash
# One-off verification of the full Alembic cycle against a throwaway Postgres,
# with seeded rows, through upgrade -> downgrade -> upgrade again.
#
# Runs unchanged locally and in CI's backend-migrations job: it only needs a
# reachable Postgres in DATABASE_URL (or BENCH_DATABASE_URL), the backend
# dependencies, and an empty database. It uses tools/pg_query.py instead of a
# psql client so no additional tooling is required.
#
#   DATABASE_URL=postgresql+asyncpg://user:password@localhost:55433/behaviordb \
#     bash tools/migration_cycle.sh
set -uo pipefail

if [ -z "${BENCH_DATABASE_URL:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
  BENCH_DATABASE_URL="$DATABASE_URL"
fi
export DATABASE_URL="${BENCH_DATABASE_URL:-postgresql+asyncpg://user:password@localhost:55433/behaviordb}"

cd "$(dirname "$0")/../backend" || exit 1

# `uv` on a developer machine, the installed console scripts in CI.
if command -v uv >/dev/null 2>&1; then RUN="uv run"; else RUN=""; fi

FAILED=0
check() { # check <label> <actual> <expected>
  if [ "$2" = "$3" ]; then echo "  PASS  $1 = $2"; else echo "  FAIL  $1 = '$2' (expected '$3')"; FAILED=1; fi
}
q() { $RUN python ../tools/pg_query.py "$1"; }
fks() { q "select conrelid::regclass::text||':'||confdeltype::text from pg_constraint where contype='f' and confrelid='behaviors'::regclass order by 1;"; }
counts() { echo "$(q 'select count(*) from behaviors')/$(q 'select count(*) from scheduled_behaviors')/$(q 'select count(*) from completion_logs')"; }

echo "== STEP 1: upgrade to b96cd1f49448 =="
$RUN alembic upgrade b96cd1f49448 2>&1 | tail -3
check "revision" "$(q 'select version_num from alembic_version')" "b96cd1f49448"

echo "== STEP 2: seed legacy data (nonzero impact_on_*) =="
$RUN python ../tools/pg_query.py - <<'SQL'
INSERT INTO users (id,email,username,password_hash,status,created_at,updated_at)
VALUES ('11111111-1111-1111-1111-111111111111','hist@example.com','histuser','x','active',now(),now());
INSERT INTO behaviors (id,user_id,name,category,min_duration,typical_duration,max_duration,
 energy_cost,is_active,preferred_time_slots,created_at,updated_at,
 impact_on_health,impact_on_productivity,impact_on_learning,impact_on_wellness,
 impact_on_social,impact_on_financial,impact_on_creativity,impact_on_mindfulness)
VALUES ('22222222-2222-2222-2222-222222222222','11111111-1111-1111-1111-111111111111',
 'Seeded Habit','HEALTH',15,30,45,2.0,true,ARRAY['MORNING']::timeslot[],now(),now(),
 0.9,0.3,0.25,0,0,0,0,0);
INSERT INTO optimization_runs (id,user_id,status,solver,start_date,end_date,time_periods,created_at,updated_at)
VALUES ('33333333-3333-3333-3333-333333333333','11111111-1111-1111-1111-111111111111',
 'COMPLETED','LINEAR',CURRENT_DATE,CURRENT_DATE,96,now(),now());
INSERT INTO scheduled_behaviors (id,optimization_run_id,behavior_id,time_period,scheduled_duration,is_scheduled,created_at)
VALUES ('44444444-4444-4444-4444-444444444444','33333333-3333-3333-3333-333333333333',
 '22222222-2222-2222-2222-222222222222',32,30,true,now());
INSERT INTO completion_logs (id,user_id,behavior_id,optimization_run_id,actual_duration,completed_at,created_at)
VALUES ('55555555-5555-5555-5555-555555555555','11111111-1111-1111-1111-111111111111',
 '22222222-2222-2222-2222-222222222222','33333333-3333-3333-3333-333333333333',30,now(),now());
SQL
check "seeded rows (behaviors/scheduled/logs)" "$(counts)" "1/1/1"
echo "  FKs before upgrade: $(fks | tr '\n' ' ')"

echo "== STEP 3: upgrade head =="
$RUN alembic upgrade head 2>&1 | tail -4 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "e6f7a8b9c0d1"
check "history rows survive upgrade" "$(counts)" "1/1/1"
echo "  objective_impacts rows:"
q "select objective_type||'='||impact_score from objective_impacts order by objective_type;" | sed 's/^/    /'
check "objective_impacts count" "$(q 'select count(*) from objective_impacts')" "3"
check "health impact" "$(q "select impact_score from objective_impacts where objective_type='HEALTH'")" "0.9"
check "productivity impact" "$(q "select impact_score from objective_impacts where objective_type='PRODUCTIVITY'")" "0.3"
check "learning impact" "$(q "select impact_score from objective_impacts where objective_type='LEARNING'")" "0.25"
check "legacy impact columns dropped" "$(q "select count(*) from information_schema.columns where table_name='behaviors' and column_name like 'impact_on_%'")" "0"
echo "  FKs after upgrade (r=RESTRICT): $(fks | tr '\n' ' ')"
check "scheduled FK is RESTRICT" "$(q "select confdeltype from pg_constraint where conrelid='scheduled_behaviors'::regclass and contype='f' and confrelid='behaviors'::regclass")" "r"
check "completion FK is RESTRICT" "$(q "select confdeltype from pg_constraint where conrelid='completion_logs'::regclass and contype='f' and confrelid='behaviors'::regclass")" "r"
check "every session got a planned_session_id" "$(q "select count(*) from scheduled_behaviors where planned_session_id is not null")" "1"
check "session plan_revision defaults to 1" "$(q "select plan_revision from scheduled_behaviors")" "1"
check "run plan_revision defaults to 1" "$(q "select plan_revision from optimization_runs")" "1"
check "legacy completion linked to its session" "$(q "select count(*) from completion_logs c join scheduled_behaviors s on s.planned_session_id=c.planned_session_id")" "1"
check "retired/released start empty" "$(q "select count(*) from scheduled_behaviors where retired_revision is not null or released_at is not null")" "0"
check "RLS enabled on every public table" "$(q "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and not c.relrowsecurity")" "0"
check "no public RLS policies" "$(q "select count(*) from pg_policies where schemaname='public'")" "0"
check "FORCE RLS off so the owner app connection still works" "$(q "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relforcerowsecurity")" "0"

echo "== STEP 3b: protected flag and candidate solver enum =="
check "is_protected exists" "$(q "select count(*) from information_schema.columns where table_name='behaviors' and column_name='is_protected'")" "1"
check "existing behaviours are not protected" "$(q 'select count(*) from behaviors where is_protected')" "0"
check "solvertype offers CANDIDATE" "$(q "select count(*) from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='solvertype' and e.enumlabel='CANDIDATE'")" "1"
echo "  enum values: $(q "select string_agg(enumlabel, ',' order by enumsortorder) from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='solvertype'")"

echo "== STEP 4: downgrade past e1f2a3b4c5d6 =="
$RUN alembic downgrade d4e5f6a7b8c9 2>&1 | tail -3 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "d4e5f6a7b8c9"
check "history rows survive e1f2 downgrade" "$(counts)" "1/1/1"
check "RLS disabled by downgrade" "$(q "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relkind='r' and c.relrowsecurity")" "0"
echo "  FKs after e1f2 downgrade (c=CASCADE): $(fks | tr '\n' ' ')"
check "scheduled FK reverted to CASCADE" "$(q "select confdeltype from pg_constraint where conrelid='scheduled_behaviors'::regclass and contype='f' and confrelid='behaviors'::regclass")" "c"
check "completion FK reverted to CASCADE" "$(q "select confdeltype from pg_constraint where conrelid='completion_logs'::regclass and contype='f' and confrelid='behaviors'::regclass")" "c"

check "downgrade removed is_protected" "$(q "select count(*) from information_schema.columns where table_name='behaviors' and column_name='is_protected'")" "0"
check "downgrade removed CANDIDATE from the enum" "$(q "select count(*) from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='solvertype' and e.enumlabel='CANDIDATE'")" "0"
check "runs fell back to LINEAR" "$(q "select count(*) from optimization_runs where solver='LINEAR'")" "1"

echo "== STEP 5: downgrade past c1a2b3c4d5e6 =="
$RUN alembic downgrade b96cd1f49448 2>&1 | tail -3 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "b96cd1f49448"
check "history rows survive c1 downgrade" "$(counts)" "1/1/1"
echo "  restored legacy impacts: $(q "select impact_on_health||','||impact_on_productivity||','||impact_on_learning from behaviors")"
check "restored health impact" "$(q "select impact_on_health from behaviors")" "0.9"
check "restored productivity impact" "$(q "select impact_on_productivity from behaviors")" "0.3"
check "restored learning impact" "$(q "select impact_on_learning from behaviors")" "0.25"
check "objective_impacts dropped" "$(q "select count(*) from information_schema.tables where table_name='objective_impacts'")" "0"

echo "== STEP 6: upgrade head again =="
$RUN alembic upgrade head 2>&1 | tail -4 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "e6f7a8b9c0d1"
check "history rows survive second upgrade" "$(counts)" "1/1/1"
check "objective_impacts count" "$(q 'select count(*) from objective_impacts')" "3"
check "health impact" "$(q "select impact_score from objective_impacts where objective_type='HEALTH'")" "0.9"
echo "  FKs after second upgrade: $(fks | tr '\n' ' ')"
check "scheduled FK RESTRICT again" "$(q "select confdeltype from pg_constraint where conrelid='scheduled_behaviors'::regclass and contype='f' and confrelid='behaviors'::regclass")" "r"

echo "== STEP 7: downgrade the timezone / identity-constraint revision =="
$RUN alembic downgrade f2a3b4c5d6e7 2>&1 | tail -3 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "f2a3b4c5d6e7"
check "history rows survive revision downgrade" "$(counts)" "1/1/1"
check "users.timezone dropped" "$(q "select count(*) from information_schema.columns where table_name='users' and column_name='timezone'")" "0"
check "per-revision identity constraint dropped" "$(q "select count(*) from pg_constraint where conname='uq_scheduled_behaviors_session_revision'")" "0"
check "global identity constraint restored" "$(q "select count(*) from pg_constraint where conname='uq_scheduled_behaviors_planned_session_id'")" "1"
check "completion FK restored" "$(q "select count(*) from pg_constraint where conname='fk_completion_logs_planned_session_id'")" "1"

echo "== STEP 8: upgrade head again =="
$RUN alembic upgrade head 2>&1 | tail -4 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "e6f7a8b9c0d1"
check "history rows survive second upgrade" "$(counts)" "1/1/1"
check "existing users default to UTC" "$(q "select timezone from users limit 1")" "UTC"
check "per-revision identity constraint in place" "$(q "select count(*) from pg_constraint where conname='uq_scheduled_behaviors_session_revision'")" "1"
check "global identity constraint gone" "$(q "select count(*) from pg_constraint where conname='uq_scheduled_behaviors_planned_session_id'")" "0"
check "completion FK gone" "$(q "select count(*) from pg_constraint where conname='fk_completion_logs_planned_session_id'")" "0"
check "session ids preserved" "$(q "select count(*) from scheduled_behaviors where planned_session_id is not null")" "1"
check "completion still linked" "$(q "select count(*) from completion_logs c join scheduled_behaviors s on s.planned_session_id=c.planned_session_id")" "1"

echo
if [ "$FAILED" -eq 0 ]; then echo "RESULT: ALL CHECKS PASSED"; else echo "RESULT: FAILURES PRESENT"; fi
exit "$FAILED"
