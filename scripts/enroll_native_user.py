"""Explicit local credential enrollment/reset; never creates application identities."""

from __future__ import annotations

import argparse
import getpass
import sys
import uuid
import warnings

from sqlalchemy.exc import SQLAlchemyError

from packages.auth.native import enroll
from packages.auth.service import AuthError
from packages.core.config import get_settings
from packages.database.session import create_database_engine, make_session_factory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=uuid.UUID)
    parser.add_argument("--login", required=True)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error("Secure interactive terminal required")
    settings = get_settings()
    if settings.auth_mode != "native":
        parser.error("Explicit MIL_AUTH_MODE=native required")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("New password (15–128 characters): ")
        confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        parser.error("Passwords do not match")
    engine = create_database_engine(settings.database_url)
    try:
        enroll(
            make_session_factory(engine),
            engine,
            args.user_id,
            args.login,
            password,
            reset=args.reset,
        )
    except (AuthError, SQLAlchemyError):
        print("Enrollment failed; verify profile, collision, configuration and database state.")
        return 1
    finally:
        engine.dispose()
    print("Credential enrolled. Existing application identity preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
