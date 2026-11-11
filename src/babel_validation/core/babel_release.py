"""Babel release names: recognising them, and ordering them by date.

Babel releases are named for the day they were built, e.g. '2026sep24', optionally with an
alphanumeric suffix after a hyphen, e.g. '2026sep24-dev'. NodeNorm reports the one it serves
as `babel_version` in /status. Because the name is a date, release names order by date: a
deployment reporting '2025sep1' predates one reporting '2026jul22', and the suffix does not
change that.

This module needs nothing beyond the standard library, so it can be used without the test
suite. The checks that fail a test over a malformed release name are in
`babel_validation.services.service_checks`.
"""

import datetime
import re

# Each part is a fixed width or a disjoint character class, so there is nothing here to
# backtrack over: the input is often a service's response.
BABEL_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
BABEL_VERSION_RE = re.compile(
    r"(?P<year>\d{4})(?P<month>" + "|".join(BABEL_MONTHS) + r")(?P<day>\d{1,2})(?:-[A-Za-z0-9]+)?"
)
BABEL_VERSION_MAX_LENGTH = 64


def match_babel_version(babel_version):
    """
    Return the regex match for a Babel release name, or None if it is not one.

    The match only says the name is well-formed: '2026feb30' matches, so use
    babel_release_date() to also check that it is a real date.

    :param babel_version: Any value, typically a /status babel_version.
    :return: The re.Match with year, month and day groups, or None.
    """
    if isinstance(babel_version, str) and len(babel_version) <= BABEL_VERSION_MAX_LENGTH:
        return BABEL_VERSION_RE.fullmatch(babel_version)
    return None


def babel_release_date(babel_version):
    """
    Return the date a Babel release name stands for, or None if it is not a release name.

    :param babel_version: The babel_version as /status reported it, or any value.
    :return: The release date, or None if babel_version is not a well-formed release name
        for a real date.
    """
    match = match_babel_version(babel_version)
    if not match:
        return None
    try:
        return datetime.date(int(match["year"]), BABEL_MONTHS.index(match["month"]) + 1, int(match["day"]))
    except ValueError:
        return None
