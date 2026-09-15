"""Initial Qsolva schema: users, tickets, messages, embeddings, AI suggestions,
feedback, notifications. Also wires the Supabase auth.users -> public.users
provisioning trigger, and RLS for the users table.

Revision ID: 0001
Revises:
Create Date: 2026-09-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
create extension if not exists vector;

create type user_role as enum ('staff', 'admin');
create type ticket_status as enum ('open', 'in_progress', 'escalated', 'resolved', 'closed');
create type ticket_priority as enum ('low', 'medium', 'high', 'critical');
create type ticket_category as enum ('network', 'hardware', 'software', 'email_account', 'access', 'other');
create type priority_source as enum ('ai', 'manual');
create type ai_suggestion_state as enum ('available', 'accepted', 'rejected', 'not_applicable');
create type feedback_outcome as enum ('solved', 'partially_solved', 'did_not_solve', 'wrong_recommendation', 'other');
create type notification_type as enum (
    'ticket_updated', 'ticket_replied', 'ticket_resolved', 'resolution_confirm_needed',
    'new_critical_ticket', 'staff_replied', 'suggestion_failed', 'sla_risk'
);

create table users (
    id uuid primary key references auth.users(id) on delete cascade,
    name text not null,
    email text not null unique,
    role user_role not null default 'staff',
    created_at timestamptz not null default now()
);

create table tickets (
    id uuid primary key default gen_random_uuid(),
    staff_id uuid not null references users(id),
    assigned_admin_id uuid references users(id),
    title text not null,
    description text not null,
    category ticket_category not null,
    status ticket_status not null default 'open',
    priority ticket_priority not null default 'medium',
    priority_confidence numeric,
    priority_source priority_source not null default 'ai',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    resolved_at timestamptz,
    closed_at timestamptz
);
create index idx_tickets_staff_id on tickets(staff_id);
create index idx_tickets_assigned_admin_id on tickets(assigned_admin_id);
create index idx_tickets_status on tickets(status);

create table ticket_messages (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    sender_id uuid not null references users(id),
    body text not null,
    created_at timestamptz not null default now()
);
create index idx_ticket_messages_ticket_id on ticket_messages(ticket_id);

create table ticket_attachments (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    uploaded_by uuid not null references users(id),
    file_url text not null,
    created_at timestamptz not null default now()
);
create index idx_ticket_attachments_ticket_id on ticket_attachments(ticket_id);

create table ticket_embeddings (
    ticket_id uuid primary key references tickets(id) on delete cascade,
    embedding vector(768) not null,
    model_name text not null,
    updated_at timestamptz not null default now()
);
create index idx_ticket_embeddings_cosine on ticket_embeddings
    using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create table ai_suggestions (
    id uuid primary key default gen_random_uuid(),
    ticket_id uuid not null references tickets(id) on delete cascade,
    resolution_text text not null,
    confidence numeric not null,
    state ai_suggestion_state not null default 'available',
    evidence jsonb not null default '[]',
    created_at timestamptz not null default now()
);
create index idx_ai_suggestions_ticket_id on ai_suggestions(ticket_id);

create table feedback (
    id uuid primary key default gen_random_uuid(),
    ai_suggestion_id uuid references ai_suggestions(id),
    ticket_id uuid not null references tickets(id) on delete cascade,
    staff_id uuid not null references users(id),
    outcome feedback_outcome not null,
    comment text,
    created_at timestamptz not null default now()
);
create index idx_feedback_ticket_id on feedback(ticket_id);

create table notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    type notification_type not null,
    ticket_id uuid references tickets(id) on delete cascade,
    is_read boolean not null default false,
    created_at timestamptz not null default now()
);
create index idx_notifications_user_id on notifications(user_id, is_read);

-- Auto-provision a public.users row (role='staff') whenever someone signs up
-- via Supabase Auth. Admin accounts are promoted manually afterward:
--   update public.users set role = 'admin' where email = '...';
create function public.handle_new_user()
returns trigger as $$
begin
    insert into public.users (id, name, email, role)
    values (
        new.id,
        coalesce(new.raw_user_meta_data->>'name', new.email),
        new.email,
        'staff'
    );
    return new;
end;
$$ language plpgsql security definer set search_path = public;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

-- RLS: only the users table is queried directly by the frontend (via the
-- Supabase client, to resolve the signed-in user's role). Every other table
-- is accessed exclusively through the FastAPI backend using the service-role
-- key, so RLS is enabled with no policies -> inaccessible via the anon key.
alter table users enable row level security;
create policy "users can read own profile" on users
    for select using (auth.uid() = id);

alter table tickets enable row level security;
alter table ticket_messages enable row level security;
alter table ticket_attachments enable row level security;
alter table ticket_embeddings enable row level security;
alter table ai_suggestions enable row level security;
alter table feedback enable row level security;
alter table notifications enable row level security;
"""

DOWNGRADE_SQL = """
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.handle_new_user();

drop table if exists notifications;
drop table if exists feedback;
drop table if exists ai_suggestions;
drop table if exists ticket_embeddings;
drop table if exists ticket_attachments;
drop table if exists ticket_messages;
drop table if exists tickets;
drop table if exists users;

drop type if exists notification_type;
drop type if exists feedback_outcome;
drop type if exists ai_suggestion_state;
drop type if exists priority_source;
drop type if exists ticket_category;
drop type if exists ticket_priority;
drop type if exists ticket_status;
drop type if exists user_role;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
