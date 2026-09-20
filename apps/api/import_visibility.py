"""HTTP visibility for import relationships; never alter stored lineage."""

from collections.abc import Iterable
from itertools import batched
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from packages.database.models import DataManifest, ImportBatch, ImportJob


def manifest_query() -> Select[tuple[DataManifest]]:
    # Null/deleted parents confer no workspace HTTP authority.
    return select(DataManifest).join(ImportJob, ImportJob.id == DataManifest.job_id)


def visible_import_ids(
    session: Session,
    model: type[DataManifest] | type[ImportBatch] | type[ImportJob],
    identifiers: Iterable[UUID | None],
) -> set[UUID]:
    """Resolve related IDs independently, using the request's scoped session.

    Bounded batches avoid per-row lookups and database parameter limits. Only
    explicit import-family authority paths belong here, not arbitrary FK traversal.
    """
    keys = {key for key in identifiers if key is not None}
    query = select(model.id)
    if model is DataManifest:
        query = manifest_query().with_only_columns(DataManifest.id)
    elif model is ImportBatch:
        query = query.join(ImportJob, ImportJob.id == ImportBatch.job_id)
    visible: set[UUID] = set()
    for batch in batched(keys, 500):
        visible.update(session.scalars(query.where(model.id.in_(batch))))
    return visible
