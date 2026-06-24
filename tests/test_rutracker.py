from unittest.mock import patch, MagicMock
import pytest
from rutracker import RutrackerClient


SEARCH_HTML = """
<table id="tor-tbl">
  <tbody>
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t=12345">
          Интерстеллар / Interstellar (2014) BDRip 1080p
        </a>
      </td>
      <td class="tor-size" data-ts_text="16344498176">15.2 GB</td>
      <td><b class="seedmed">142</b></td>
    </tr>
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t=67890">
          Интерстеллар / Interstellar (2014) HDRip 720p
        </a>
      </td>
      <td class="tor-size" data-ts_text="5000000000">4.8 GB</td>
      <td><b class="seedmed">89</b></td>
    </tr>
  </tbody>
</table>
"""

EMPTY_HTML = "<html><body><p>No results</p></body></html>"


def make_client():
    return RutrackerClient("testuser", "testpass")


@patch("rutracker.requests.Session")
def test_login_success(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {"bb_session": "abc123"}

    client = make_client()
    client.login()

    assert client._logged_in is True
    mock_session.post.assert_called_once()


@patch("rutracker.requests.Session")
def test_login_failure_no_cookie(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {}

    client = make_client()
    with pytest.raises(ValueError, match="Login failed"):
        client.login()

    assert client._logged_in is False


def test_parse_search_results_returns_results():
    client = make_client()
    results = client._parse_search_results(SEARCH_HTML)
    assert len(results) == 2
    assert results[0].topic_id == "12345"
    assert results[0].title == "Интерстеллар / Interstellar (2014) BDRip 1080p"
    assert results[0].size == "15.2 GB"
    assert results[0].seeders == 142


def test_parse_search_results_empty_page():
    client = make_client()
    results = client._parse_search_results(EMPTY_HTML)
    assert results == []


def test_parse_search_results_caps_at_10():
    row = """
    <tr class="tCenter">
      <td class="t-title">
        <a class="tLink" href="/forum/viewtopic.php?t={i}">Title {i}</a>
      </td>
      <td class="tor-size">1 GB</td>
      <td><b class="seedmed">10</b></td>
    </tr>"""
    rows = "".join(row.format(i=i) for i in range(15))
    html = f'<table id="tor-tbl"><tbody>{rows}</tbody></table>'
    client = make_client()
    results = client._parse_search_results(html)
    assert len(results) == 10


@patch("rutracker.requests.Session")
def test_search_redirects_to_login_triggers_relogin(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session

    # First get: redirected to login page
    redirect_response = MagicMock()
    redirect_response.url = "https://rutracker.org/forum/login.php"
    redirect_response.text = EMPTY_HTML

    # After re-login: normal response
    normal_response = MagicMock()
    normal_response.url = "https://rutracker.org/forum/tracker.php"
    normal_response.text = SEARCH_HTML

    mock_session.get.side_effect = [redirect_response, normal_response]
    mock_session.post.return_value = MagicMock()
    mock_session.cookies = {"bb_session": "abc123"}

    client = make_client()
    client._logged_in = True
    results = client.search("Интерстеллар")

    assert mock_session.post.called  # re-login happened
    assert len(results) == 2


TOPIC_HTML_WITH_MAGNET = """
<html><body>
<a class="magnet-link" href="magnet:?xt=urn:btih:abc123def456&dn=Interstellar">
  Magnet link
</a>
</body></html>
"""

TOPIC_HTML_NO_MAGNET = "<html><body><p>No magnet here</p></body></html>"

FAKE_TORRENT_BYTES = b"d8:announce35:http://retracker.local/announce13:announce-listlee"


@patch("rutracker.requests.Session")
def test_get_torrent_returns_bytes(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.url = "https://rutracker.org/forum/dl.php?t=12345"
    mock_response.content = FAKE_TORRENT_BYTES
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    result = client.get_torrent("12345")

    assert result == FAKE_TORRENT_BYTES
    mock_session.get.assert_called_once()
    call_args = mock_session.get.call_args
    assert "dl.php" in call_args.args[0]


@patch("rutracker.requests.Session")
def test_get_magnet_returns_link(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.text = TOPIC_HTML_WITH_MAGNET
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    magnet = client.get_magnet("12345")

    assert magnet == "magnet:?xt=urn:btih:abc123def456&dn=Interstellar"


@patch("rutracker.requests.Session")
def test_get_magnet_returns_none_if_not_found(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    mock_response = MagicMock()
    mock_response.text = TOPIC_HTML_NO_MAGNET
    mock_session.get.return_value = mock_response

    client = make_client()
    client._logged_in = True
    magnet = client.get_magnet("12345")

    assert magnet is None
