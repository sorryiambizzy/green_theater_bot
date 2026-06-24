from unittest.mock import patch, MagicMock
import pytest
from rutracker import RutrackerClient


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
