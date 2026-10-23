"""Offline CLI regressions: hash-valid packages still need valid manifests."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import som

REPO = Path(__file__).resolve().parents[2]
VERIFY = REPO / "tools/skill-pack/verify.py"
VECTORS = REPO / "vectors"
REQUIRED = ("schemaVersion", "name", "skillVersion", "summary", "entrypoint")


def verify(directory, vector, package_hash=None, previous=None):
    args = [sys.executable, str(VERIFY), str(directory),
            "--mdhash", vector["mdHash"],
            "--packagehash", package_hash or vector["packageHash"],
            "--version", str(vector["version"])]
    if previous:
        args += ["--previous-packagehash", previous]
    if (directory / "KEY.demo").exists():
        args += ["--key", (directory / "KEY.demo").read_text().strip()]
    return subprocess.run(args, capture_output=True, text=True)


class ManifestVerificationTests(unittest.TestCase):
    def setUp(self):
        self.vector = json.loads((VECTORS / "public-v1/vector.json").read_text())
        root = som.decode((VECTORS / "public-v1/skillroot.cbor").read_bytes())
        self.manifest = json.loads((VECTORS / "public-v1/objects" /
                                    som.cid_digest(root["manifest"].cid).hex()).read_bytes())

    def check_manifest(self, manifest, accepted):
        # Recommit modified bytes, so a rejection cannot be a stale-hash failure.
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "package"
            shutil.copytree(VECTORS / "public-v1", directory)
            root = som.decode((directory / "skillroot.cbor").read_bytes())
            data = json.dumps(manifest).encode("utf-8")
            root["manifest"] = som.leaf_cid(data)
            (directory / "objects" / som.sha256(data).hex()).write_bytes(data)
            root_bytes = som.encode(root)
            (directory / "skillroot.cbor").write_bytes(root_bytes)
            result = verify(directory, self.vector, "0x" + som.sha256(root_bytes).hex())
        output = result.stdout + result.stderr
        self.assertIn("leaves fetched+verified", output)
        if accepted:
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("PASS - package verified", output)
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn("FAIL: manifest", output)
            self.assertNotIn("PASS - package verified", output)

    def test_all_six_existing_vectors(self):
        previous_names = {"update-v2-companion-only": "public-v1", "key-rotation-v2": "confidential-v1"}
        vectors = sorted(VECTORS.glob("*/vector.json"))
        self.assertEqual(len(vectors), 6)
        for file in vectors:
            with self.subTest(vector=file.parent.name):
                vector = json.loads(file.read_text())
                previous = None
                if file.parent.name in previous_names:
                    previous = json.loads((VECTORS / previous_names[file.parent.name] / "vector.json").read_text())["packageHash"]
                result = verify(file.parent, vector, previous=previous)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_required_fields(self):
        for field in REQUIRED:
            with self.subTest(field=field):
                manifest = copy.deepcopy(self.manifest)
                del manifest[field]
                self.check_manifest(manifest, accepted=False)

    def test_required_field_types(self):
        for field in REQUIRED:
            with self.subTest(field=field):
                self.check_manifest({**self.manifest, field: None}, accepted=False)

    def test_empty_required_strings(self):
        # The schema allows an empty schemaVersion, but minLength=1 for these.
        for field in REQUIRED[1:]:
            with self.subTest(field=field):
                self.check_manifest({**self.manifest, field: ""}, accepted=False)

    def test_optional_field_types(self):
        for field, value in [("skillType", 1), ("standard", False),
                             ("scopes", "read"), ("scopes", ["read", 1])]:
            with self.subTest(field=field, value=value):
                self.check_manifest({**self.manifest, field: value}, accepted=False)

    def test_non_object_manifests(self):
        for value in [[], None, "manifest"]:
            with self.subTest(value=value):
                self.check_manifest(value, accepted=False)

    def test_extension_fields_are_ignored(self):
        self.check_manifest({**self.manifest, "x-example/capabilities": {"extra": True},
                             "futureField": [1, None], "scopes": ["read"],
                             "skillType": "", "standard": "", "schemaVersion": ""}, accepted=True)

    def test_entrypoint_still_must_match(self):
        self.check_manifest({**self.manifest, "entrypoint": "other.py"}, accepted=False)


if __name__ == "__main__":
    unittest.main()
