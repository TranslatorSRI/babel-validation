import logging

import requests
import pytest

from src.babel_validation.sources.google_sheets.blocklist import BlocklistEntry, load_blocklist_from_gsheet

# Parameterize blocklist entries.
blocklist_entries = load_blocklist_from_gsheet()


@pytest.mark.parametrize("blocklist_entry", blocklist_entries)
def test_check_blocklist_entry(target_info, blocklist_entry, categories_include):
    """
    Test whether a NameRes instance has blocked every item from a blocklist.

    :param target_info: The test target information.
    """
    nameres_url = target_info['NameResURL']
    nameres_url_reverse_lookup = nameres_url + 'reverse_lookup'

    # If there is any test category provided, this test is not relevant and we can skip it.
    if categories_include:
        pytest.skip(f"Skipping blocklist entry as it is not part of any category and the category filter is set to include {categories_include}.")
        return

    # Only "blocked" entries are considered, since most of the spreadsheet is things we decided _not_ to block.
    if blocklist_entry.Blocked == 'y':
        flag_expect_present = False
    elif blocklist_entry.Blocked == 'n':
        flag_expect_present = True
    else:
        logging.info(f"Skipping blocklist entry as it is not asserted to be blocked: {blocklist_entry}")
        return

    if flag_expect_present and not blocklist_entry.CURIE:
        # We've got a bunch of these, just ignore them.
        pytest.skip(f"Blocklist entry expected to not be blocked, but no CURIE provided: {blocklist_entry}")

    assert blocklist_entry.CURIE, f"Blocklist entry claims to be blocked, but does not have a CURIE: {blocklist_entry}"

    # Someday we would like to do this with the query as well, but that would require some work.
    # So we only test the CURIE for now.
    response = requests.get(nameres_url_reverse_lookup, params={
        'curies': blocklist_entry.CURIE,
    })
    assert response.ok
    result = response.json()[blocklist_entry.CURIE]

    if flag_expect_present:
        assert result != {}, f"Expected {blocklist_entry.CURIE} to be present on {nameres_url_reverse_lookup}, but found: {result}"
    else:
        assert result == {}, f"Expected {blocklist_entry.CURIE} to be absent on {nameres_url_reverse_lookup}, but found: {result}"
