"""Tests for JS/TS test presence check."""

from codewatch.checks.js_tests import check_js_test_presence
from codewatch.types import Severity


def test_missing_test_file_warns(tmp_path, monkeypatch):
    src = tmp_path / "app.js"
    src.write_text("export const x = 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("app.js", ["export const x = 1;"])
    assert result.passed
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.WARNING
    assert "No test file found" in result.violations[0].message


def test_colocated_test_passes(tmp_path, monkeypatch):
    src = tmp_path / "app.js"
    src.write_text("export const x = 1;\n", encoding="utf-8")
    (tmp_path / "app.test.js").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("app.js", ["export const x = 1;"])
    assert result.violations == []


def test_spec_file_passes(tmp_path, monkeypatch):
    src = tmp_path / "utils.ts"
    src.write_text("export const x = 1;\n", encoding="utf-8")
    (tmp_path / "utils.spec.ts").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("utils.ts", ["export const x = 1;"])
    assert result.violations == []


def test_tests_directory_passes(tmp_path, monkeypatch):
    src = tmp_path / "src" / "utils.ts"
    src.parent.mkdir(parents=True)
    src.write_text("export const x = 1;\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "utils.test.ts").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("src/utils.ts", ["export const x = 1;"])
    assert result.violations == []


def test_dunder_tests_directory_passes(tmp_path, monkeypatch):
    src = tmp_path / "src" / "Button.tsx"
    src.parent.mkdir(parents=True)
    src.write_text("export const Button = () => <button />;\n", encoding="utf-8")
    tests_dir = tmp_path / "__tests__"
    tests_dir.mkdir()
    (tests_dir / "Button.test.tsx").write_text("test('b', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("src/Button.tsx", ["export const Button = () => <button />;"])
    assert result.violations == []


def test_test_prefix_passes(tmp_path, monkeypatch):
    src = tmp_path / "helpers.js"
    src.write_text("export const x = 1;\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_helpers.js").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("helpers.js", ["export const x = 1;"])
    assert result.violations == []


def test_test_file_itself_skipped(tmp_path, monkeypatch):
    src = tmp_path / "app.test.js"
    src.write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("app.test.js", ["test('x', () => {});"])
    assert result.skipped
    assert "test" in result.skip_reason


def test_spec_file_itself_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("app.spec.ts", ["test('x', () => {});"])
    assert result.skipped


def test_dunder_tests_source_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("src/__tests__/app.test.ts", ["test('x', () => {});"])
    assert result.skipped


def test_type_definition_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("types/index.d.ts", ["export interface X {}"])
    assert result.skipped
    assert "type definition" in result.skip_reason


def test_jest_config_skipped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_test_presence("jest.config.js", ["module.exports = {};"])
    assert result.skipped