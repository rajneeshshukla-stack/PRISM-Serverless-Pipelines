"""Checksum verification (R2.16, R3.6, R7.7): a Windows checkout must not be reported as corrupt.

CHECKSUMS.sha256 records LF file contents. Git for Windows (core.autocrlf=true) checks text files out with
CRLF line endings, which made `build_manifest.py --verify` flag 201 of 290 files on an unmodified checkout.
The verifier now accepts a text file whose only difference is CRLF line endings, and still fails on any
content change, on a missing file, and on any byte change in a binary file."""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_manifest  # noqa: E402

RECORDED = {                                   # contents as hashed into the manifest
    "src/a.py": b"line one\nline two\n",       # text, recorded LF
    "data/b.csv": b"x,y\n1,2\n",               # text, recorded LF
    "results/c.npz": b"PK\x03\x04\x00\nbin\n",  # binary (NUL byte) with LF bytes inside
    "results/d.png": b"\x89PNG\r\n\x1a\n\x00",  # binary with a CRLF pair inside
    "docs/e.md": b"recorded with CRLF\r\n",    # text recorded with CRLF: byte-for-byte only
    "notes/f.dat": b"one\ntwo\n",              # unknown suffix: never normalised
}


class TestVerifyLineEndings(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        # the manifest itself is a text file and is also converted at checkout
        with open(os.path.join(self.d, "CHECKSUMS.sha256"), "w", encoding="utf-8", newline="\r\n") as fh:
            for p, b in RECORDED.items():
                fh.write(f"{hashlib.sha256(b).hexdigest()}  {p}\n")
        for p, b in RECORDED.items():
            self._write(p, b)
        # what Git for Windows does at checkout: LF -> CRLF in the text files it recognises
        for p in ("src/a.py", "data/b.csv"):
            self._write(p, RECORDED[p].replace(b"\n", b"\r\n"))

    def tearDown(self):
        shutil.rmtree(self.d)

    def _write(self, p, b):
        fp = os.path.join(self.d, p)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as fh:
            fh.write(b)

    def _run(self):
        msgs = []
        return build_manifest.verify(self.d, report=msgs.append), msgs

    def test_checkout_conversion_is_not_a_mismatch(self):
        n, msgs = self._run()
        self.assertEqual((n["files"], n["exact"], n["eol_normalised"], n["mismatch"], n["missing"]), (6, 4, 2, 0, 0))
        self.assertFalse([m for m in msgs if m.startswith(("MISMATCH", "MISSING"))])

    def test_content_change_still_fails(self):
        self._write("src/a.py", b"line one\r\nline 2\r\n")
        n, msgs = self._run()
        self.assertEqual((n["mismatch"], n["eol_normalised"]), (1, 1))
        self.assertIn("MISMATCH src/a.py", msgs)

    def test_missing_file_still_fails(self):
        os.remove(os.path.join(self.d, "data", "b.csv"))
        n, msgs = self._run()
        self.assertEqual(n["missing"], 1)
        self.assertIn("MISSING data/b.csv", msgs)

    def test_binary_converted_at_checkout_fails(self):
        # a binary whose LF bytes were turned into CRLF is corrupt, although normalising would "repair" it
        self._write("results/c.npz", RECORDED["results/c.npz"].replace(b"\n", b"\r\n"))
        n, msgs = self._run()
        self.assertIn("MISMATCH results/c.npz", msgs)
        self.assertEqual(n["mismatch"], 1)

    def test_unknown_suffix_and_crlf_record_are_byte_checked(self):
        self._write("notes/f.dat", RECORDED["notes/f.dat"].replace(b"\n", b"\r\n"))
        self._write("docs/e.md", b"recorded with CRLF\n")      # LF where the record has CRLF
        n, msgs = self._run()
        self.assertIn("MISMATCH notes/f.dat", msgs)
        self.assertIn("MISMATCH docs/e.md", msgs)
        self.assertEqual(n["mismatch"], 2)

    def test_root_without_verify_is_refused_before_any_write(self):
        def boom(*a, **k):
            raise AssertionError("build (writing) mode was entered")
        saved = (sys.argv, build_manifest.git, build_manifest.env, build_manifest.experiments)
        sys.argv = ["build_manifest.py", "--root", self.d]
        build_manifest.git = build_manifest.env = build_manifest.experiments = boom
        try:
            with self.assertRaises(SystemExit) as cm:
                build_manifest.main()
            self.assertEqual(cm.exception.code, 2)
        finally:
            sys.argv, build_manifest.git, build_manifest.env, build_manifest.experiments = saved

    def test_verify_main_on_other_root(self):
        saved = sys.argv
        sys.argv = ["build_manifest.py", "--verify", "--root", self.d]
        try:
            with self.assertRaises(SystemExit) as cm:
                build_manifest.main()
            self.assertEqual(cm.exception.code, 0)
        finally:
            sys.argv = saved

    def test_text_paths(self):
        for p in ("a/b.py", "x.JSONL", "Makefile", "sub/Dockerfile", ".gitignore", "r/c.csv"):
            self.assertTrue(build_manifest.is_text_path(p), p)
        for p in ("a.npz", "b.png", "c.pdf", "d.dat", "Makefile.bak"):
            self.assertFalse(build_manifest.is_text_path(p), p)


if __name__ == "__main__":
    unittest.main()
