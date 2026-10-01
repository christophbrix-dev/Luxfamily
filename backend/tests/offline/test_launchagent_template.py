"""The LaunchAgent that is supposed to make the crawler actually run.

A scheduled job is the hardest kind of code to notice being broken. It has no
caller watching it, no user waiting on a response, and a failure three times a
day looks exactly like a success three times a day: nothing happens either way.
That is not hypothetical here — the server's own scheduler was switched on
correctly and sat there for a day and a half without running, and the only
reason anybody found out was a count that had not moved.

So the two halves of the job are checked against each other:

  - the template, which holds the schedule and the placeholders, and
  - install-launchagent.sh, which substitutes them.

A placeholder the installer does not know about yields a plist pointing at a
file named "__PYTHON__". launchd loads it happily and it fails, silently, on
schedule.
"""
import plistlib
import re
from pathlib import Path

import pytest

OPS = Path(__file__).resolve().parents[3] / "ops"
TEMPLATE = OPS / "lu.luxfamily.importers.plist.template"
INSTALLER = OPS / "install-launchagent.sh"

PLACEHOLDER = re.compile(r"__[A-Z_]+__")

# The three times the server's scheduler used. Changing them is allowed;
# changing them in one of the two places is the failure this guards.
EXPECTED_HOURS = {5, 12, 18}


@pytest.fixture(scope="module")
def template_text() -> str:
    return TEMPLATE.read_text()


@pytest.fixture(scope="module")
def installer_text() -> str:
    return INSTALLER.read_text()


@pytest.fixture(scope="module")
def filled(template_text: str) -> dict:
    """The template with plausible paths substituted, parsed as launchd would.

    Parsing the template directly is not possible — a placeholder is not a
    valid path but it *is* a valid string, so plistlib would accept it and the
    test would prove nothing about the real file.
    """
    text = template_text
    for name, value in {
        "__PYTHON__": "/Users/someone/repo/backend/.venv/bin/python",
        "__SCRIPT__": "/Users/someone/repo/backend/run_importers.py",
        "__WORKDIR__": "/Users/someone/repo/backend",
        "__LOG__": "/Users/someone/Library/Logs/Luxfamily/importers.log",
    }.items():
        text = text.replace(name, value)
    return plistlib.loads(text.encode())


class TestTheTemplateAndTheInstallerAgree:
    def test_every_placeholder_is_one_the_installer_substitutes(self, template_text, installer_text):
        """The silent-failure case: a plist that points at "__PYTHON__"."""
        in_template = set(PLACEHOLDER.findall(template_text))
        assert in_template, "the template has no placeholders — did it get flattened?"
        missing = {p for p in in_template if f"s|{p}|" not in installer_text}
        assert not missing, f"the installer does not substitute: {sorted(missing)}"

    def test_the_installer_refuses_a_file_that_still_has_one(self, installer_text):
        """Belt as well as braces: checked at install time, not only here."""
        assert 'grep -q "__" "$TARGET"' in installer_text

    def test_the_installer_validates_the_plist_before_loading_it(self, installer_text):
        """launchd reports a rejected plist much like an accepted one."""
        assert "plutil -lint" in installer_text


class TestTheSchedule:
    def test_it_is_the_three_documented_times(self, filled):
        hours = {entry["Hour"] for entry in filled["StartCalendarInterval"]}
        assert hours == EXPECTED_HOURS

    def test_each_one_is_on_the_hour(self, filled):
        assert all(entry["Minute"] == 0 for entry in filled["StartCalendarInterval"])

    def test_the_server_schedules_the_same_hours(self):
        """Two schedules that drift apart would crawl at four times of day."""
        import inspect

        import server
        src = inspect.getsource(server.lifespan)
        match = re.search(r'hour="([\d,]+)"', src)
        assert match, "the server's CronTrigger no longer spells out its hours"
        assert {int(h) for h in match.group(1).split(",")} == EXPECTED_HOURS

    def test_it_does_not_also_crawl_at_every_login(self, filled):
        """Somebody else's bandwidth. A missed slot is caught up on wake anyway."""
        assert filled["RunAtLoad"] is False


class TestWhatItRuns:
    def test_it_calls_the_standalone_entry_point(self, filled):
        assert filled["ProgramArguments"][1].endswith("/run_importers.py")

    def test_it_uses_the_projects_own_python(self, filled):
        """The system python has neither motor nor dotenv installed."""
        assert filled["ProgramArguments"][0].endswith("/.venv/bin/python")

    def test_output_and_errors_land_in_the_same_file(self, filled):
        """One file read top to bottom, rather than two to correlate by hand."""
        assert filled["StandardOutPath"] == filled["StandardErrorPath"]

    def test_it_runs_out_of_the_way(self, filled):
        """A crawler must not be why the machine feels slow."""
        assert filled["ProcessType"] == "Background"
        assert filled["LowPriorityIO"] is True


class TestTheLogStaysReadable:
    """A log is only a record if somebody can find the record in it.

    httpx logs every request at INFO, and a full crawl makes roughly a
    thousand of them. launchd appends to a single file forever, so without
    this the one line that says what a run achieved sits buried in a day's
    worth of "HTTP/1.1 200 OK" — and the first run proved it: 86 lines in the
    first 45 seconds, 85 of them requests.
    """

    def test_the_http_clients_are_turned_down(self):
        import run_importers
        assert "httpx" in run_importers.NOISY_LOGGERS

    def test_turning_them_down_still_lets_failures_through(self):
        """WARNING, not CRITICAL: a request that fails is worth a line."""
        import inspect
        import logging

        import run_importers
        src = inspect.getsource(run_importers._setup_logging)
        assert "logging.WARNING" in src
        run_importers._setup_logging(quiet=False)
        assert logging.getLogger("httpx").level == logging.WARNING

    def test_our_own_loggers_are_not_turned_down(self):
        """The crawler's own decisions — refused, skipped, geocoded — are the record."""
        import run_importers
        assert not any(n.startswith("lux-backend") for n in run_importers.NOISY_LOGGERS)
