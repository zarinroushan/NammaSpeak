"""Create the NammaSpeak PostgreSQL schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "phrases",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("category", sa.String(255), nullable=False),
        sa.Column("kn", sa.Text(), nullable=False),
        sa.Column("roman", sa.Text(), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("tag", sa.String(255), nullable=False),
        sa.Column("formality", sa.String(255)),
        sa.Column("speech", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.String(255), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("speaker_avatar", sa.Text(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("related_phrase_id", sa.String(255)),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(254), unique=True),
        sa.Column("password_hash", sa.Text()),
        sa.Column("preferred_language", sa.String(8)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint("account_type IN ('guest', 'registered')"),
    )
    op.create_table(
        "saved_phrases",
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("phrase_id", sa.String(255), sa.ForeignKey("phrases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("saved_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "user_progress",
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("answered_count", sa.Integer(), server_default="0"),
        sa.Column("correct_count", sa.Integer(), server_default="0"),
        sa.Column("best_score", sa.Integer(), server_default="0"),
        sa.Column("last_active_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "phrase_learning_stats",
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("phrase_id", sa.String(255), sa.ForeignKey("phrases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("correct_count", sa.Integer(), server_default="0"),
        sa.Column("mistakes", sa.Integer(), server_default="0"),
        sa.Column("needs_revision", sa.Integer(), server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime()),
    )
    op.create_table(
        "translation_cache",
        sa.Column("source_version", sa.String(255), primary_key=True),
        sa.Column("target_lang", sa.String(8), primary_key=True),
        sa.Column("translation_key", sa.String(255), primary_key=True),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "phrase_translations",
        sa.Column("phrase_id", sa.String(255), sa.ForeignKey("phrases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("target_lang", sa.String(8), primary_key=True),
        sa.Column("meaning", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "scenario_translations",
        sa.Column("scenario_id", sa.String(255), primary_key=True),
        sa.Column("target_lang", sa.String(8), primary_key=True),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_why_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    for table in (
        "scenario_translations", "phrase_translations", "translation_cache",
        "phrase_learning_stats", "user_progress", "saved_phrases", "users",
        "scenarios", "phrases",
    ):
        op.drop_table(table)
