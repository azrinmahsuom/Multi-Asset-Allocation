import pytest

from analysis import manifest


@pytest.fixture
def raw(tmp_path):
    root = tmp_path / "raw"
    (root / "src").mkdir(parents=True)
    path = root / "src" / "file.csv"
    path.write_text("date,value\n2020-01,1\n")
    return root, path, tmp_path / "MANIFEST.yaml"


def test_record_then_verify_passes(raw):
    root, path, manifest_path = raw
    manifest.record(path, {"source": "test"}, manifest_path, root)
    assert manifest.load(manifest_path)["src/file.csv"]["source"] == "test"
    assert manifest.verify_data(manifest_path, root) == 1


def test_verify_fails_when_file_changes(raw):
    root, path, manifest_path = raw
    manifest.record(path, {"source": "test"}, manifest_path, root)
    path.write_text("date,value\n2020-01,2\n")
    with pytest.raises(manifest.DataVerificationError, match="hash mismatch"):
        manifest.verify_data(manifest_path, root)


def test_verify_fails_when_file_missing(raw):
    root, path, manifest_path = raw
    manifest.record(path, {"source": "test"}, manifest_path, root)
    path.unlink()
    with pytest.raises(manifest.DataVerificationError, match="missing"):
        manifest.verify_data(manifest_path, root)


def test_verify_fails_on_empty_manifest(tmp_path):
    with pytest.raises(manifest.DataVerificationError):
        manifest.verify_data(tmp_path / "MANIFEST.yaml", tmp_path)


def test_data_status_separates_ok_missing_changed(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.csv").write_text("1")
    (raw / "b.csv").write_text("2")
    m = tmp_path / "MANIFEST.yaml"
    manifest.record(raw / "a.csv", {}, m, raw)
    manifest.record(raw / "b.csv", {}, m, raw)
    entries = manifest.load(m)
    entries["c.csv"] = {"sha256": "0"}
    manifest.save(entries, m)
    (raw / "b.csv").write_text("changed")
    status = manifest.data_status(m, raw)
    assert status == {"ok": ["a.csv"], "missing": ["c.csv"], "changed": ["b.csv"]}
