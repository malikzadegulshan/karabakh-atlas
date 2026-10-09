#!/usr/bin/python3
"""Helpers shared by every view that deletes or counts forum posts.

Replies are ForumPost rows whose parent_id points at the top-level post
they answer (threads are one level deep — see create_forum_post in
api/v1/views/forum.py). That foreign key means a parent can't be
deleted while any reply still references it, and a reply is only worth
showing while its parent is.
"""
from models import storage
from models.forum_post import ForumPost


def delete_forum_posts(posts):
    """Delete the given posts, replies before the posts they answer.

    The order has to be enforced in the database, not just in Python:
    session.delete() only marks rows, and SQLAlchemy flushes same-table
    deletes in primary-key order (no relationship() tells it a reply must
    go first), so deleting everything before one commit can remove a
    parent while a reply still references it and PostgreSQL rejects it
    with a foreign-key violation. So the replies are committed first,
    then the rest. (File storage has no foreign keys, which is why only a
    real database catches this.) Callers pass every post they want gone;
    replies share their parent's city/news target, so the cascades in
    cities/regions/news already collect them.
    """
    replies = [post for post in posts if post.parent_id is not None]
    others = [post for post in posts if post.parent_id is None]
    for reply in replies:
        reply.delete()
    if replies:
        storage.save()
    for post in others:
        post.delete()


def delete_post_and_replies(post):
    """Delete one post along with every reply to it."""
    replies = [
        p for p in storage.all(ForumPost).values() if p.parent_id == post.id]
    delete_forum_posts(replies + [post])


def publicly_visible(post, posts_by_id):
    """True when a post is approved and, for a reply, so is the post it
    answers — rejecting or un-approving a parent hides its replies
    instead of leaving them dangling in the list."""
    if post.status != "approved":
        return False
    if post.parent_id is None:
        return True
    parent = posts_by_id.get(post.parent_id)
    return parent is not None and parent.status == "approved"


def posts_by_id():
    """Every stored ForumPost keyed by its bare id."""
    return {p.id: p for p in storage.all(ForumPost).values()}
