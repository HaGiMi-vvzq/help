"""Alembic migration — initial PostgreSQL schema (also compatible with SQLite)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a000001_production_schema'
down_revision: Union[str, Sequence[str], None] = '35e9f6eea385'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Users ──
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('password_hash', sa.String(128), nullable=False),
        sa.Column('role', sa.String(20), server_default='user', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('skill_tags', sa.JSON(), nullable=True),
        sa.Column('profile_embedding', sa.JSON(), nullable=True),
        sa.Column('avatar', sa.Text(), nullable=True),
        sa.Column('school', sa.String(100), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column('rating_score', sa.Float(), server_default='5.0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Needs ──
    op.create_table(
        'needs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('req_tags', sa.JSON(), nullable=True),
        sa.Column('need_embedding', sa.JSON(), nullable=True),
        sa.Column('selection_mode', sa.String(20), server_default='single', nullable=True),
        sa.Column('selected_user_ids', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), server_default='开放', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Messages ──
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('need_id', sa.Integer(), sa.ForeignKey('needs.id'), nullable=False),
        sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('receiver_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Matches ──
    op.create_table(
        'matches',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('need_id', sa.Integer(), sa.ForeignKey('needs.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('ai_reason', sa.Text(), nullable=False),
        sa.Column('feedback', sa.Integer(), nullable=True),
    )

    # ── Need Applications ──
    op.create_table(
        'need_applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('need_id', sa.Integer(), sa.ForeignKey('needs.id'), index=True, nullable=False),
        sa.Column('applicant_user_id', sa.Integer(), sa.ForeignKey('users.id'), index=True, nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('owner_reply', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Agent Sessions ──
    op.create_table(
        'agent_sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(200), server_default='新对话', nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('planning_state', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Agent Messages ──
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Agent Tasks ──
    op.create_table(
        'agent_tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_task_id', sa.Integer(), sa.ForeignKey('agent_tasks.id'), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=True),
        sa.Column('goal', sa.String(300), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),
        sa.Column('assigned_agent', sa.String(50), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('need_id', sa.Integer(), nullable=True),
        sa.Column('match_id', sa.Integer(), nullable=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('agent_files.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Agent Files ──
    op.create_table(
        'agent_files',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('agent_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(200), nullable=False),
        sa.Column('file_type', sa.String(20), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('extracted_info', sa.JSON(), nullable=True),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # ── Supporting tables ──
    op.create_table(
        'skill_graph',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('skill_a', sa.String(100), index=True, nullable=False),
        sa.Column('skill_b', sa.String(100), index=True, nullable=False),
        sa.Column('count', sa.Integer(), server_default='1', nullable=False),
        sa.UniqueConstraint('skill_a', 'skill_b'),
    )

    op.create_table(
        'match_memory',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('need_description', sa.Text(), nullable=False),
        sa.Column('need_embedding', sa.JSON(), nullable=False),
        sa.Column('matched_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('ai_reason', sa.Text(), nullable=False),
        sa.Column('feedback', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'behavior_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('need_id', sa.Integer(), sa.ForeignKey('needs.id'), nullable=True),
        sa.Column('extra_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'preference_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), unique=True, nullable=False),
        sa.Column('preference_vector', sa.JSON(), nullable=True),
        sa.Column('behavioral_tags', sa.JSON(), nullable=True),
        sa.Column('last_reflected_at', sa.DateTime(), nullable=True),
        sa.Column('reflection_count', sa.Integer(), server_default='0', nullable=False),
    )

    op.create_table(
        'system_config',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.String(500), server_default='', nullable=False),
    )


def downgrade() -> None:
    op.drop_table('system_config')
    op.drop_table('preference_profiles')
    op.drop_table('behavior_logs')
    op.drop_table('match_memory')
    op.drop_table('skill_graph')
    op.drop_table('agent_files')
    op.drop_table('agent_tasks')
    op.drop_table('agent_messages')
    op.drop_table('agent_sessions')
    op.drop_table('need_applications')
    op.drop_table('matches')
    op.drop_table('messages')
    op.drop_table('needs')
    op.drop_table('users')
