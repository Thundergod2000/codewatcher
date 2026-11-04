"""Tests for JS/TS JSDoc check."""

from codewatch.checks.js_docstrings import check_js_docstrings
from codewatch.types import Severity


def test_exported_function_without_jsdoc_warns(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "export function fetchUser(id) {\n"
        "    return id;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["export function fetchUser(id) {"])
    assert result.passed  # warns only
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.WARNING
    assert result.violations[0].line == 1
    assert "fetchUser" in result.violations[0].message


def test_exported_function_with_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "/** Fetch a user by id. */\n"
        "export function fetchUser(id) {\n"
        "    return id;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["export function fetchUser(id) {"])
    assert result.violations == []


def test_multiline_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "/**\n"
        " * Fetch a user by id.\n"
        " * @param {string} id\n"
        " */\n"
        "export function fetchUser(id) {\n"
        "    return id;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["export function fetchUser(id) {"])
    assert result.violations == []


def test_exported_class_without_jsdoc_warns(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "export class UserService {\n"
        "    find() { return null; }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["export class UserService {"])
    by_name = [v for v in result.violations if "UserService" in v.message]
    assert len(by_name) == 1


def test_exported_class_with_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "/** User services. */\n"
        "export class UserService {\n"
        "    find() { return null; }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["export class UserService {"])
    assert result.violations == []


def test_exported_arrow_function_without_jsdoc_warns(tmp_path, monkeypatch):
    src = tmp_path / "utils.ts"
    src.write_text(
        "export const double = (n: number): number => n * 2;\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("utils.ts", ["export const double = (n: number): number => n * 2;"])
    assert len(result.violations) == 1
    assert "double" in result.violations[0].message


def test_exported_arrow_function_with_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "utils.ts"
    src.write_text(
        "/** Double a number. */\n"
        "export const double = (n: number): number => n * 2;\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("utils.ts", ["export const double = (n: number): number => n * 2;"])
    assert result.violations == []


def test_exported_ts_component_without_jsdoc_warns(tmp_path, monkeypatch):
    src = tmp_path / "Button.tsx"
    src.write_text(
        "export const Button = ({ label }: { label: string }) => <button>{label}</button>;\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings(
        "Button.tsx",
        ["export const Button = ({ label }: { label: string }) => <button>{label}</button>;"],
    )
    assert len(result.violations) == 1
    assert "Button" in result.violations[0].message


def test_exported_ts_component_with_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "Button.tsx"
    src.write_text(
        "/** Renders a button. */\n"
        "export const Button = ({ label }: { label: string }) => <button>{label}</button>;\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings(
        "Button.tsx",
        ["export const Button = ({ label }: { label: string }) => <button>{label}</button>;"],
    )
    assert result.violations == []


def test_non_exported_function_ignored(tmp_path, monkeypatch):
    src = tmp_path / "internal.js"
    src.write_text(
        "function helper() {\n"
        "    return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("internal.js", ["function helper() {"])
    assert result.violations == []


def test_internal_arrow_function_ignored(tmp_path, monkeypatch):
    src = tmp_path / "internal.js"
    src.write_text(
        "function run() {\n"
        "    const inner = () => 1;\n"
        "    return inner();\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("internal.js", ["const inner = () => 1;"])
    assert result.violations == []


def test_export_clause_declaration_warns(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "function clauseFn() {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "export { clauseFn };\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["function clauseFn() {"])
    by_name = [v for v in result.violations if "clauseFn" in v.message]
    assert len(by_name) == 1


def test_exported_interface_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "types.ts"
    src.write_text("export interface Props { label: string; }\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("types.ts", ["export interface Props { label: string; }"])
    assert result.violations == []


def test_exported_type_alias_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "types.ts"
    src.write_text("export type Id = string;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("types.ts", ["export type Id = string;"])
    assert result.violations == []


def test_exported_enum_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "types.ts"
    src.write_text("export enum Color { Red, Green }\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("types.ts", ["export enum Color { Red, Green }"])
    assert result.violations == []


def test_class_methods_not_individually_flagged(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "/** A service. */\n"
        "export class Service {\n"
        "    run() { return 1; }\n"
        "    stop() { return 2; }\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["run() { return 1; }", "stop() { return 2; }"])
    assert result.violations == []


def test_preexisting_undocumented_export_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "api.js"
    src.write_text(
        "export function oldExport() {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "/** New export. */\n"
        "export function newExport() {\n"
        "    return 2;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("api.js", ["/** New export. */", "export function newExport() {"])
    assert result.violations == []


def test_missing_file_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("missing.js", ["export const x = 1;"])
    assert result.skipped
    assert "not found" in result.skip_reason


def test_decorated_export_with_jsdoc_passes(tmp_path, monkeypatch):
    src = tmp_path / "app.ts"
    src.write_text(
        "/** App component. */\n"
        "@Component({\n"
        "    selector: 'app-root',\n"
        "})\n"
        "export class AppComponent {\n"
        "    title = 'app';\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("app.ts", ["export class AppComponent {"])
    assert result.violations == []


def test_syntax_error_skips(tmp_path, monkeypatch):
    src = tmp_path / "broken.js"
    src.write_text("export function broken( { return 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_docstrings("broken.js", ["export function broken( {"])
    assert result.skipped
    assert "syntax" in result.skip_reason