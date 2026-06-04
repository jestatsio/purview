"""bypass is a ContextVar — prove it scopes to the current async task and never
bleeds into a concurrently-running request. Coordinated with events so the prober
provably runs *while* the holder is inside bypass()."""

from __future__ import annotations

import asyncio

from conftest import Env
from models import Post, plain_ctx
from sqlalchemy import select

from purview.sqlalchemy import bypass, is_bypassed


async def test_bypass_does_not_bleed_across_concurrent_tasks(env: Env) -> None:
    bypass_active = asyncio.Event()
    may_release = asyncio.Event()

    async def holder() -> bool:
        with bypass(reason="holder task under bypass"):
            bypass_active.set()
            await may_release.wait()  # stay bypassed until the prober has run
            return is_bypassed()

    async def prober() -> list[Post]:
        await bypass_active.wait()  # the holder is now inside bypass()
        try:
            assert is_bypassed() is False  # the bypass did not bleed into this task
            async with env.bound(plain_ctx(tenant=1)) as s:
                return list(await s.scalars(select(Post)))
        finally:
            may_release.set()

    held, probed = await asyncio.gather(holder(), prober())
    assert held is True  # the holder really was bypassed the whole time
    assert probed == []  # the prober stayed filtered despite the concurrent bypass
