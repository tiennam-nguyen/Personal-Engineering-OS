"""SQLite derived artifact projection."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from peos.domain.artifacts.model import Artifact, Author, Provenance, SearchResult, StoredArtifact
from peos.domain.errors import (
    ArtifactNotFound,
    DuplicateArtifactId,
    IndexRebuildError,
    WorkspaceConfigurationError,
)

SCHEMA = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE artifact (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    title_folded TEXT NOT NULL,
    status TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    canonical_path TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    body_text TEXT NOT NULL,
    search_text TEXT NOT NULL
);
"""


class SQLiteArtifactIndex:
    def __init__(self, index_path: Path) -> None:
        self._path = index_path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect(self._path)
        try:
            self._create_schema(connection)
            connection.commit()
        finally:
            connection.close()

    def upsert(self, stored: StoredArtifact) -> None:
        try:
            connection = self._connect(self._path)
            try:
                self._validate_schema(connection)
                self._insert(connection, stored)
                connection.commit()
            finally:
                connection.close()
        except sqlite3.IntegrityError as error:
            message = "Artifact ID or canonical path already exists in the index."
            raise DuplicateArtifactId(message) from error

    def get(self, artifact_id: str) -> StoredArtifact:
        connection = self._connect(self._path)
        try:
            self._validate_schema(connection)
            row = connection.execute(
                "SELECT * FROM artifact WHERE id = ?", (artifact_id,)
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ArtifactNotFound("Artifact was not found in the index.")
        return self._stored_from_row(row)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not query.strip() or not 1 <= limit <= 100:
            raise WorkspaceConfigurationError("Search query or limit is invalid.")
        escaped = query.casefold().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        sql = """
            SELECT id,type,title,status,sensitivity,canonical_path,content_hash
            FROM artifact
            WHERE search_text LIKE '%' || ? || '%' ESCAPE '\\'
            ORDER BY
                CASE
                    WHEN title_folded = ? THEN 0
                    WHEN title_folded LIKE '%' || ? || '%' ESCAPE '\\' THEN 1
                    ELSE 2
                END,
                updated_at DESC,
                id ASC
            LIMIT ?
        """
        connection = self._connect(self._path)
        try:
            self._validate_schema(connection)
            rows = connection.execute(sql, (escaped, query.casefold(), escaped, limit)).fetchall()
        finally:
            connection.close()
        return [SearchResult(**dict(row)) for row in rows]

    def rebuild(self, records: list[StoredArtifact]) -> int:
        temporary = self._path.with_name(f"{self._path.name}.rebuild-{uuid.uuid4().hex}")
        backup = self._path.with_name(f"{self._path.name}.backup-{uuid.uuid4().hex}")
        try:
            self._reject_duplicate_ids(records)
            connection = self._connect(temporary)
            try:
                self._create_schema(connection)
                for record in records:
                    self._insert(connection, record)
                count = connection.execute("SELECT COUNT(*) FROM artifact").fetchone()[0]
                if count != len(records):
                    raise IndexRebuildError("Rebuilt index count does not match canonical count.")
                connection.commit()
            finally:
                connection.close()
            if self._path.exists():
                self._path.replace(backup)
            temporary.replace(self._path)
            if not self.is_healthy():
                raise IndexRebuildError("Rebuilt index failed post-swap verification.")
            if backup.exists():
                backup.unlink()
            return len(records)
        except Exception as error:
            if temporary.exists():
                temporary.unlink()
            if backup.exists() and not self._path.exists():
                backup.replace(self._path)
            if isinstance(error, IndexRebuildError):
                raise
            if isinstance(error, sqlite3.Error):
                raise IndexRebuildError("Index rebuild failed.") from error
            raise

    def is_healthy(self) -> bool:
        if not self._path.exists():
            return False
        try:
            connection = self._connect(self._path)
            try:
                self._validate_schema(connection)
            finally:
                connection.close()
        except (sqlite3.Error, WorkspaceConfigurationError):
            return False
        return True

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        return connection

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT INTO metadata(key, value) VALUES (?, ?)", ("schema_version", "1")
        )

    @staticmethod
    def _validate_schema(connection: sqlite3.Connection) -> None:
        try:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?", ("schema_version",)
            ).fetchone()
        except sqlite3.Error as error:
            raise WorkspaceConfigurationError("Artifact index schema is unavailable.") from error
        if row is None or row["value"] != "1":
            raise WorkspaceConfigurationError("Artifact index schema is incompatible.")

    @staticmethod
    def _insert(connection: sqlite3.Connection, stored: StoredArtifact) -> None:
        artifact = stored.artifact
        values = (
            artifact.id,
            artifact.type,
            artifact.schema_version,
            artifact.title,
            artifact.title.casefold(),
            artifact.status,
            artifact.sensitivity,
            artifact.workspace_id,
            artifact.created_at,
            artifact.updated_at,
            stored.canonical_path,
            artifact.content_hash,
            artifact.body,
            (artifact.title + "\n" + artifact.body).casefold(),
        )
        connection.execute(
            """INSERT INTO artifact(
                id,type,schema_version,title,title_folded,status,sensitivity,workspace_id,
                created_at,updated_at,canonical_path,content_hash,body_text,search_text
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            values,
        )

    @staticmethod
    def _reject_duplicate_ids(records: list[StoredArtifact]) -> None:
        ids = [record.artifact.id for record in records]
        if len(ids) != len(set(ids)):
            raise IndexRebuildError("Duplicate artifact ID encountered during rebuild.")

    @staticmethod
    def _stored_from_row(row: sqlite3.Row) -> StoredArtifact:
        artifact = Artifact(
            id=row["id"],
            type=row["type"],
            schema_version=row["schema_version"],
            title=row["title"],
            status=row["status"],
            workspace_id=row["workspace_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            authors=(Author(kind="human", id="user"),),
            sensitivity=row["sensitivity"],
            tags=(),
            links=(),
            provenance=Provenance(producer="human", run_id=None, source_refs=()),
            content_hash=row["content_hash"],
            body=row["body_text"],
        )
        return StoredArtifact(artifact=artifact, canonical_path=row["canonical_path"])
