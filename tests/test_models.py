from sqlalchemy import func, select

from app.models import Post, User


def test_deleting_a_user_deletes_their_posts(db_session):
    """Documented policy: posts are removed together with their author."""
    user = User(username="author", email="author@example.com", hashed_password="x")
    user.posts = [Post(title="a", content="b"), Post(title="c", content="d")]
    db_session.add(user)
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(Post)) == 2

    db_session.delete(user)
    db_session.commit()
    assert db_session.scalar(select(func.count()).select_from(Post)) == 0
