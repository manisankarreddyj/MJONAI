"""Mark every test under tests/research with the `research` marker.

These suites are data-layer heavy. They are gated: a bare `pytest` only
*collects* them (import is network-free) and skips execution unless the
`--run-research` option is passed (see root conftest). Run them with:

    python -m pytest --run-research tests/research -q
"""
import pytest

pytestmark = pytest.mark.research