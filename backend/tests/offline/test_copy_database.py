"""Copying a database is the one operation that must not be trusted on its word.

Two scripts in this repository have already reported success while leaving the
job half done, so the copy tool is built to be checked rather than believed:
`--verify` counts both sides afterwards and is a separate command from the one
that writes.

The other thing being tested here is the password. A connection string holds
one, and it is only safe as long as nothing prints it and nothing accepts it on
a command line, where it would land in shell history and in `ps`.
"""
import mongomock
import pytest

import copy_database as cdb


@pytest.fixture
def source():
    db = mongomock.MongoClient()["source"]
    db.events.insert_many([{"_id": i, "title": f"Event {i}"} for i in range(1200)])
    db.places.insert_many([{"_id": i, "name": f"Place {i}"} for i in range(50)])
    db.sources.insert_one({"_id": 1, "name": "A source"})
    return db


@pytest.fixture
def target():
    return mongomock.MongoClient()["target"]


class TestTheCredentialsNeverLeak:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("mongodb+srv://user:s3cret@cluster.mongodb.net/",
             "mongodb+srv://***@cluster.mongodb.net/"),
            ("mongodb://admin:pw@10.0.0.1:27017", "mongodb://***@10.0.0.1:27017"),
            ("mongodb://127.0.0.1:27017", "mongodb://127.0.0.1:27017"),
        ],
    )
    def test_the_host_stays_and_the_password_goes(self, url, expected):
        assert cdb._masked(url) == expected

    def test_a_masked_url_carries_no_part_of_the_password(self):
        assert "s3cret" not in cdb._masked("mongodb+srv://u:s3cret@c.net/")

    def test_the_target_is_read_from_the_environment_not_an_argument(self, monkeypatch):
        """So it cannot end up in shell history, in `ps`, or in a CI log."""
        monkeypatch.delenv("TARGET_MONGO_URL", raising=False)
        monkeypatch.delenv("TARGET_DB_NAME", raising=False)
        with pytest.raises(SystemExit) as exc:
            cdb._target()
        assert "shell history" in str(exc.value)

    def test_half_a_target_is_not_a_target(self, monkeypatch):
        monkeypatch.setenv("TARGET_MONGO_URL", "mongodb://x")
        monkeypatch.delenv("TARGET_DB_NAME", raising=False)
        with pytest.raises(SystemExit):
            cdb._target()


class TestTheCopy:
    def test_everything_arrives_including_past_one_batch(self, source, target):
        """1200 documents against a batch size of 500 — three round trips."""
        rows = cdb.plan(source, target)
        copied = cdb.copy(source, target, rows, replace=False)

        assert copied == 1251
        assert target.events.count_documents({}) == 1200
        assert target.places.count_documents({}) == 50
        assert target.sources.count_documents({}) == 1

    def test_the_documents_are_the_same_ones(self, source, target):
        cdb.copy(source, target, cdb.plan(source, target), replace=False)
        assert target.events.find_one({"_id": 7})["title"] == "Event 7"

    def test_verify_agrees_afterwards(self, source, target):
        cdb.copy(source, target, cdb.plan(source, target), replace=False)
        assert cdb.verify(source, target) is True

    def test_verify_says_no_when_the_copy_never_happened(self, source, target):
        assert cdb.verify(source, target) is False

    def test_verify_notices_a_partial_copy(self, source, target):
        """The failure mode that matters: most of it arrived."""
        target.events.insert_many([{"_id": i} for i in range(1200)])
        target.places.insert_many([{"_id": i} for i in range(50)])
        assert cdb.verify(source, target) is False, "sources is still missing"


class TestRunningItTwice:
    def test_a_second_run_does_not_double_anything(self, source, target):
        cdb.copy(source, target, cdb.plan(source, target), replace=False)
        cdb.copy(source, target, cdb.plan(source, target), replace=False)
        assert target.events.count_documents({}) == 1200

    def test_a_non_empty_target_is_left_alone_by_default(self, source, target):
        target.events.insert_one({"_id": 999, "title": "Do not lose me"})
        cdb.copy(source, target, cdb.plan(source, target), replace=False)
        assert target.events.count_documents({}) == 1
        assert target.events.find_one({"_id": 999}) is not None

    def test_replace_is_what_overwrites_and_it_has_to_be_asked_for(
        self, source, target
    ):
        # An id the source does not have, so its disappearance can only be
        # the delete and not a document overwriting itself.
        target.events.insert_one({"_id": "stale", "title": "Stale"})
        cdb.copy(source, target, cdb.plan(source, target), replace=True)
        assert target.events.count_documents({}) == 1200
        assert target.events.find_one({"_id": "stale"}) is None

    def test_an_empty_source_collection_is_not_copied_over_a_full_target(
        self, source, target
    ):
        """A collection that is empty here must not empty the other side."""
        source.create_collection("partners")
        target.partners.insert_one({"_id": 1, "name": "Real partner"})
        cdb.copy(source, target, cdb.plan(source, target), replace=True)
        assert target.partners.count_documents({}) == 1
