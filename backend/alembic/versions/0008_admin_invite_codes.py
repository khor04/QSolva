"""Admin self-registration via invite code, replacing manual SQL role
promotion. Adds admin_invite_codes (hashed, single-use by default, optional
expiry) and extends the existing handle_new_user() trigger to read a
requested role + code from signup metadata: if the caller asked for 'admin',
the code must atomically claim an unused, unexpired, unrevoked row or the
whole signup is rejected (raising inside an AFTER INSERT trigger rolls back
the auth.users insert too, so no orphaned account is left behind). Codes are
minted with a one-time SQL insert (see docs/SETUP.md) — no admin-management
UI, since this project only ever needs a handful of admin accounts.

The code itself is hashed (md5 — no crypto extension needed, and this is
just to avoid storing invite codes in plaintext, not to resist a targeted
attack) so a DB read doesn't reveal usable codes.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_HANDLE_NEW_USER = """
create or replace function public.handle_new_user()
returns trigger as $$
declare
    requested_role text := coalesce(new.raw_user_meta_data->>'requested_role', 'staff');
    submitted_code text := new.raw_user_meta_data->>'admin_code';
    claimed_hash text;
    final_role user_role := 'staff';
begin
    if requested_role = 'admin' then
        update admin_invite_codes
        set used_count = used_count + 1
        where code_hash = md5(coalesce(submitted_code, ''))
          and not revoked
          and (expires_at is null or expires_at > now())
          and used_count < max_uses
        returning code_hash into claimed_hash;

        if claimed_hash is null then
            raise exception 'Invalid or expired admin invite code';
        end if;

        final_role := 'admin';
    end if;

    insert into public.users (id, name, email, role)
    values (
        new.id,
        coalesce(new.raw_user_meta_data->>'name', new.email),
        new.email,
        final_role
    );
    return new;
end;
$$ language plpgsql security definer set search_path = public;
"""

OLD_HANDLE_NEW_USER = """
create or replace function public.handle_new_user()
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
"""


def upgrade() -> None:
    op.execute(
        """
        create table admin_invite_codes (
            code_hash text primary key,
            created_by uuid references users(id),
            expires_at timestamptz,
            max_uses int not null default 1,
            used_count int not null default 0,
            revoked boolean not null default false,
            created_at timestamptz not null default now()
        )
        """
    )
    op.execute(NEW_HANDLE_NEW_USER)


def downgrade() -> None:
    op.execute(OLD_HANDLE_NEW_USER)
    op.execute("drop table admin_invite_codes")
