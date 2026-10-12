import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.request import Request

from data.pipeline import download_aact as downloader


class Response(io.BytesIO):
    def __init__(self, payload, *, length, status=200, content_range=None):
        super().__init__(payload)
        self.status = status
        self.url = "https://us.aws.cdn.hf.co/test-input?Signature=transient-secret"
        self.headers = {"Content-Length": str(length)}
        if content_range is not None:
            self.headers["Content-Range"] = content_range


class AactDownloadTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.cache = Path(self.workspace.name) / "cache"
        self.payload = b"Fictional small database bytes for downloader tests."
        self.source = {
            **downloader.load_source(),
            "bytes": len(self.payload),
            "sha256": hashlib.sha256(self.payload).hexdigest(),
        }
        self.directory = self.cache / "aact" / self.source["revision"] / self.source["sha256"]
        self.database = self.directory / "clinicaltrials.duckdb"
        self.partial = self.directory / "clinicaltrials.duckdb.partial"
        self.receipt = self.directory / "acquisition-receipt.json"

    def tearDown(self):
        self.workspace.cleanup()

    def test_verified_download_and_reuse_require_the_exact_bytes(self):
        response = Response(self.payload, length=len(self.payload))
        opener = Mock()
        opener.open.return_value = response
        with patch.object(downloader, "build_opener", return_value=opener):
            result = downloader.download_aact(self.source, self.cache)
        self.assertEqual(self.database.read_bytes(), self.payload)
        self.assertFalse(self.partial.exists())
        self.assertFalse(result["cache_reused"])
        receipt = json.loads(self.receipt.read_text())
        self.assertEqual(receipt["source"], self.source)
        self.assertFalse(receipt["source_review_approved"])
        self.assertNotIn("transient-secret", self.receipt.read_text())
        with patch.object(downloader, "build_opener") as network:
            self.assertTrue(downloader.download_aact(self.source, self.cache)["cache_reused"])
            self.database.write_bytes(b"x" * len(self.payload))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                downloader.download_aact(self.source, self.cache)
            network.assert_not_called()
        self.assertEqual(self.database.read_bytes(), b"x" * len(self.payload))

    def test_truncated_download_resumes_with_an_exact_range_and_full_hash(self):
        split = 12
        opener = Mock()
        opener.open.side_effect = [
            Response(self.payload[:split], length=len(self.payload)),
            Response(
                self.payload[split:], length=len(self.payload) - split, status=206,
                content_range=f"bytes {split}-{len(self.payload) - 1}/{len(self.payload)}",
            ),
        ]
        with patch.object(downloader, "build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "truncated"):
                downloader.download_aact(self.source, self.cache)
            self.assertEqual(self.partial.read_bytes(), self.payload[:split])
            self.assertFalse(self.receipt.exists())
            self.assertFalse(self.database.exists())
            result = downloader.download_aact(self.source, self.cache)
        resumed_request = opener.open.call_args.args[0]
        self.assertEqual(resumed_request.get_header("Range"), f"bytes={split}-")
        self.assertTrue(result["checksum_verified"])
        self.assertEqual(self.database.read_bytes(), self.payload)

    def test_cache_reuse_rejects_missing_or_mismatched_receipts_without_network(self):
        with patch.object(
            downloader, "open_source", return_value=Response(self.payload, length=len(self.payload))
        ):
            downloader.download_aact(self.source, self.cache)
        receipt = json.loads(self.receipt.read_text())
        with patch.object(downloader, "open_source") as network:
            for key, value in (
                ("sha256", "0" * 64),
                ("bytes", 1),
                ("source_review_approved", True),
                ("attendee_release_approved", True),
            ):
                with self.subTest(key=key):
                    self.receipt.write_text(json.dumps({**receipt, key: value}))
                    with self.assertRaisesRegex(ValueError, "receipt does not match"):
                        downloader.download_aact(self.source, self.cache)
            self.receipt.unlink()
            with self.assertRaisesRegex(ValueError, "no acquisition receipt"):
                downloader.download_aact(self.source, self.cache)
            network.assert_not_called()
        self.assertEqual(self.database.read_bytes(), self.payload)

    def test_resume_rejects_ignored_or_wrong_ranges_without_appending(self):
        self.directory.mkdir(parents=True)
        self.partial.write_bytes(self.payload[:5])
        for status, content_range in ((200, None), (206, "bytes 0-3/4")):
            with self.subTest(status=status, content_range=content_range):
                response = Response(
                    self.payload[5:], length=len(self.payload) - 5,
                    status=status, content_range=content_range,
                )
                with patch.object(downloader, "open_source", return_value=response):
                    with self.assertRaisesRegex(ValueError, "range contract"):
                        downloader.download_aact(self.source, self.cache)
                self.assertEqual(self.partial.read_bytes(), self.payload[:5])
                self.assertFalse(self.database.exists())
                self.assertFalse(self.receipt.exists())

    def test_bad_size_hash_or_encoding_never_publishes_a_cache(self):
        for fault in ("advertised-size", "oversized", "hash", "encoding"):
            with self.subTest(fault=fault):
                cache = self.cache / fault
                response = Response(
                    self.payload + b"x" if fault == "oversized" else (
                        b"x" * len(self.payload) if fault == "hash" else self.payload
                    ),
                    length=len(self.payload) + (1 if fault == "advertised-size" else 0),
                )
                if fault == "encoding":
                    response.headers["Content-Encoding"] = "gzip"
                with patch.object(downloader, "open_source", return_value=response):
                    with self.assertRaises(ValueError):
                        downloader.download_aact(self.source, cache)
                self.assertFalse(list(cache.rglob("clinicaltrials.duckdb")))
                self.assertFalse(list(cache.rglob("acquisition-receipt.json")))

    def test_empty_and_complete_partial_files_can_finish_without_overwrite(self):
        self.directory.mkdir(parents=True)
        self.partial.touch()
        with patch.object(
            downloader, "open_source", return_value=Response(self.payload, length=len(self.payload))
        ):
            downloader.download_aact(self.source, self.cache)
        self.assertEqual(self.database.read_bytes(), self.payload)
        self.database.rename(self.partial)
        self.receipt.unlink()
        with patch.object(downloader, "open_source") as network:
            downloader.download_aact(self.source, self.cache)
            network.assert_not_called()
        self.assertEqual(self.database.read_bytes(), self.payload)

    def test_scope_space_and_lock_fail_before_network_or_overwrite(self):
        with patch.object(downloader, "open_source") as network:
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                downloader.download_aact(self.source, downloader.ROOT / ".raw-source-cache")
            with patch.object(
                downloader.shutil, "disk_usage", return_value=SimpleNamespace(free=0)
            ):
                with self.assertRaisesRegex(OSError, "Insufficient cache space"):
                    downloader.download_aact(self.source, self.cache)
            lock = self.directory / ".download.lock"
            lock.write_text("another downloader")
            with self.assertRaisesRegex(FileExistsError, "locked"):
                downloader.download_aact(self.source, self.cache)
            self.assertEqual(lock.read_text(), "another downloader")
            network.assert_not_called()

    def test_availability_check_does_not_create_or_download_a_cache(self):
        response = Response(b"", length=self.source["bytes"])
        opener = Mock()
        opener.open.return_value = response
        with patch.object(downloader, "build_opener", return_value=opener):
            result = downloader.check_source(self.source)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), "HEAD")
        self.assertFalse(result["downloaded"])
        self.assertFalse(result["checksum_verified"])
        self.assertFalse(self.cache.exists())
        with patch.object(
            downloader, "open_source", return_value=Response(b"", length=self.source["bytes"] + 1)
        ), self.assertRaisesRegex(ValueError, "advertised size"):
            downloader.check_source(self.source)

    def test_mutable_or_unsafe_pins_and_redirects_are_rejected(self):
        descriptor = Path(self.workspace.name) / "source.json"
        for key, value in (
            ("revision", "main"),
            ("bytes", True),
            ("sha256", "not-a-checksum"),
            ("filename", "..\\clinicaltrials.duckdb"),
            ("source_review_approved", True),
            ("url", self.source["url"] + "?token=private"),
        ):
            with self.subTest(key=key):
                descriptor.write_text(json.dumps({**self.source, key: value}))
                with patch.object(downloader, "SOURCE_PATH", descriptor):
                    with self.assertRaises(ValueError):
                        downloader.load_source()
        handler = downloader.HuggingFaceRedirects()
        for url in (
            "http://us.aws.cdn.hf.co/file",
            "https://untrusted.example/file",
            "https://huggingface.co.untrusted.example/file",
            "https://name:password@huggingface.co/file",
            "https://us.aws.cdn.hf.co:444/file",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(Request(self.source["url"]), None, 302, "Found", {}, url)


if __name__ == "__main__":
    unittest.main()
