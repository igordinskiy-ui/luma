"""Small Redis lock primitives shared by background workers."""
from typing import Protocol


OUTBOX_WORKER_LOCK_KEY = "kurilka:outbox-worker"
# A read followed by a delete is racy: a slow worker could delete a lock that
# has expired and been acquired by another worker. Redis executes this script
# atomically, so only the owner of the current token can release it.
RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class RedisLockClient(Protocol):
    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int: ...


async def release_worker_lock(redis: RedisLockClient, lock_token: str) -> bool:
    return bool(await redis.eval(RELEASE_LOCK_SCRIPT, 1, OUTBOX_WORKER_LOCK_KEY, lock_token))
