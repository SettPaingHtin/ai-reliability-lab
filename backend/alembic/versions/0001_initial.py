"""initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(1000)),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("expected", sa.Text),
        sa.Column("context", sa.Text),
        sa.Column("rules", sa.JSON, nullable=False),
        sa.Column("metadata", sa.JSON, nullable=False),
    )
    op.create_index("ix_eval_cases_dataset_id", "eval_cases", ["dataset_id"])
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("passed", sa.Integer),
        sa.Column("failed", sa.Integer),
        sa.Column("errored", sa.Integer),
        sa.Column("pass_rate", sa.Float),
        sa.Column("avg_latency_ms", sa.Float),
        sa.Column("p50_latency_ms", sa.Float),
        sa.Column("p95_latency_ms", sa.Float),
        sa.Column("total_tokens", sa.Integer),
        sa.Column("total_cost_usd", sa.Float),
        sa.Column("error_message", sa.String(500)),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("started_at", TS),
        sa.Column("finished_at", TS),
        sa.CheckConstraint("status in ('queued','running','completed','failed')", name="ck_runs_status"),
    )
    op.create_index("ix_runs_project_created", "runs", ["project_id", "created_at"])
    op.create_index("ix_runs_dataset_id", "runs", ["dataset_id"])
    op.create_table(
        "results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("eval_cases.id", ondelete="SET NULL")),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("input_snapshot", sa.Text, nullable=False),
        sa.Column("expected_snapshot", sa.Text),
        sa.Column("context_snapshot", sa.Text),
        sa.Column("rules_snapshot", sa.JSON, nullable=False),
        sa.Column("output", sa.Text),
        sa.Column("score", sa.Float),
        sa.Column("score_details", sa.JSON, nullable=False),
        sa.Column("latency_ms", sa.Float),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Float),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("error", sa.String(500)),
        sa.UniqueConstraint("run_id", "case_id", name="uq_results_run_case"),
        sa.CheckConstraint("status in ('passed','failed','error')", name="ck_results_status"),
    )
    op.create_index("ix_results_run_status", "results", ["run_id", "status"])


def downgrade() -> None:
    for table in ("results", "runs", "eval_cases", "datasets", "projects"):
        op.drop_table(table)
