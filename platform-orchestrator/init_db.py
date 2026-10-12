"""
Database Initialization Script for Platform Orchestrator Service.
Creates SQLite database with all 8 enterprise tables, performance indexes, and initial configuration.
Usage:
    python init_db.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.storage.orchestrator_storage import OrchestratorStorage


def main():
    print("=================================================================")
    print("Platform Orchestrator — Database Initialization & Schema Setup")
    print("=================================================================")

    storage = OrchestratorStorage()
    summary = storage.get_database_summary()

    print(f"\n[+] Database Location: {summary['database_path']}")
    print("[+] Status: READY\n")
    print("Tables & Current Row Counts:")
    print("-----------------------------------------------------------------")
    for table_name, count in summary["table_counts"].items():
        print(f"  • {table_name:<35} : {count} rows")
    print("-----------------------------------------------------------------")
    print("\nAll 8 core schema domains initialized successfully:")
    print("  1. orchestrator_runs              (Workflow run lifecycle & version locks)")
    print("  2. orchestrator_checkpoints       (Durable Human-in-the-Loop checkpoints)")
    print("  3. orchestrator_task_queue        (Asynchronous dispatch queue & retries)")
    print("  4. orchestrator_telemetry_spans   (OpenTelemetry distributed trace spans)")
    print("  5. orchestrator_telemetry_logs    (Correlated structured execution logs)")
    print("  6. orchestrator_telemetry_metrics (Point-in-time & aggregated metrics)")
    print("  7. orchestrator_audit_events      (HITL decisions & governance audit trail)")
    print("  8. orchestrator_policy_snapshots  (Immutable versioned policy rules)")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
