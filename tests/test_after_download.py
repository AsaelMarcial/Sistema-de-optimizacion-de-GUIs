import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from app import create_app
from engine.domain.models.session import Session


class AfterDownloadTest(unittest.TestCase):
    def test_download_after_folder_as_glow_design_zip_without_after_root(self) -> None:
        original_sessions_root = Session.SESSIONS_ROOT

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                Session.SESSIONS_ROOT = Path(temp_dir)
                after_dir = (
                    Session.SESSIONS_ROOT
                    / "session_download_test"
                    / "after"
                )
                (after_dir / "site" / "css").mkdir(parents=True)
                (after_dir / "site" / "index.html").write_text(
                    "<!doctype html><html></html>",
                    encoding="utf-8",
                )
                (after_dir / "site" / "css" / "glow.css").write_text(
                    ":root {}",
                    encoding="utf-8",
                )
                jpeg_payload = b"\xff\xd8\xff\xe0jpeg-test-bytes\xff\xd9"
                (after_dir / "site" / "assets").mkdir(parents=True)
                (after_dir / "site" / "assets" / "photo.jpeg").write_bytes(
                    jpeg_payload
                )

                app = create_app()
                client = app.test_client()
                response = client.get(
                    "/sessions/session_download_test/download"
                )

                try:
                    self.assertEqual(200, response.status_code)
                    self.assertIn(
                        "glow_design.zip",
                        response.headers.get("Content-Disposition", ""),
                    )

                    with zipfile.ZipFile(
                        io.BytesIO(response.data),
                        "r",
                    ) as archive:
                        names = set(archive.namelist())
                        jpeg_bytes = archive.read(
                            "site/assets/photo.jpeg"
                        )

                    self.assertIn("site/index.html", names)
                    self.assertIn("site/css/glow.css", names)
                    self.assertIn("site/assets/photo.jpeg", names)
                    self.assertEqual(jpeg_payload, jpeg_bytes)
                    self.assertFalse(
                        any(name.startswith("after/") for name in names)
                    )
                finally:
                    response.close()
        finally:
            Session.SESSIONS_ROOT = original_sessions_root


if __name__ == "__main__":
    unittest.main()
