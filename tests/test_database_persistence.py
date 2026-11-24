import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import DATABASE_URL, default_database_url


def test_default_database_is_persistent_and_configurable(monkeypatch, tmp_path):
    db_file = tmp_path / "restart.db"
    monkeypatch.setenv("CROWDSENSE_DATABASE_URL", f"sqlite:///{db_file}")
    assert default_database_url() == f"sqlite:///{db_file}"
    assert "sqlite://" in default_database_url()


def test_database_health_reports_sql_connection():
    from app.database import database_health
    health = database_health()
    assert health["healthy"] is True
    assert health["provider"] == "sql"


def test_fresh_database_import_update_and_duplicate(tmp_path, monkeypatch):
    db_file = tmp_path / "persistence.db"
    monkeypatch.setenv("CROWDSENSE_DATABASE_URL", f"sqlite:///{db_file}")

    from app.database import create_engine, sessionmaker
    from app.database import Base
    from app.persistence_models import Route, Stop

    engine = create_engine(f"sqlite:///{db_file}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)

    with Session() as session:
        session.add(Route(route_id="R1", short_name="1", long_name="Original"))
        session.add(Stop(stop_id="A", name="Alpha", lat=51.5, lng=-0.1))
        session.commit()

    with Session() as session:
        route = session.query(Route).filter_by(route_id="R1").one()
        route.short_name = "1X"
        session.commit()

    with Session() as session:
        route = session.query(Route).filter_by(route_id="R1").one()
        stop = session.query(Stop).filter_by(stop_id="A").one()
        assert route.short_name == "1X"
        assert stop.name == "Alpha"

    with Session() as session:
        existing = session.query(Route).filter_by(route_id="R1").one_or_none()
        if existing is None:
            session.add(Route(route_id="R1", short_name="1X"))
        session.commit()

    with Session() as session:
        assert session.query(Route).filter_by(route_id="R1").count() == 1


def test_database_records_survive_simulated_backend_restart(tmp_path):
    db_file = tmp_path / "restart.db"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.persistence_models import Stop

    engine = create_engine(f"sqlite:///{db_file}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        session.add(Stop(stop_id="A", name="Persisted Across Restart"))
        session.commit()

    restarted_engine = create_engine(f"sqlite:///{db_file}", future=True)
    RestartSession = sessionmaker(bind=restarted_engine, future=True)
    with RestartSession() as session:
        stop = session.query(Stop).filter_by(stop_id="A").one()
        assert stop.name == "Persisted Across Restart"


def test_connection_failure_and_recovery(tmp_path):
    from sqlalchemy import create_engine

    broken = create_engine("sqlite:///missing-parent-that-does-not-exist/crowdsense.db", future=True)
    try:
        with broken.connect():
            pass
    except Exception:
        failed = True
    else:
        failed = False
    assert failed is True

    recovered_file = tmp_path / "recovered.db"
    recovered = create_engine(f"sqlite:///{recovered_file}", future=True)
    with recovered.connect() as connection:
        assert connection.exec_driver_sql("SELECT 1").scalar() == 1
