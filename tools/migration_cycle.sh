#!/usr/bin/env bash
# One-off verification of the full Alembic cycle against a throwaway Postgres.
# Requires: a throwaway Postgres container. Override BENCH_DATABASE_URL; the
# default points at the disposable dev container used while writing this script.
set -uo pipefail

export DATABASE_URL="${BENCH_DATABASE_URL:-postgresql+asyncpg://user:password@localhost:55433/behaviordb}"
cd "$(dirname "$0")/../backend" || exit 1

FAILED=0
check() { # check <label> <actual> <expected>
  if [ "$2" = "$3" ]; then echo "  PASS  $1 = $2"; else echo "  FAIL  $1 = '$2' (expected '$3')"; FAILED=1; fi
}
q() { docker exec -i habitos-pg-test psql -tA -U user -d behaviordb -c "$1" 2>&1 | tr -d '\r'; }
fks() { q "select conrelid::regclass::text||':'||confdeltype::text from pg_constraint where contype='f' and confrelid='behaviors'::regclass order by 1;"; }
counts() { echo "$(q 'select count(*) from behaviors')/$(q 'select count(*) from scheduled_behaviors')/$(q 'select count(*) from completion_logs')"; }

echo "== STEP 1: upgrade to b96cd1f49448 =="
uv run alembic upgrade b96cd1f49448 2>&1 | tail -3
check "revision" "$(q 'select version_num from alembic_version')" "b96cd1f49448"

echo "== STEP 2: seed legacy data (nonzero impact_on_*) =="
docker exec -i habitos-pg-test psql -v ON_ERROR_STOP=1 -U user -d behaviordb <<'SQL' >/dev/null
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
uv run alembic upgrade head 2>&1 | tail -4 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "e1f2a3b4c5d6"
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

echo "== STEP 4: downgrade past e1f2a3b4c5d6 =="
uv run alembic downgrade d4e5f6a7b8c9 2>&1 | tail -3 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "d4e5f6a7b8c9"
check "history rows survive e1f2 downgrade" "$(counts)" "1/1/1"
echo "  FKs after e1f2 downgrade (c=CASCADE): $(fks | tr '\n' ' ')"
check "scheduled FK reverted to CASCADE" "$(q "select confdeltype from pg_constraint where conrelid='scheduled_behaviors'::regclass and contype='f' and confrelid='behaviors'::regclass")" "c"
check "completion FK reverted to CASCADE" "$(q "select confdeltype from pg_constraint where conrelid='completion_logs'::regclass and contype='f' and confrelid='behaviors'::regclass")" "c"

echo "== STEP 5: downgrade past c1a2b3c4d5e6 =="
uv run alembic downgrade b96cd1f49448 2>&1 | tail -3 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "b96cd1f49448"
check "history rows survive c1 downgrade" "$(counts)" "1/1/1"
echo "  restored legacy impacts: $(q "select impact_on_health||','||impact_on_productivity||','||impact_on_learning from behaviors")"
check "restored health impact" "$(q "select impact_on_health from behaviors")" "0.9"
check "restored productivity impact" "$(q "select impact_on_productivity from behaviors")" "0.3"
check "restored learning impact" "$(q "select impact_on_learning from behaviors")" "0.25"
check "objective_impacts dropped" "$(q "select count(*) from information_schema.tables where table_name='objective_impacts'")" "0"

echo "== STEP 6: upgrade head again =="
uv run alembic upgrade head 2>&1 | tail -4 || FAILED=1
check "revision" "$(q 'select version_num from alembic_version')" "e1f2a3b4c5d6"
check "history rows survive second upgrade" "$(counts)" "1/1/1"
check "objective_impacts count" "$(q 'select count(*) from objective_impacts')" "3"
check "health impact" "$(q "select impact_score from objective_impacts where objective_type='HEALTH'")" "0.9"
echo "  FKs after second upgrade: $(fks | tr '\n' ' ')"
check "scheduled FK RESTRICT again" "$(q "select confdeltype from pg_constraint where conrelid='scheduled_behaviors'::regclass and contype='f' and confrelid='behaviors'::regclass")" "r"

echo
if [ "$FAILED" -eq 0 ]; then echo "RESULT: ALL CHECKS PASSED"; else echo "RESULT: FAILURES PRESENT"; fi
exit "$FAILED"
