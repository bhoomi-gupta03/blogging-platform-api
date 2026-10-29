import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.dependencies import CurrentUser, DbSession
from app.models import Post, User
from app.schemas import PostCreate, PostPublic, PostUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/posts", tags=["Blog posts"])


def get_post_or_404(db: DbSession, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


def get_owned_post(db: DbSession, post_id: int, user: User) -> Post:
    """Return the post only if `user` owns it.
    Policy: a missing post is 404; someone else's post is 403. Posts are public
    to read, so their existence is not a secret and 403 gives the clearest message."""
    post = get_post_or_404(db, post_id)
    if post.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only modify your own posts")
    return post


@router.post("", response_model=PostPublic, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: DbSession, current_user: CurrentUser):
    post = Post(title=payload.title, content=payload.content, owner_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    logger.info("User id=%s created post id=%s", current_user.id, post.id)
    return post


@router.get("", response_model=list[PostPublic])
def list_posts(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    # id is a tie-breaker so the order (and therefore pagination) is stable
    stmt = select(Post).order_by(Post.created_at.desc(), Post.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(stmt))


@router.get("/{post_id}", response_model=PostPublic)
def get_post(post_id: int, db: DbSession):
    return get_post_or_404(db, post_id)


@router.put("/{post_id}", response_model=PostPublic)
def update_post(post_id: int, payload: PostUpdate, db: DbSession, current_user: CurrentUser):
    post = get_owned_post(db, post_id, current_user)
    post.title = payload.title
    post.content = payload.content
    db.commit()
    db.refresh(post)
    logger.info("User id=%s updated post id=%s", current_user.id, post.id)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, db: DbSession, current_user: CurrentUser):
    post = get_owned_post(db, post_id, current_user)
    db.delete(post)
    db.commit()
    logger.info("User id=%s deleted post id=%s", current_user.id, post_id)
