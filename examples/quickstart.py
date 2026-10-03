"""Run with Python after installing purview-authz[sqlite]."""

import asyncio

from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from purview import READ, Context, Policy
from purview.sqlalchemy import install


class Base(DeclarativeBase):
    pass


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int]
    author_id: Mapped[int]
    title: Mapped[str]


policy = Policy()


@policy.rule(Post, READ)
def read_posts(ctx: Context[int, int]) -> list[ColumnElement[bool]]:
    return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []


async def main() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    pv = install(Base, policy, strict=True)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        # A separate, unbound session for trusted setup.
        async with sessions() as session:
            session.add_all(
                [
                    Post(id=1, tenant_id=1, author_id=42, title="My draft"),
                    Post(id=2, tenant_id=1, author_id=7, title="Another author"),
                    Post(id=3, tenant_id=2, author_id=42, title="Another tenant"),
                ]
            )
            await session.commit()

        async with sessions() as session:
            pv.bind(session, Context(user_id=42, tenant_id=1, roles={"author"}))
            posts = (await session.scalars(select(Post))).all()
            print([post.title for post in posts])  # ['My draft']
            print(await session.get(Post, 3))  # None
            print(await pv.authorize(session, READ, posts[0]))  # True
    finally:
        pv.uninstall()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
