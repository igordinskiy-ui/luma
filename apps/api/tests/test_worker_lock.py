import pytest

from app.redis_lock import OUTBOX_WORKER_LOCK_KEY, RELEASE_LOCK_SCRIPT, release_worker_lock


class FakeRedis:
    def __init__(self, current_token: str):
        self.current_token = current_token
        self.calls: list[tuple[str, int, str, str]] = []

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        self.calls.append((script, numkeys, key, token))
        if self.current_token != token:
            return 0
        self.current_token = ""
        return 1


@pytest.mark.asyncio
async def test_release_worker_lock_deletes_only_its_own_token():
    redis = FakeRedis("other-worker-token")

    released = await release_worker_lock(redis, "this-worker-token")

    assert released is False
    assert redis.current_token == "other-worker-token"
    assert redis.calls == [(RELEASE_LOCK_SCRIPT, 1, OUTBOX_WORKER_LOCK_KEY, "this-worker-token")]


@pytest.mark.asyncio
async def test_release_worker_lock_releases_matching_token():
    redis = FakeRedis("this-worker-token")

    released = await release_worker_lock(redis, "this-worker-token")

    assert released is True
    assert redis.current_token == ""
