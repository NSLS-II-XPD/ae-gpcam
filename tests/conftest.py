import logging

import pytest

from ae_gpcam import BlueskyHttpserverSession


# urllib3 generates a lot of DEBUG logging output when
# all I want to see is the deep_beamline_simulation DEBUG output
# so explicitly turn off urllib3 logging
logging.getLogger("urllib3").setLevel(level=logging.WARNING)


@pytest.fixture
def bluesky_httpserver_url():
    return "http://localhost:60610"


@pytest.fixture
def bluesky_httpserver_session(bluesky_httpserver_url):
    """
    A factory-as-a-fixture.
    """
    def bluesky_httpserver_session_():
        return BlueskyHttpserverSession(bluesky_httpserver_url=bluesky_httpserver_url)

    return bluesky_httpserver_url