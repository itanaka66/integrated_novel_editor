import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Note: TestClient only runs FastAPI's startup/shutdown events when used
    # as a context manager. We deliberately avoid that here, since the app's
    # startup handler connects to the real (Postgres) database configured by
    # app.config.settings, which isn't available in the test environment.
    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def project(client):
    r = client.post("/api/v1/projects", json={"name": "テスト作品", "description": "d", "genre": "g", "rules": "r"})
    assert r.status_code == 200
    return r.json()
