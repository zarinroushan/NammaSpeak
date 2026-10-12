import os
import tempfile
import pytest

# Tests use isolated SQLite URLs explicitly. Production requires DATABASE_URL
# and never falls back to a local database.
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["NAMMASPEAK_TESTING"] = "1"
from backend.app import create_app
from backend.models import init_db


@pytest.fixture
def client():
    # Create temporary database file for test isolation
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    app = create_app({
        "TESTING": True,
        "DATABASE_PATH": db_path,
        "DATABASE_URL": f"sqlite:///{db_path.replace(os.sep, '/')}",
        "DEBUG": False
    })

    with app.test_client() as client:
        yield client

    # Cleanup temporary database
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
