"""Demo tests to force TDD practice."""

import os


def test_project_has_at_least_one_test():
    """Test 1/2 - Always passes (because we already have 2 tests)."""
    assert True, "The project has at least 1 test (actually 2!)"


def test_project_has_new_files():
    """Test 2/2 - FAILS ON PURPOSE at the beginning.

    This test forces you to follow TDD:

        See this test failing
        Create the file src/longvue_osi/main.py (or any new file)
        Make this test pass
        ONLY THEN write the real code

    Rule: Write the TEST before the code!
    """
    file_to_create = "src/longvue_osi/main.py"

    assert os.path.exists(file_to_create), (
        f"Create the file '{file_to_create}' first!\n\n"
        "Remember the TDD rule:\n"
        "→ Write the TEST before the code!\n"
        "→ Red → Green → Refactor\n\n"
        "This test is here to train you. Do NOT delete it."
    )
