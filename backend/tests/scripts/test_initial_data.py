from unittest.mock import MagicMock, patch

from app.initial_data import init, main, logger


def test_init_calls_init_db() -> None:
    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.initial_data.Session", return_value=session_mock),
        patch("app.initial_data.init_db") as mock_init_db,
    ):
        init()
        mock_init_db.assert_called_once_with(session_mock)


def test_main_logs_and_calls_init() -> None:
    with (
        patch("app.initial_data.init") as mock_init,
        patch.object(logger, "info") as mock_log,
    ):
        main()
        mock_init.assert_called_once()
        assert mock_log.call_count == 2
