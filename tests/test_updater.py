import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile

from core.updater import (
    write_status,
    extract_and_stage,
    download_file,
    get_latest_release,
    STATUS_FILE,
    PROTECTED_FILES,
    PROTECTED_DIRS
)


class TestUpdater(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_status(self):
        test_status = os.path.join(self.temp_dir, "test_status.json")
        with patch("core.updater.STATUS_FILE", test_status):
            write_status(
                status="DOWNLOADING",
                pct=45,
                message="Testing status write",
                speed_mb=3.5,
                downloaded_mb=5.0,
                total_mb=11.0,
                version="v2.4.0"
            )
            self.assertTrue(os.path.exists(test_status))
            with open(test_status, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["status"], "DOWNLOADING")
            self.assertEqual(data["pct"], 45)
            self.assertEqual(data["version"], "v2.4.0")
            self.assertEqual(data["speed_mb"], 3.5)

    def test_extract_and_stage_preserves_user_data(self):
        # Create a mock zip archive containing both core files and default user files
        zip_path = os.path.join(self.temp_dir, "test_release.zip")
        staging_dir = os.path.join(self.temp_dir, "staging")
        
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("main.py", "# new main")
            zf.writestr("infosphere_live_wallpaper.html", "<!-- new html -->")
            zf.writestr("user_information.txt", "DEFAULT OPERATOR")  # Must be stripped
            zf.writestr(".env", "DEFAULT ROUTER")                    # Must be stripped
            zf.writestr("Picture/Original Picture/sample.jpg", "pic") # Must be stripped
            zf.writestr("core/test.py", "# core")

        resolved_root = extract_and_stage(zip_path, staging_dir, "v2.4.0")

        self.assertTrue(os.path.exists(os.path.join(resolved_root, "main.py")))
        self.assertTrue(os.path.exists(os.path.join(resolved_root, "infosphere_live_wallpaper.html")))
        self.assertTrue(os.path.exists(os.path.join(resolved_root, "core", "test.py")))

        # Check that protected user data was completely stripped from staging
        self.assertFalse(os.path.exists(os.path.join(resolved_root, "user_information.txt")))
        self.assertFalse(os.path.exists(os.path.join(resolved_root, ".env")))
        self.assertFalse(os.path.exists(os.path.join(resolved_root, "Picture", "Original Picture")))

    def test_extract_and_stage_handles_nested_root_folder(self):
        # Create a mock zip with a single top-level folder (e.g. InfoSphere-v2.4.0/)
        zip_path = os.path.join(self.temp_dir, "nested_release.zip")
        staging_dir = os.path.join(self.temp_dir, "staging_nested")

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("InfoSphere-v2.4.0/main.py", "# nested main")
            zf.writestr("InfoSphere-v2.4.0/infosphere_live_wallpaper.html", "<!-- nested html -->")

        resolved_root = extract_and_stage(zip_path, staging_dir, "v2.4.0")

        self.assertTrue(os.path.exists(os.path.join(resolved_root, "main.py")))
        self.assertTrue(os.path.exists(os.path.join(resolved_root, "infosphere_live_wallpaper.html")))

    @patch("urllib.request.urlopen")
    def test_get_latest_release(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "tag_name": "v2.4.0",
            "name": "InfoSphere v2.4.0 Tactical Release",
            "body": "Changelog details",
            "published_at": "2026-09-21T18:00:00Z",
            "assets": [
                {
                    "name": "InfoSphere-v2.4.0-Windows.zip",
                    "browser_download_url": "https://github.com/mock/download.zip"
                }
            ]
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        rel = get_latest_release()
        self.assertEqual(rel["version"], "v2.4.0")
        self.assertEqual(rel["download_url"], "https://github.com/mock/download.zip")


if __name__ == "__main__":
    unittest.main()
