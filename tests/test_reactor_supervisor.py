import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "Requires Linux root supervisor")
class PrivateWorkingData(unittest.TestCase):
    def test_only_the_task_execution_user_can_read_its_server_owned_note(self):
        from src.runtime import remote_runner
        with tempfile.TemporaryDirectory() as directory:
            os.chmod(directory, 0o755)
            path = Path(directory) / "note.txt"
            with patch.object(remote_runner.pathlib, "Path", return_value=path):
                remote_runner.prepare_customer_note({"customer_note": "fictional Alice marker"})
            self.assertEqual(path.stat().st_uid, 65534)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            result = subprocess.run(
                [sys.executable, "-I", "-c", "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text())", str(path)],
                preexec_fn=remote_runner.drop_privileges, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b"fictional Alice marker")
            link = Path(directory) / "redirect"
            link.symlink_to(path)
            with patch.object(remote_runner.pathlib, "Path", return_value=link), self.assertRaises(PermissionError):
                remote_runner.prepare_customer_note({"customer_note": "must not overwrite"})
            self.assertEqual(path.read_text(), "fictional Alice marker")


if __name__ == "__main__":
    unittest.main()
