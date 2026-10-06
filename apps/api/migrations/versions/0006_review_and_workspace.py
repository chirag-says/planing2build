"""Review decisions and the project workspace: specification masters, stage instances, project
specification lines and their ledger.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-04

Seeds (data migration, DATA_ARCHITECTURE section 12):
- The three specification packages and the 67 specification masters, version 1, from
  migrations/data/spec_lines_v1.json, which `tools/extract_s04_spec_lines.py --check` proves equal
  to S04 (product-owner-approved v1 seed, Chirag 2026-10-04, ruling 2.5). Structural lines (†:
  A01, A02, A04, A05, A09, A12, A13, A19) carry no brand category and engineer sign-off PENDING
  (rulings D-03 and 2.4). The file is frozen; a change is a new master version and a migration.
"""

import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPEC_LINES_V1 = Path(__file__).resolve().parents[1] / "data" / "spec_lines_v1.json"
STAGE_STATES = (
    "'NOT_STARTED', 'IN_PROGRESS', 'COMPLETION_REQUESTED', 'COMPLETED', 'BLOCKED', 'ON_HOLD'"
)
GATE_STATUSES = "'NOT_INSPECTED', 'SCHEDULED', 'OPEN_NC', 'CLEARED'"
LINE_STATES = "'SPECIFIED', 'OPTIONS_ISSUED', 'CHOSEN', 'PURCHASED', 'INSTALLED', 'VERIFIED'"
SIGNOFF = "'PENDING', 'SIGNED', 'NOT_REQUIRED'"


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    packages = op.create_table(
        "spec_packages",
        sa.Column("code", sa.String(1), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("issued", sa.String(120), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
    )
    masters = op.create_table(
        "spec_line_masters",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column(
            "package",
            sa.String(1),
            sa.ForeignKey("spec_packages.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("item", sa.String(120), nullable=False),
        sa.Column("consuming_stages", pg.ARRAY(sa.SmallInteger()), nullable=False),
        sa.Column("decide_by_weeks", sa.SmallInteger(), nullable=False),
        sa.Column("verified_at", sa.String(120)),
        sa.Column("brand_category", sa.String(60)),
        sa.Column("is_structural", sa.Boolean(), nullable=False),
        sa.Column("is_long_lead", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "NOT (is_structural AND brand_category IS NOT NULL)", name="structural_has_no_brand"
        ),
        sa.CheckConstraint("decide_by_weeks > 0", name="decide_by_positive"),
        sa.CheckConstraint("cardinality(consuming_stages) >= 1", name="has_consuming_stage"),
    )
    versions = op.create_table(
        "spec_line_master_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "code",
            sa.String(3),
            sa.ForeignKey("spec_line_masters.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("performance_specification", sa.Text(), nullable=False),
        sa.Column("engineer_signoff", sa.String(15), nullable=False),
        sa.Column("approved_note", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.Uuid()),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("code", "version"),
        sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="status"),
        sa.CheckConstraint(f"engineer_signoff IN ({SIGNOFF})", name="engineer_signoff"),
    )
    op.create_index(
        "uq_spec_line_master_versions_one_active",
        "spec_line_master_versions",
        ["code"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )

    op.create_table(
        "stage_instances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "stage_master_id",
            sa.Uuid(),
            sa.ForeignKey("stage_masters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stage_number", sa.SmallInteger(), nullable=False),
        sa.Column("floor", sa.SmallInteger()),
        sa.Column("sequence", sa.SmallInteger(), nullable=False),
        sa.Column("state", sa.String(25), nullable=False),
        sa.Column("is_gate", sa.Boolean(), nullable=False),
        sa.Column("gate_status", sa.String(20)),
        sa.Column("is_payment_milestone", sa.Boolean(), nullable=False),
        sa.Column("planned_start", sa.Date()),
        sa.Column("planned_end", sa.Date()),
        sa.Column("actual_start", sa.Date()),
        sa.Column("actual_end", sa.Date()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint(
            "project_id", "stage_number", "floor", postgresql_nulls_not_distinct=True
        ),
        sa.CheckConstraint(f"state IN ({STAGE_STATES})", name="state"),
        sa.CheckConstraint(
            f"gate_status IS NULL OR gate_status IN ({GATE_STATUSES})", name="gate_status"
        ),
        sa.CheckConstraint("(gate_status IS NOT NULL) = is_gate", name="gate_status_on_gates"),
        sa.CheckConstraint("stage_number BETWEEN 1 AND 16", name="stage_number"),
        sa.CheckConstraint("floor IS NULL OR floor BETWEEN -1 AND 3", name="floor"),
    )
    op.create_index(
        "ix_stage_instances_project_sequence", "stage_instances", ["project_id", "sequence"]
    )

    op.create_table(
        "project_spec_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(3),
            sa.ForeignKey("spec_line_masters.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "master_version_id",
            sa.Uuid(),
            sa.ForeignKey("spec_line_master_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("issued_criteria", sa.Text(), nullable=False),
        sa.Column("engineer_signoff", sa.String(15), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("is_long_lead", sa.Boolean(), nullable=False),
        sa.Column("decide_by", sa.Date()),
        sa.Column(
            "consuming_stage_instance_id",
            sa.Uuid(),
            sa.ForeignKey("stage_instances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("project_id", "code"),
        sa.CheckConstraint(f"state IN ({LINE_STATES})", name="state"),
        sa.CheckConstraint(f"engineer_signoff IN ({SIGNOFF})", name="engineer_signoff"),
    )
    op.create_index(
        "ix_project_spec_lines_project_state", "project_spec_lines", ["project_id", "state"]
    )

    op.create_table(
        "spec_line_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "line_id",
            sa.Uuid(),
            sa.ForeignKey("project_spec_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(20)),
        sa.Column("to_state", sa.String(20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("actor_role", sa.String(30)),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", pg.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.create_index("ix_spec_line_events_line_at", "spec_line_events", ["line_id", "at"])
    op.execute(
        "CREATE TRIGGER spec_line_events_append_only BEFORE UPDATE OR DELETE ON spec_line_events "
        "FOR EACH ROW EXECUTE FUNCTION p2b_forbid_mutation()"
    )

    seed = json.loads(SPEC_LINES_V1.read_text(encoding="utf-8"))
    op.bulk_insert(
        packages,
        [
            {"code": p["code"], "name": p["name"], "issued": p["issued"], "sequence": index + 1}
            for index, p in enumerate(seed["packages"])
        ],
    )
    op.bulk_insert(
        masters,
        [
            {
                "code": line["code"],
                "package": line["package"],
                "sequence": index + 1,
                "item": line["item"],
                "consuming_stages": line["consuming_stages"],
                "decide_by_weeks": line["decide_by_weeks"],
                "verified_at": line["verified_at"],
                "brand_category": line["brand_category"],
                "is_structural": line["is_structural"],
                "is_long_lead": line["is_long_lead"],
            }
            for index, line in enumerate(seed["lines"])
        ],
    )
    op.bulk_insert(
        versions,
        [
            {
                "id": uuid.uuid4(),
                "code": line["code"],
                "version": seed["version"],
                "status": "ACTIVE",
                "performance_specification": line["performance_specification"],
                "engineer_signoff": line["engineer_signoff"],
                "approved_note": seed["approved_note"],
            }
            for line in seed["lines"]
        ],
    )
    op.execute("UPDATE spec_line_master_versions SET activated_at = now()")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
                GRANT SELECT ON spec_packages, spec_line_masters, spec_line_master_versions TO app_rw;
                GRANT SELECT, INSERT, UPDATE ON stage_instances, project_spec_lines TO app_rw;
                GRANT SELECT, INSERT ON spec_line_events TO app_rw;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    for table in (
        "spec_line_events",
        "project_spec_lines",
        "stage_instances",
        "spec_line_master_versions",
        "spec_line_masters",
        "spec_packages",
    ):
        op.drop_table(table)
