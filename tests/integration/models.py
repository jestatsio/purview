"""Shared models + a standard policy for integration tests.

Tenant column is ``org_id``. ``Org`` (the tenant root) and ``GlobalThing``
(reference data) are marked global; everything else is tenant-scoped.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, true
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from purview import READ, Context, Policy


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "org"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(50))


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    title: Mapped[str] = mapped_column(String(50))
    author: Mapped[User] = relationship()
    comments: Mapped[list[Comment]] = relationship(back_populates="post")


class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"))
    body: Mapped[str] = mapped_column(String(50))
    post: Mapped[Post] = relationship(back_populates="comments")


class GlobalThing(Base):
    __tablename__ = "global_thing"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(50))


class Animal(Base):
    __tablename__ = "animal"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(50))
    __mapper_args__ = {"polymorphic_on": "type", "polymorphic_identity": "animal"}


class Dog(Animal):
    __tablename__ = "dog"
    id: Mapped[int] = mapped_column(ForeignKey("animal.id"), primary_key=True)
    breed: Mapped[str] = mapped_column(String(50))
    __mapper_args__ = {"polymorphic_identity": "dog"}


def build_policy() -> Policy:
    """The standard policy: Post has a read rule (authors see own, org_admins see
    all in-tenant); Comment/Animal have no read rule (tenant-scope only)."""
    policy = Policy()
    policy.global_model(Org)
    policy.global_model(GlobalThing)

    @policy.rule(Post, READ)
    def read_post(ctx: Context[int, int]) -> list:
        rules = []
        if ctx.has_role("author"):
            rules.append(Post.author_id == ctx.user_id)
        if ctx.has_role("org_admin"):
            rules.append(true())  # whole tenant; tenant scope applied separately
        return rules

    @policy.rule(Post, "update")
    def update_post(ctx: Context[int, int]) -> list:
        # Stricter than read: only the author may update, even though an
        # org_admin can read every post in the tenant.
        return [Post.author_id == ctx.user_id] if ctx.has_role("author") else []

    return policy


# Convenience context builders ------------------------------------------------ #
def author_ctx(user_id: int = 1, tenant: int = 1) -> Context[int, int]:
    return Context(user_id, tenant, frozenset({"author"}))


def admin_ctx(tenant: int = 1) -> Context[int, int]:
    return Context(999, tenant, frozenset({"org_admin"}))


def plain_ctx(user_id: int = 1, tenant: int = 1) -> Context[int, int]:
    return Context(user_id, tenant, frozenset())
