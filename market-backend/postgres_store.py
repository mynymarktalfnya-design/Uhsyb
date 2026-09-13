"""Small PostgreSQL-backed document store used by the existing Mongo-shaped routes.

The application routes already use a consistent document API. Keeping that API
over Neon lets us move persistence without rewriting every sale, purchase,
report, and account endpoint at once.
"""
from __future__ import annotations

import copy
import re
from threading import RLock
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import Json


_MISSING = object()


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__market_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__market_type__": "date", "value": value.isoformat()}
    if isinstance(value, Decimal):
        return {"__market_type__": "decimal", "value": str(value)}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        kind = value.get("__market_type__")
        if kind == "datetime":
            try:
                return datetime.fromisoformat(value["value"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        if kind == "date":
            try:
                return date.fromisoformat(value["value"])
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        if kind == "decimal":
            try:
                return float(value["value"])
            except (KeyError, TypeError, ValueError):
                return value.get("value")
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def _get(document: dict, path: str, default: Any = _MISSING) -> Any:
    current: Any = document
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return default
    return current


def _set(document: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _delete(document: dict, path: str) -> None:
    parts = path.split(".")
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _compare(left: Any, right: Any, op: str) -> bool:
    if left is _MISSING:
        return op in ("$ne", "$nin")
    candidates = _values(left)
    if op == "$in":
        return any(any(_compare(v, item, "$eq") for item in candidates) for v in _values(right))
    if op == "$nin":
        return not _compare(left, right, "$in")
    if op == "$ne":
        return not _compare(left, right, "$eq")
    if op == "$eq":
        if isinstance(left, list) and not isinstance(right, list):
            return right in left
        return left == right
    if op == "$exists":
        return bool(right) == (left is not _MISSING)
    if op == "$regex":
        flags = re.IGNORECASE if isinstance(right, tuple) and "i" in right[1] else 0
        pattern = right[0] if isinstance(right, tuple) else right
        return any(re.search(pattern, str(v), flags) is not None for v in candidates)
    if op in ("$gt", "$gte", "$lt", "$lte"):
        for candidate in candidates:
            try:
                if {"$gt": candidate > right, "$gte": candidate >= right,
                    "$lt": candidate < right, "$lte": candidate <= right}[op]:
                    return True
            except (TypeError, ValueError):
                continue
        return False
    if op == "$elemMatch":
        return any(
            _matches(v, right) if isinstance(v, dict) else _matches({"value": v}, {"value": right})
            for v in candidates if isinstance(v, (dict, list))
        )
    return False


def _field_matches(value: Any, condition: Any) -> bool:
    if not isinstance(condition, dict) or not any(str(k).startswith("$") for k in condition):
        if value is _MISSING:
            return condition is None
        return _compare(value, condition, "$eq")
    for op, expected in condition.items():
        if op == "$options":
            continue
        if op == "$regex":
            options = condition.get("$options", "")
            if not _compare(value, (expected, options), "$regex"):
                return False
        elif not _compare(value, expected, op):
            return False
    return True


def _matches(document: dict, query: dict | None) -> bool:
    if not query:
        return True
    for key, condition in query.items():
        if key == "$or":
            if not any(_matches(document, item) for item in condition):
                return False
            continue
        if key == "$and":
            if not all(_matches(document, item) for item in condition):
                return False
            continue
        if key == "$nor":
            if any(_matches(document, item) for item in condition):
                return False
            continue
        if key == "$expr":
            if not _eval_expr(document, condition):
                return False
            continue
        if not _field_matches(_get(document, key), condition):
            return False
    return True


def _project(document: dict, projection: dict | None) -> dict:
    if not projection:
        return copy.deepcopy(document)
    include = [k for k, v in projection.items() if v and k != "_id"]
    exclude = [k for k, v in projection.items() if not v]
    if include:
        result = {}
        if projection.get("_id", 1) and "_id" in document:
            result["_id"] = document["_id"]
        for key in include:
            value = _get(document, key)
            if value is not _MISSING:
                _set(result, key, copy.deepcopy(value))
        return result
    result = copy.deepcopy(document)
    for key in exclude:
        _delete(result, key)
    return result


def _eval_expr(document: dict, expression: Any) -> Any:
    if isinstance(expression, str) and expression.startswith("$"):
        return _get(document, expression[1:], None)
    if not isinstance(expression, dict):
        return expression
    if "$dateToString" in expression:
        spec = expression["$dateToString"]
        value = _eval_expr(document, spec.get("date"))
        if isinstance(value, datetime):
            return value.strftime(spec.get("format", "%Y-%m-%d"))
        return str(value)[:10] if value else None
    if "$ifNull" in expression:
        for item in expression["$ifNull"]:
            value = _eval_expr(document, item)
            if value is not None:
                return value
        return None
    if "$multiply" in expression:
        result = 1
        for item in expression["$multiply"]:
            result *= _eval_expr(document, item) or 0
        return result
    if "$add" in expression:
        return sum((_eval_expr(document, item) or 0) for item in expression["$add"])
    if "$subtract" in expression:
        values = expression["$subtract"]
        return (_eval_expr(document, values[0]) or 0) - (_eval_expr(document, values[1]) or 0)
    for operator, comparator in (
        ("$eq", lambda a, b: a == b),
        ("$gt", lambda a, b: a > b),
        ("$gte", lambda a, b: a >= b),
        ("$lt", lambda a, b: a < b),
        ("$lte", lambda a, b: a <= b),
    ):
        if operator in expression:
            values = expression[operator]
            left, right = (_eval_expr(document, item) for item in values)
            try:
                return comparator(left, right)
            except TypeError:
                return False
    if "$and" in expression:
        return all(_eval_expr(document, item) for item in expression["$and"])
    if "$or" in expression:
        return any(_eval_expr(document, item) for item in expression["$or"])
    if "$cond" in expression:
        condition, yes, no = expression["$cond"]
        return _eval_expr(document, yes if _eval_expr(document, condition) else no)
    return {key: _eval_expr(document, value) for key, value in expression.items()}


def _apply_update(document: dict, update: dict, inserting: bool = False) -> dict:
    result = copy.deepcopy(document)
    if not any(key.startswith("$") for key in update):
        result.update(copy.deepcopy(update))
        return result
    for key, values in update.items():
        if key == "$set" or (key == "$setOnInsert" and inserting):
            for path, value in values.items():
                _set(result, path, copy.deepcopy(value))
        elif key == "$unset":
            for path in values:
                _delete(result, path)
        elif key == "$inc":
            for path, amount in values.items():
                old = _get(result, path, 0)
                _set(result, path, (0 if old is None else old) + amount)
        elif key in ("$push", "$addToSet"):
            for path, value in values.items():
                current = _get(result, path, [])
                if not isinstance(current, list):
                    current = []
                additions = value.get("$each", []) if isinstance(value, dict) and "$each" in value else [value]
                for item in additions:
                    if key == "$push" or item not in current:
                        current.append(copy.deepcopy(item))
                _set(result, path, current)
        elif key == "$pull":
            for path, condition in values.items():
                current = _get(result, path, [])
                if isinstance(current, list):
                    current = [item for item in current if not _field_matches(item, condition)]
                    _set(result, path, current)
    return result


class PostgresCursor:
    def __init__(self, documents: Iterable[dict]):
        self.documents = list(documents)

    def sort(self, key_or_list, direction=None):
        pairs = key_or_list if isinstance(key_or_list, list) else [(key_or_list, direction or 1)]
        for key, order in reversed(pairs):
            self.documents.sort(
                key=lambda item: (item.get(key) is None, item.get(key)),
                reverse=order < 0,
            )
        return self

    def limit(self, amount: int):
        if amount:
            self.documents = self.documents[:amount]
        return self

    def skip(self, amount: int):
        self.documents = self.documents[amount:]
        return self

    def __iter__(self):
        return iter(self.documents)

    def __len__(self):
        return len(self.documents)


class PostgresCollection:
    def __init__(self, store: "PostgresStore", name: str):
        self.store = store
        self.name = name

    def _all(self) -> list[dict]:
        with self.store._cache_lock:
            if self.name in self.store._cache:
                return copy.deepcopy(self.store._cache[self.name])
        with self.store._cursor() as cur:
            cur.execute(
                "SELECT document FROM market_documents WHERE collection = %s",
                (self.name,),
            )
            documents = [_decode(row[0]) for row in cur.fetchall()]
        with self.store._cache_lock:
            self.store._cache[self.name] = copy.deepcopy(documents)
        return documents

    def _save(self, document: dict) -> None:
        document = copy.deepcopy(document)
        document.setdefault("_id", self.store.new_id())
        with self.store._cursor() as cur:
            cur.execute(
                """
                INSERT INTO market_documents(collection, doc_id, document)
                VALUES (%s, %s, %s)
                ON CONFLICT (collection, doc_id) DO UPDATE SET document = EXCLUDED.document
                """,
                (self.name, str(document["_id"]), Json(_encode(document))),
            )
        with self.store._cache_lock:
            cached = self.store._cache.get(self.name)
            if cached is not None:
                replaced = False
                for index, current in enumerate(cached):
                    if str(current.get("_id")) == str(document["_id"]):
                        cached[index] = copy.deepcopy(document)
                        replaced = True
                        break
                if not replaced:
                    cached.append(copy.deepcopy(document))

    def find(self, query=None, projection=None):
        return PostgresCursor([
            _project(doc, projection)
            for doc in self._all()
            if _matches(doc, query)
        ])

    def find_one(self, query=None, projection=None):
        for document in self.find(query, projection):
            return document
        return None

    def insert_one(self, document):
        document = copy.deepcopy(document)
        document.setdefault("_id", self.store.new_id())
        self._save(document)
        return type("InsertResult", (), {"inserted_id": document["_id"]})()

    def insert_many(self, documents):
        ids = []
        for document in documents:
            ids.append(self.insert_one(document).inserted_id)
        return type("InsertManyResult", (), {"inserted_ids": ids})()

    def update_one(self, query, update, upsert=False):
        current = self.find_one(query)
        if current is None and upsert:
            base = {k: v for k, v in query.items() if not k.startswith("$") and not isinstance(v, dict)}
            current = _apply_update(base, update, inserting=True)
            self.insert_one(current)
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0, "upserted_id": current["_id"]})()
        if current is None:
            return type("UpdateResult", (), {"matched_count": 0, "modified_count": 0, "upserted_id": None})()
        changed = _apply_update(current, update)
        self._save(changed)
        return type("UpdateResult", (), {"matched_count": 1, "modified_count": int(changed != current), "upserted_id": None})()

    def update_many(self, query, update, upsert=False):
        matches = [doc for doc in self._all() if _matches(doc, query)]
        for document in matches:
            self._save(_apply_update(document, update))
        if not matches and upsert:
            return self.update_one(query, update, upsert=True)
        return type("UpdateResult", (), {"matched_count": len(matches), "modified_count": len(matches), "upserted_id": None})()

    def delete_one(self, query):
        document = self.find_one(query)
        if document:
            self._delete_id(document["_id"])
        return type("DeleteResult", (), {"deleted_count": int(bool(document))})()

    def delete_many(self, query):
        documents = [doc for doc in self._all() if _matches(doc, query)]
        for document in documents:
            self._delete_id(document["_id"])
        return type("DeleteResult", (), {"deleted_count": len(documents)})()

    def _delete_id(self, doc_id):
        with self.store._cursor() as cur:
            cur.execute(
                "DELETE FROM market_documents WHERE collection = %s AND doc_id = %s",
                (self.name, str(doc_id)),
            )
        with self.store._cache_lock:
            if self.name in self.store._cache:
                self.store._cache[self.name] = [
                    item for item in self.store._cache[self.name]
                    if str(item.get("_id")) != str(doc_id)
                ]

    def count_documents(self, query=None):
        return sum(1 for doc in self._all() if _matches(doc, query))

    def distinct(self, field, query=None):
        result = []
        for document in self.find(query):
            value = _get(document, field)
            if value is not _MISSING and value not in result:
                result.append(value)
        return result

    def create_index(self, *args, **kwargs):
        return None

    def drop(self):
        with self.store._cursor() as cur:
            cur.execute("DELETE FROM market_documents WHERE collection = %s", (self.name,))
        with self.store._cache_lock:
            self.store._cache.pop(self.name, None)

    def aggregate(self, pipeline):
        documents = self._all()
        for stage in pipeline:
            if "$match" in stage:
                documents = [d for d in documents if _matches(d, stage["$match"])]
            elif "$sort" in stage:
                for key, order in reversed(list(stage["$sort"].items())):
                    documents.sort(
                        key=lambda item: (_get(item, key) is None, _get(item, key)),
                        reverse=order < 0,
                    )
            elif "$skip" in stage:
                documents = documents[stage["$skip"]:]
            elif "$limit" in stage:
                documents = documents[:stage["$limit"]]
            elif "$project" in stage:
                documents = [
                    {
                        key: (_eval_expr(doc, value) if not isinstance(value, int)
                              else _get(doc, key))
                        for key, value in stage["$project"].items()
                        if value or key == "_id"
                    }
                    for doc in documents
                ]
            elif "$lookup" in stage:
                spec = stage["$lookup"]
                foreign = self.store[spec["from"]]._all()
                for document in documents:
                    local = _get(document, spec["localField"])
                    matches = [
                        copy.deepcopy(item) for item in foreign
                        if _compare(_get(item, spec["foreignField"]), local, "$eq")
                    ]
                    _set(document, spec["as"], matches)
            elif "$unwind" in stage:
                path = stage["$unwind"]
                path = path.get("path") if isinstance(path, dict) else path
                path = path.lstrip("$")
                expanded = []
                for document in documents:
                    values = _get(document, path, [])
                    values = values if isinstance(values, list) else [values]
                    for value in values:
                        clone = copy.deepcopy(document)
                        _set(clone, path, value)
                        expanded.append(clone)
                documents = expanded
            elif "$group" in stage:
                spec = stage["$group"]
                grouped = {}
                for document in documents:
                    group_id = _eval_expr(document, spec.get("_id"))
                    key = repr(group_id)
                    if key not in grouped:
                        grouped[key] = {"_id": group_id}
                    target = grouped[key]
                    for field, accumulator in spec.items():
                        if field == "_id":
                            continue
                        if "$sum" in accumulator:
                            value = accumulator["$sum"]
                            amount = 1 if value == 1 else (_eval_expr(document, value) or 0)
                            target[field] = target.get(field, 0) + amount
                        elif "$first" in accumulator and field not in target:
                            target[field] = _eval_expr(document, accumulator["$first"])
                        elif "$last" in accumulator:
                            target[field] = _eval_expr(document, accumulator["$last"])
                        elif "$push" in accumulator:
                            target.setdefault(field, []).append(_eval_expr(document, accumulator["$push"]))
                documents = list(grouped.values())
            elif "$count" in stage:
                documents = [{stage["$count"]: len(documents)}] if documents else []
        return PostgresCursor(documents)


class PostgresStore:
    def __init__(self, dsn: str):
        self._cache: dict[str, list[dict]] = {}
        self._cache_lock = RLock()
        self.pool = ThreadedConnectionPool(1, 8, dsn)
        with self._cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS market_documents (
                    collection TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    document JSONB NOT NULL,
                    PRIMARY KEY (collection, doc_id)
                )
                """
            )

    @staticmethod
    def new_id() -> str:
        import uuid
        return str(uuid.uuid4())

    @contextmanager
    def _cursor(self):
        connection = self.pool.getconn()
        try:
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            self.pool.putconn(connection)

    def __getitem__(self, name: str) -> PostgresCollection:
        return PostgresCollection(self, name)

    def command(self, name: str):
        if name != "ping":
            raise ValueError(f"Unsupported database command: {name}")
        with self._cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"ok": 1}

    def list_collection_names(self):
        with self._cursor() as cur:
            cur.execute("SELECT DISTINCT collection FROM market_documents ORDER BY collection")
            return [row[0] for row in cur.fetchall()]

    def close(self):
        self.pool.closeall()