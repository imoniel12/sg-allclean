import os
from pathlib import Path

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app import (
    BASE_DIR,
    Base,
    AdminUser,
    SiteSettings,
    Page,
    Service,
    Post,
    ContactField,
    NavItem,
    ContentSnippet,
    normalize_database_url,
)


MODELS = [
    AdminUser,
    SiteSettings,
    Page,
    Service,
    Post,
    ContactField,
    NavItem,
    ContentSnippet,
]


def build_engine(database_url: str):
    normalized = normalize_database_url(database_url)
    engine_kwargs = {"pool_pre_ping": True}
    if normalized.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(normalized, **engine_kwargs)


def row_to_dict(row) -> dict:
    values = {}
    for column in row.__table__.columns:
        values[column.name] = getattr(row, column.name)
    return values


def table_count(session: Session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def reset_postgres_sequence(connection, model) -> None:
    table_name = model.__tablename__
    connection.execute(
        text(
            """
            SELECT setval(
                pg_get_serial_sequence(:table_name, 'id'),
                COALESCE((SELECT MAX(id) FROM """
            + table_name
            + """), 1),
                COALESCE((SELECT MAX(id) FROM """
            + table_name
            + """), 0) > 0
            )
            """
        ),
        {"table_name": table_name},
    )


def migrate(source_url: str, target_url: str, wipe_target: bool) -> None:
    source_engine = build_engine(source_url)
    target_engine = build_engine(target_url)
    SourceSession = sessionmaker(bind=source_engine, autoflush=False, autocommit=False)
    TargetSession = sessionmaker(bind=target_engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=target_engine)

    with SourceSession() as source_session, TargetSession() as target_session:
        source_counts = {model.__tablename__: table_count(source_session, model) for model in MODELS}

        existing_rows = {
            model.__tablename__: table_count(target_session, model)
            for model in MODELS
        }
        if any(existing_rows.values()) and not wipe_target:
            non_empty = ", ".join(
                f"{table}={count}" for table, count in existing_rows.items() if count
            )
            raise RuntimeError(
                "Target database is not empty. "
                "Set WIPE_TARGET=true to replace its current content. "
                f"Existing rows: {non_empty}"
            )

        if wipe_target:
            for model in reversed(MODELS):
                target_session.execute(text(f"DELETE FROM {model.__tablename__}"))
            target_session.commit()

        copied_counts = {}
        for model in MODELS:
            rows = source_session.scalars(select(model)).all()
            for row in rows:
                target_session.add(model(**row_to_dict(row)))
            target_session.commit()
            copied_counts[model.__tablename__] = len(rows)

        if target_engine.dialect.name == "postgresql":
            with target_engine.begin() as connection:
                for model in MODELS:
                    reset_postgres_sequence(connection, model)

    print("Migration completed.")
    print(f"Source: {normalize_database_url(source_url)}")
    print(f"Target: {normalize_database_url(target_url)}")
    for table_name in copied_counts:
        print(f"{table_name}: {copied_counts[table_name]} rows")
    print("Source counts:", source_counts)


if __name__ == "__main__":
    default_source = f"sqlite:///{BASE_DIR / 'sg_allclean.db'}"
    source_url = os.environ.get("SOURCE_DATABASE_URL") or default_source
    target_url = os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
    wipe_target = os.environ.get("WIPE_TARGET", "false").lower() == "true"

    if not target_url:
        raise SystemExit(
            "Missing target database. Set TARGET_DATABASE_URL or DATABASE_URL before running the migration."
        )

    migrate(source_url, target_url, wipe_target)
