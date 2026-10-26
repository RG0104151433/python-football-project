import json

import pytest

from src.artifact_store import INDEX, digest, resolve_artifact, resolve_input


def fixture_store(tmp_path):
    canonical = tmp_path / 'sources/page.html'
    canonical.parent.mkdir()
    canonical.write_text('preserved bytes', encoding='utf-8')
    index = tmp_path / INDEX
    index.parent.mkdir(parents=True)
    record = {'canonical_path':'sources/page.html', 'sha256':digest(canonical)}
    index.write_text(json.dumps({'aliases':{'old/path/page.html':record}}), encoding='utf-8')
    return canonical, record


def test_historical_path_resolves_same_bytes(tmp_path):
    canonical, record = fixture_store(tmp_path)
    assert resolve_artifact('old/path/page.html', tmp_path) == canonical
    item = {'snapshot_path':'old/path/page.html', 'sha256':record['sha256']}
    assert resolve_input(tmp_path, item, tmp_path) == canonical


def test_changed_shared_file_is_rejected(tmp_path):
    canonical, _ = fixture_store(tmp_path)
    canonical.write_text('different bytes', encoding='utf-8')
    with pytest.raises(ValueError):
        resolve_artifact('old/path/page.html', tmp_path)


def test_shared_record_checks_hash_and_cannot_invent_missing_alias(tmp_path):
    canonical, record = fixture_store(tmp_path)
    item = {'storage':'shared', 'shared_path':'sources/page.html', 'sha256':record['sha256']}
    assert resolve_input(tmp_path, item, tmp_path) == canonical
    with pytest.raises(FileNotFoundError):
        resolve_artifact('another/missing.html', tmp_path)
    item['sha256'] = 'wrong'
    with pytest.raises(ValueError):
        resolve_input(tmp_path, item, tmp_path)
