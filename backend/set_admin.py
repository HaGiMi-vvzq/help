"""Promote a user to admin role.

Usage:
    cd backend
    python set_admin.py <username>    # promote to admin
    python set_admin.py <username> --revoke  # revoke admin role
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import async_session
from app.models.user import User


async def set_admin(username: str, revoke: bool = False):
    async with async_session() as db:
        user = await db.scalar(select(User).where(User.username == username))
        if not user:
            print(f"Error: User '{username}' not found. Register first.")
            return

        new_role = "user" if revoke else "admin"
        old_role = user.role
        user.role = new_role
        await db.commit()
        await db.refresh(user)

        if revoke:
            print(f"Revoked admin from '{username}': {old_role} -> {new_role}")
        else:
            print(f"Promoted '{username}' to admin: {old_role} -> {new_role}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    username = sys.argv[1]
    revoke = "--revoke" in sys.argv
    asyncio.run(set_admin(username, revoke))


if __name__ == "__main__":
    main()
