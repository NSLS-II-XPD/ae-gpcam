from ae_gpcam import BlueskyHttpserverSession


def test_connect(bluesky_httpserver_url):
    """
    This test is successful if no exception is raised.
    """
    with BlueskyHttpserverSession(bluesky_httpserver_url=bluesky_httpserver_url) as bluesky_httpserver_session:
        pass
