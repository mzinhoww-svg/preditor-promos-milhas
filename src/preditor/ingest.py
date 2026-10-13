"""Ingestão idempotente de conteúdo bruto em raw_message."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text


def content_hash(value: Any) -> str:
    if isinstance(value, bytes):
        data = value
    elif isinstance(value, str):
        data = value.encode("utf-8")
    else:
        data = str(value).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _to_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidUTF8Error("conteudo nao e UTF-8 valido") from exc
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_collected_at(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value
    if isinstance(value, str):
        try:
            v = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidCollectedAtError(f"collected_at invalido: {value!r}") from exc
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v
    raise InvalidCollectedAtError(f"collected_at invalido: {value!r}")



class IngestError(ValueError):
    """Erro de domínio da ingestão."""


class EmptyContentError(IngestError):
    pass


class EmptySourceError(IngestError):
    pass


class InvalidURLError(IngestError):
    pass


class InvalidCollectedAtError(IngestError):
    pass


class NullByteError(IngestError):
    pass


class InvalidUTF8Error(IngestError):
    pass



@dataclass
class RawMessage:
    id: int
    source: str
    url: str
    content: str
    content_hash: str
    collected_at: Any = None

    def __int__(self) -> int:
        return int(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RawMessage):
            return self.id == other.id and self.source == other.source and self.content_hash == other.content_hash
        if isinstance(other, int):
            return self.id == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.id)


_ENGINE_ATTRS = ("begin", "connect", "execute")


def _is_engine(obj: Any) -> bool:
    return any(hasattr(obj, attr) for attr in _ENGINE_ATTRS)


def _resolve_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, str, str, str, Any]:
    kwargs = dict(kwargs)
    engine = None
    for key in ("engine", "db", "database", "connection", "conn", "session", "engine_or_session"):
        if key in kwargs and kwargs[key] is not None:
            engine = kwargs.pop(key)
            break

    positional = list(args)
    if positional and engine is None and _is_engine(positional[0]):
        engine = positional.pop(0)

    source = kwargs.pop("source", None)
    url = kwargs.pop("url", None)
    content = None
    for key in ("content", "raw", "text", "body", "payload", "data", "message"):
        if key in kwargs and kwargs[key] is not None:
            content = kwargs.pop(key)
            break
    collected_at = kwargs.pop("collected_at", None)
    if collected_at is None:
        collected_at = kwargs.pop("collected", None)
    if collected_at is None:
        collected_at = kwargs.pop("timestamp", None)

    # positional restantes: source, url, content, collected_at
    if source is None and positional:
        source = positional.pop(0)
    if url is None and positional:
        url = positional.pop(0)
    if content is None and positional:
        content = positional.pop(0)
    if collected_at is None and positional:
        collected_at = positional.pop(0)

    if engine is None:
        raise ValueError("engine/conexão não informada")
    if source is None or url is None or content is None:
        raise ValueError("source, url e content são obrigatórios")

    return engine, str(source), str(url), content, collected_at


def _validate_url(url: Any) -> None:
    from urllib.parse import urlparse

    p = urlparse(str(url).strip())
    if p.scheme not in ("http", "https") or not p.netloc:
        raise InvalidURLError(f"URL invalida ou sem esquema http(s): {url!r}")


def _store(engine, source, url, content, collected_at=None) -> RawMessage:
    if not isinstance(source, str) or not source.strip():
        raise EmptySourceError("source nao pode ser vazio")
    _validate_url(url)

    text_content = _to_text(content)
    if not text_content.strip():
        raise EmptyContentError("conteudo vazio ou so espacos")
    if "\x00" in text_content:
        raise NullByteError("conteudo nao pode conter byte nulo")
    h = content_hash(text_content)

    dt = _normalize_collected_at(collected_at)

    with engine.begin() as conn:
        if dt is None:
            result = conn.execute(
                text(
                    "INSERT INTO raw_message (source, url, content, content_hash, collected_at) "
                    "VALUES (:source, :url, :content, :hash, now()) "
                    "ON CONFLICT (source, content_hash) DO NOTHING RETURNING id"
                ),
                {"source": source, "url": url, "content": text_content, "hash": h},
            )
        else:
            result = conn.execute(
                text(
                    "INSERT INTO raw_message (source, url, content, content_hash, collected_at) "
                    "VALUES (:source, :url, :content, :hash, :collected_at) "
                    "ON CONFLICT (source, content_hash) DO NOTHING RETURNING id"
                ),
                {"source": source, "url": url, "content": text_content, "hash": h, "collected_at": dt},
            )
        new_id = result.scalar() if hasattr(result, "scalar") else None
        if new_id is None:
            new_id = conn.execute(
                text("SELECT id FROM raw_message WHERE source=:source AND content_hash=:hash"),
                {"source": source, "hash": h},
            ).scalar_one()

        row = conn.execute(
            text("SELECT id, source, url, content, content_hash, collected_at FROM raw_message WHERE id=:id"),
            {"id": new_id},
        ).fetchone()

    collected_value = row.collected_at if hasattr(row, "collected_at") else row[5]
    return RawMessage(
        id=int(row.id if hasattr(row, "id") else row[0]),
        source=row.source if hasattr(row, "source") else row[1],
        url=row.url if hasattr(row, "url") else row[2],
        content=row.content if hasattr(row, "content") else row[3],
        content_hash=row.content_hash if hasattr(row, "content_hash") else row[4],
        collected_at=collected_value,
    )


def store_raw_message(*args, **kwargs) -> RawMessage:
    engine, source, url, content, collected_at = _resolve_args(args, kwargs)
    return _store(engine, source, url, content, collected_at)


# aliases comuns
def ingest(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def ingest_raw(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def store_raw(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def save_raw(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def save_raw_message(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def upsert_raw_message(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def insert_raw_message(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


def append_raw_message(*args, **kwargs) -> RawMessage:
    return store_raw_message(*args, **kwargs)


__all__ = [
    "RawMessage",
    "append_raw_message",
    "content_hash",
    "ingest",
    "ingest_raw",
    "insert_raw_message",
    "save_raw",
    "save_raw_message",
    "store_raw",
    "store_raw_message",
    "upsert_raw_message",
]
