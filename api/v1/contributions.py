#!/usr/bin/python3
"""Contribution tiers: a lightweight "how much has this person added
to the atlas" signal derived from their approved forum posts.

This app has no separate "review" model — a post targeting a city or
point of interest *is* the review, a general one *is* a forum
contribution, and both come from the same ForumPost table. Computed
live from the current approved-post count rather than stored as an
incrementing counter on User, so it can never drift out of sync with
moderation or a deleted post.
"""
from models import storage
from models.forum_post import ForumPost

# (minimum approved posts, tier key) pairs, highest first. Small
# numbers on purpose — this is a university-project community forum,
# not a global platform, and should be reachable within a demo without
# needing dozens of seeded posts to show off the top tier.
CONTRIBUTION_TIERS = (
    (10, "local_expert"),
    (3, "contributor"),
    (1, "newcomer"),
)


def approved_post_count(user_id):
    """Count a user's own approved (publicly visible) forum posts."""
    return sum(
        1 for post in storage.all(ForumPost).values()
        if post.author_id == user_id and post.status == "approved"
    )


def contribution_tier(count):
    """Return the tier key a contribution count has reached, or None
    if it hasn't reached even the first tier yet."""
    for minimum, tier in CONTRIBUTION_TIERS:
        if count >= minimum:
            return tier
    return None
