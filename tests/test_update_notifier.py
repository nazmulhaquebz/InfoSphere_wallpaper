import unittest
from unittest.mock import patch, MagicMock
import json

from core.update_notifier import UpdateNotifier, parse_version
from core.telemetry_snapshot import build_snapshot, validate_snapshot
from tests.test_wallpaper_regression import sample_system, sample_router


class TestUpdateNotifier(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("v2.3.0"), (2, 3, 0))
        self.assertEqual(parse_version("2.3.0"), (2, 3, 0))
        self.assertEqual(parse_version("v2.10.5"), (2, 10, 5))
        self.assertEqual(parse_version("v3.0.0-rc1"), (3, 0, 0))
        self.assertEqual(parse_version("invalid"), (0, 0, 0))

    def test_version_comparison_logic(self):
        self.assertTrue(parse_version("v2.4.0") > parse_version("v2.3.0"))
        self.assertTrue(parse_version("v3.0.0") > parse_version("v2.3.0"))
        self.assertFalse(parse_version("v2.3.0") > parse_version("v2.3.0"))
        self.assertFalse(parse_version("v2.2.9") > parse_version("v2.3.0"))

    @patch("urllib.request.urlopen")
    def test_check_for_updates_available(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.4.0",
            "name": "v2.4.0 Tactical Quantum Release",
            "html_url": "https://github.com/nazmulhaquebz/InfoSphere_wallpaper/releases/tag/v2.4.0",
            "body": "Major performance upgrade and new HUD features."
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        notifier = UpdateNotifier(current_version="v2.3.0")
        info = notifier.check_for_updates()

        self.assertTrue(info["update_available"])
        self.assertEqual(info["latest_version"], "v2.4.0")
        self.assertEqual(info["check_status"], "UPDATE_AVAILABLE")
        self.assertEqual(info["release_url"], "https://github.com/nazmulhaquebz/InfoSphere_wallpaper/releases/tag/v2.4.0")

    @patch("urllib.request.urlopen")
    def test_check_for_updates_up_to_date(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.3.0",
            "name": "v2.3.0",
            "html_url": "https://github.com/nazmulhaquebz/InfoSphere_wallpaper/releases/tag/v2.3.0",
            "body": "Current release."
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        notifier = UpdateNotifier(current_version="v2.3.0")
        info = notifier.check_for_updates()

        self.assertFalse(info["update_available"])
        self.assertEqual(info["latest_version"], "v2.3.0")
        self.assertEqual(info["check_status"], "UP_TO_DATE")

    @patch("urllib.request.urlopen")
    def test_check_for_updates_network_offline(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        notifier = UpdateNotifier(current_version="v2.3.0")
        info = notifier.check_for_updates()

        self.assertFalse(info["update_available"])
        self.assertEqual(info["check_status"], "OFFLINE")

    def test_snapshot_telemetry_integration(self):
        update_info = {
            "update_available": True,
            "current_version": "v2.3.0",
            "latest_version": "v2.4.0",
            "release_url": "https://github.com/nazmulhaquebz/InfoSphere_wallpaper/releases/latest",
            "release_name": "v2.4.0 Tactical Release",
            "published_at": "2026-09-21T12:00:00Z",
            "check_status": "UPDATE_AVAILABLE",
            "last_checked": "2026-09-21 12:00:00"
        }
        snap = build_snapshot(
            sample_system(),
            ["[INFO] test telemetry"],
            {"temp": "25C"},
            sample_router(),
            {"ping_ms": 12.0},
            {"active_file": "test.jpg"},
            {"monitor_count": 1},
            10.0,
            False,
            update_info=update_info
        )
        self.assertEqual([], validate_snapshot(snap))
        self.assertIn("update_info", snap)
        self.assertTrue(snap["update_info"]["update_available"])
        self.assertEqual(snap["update_info"]["latest_version"], "v2.4.0")


if __name__ == "__main__":
    unittest.main()
