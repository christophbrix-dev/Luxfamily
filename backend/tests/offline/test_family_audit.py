"""The standing audit over already-stored content.

The import filter only guards what arrives. Everything stored before it
existed came in unchecked, and a source can change what it publishes, so the
same question has to be asked again of the database itself.

The quarantine path is what these tests are really for. It is the one piece of
this feature that writes to live data, and it is the piece nobody exercises by
hand — you only find out it was wrong on the day it matters.
"""
import pytest

pytest.importorskip("mongomock_motor", reason="pip install -r requirements-dev.txt")

import check_family_safe as audit


@pytest.fixture
def db(monkeypatch):
    """A fresh in-memory database, wired into the script's own connection."""
    from mongomock_motor import AsyncMongoMockClient

    client = AsyncMongoMockClient()
    monkeypatch.setattr(audit, "mongo_settings", lambda: ("mongodb://offline", "audit"))
    monkeypatch.setattr(audit, "AsyncIOMotorClient", lambda _url: client)
    return client["audit"]


CLEAN = {
    "id": "ev-clean",
    "title": {"de": "Schueberfouer", "fr": "Schueberfouer"},
    "description": {"de": "Bierzelt a Kartoffelpuffer, owes ab 18 Joer."},
    "source_name": "Ville de Luxembourg",
    "published": True,
}
EXPLICIT = {
    "id": "ev-bad",
    "title": {"de": "Abend im Zentrum"},
    "description": {"de": "Striptease und Table-Dance."},
    "source_name": "Irgendeine Quelle",
    "published": True,
}


class TestReporting:
    def test_clean_database_reports_nothing(self, db, run):
        run(db.events.insert_one(dict(CLEAN)))
        assert run(audit.run(quarantine=False)) == 0

    def test_a_finding_exits_nonzero(self, db, run):
        """So cron and CI can actually raise an alarm."""
        run(db.events.insert_many([dict(CLEAN), dict(EXPLICIT)]))
        assert run(audit.run(quarantine=False)) == 1

    def test_reporting_changes_nothing(self, db, run):
        run(db.events.insert_one(dict(EXPLICIT)))
        run(audit.run(quarantine=False))
        stored = run(db.events.find_one({"id": "ev-bad"}))
        assert stored["published"] is True
        assert "family_flag" not in stored


class TestQuarantine:
    def test_the_finding_is_hidden(self, db, run):
        run(db.events.insert_one(dict(EXPLICIT)))
        run(audit.run(quarantine=True))
        stored = run(db.events.find_one({"id": "ev-bad"}))
        assert stored["published"] is False

    def test_it_records_why(self, db, run):
        """A hidden entry with no reason is one nobody can review."""
        run(db.events.insert_one(dict(EXPLICIT)))
        run(audit.run(quarantine=True))
        flag = run(db.events.find_one({"id": "ev-bad"}))["family_flag"]
        assert flag["reason"] == "explicit"
        assert "striptease" in flag["matched"].lower()
        assert flag["at"]

    def test_nothing_is_deleted(self, db, run):
        """A finding is a question for a human, not a verdict.

        Deleting would make the entry impossible to look at afterwards, so a
        wrong rule could never be discovered — only its silence.
        """
        run(db.events.insert_one(dict(EXPLICIT)))
        run(audit.run(quarantine=True))
        assert run(db.events.count_documents({})) == 1

    def test_clean_entries_are_left_alone(self, db, run):
        run(db.events.insert_many([dict(CLEAN), dict(EXPLICIT)]))
        run(audit.run(quarantine=True))
        stored = run(db.events.find_one({"id": "ev-clean"}))
        assert stored["published"] is True
        assert "family_flag" not in stored


class TestSchedulerEntryPoint:
    """audit_family_safety is what runs after every crawl, unattended."""

    def test_hides_and_reports_the_count(self, db, run):
        run(db.events.insert_many([dict(CLEAN), dict(EXPLICIT)]))
        assert run(audit.audit_family_safety(db)) == 1
        assert run(db.events.find_one({"id": "ev-bad"}))["published"] is False

    def test_a_clean_database_costs_one_scan_and_no_writes(self, db, run):
        run(db.events.insert_one(dict(CLEAN)))
        assert run(audit.audit_family_safety(db)) == 0
        assert "family_flag" not in run(db.events.find_one({"id": "ev-clean"}))

    def test_the_script_and_the_scheduler_share_one_scan(self):
        """Two implementations would eventually disagree about what is safe."""
        import inspect

        assert "scan(" in inspect.getsource(audit.audit_family_safety)
        assert "scan(" in inspect.getsource(audit.run)

    def test_importing_does_not_reconfigure_logging(self):
        """server.py imports this module; basicConfig here would rewrite the
        backend's whole log format as a side effect of that import."""
        import inspect

        module_level = inspect.getsource(audit).split("def main(")[0]
        code = [
            line for line in module_level.splitlines()
            if not line.lstrip().startswith("#")   # the comment saying so does not count
        ]
        assert "basicConfig" not in "\n".join(code)


class TestWhereItLooks:
    def test_places_are_checked_too(self, db, run):
        run(db.places.insert_one(
            {"id": "pl-bad", "name": {"de": "Saunaclub Wellness"}, "published": True}
        ))
        assert run(audit.run(quarantine=False)) == 1

    def test_a_clean_german_side_does_not_launder_the_french(self, db, run):
        """Checking one language would let the other through."""
        run(db.events.insert_one({
            "id": "ev-fr",
            "title": {"de": "Soirée privée", "fr": "Club libertin – soirée privée"},
            "published": True,
        }))
        assert run(audit.run(quarantine=False)) == 1

    def test_categories_are_searched(self, db, run):
        run(db.events.insert_one({
            "id": "ev-cat",
            "title": {"de": "Abend"},
            "category": ["Nightlife", "Striptease"],
            "published": True,
        }))
        assert run(audit.run(quarantine=False)) == 1
