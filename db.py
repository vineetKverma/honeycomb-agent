from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure, OperationFailure

import config

_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        try:
            _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
        except Exception as e:
            raise ConnectionError(f"Failed to create MongoDB client: {e}") from e
    return _client


def get_collection() -> Collection:
    return _get_client()[config.MONGODB_DB][config.MONGODB_COLLECTION]


def ensure_indexes() -> None:
    col = get_collection()
    col.create_index([("name_lower", ASCENDING)], unique=True)


def vector_search(query_embedding: list[float], limit: int = 5) -> list[dict]:
    col = get_collection()
    pipeline = [
        {
            "$vectorSearch": {
                "index": config.VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": limit * 10,
                "limit": limit,
            }
        },
        {
            "$addFields": {
                "_score": {"$meta": "vectorSearchScore"},
            }
        },
        {
            "$project": {"embedding": 0}
        },
    ]
    try:
        return list(col.aggregate(pipeline))
    except OperationFailure as e:
        raise RuntimeError(
            f"Vector search failed - ensure the '{config.VECTOR_INDEX_NAME}' Atlas Search index exists "
            f"and is in READY state. Original error: {e}"
        ) from e


def health_check() -> bool:
    try:
        _get_client().admin.command("ping")
        return True
    except (ConnectionFailure, ConnectionError) as e:
        print(f"Atlas health check failed: {e}")
        return False


if __name__ == "__main__":
    ok = health_check()
    print(f"Atlas reachable: {ok}")
