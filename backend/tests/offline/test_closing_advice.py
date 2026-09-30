"""The advice a tool gives at the end is part of what the tool does.

`check_atlas.py` used to close every run with the same line: the next step is
`copy_database.py --write`. That was correct for exactly one day — the day the
Atlas cluster was empty and Emergent's container held the only copy.

Since then the direction has reversed. Atlas carries the stock and is crawled
three times a day; the container has stood still since August. The closing line
kept pointing at the copy, which now means copying the smaller database over
the larger one. Nothing checked it, because nobody tests what a script prints
after it has finished its work.

This does.
"""
import check_atlas


class TestAnEmptyTargetIsInvitedToMove:
    def test_the_copy_is_the_next_step(self):
        advice = "\n".join(check_atlas.closing_advice({}))
        assert "copy_database.py --write" in advice

    def test_and_verifying_is_named_with_it(self):
        """Copying and having copied are two claims; the second needs --verify."""
        assert "--verify" in "\n".join(check_atlas.closing_advice({}))


class TestAFilledTargetIsNot:
    FILLED = {"events": 1010, "places": 7856, "sources": 103}

    def test_the_copy_is_not_offered(self):
        advice = "\n".join(check_atlas.closing_advice(self.FILLED))
        assert "copy_database.py --write" not in advice

    def test_replace_is_named_only_to_warn_against_it(self):
        advice = "\n".join(check_atlas.closing_advice(self.FILLED))
        assert "--replace" in advice
        assert "Kein copy_database.py --replace" in advice

    def test_what_it_offers_instead_is_switching_over(self):
        advice = "\n".join(check_atlas.closing_advice(self.FILLED))
        assert "MONGO_URL" in advice and "DB_NAME" in advice

    def test_it_says_why_it_cannot_decide_this_itself(self):
        """Which side is newer is not something a connection check can see."""
        assert "wissen" in "\n".join(check_atlas.closing_advice(self.FILLED))

    def test_one_filled_collection_is_enough(self):
        """Not all four have to be there — `users` is empty on a fresh install."""
        advice = "\n".join(check_atlas.closing_advice({"events": 1}))
        assert "copy_database.py --write" not in advice
