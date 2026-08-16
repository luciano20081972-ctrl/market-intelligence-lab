# ruff: noqa: E501
from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import text

from packages.core.config import get_settings
from packages.database.phase5_reconciliation import LEGACY_REVISION
from packages.database.session import create_database_engine

USER_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
WORKSPACE_ID = uuid.UUID("10000000-0000-4000-8000-000000000002")
MEMBERSHIP_ID = uuid.UUID("10000000-0000-4000-8000-000000000003")
JOB_ID = uuid.UUID("10000000-0000-4000-8000-000000000004")
TRANSITION_ID = uuid.UUID("10000000-0000-4000-8000-000000000005")
LEDGER_ID = uuid.UUID("10000000-0000-4000-8000-000000000006")
HEARTBEAT_ID = uuid.UUID("10000000-0000-4000-8000-000000000007")
FRESHNESS_ID = uuid.UUID("10000000-0000-4000-8000-000000000008")
SIGNAL_ID = uuid.UUID("10000000-0000-4000-8000-000000000009")
ALERT_ID = uuid.UUID("10000000-0000-4000-8000-00000000000a")
FIXTURE_TIME = datetime(2026, 8, 15, 12, tzinfo=UTC)


def main() -> int:
    settings = get_settings()
    if settings.environment.lower() not in {"test", "ci"}:
        raise SystemExit("Phase-5 fixture refuses to run outside test/CI")
    if not settings.database_url.startswith("postgresql"):
        raise SystemExit("Phase-5 fixture requires disposable PostgreSQL")
    engine = create_database_engine(settings.database_url)
    payload = json.dumps({"fixture": "phase5-reconciliation"}, sort_keys=True)
    empty = json.dumps({}, sort_keys=True)
    try:
        with engine.begin() as connection:
            revisions = set(connection.scalars(text("SELECT version_num FROM alembic_version")))
            if revisions != {LEGACY_REVISION}:
                raise RuntimeError(f"fixture requires legacy revision {LEGACY_REVISION}")
            common = {"now": FIXTURE_TIME}
            connection.execute(
                text(
                    "INSERT INTO user_profiles "
                    "(id,auth_subject,email,display_name,email_verified,is_disabled,created_at,updated_at) "
                    "VALUES (:id,:subject,:email,:name,true,false,:now,:now)"
                ),
                {
                    **common,
                    "id": USER_ID,
                    "subject": "fixture-supabase-owner-subject",
                    "email": "owner@phase5.example.test",
                    "name": "Phase-5 Owner",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO workspaces (id,name,slug,created_by_user_id,created_at,updated_at) "
                    "VALUES (:id,:name,:slug,:user_id,:now,:now)"
                ),
                {
                    **common,
                    "id": WORKSPACE_ID,
                    "name": "Phase-5 Fixture",
                    "slug": "phase5-production-fixture",
                    "user_id": USER_ID,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO workspace_memberships "
                    "(id,workspace_id,user_id,role,created_at,updated_at) "
                    "VALUES (:id,:workspace_id,:user_id,'owner',:now,:now)"
                ),
                {**common, "id": MEMBERSHIP_ID, "workspace_id": WORKSPACE_ID, "user_id": USER_ID},
            )
            connection.execute(
                text(
                    "INSERT INTO compute_jobs "
                    "(id,workspace_id,requested_by_user_id,submission_key,job_type,job_class,priority,"
                    "state,deadline,symbols,date_start,date_end,parameters,strategy_version,"
                    "hypothesis_version,model_version,input_manifest,input_manifest_hash,"
                    "data_provenance,data_version,estimated_cpu,estimated_ram_mb,"
                    "estimated_runtime_seconds,estimated_cost_usd,max_cost_usd,selected_provider,"
                    "cloud_execution_id,attempt_count,max_attempts,checkpoint_state,result_manifest,"
                    "error_classification,error_detail,created_at,started_at,completed_at,updated_at) "
                    "VALUES (:id,:workspace_id,:user_id,'fixture-job','fixture','INTERACTIVE_LIGHT',10,"
                    "'SUCCEEDED',NULL,CAST(:payload AS json),:day,:day,CAST(:empty AS json),NULL,NULL,"
                    "'fixture-v1',CAST(:payload AS json),:hash,CAST(:payload AS json),'fixture-v1',"
                    ":cpu,256,30,:cost,:cost,'local',NULL,1,3,CAST(:empty AS json),"
                    "CAST(:payload AS json),NULL,NULL,:now,:now,:now,:now)"
                ),
                {
                    **common,
                    "id": JOB_ID,
                    "workspace_id": WORKSPACE_ID,
                    "user_id": USER_ID,
                    "payload": payload,
                    "empty": empty,
                    "day": date(2026, 8, 15),
                    "hash": "a" * 64,
                    "cpu": Decimal("1.0"),
                    "cost": Decimal("0.0"),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO compute_job_transitions "
                    "(id,job_id,from_state,to_state,reason,details,created_at) "
                    "VALUES (:id,:job_id,'LOCAL_RUNNING','SUCCEEDED','fixture',CAST(:payload AS json),:now)"
                ),
                {**common, "id": TRANSITION_ID, "job_id": JOB_ID, "payload": payload},
            )
            connection.execute(
                text(
                    "INSERT INTO cloud_usage_ledger "
                    "(id,workspace_id,job_id,provider,estimated_usd,observed_usd,task_count,usage_date,created_at) "
                    "VALUES (:id,:workspace_id,:job_id,'local',0,0,1,:day,:now)"
                ),
                {
                    **common,
                    "id": LEDGER_ID,
                    "workspace_id": WORKSPACE_ID,
                    "job_id": JOB_ID,
                    "day": date(2026, 8, 15),
                },
            )
            connection.execute(
                text(
                    "INSERT INTO market_supervisor_heartbeats "
                    "(id,instance_id,session_state,cloud_enabled,provider_health,scheduler_state,"
                    "last_signal_scan_at,last_error,heartbeat_at,started_at) "
                    "VALUES (:id,'fixture-supervisor','CLOSED',false,CAST(:payload AS json),"
                    "CAST(:empty AS json),:now,NULL,:now,:now)"
                ),
                {**common, "id": HEARTBEAT_ID, "payload": payload, "empty": empty},
            )
            connection.execute(
                text(
                    "INSERT INTO data_freshness_observations "
                    "(id,workspace_id,source,symbol,market_timestamp,received_at,processed_at,"
                    "age_seconds,classification,details) VALUES "
                    "(:id,:workspace_id,'fixture','AAPL',:now,:now,:now,0,'REAL_TIME',CAST(:payload AS json))"
                ),
                {**common, "id": FRESHNESS_ID, "workspace_id": WORKSPACE_ID, "payload": payload},
            )
            connection.execute(
                text(
                    "INSERT INTO decision_signals "
                    "(id,workspace_id,symbol,decision,confidence,horizon,market_regime,evidence,"
                    "contradicting_signals,entry_zone,invalidation_rule,risk_reference,freshness,"
                    "strategy_version,reproducibility_manifest,created_at) VALUES "
                    "(:id,:workspace_id,'AAPL','WATCH',:confidence,'1d','fixture',CAST(:payload AS json),"
                    "CAST(:empty AS json),CAST(:empty AS json),'fixture-only',CAST(:empty AS json),"
                    "CAST(:payload AS json),'fixture-v1',CAST(:payload AS json),:now)"
                ),
                {
                    **common,
                    "id": SIGNAL_ID,
                    "workspace_id": WORKSPACE_ID,
                    "confidence": Decimal("0.5"),
                    "payload": payload,
                    "empty": empty,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO alert_events "
                    "(id,workspace_id,category,severity,dedupe_key,title,message,payload,channel,status,"
                    "occurrence_count,cooldown_until,last_seen_at,created_at) VALUES "
                    "(:id,:workspace_id,'fixture','INFO','fixture-alert','Fixture','Synthetic only',"
                    "CAST(:payload AS json),'in_app','RESOLVED',1,NULL,:now,:now)"
                ),
                {**common, "id": ALERT_ID, "workspace_id": WORKSPACE_ID, "payload": payload},
            )
    finally:
        engine.dispose()
    print("Phase-5 reconciliation fixture created in disposable PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
