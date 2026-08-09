"""Strict canonical YAML loader for evaluation registries, suites, and cases."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from peos.domain.errors import EvaluationConfigurationError, EvaluationIntegrityError
from peos.domain.evaluations import BudgetLimits, EvalCase, EvalSuite

JsonObject = dict[str, object]
REGISTRY_KEYS = {"schema_version", "suites"}
REF_KEYS = {"name", "version", "task_kind", "path", "sha256", "status", "qualification_suite"}
SUITE_KEYS = {
    "schema_version",
    "name",
    "version",
    "task_kind",
    "protocol",
    "output_contract",
    "required_capabilities",
    "sensitivity_ceiling",
    "scorers",
    "thresholds",
    "budget",
    "cases",
}
CASE_KEYS = {"schema_version", "id", "task_kind", "input_fixture", "expected", "tags"}


class FilesystemEvaluationSuiteRepository:
    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root.resolve()
        self._evals = (self._root / "evals").resolve()

    def list_active(self) -> tuple[EvalSuite, ...]:
        registry = self._mapping(self._read(self._evals / "registry.yaml"), REGISTRY_KEYS)
        if registry.get("schema_version") != 1 or not isinstance(registry.get("suites"), list):
            raise EvaluationConfigurationError("Evaluation registry is invalid.")
        refs = registry["suites"]
        assert isinstance(refs, list)
        active: list[EvalSuite] = []
        identities: set[tuple[object, object]] = set()
        active_tasks: set[str] = set()
        for value in refs:
            ref = self._strict_object(value, REF_KEYS, "suite registry entry")
            identity = (ref["name"], ref["version"])
            if identity in identities:
                raise EvaluationConfigurationError("Evaluation suite name/version is duplicated.")
            identities.add(identity)
            if ref["status"] != "active" or ref["qualification_suite"] is not True:
                continue
            task = self._text(ref["task_kind"], "task kind")
            if task in active_tasks:
                raise EvaluationConfigurationError("Task has multiple active qualification suites.")
            active_tasks.add(task)
            active.append(self._load_ref(ref))
        return tuple(sorted(active, key=lambda suite: (suite.task_kind, suite.name, suite.version)))

    def get(self, name: str) -> EvalSuite:
        matches = [suite for suite in self.list_active() if suite.name == name]
        if len(matches) != 1:
            raise EvaluationConfigurationError("Active evaluation suite was not found uniquely.")
        return matches[0]

    def active_for_task(self, task_kind: str) -> EvalSuite:
        matches = [suite for suite in self.list_active() if suite.task_kind == task_kind]
        if len(matches) != 1:
            raise EvaluationConfigurationError("Task lacks one active qualification suite.")
        return matches[0]

    def _load_ref(self, ref: JsonObject) -> EvalSuite:
        path = self._path(self._text(ref["path"], "suite path"))
        raw = self._read(path)
        self._hash(raw, self._text(ref["sha256"], "suite hash"))
        data = self._mapping(raw, SUITE_KEYS)
        for key in ("name", "version", "task_kind"):
            if data[key] != ref[key]:
                raise EvaluationIntegrityError(
                    "Suite registry identity conflicts with suite bytes."
                )
        protocol = self._strict_object(data["protocol"], {"name", "version", "sha256"}, "protocol")
        contract = self._strict_object(
            data["output_contract"], {"name", "schema_hash"}, "output contract"
        )
        scorers = self._strict_object(data["scorers"], {"deterministic", "reference"}, "scorers")
        thresholds = self._strict_object(
            data["thresholds"], {"deterministic_all_pass", "min_reference_pass_rate"}, "thresholds"
        )
        budget = self._strict_object(
            data["budget"],
            {
                "max_provider_calls_per_case",
                "max_input_tokens_per_case",
                "max_output_tokens_per_case",
                "max_input_bytes_per_case",
                "max_output_bytes_per_case",
            },
            "budget",
        )
        if thresholds["deterministic_all_pass"] is not True:
            raise EvaluationConfigurationError("Deterministic scorers must all pass.")
        case_refs = data["cases"]
        if not isinstance(case_refs, list):
            raise EvaluationConfigurationError("Suite cases must be a list.")
        cases: list[EvalCase] = []
        seen_paths: set[str] = set()
        for item in case_refs:
            case_ref = self._strict_object(item, {"path", "sha256"}, "case reference")
            relative = self._text(case_ref["path"], "case path")
            if relative in seen_paths:
                raise EvaluationConfigurationError("Case path is duplicated.")
            seen_paths.add(relative)
            case_raw = self._read(self._path(relative))
            self._hash(case_raw, self._text(case_ref["sha256"], "case hash"))
            case_data = self._mapping(case_raw, CASE_KEYS)
            if case_data["schema_version"] != 1 or case_data["task_kind"] != data["task_kind"]:
                raise EvaluationConfigurationError("Evaluation case identity is invalid.")
            fixture, expected = case_data["input_fixture"], case_data["expected"]
            tags = case_data["tags"]
            if (
                not isinstance(fixture, dict)
                or not isinstance(expected, dict)
                or not isinstance(tags, list)
                or not all(isinstance(tag, str) for tag in tags)
            ):
                raise EvaluationConfigurationError("Evaluation case payload is invalid.")
            cases.append(
                EvalCase(
                    self._text(case_data["id"], "case ID"),
                    self._text(case_data["task_kind"], "task kind"),
                    cast(JsonObject, fixture),
                    cast(JsonObject, expected),
                    tuple(tags),
                    self._digest(case_raw),
                )
            )
        capabilities = data["required_capabilities"]
        if not isinstance(capabilities, list) or not all(
            isinstance(item, str) for item in capabilities
        ):
            raise EvaluationConfigurationError("Required capabilities are invalid.")
        deterministic, reference = scorers["deterministic"], scorers["reference"]
        if (
            not isinstance(deterministic, list)
            or not isinstance(reference, list)
            or not all(isinstance(item, str) for item in [*deterministic, *reference])
        ):
            raise EvaluationConfigurationError("Scorer lists are invalid.")
        return EvalSuite(
            self._text(data["name"], "suite name"),
            self._text(data["version"], "suite version"),
            self._text(data["task_kind"], "task kind"),
            self._digest(raw),
            self._text(protocol["name"], "protocol name"),
            self._text(protocol["version"], "protocol version"),
            self._text(protocol["sha256"], "protocol hash"),
            self._text(contract["name"], "contract name"),
            self._text(contract["schema_hash"], "schema hash"),
            frozenset(capabilities),
            self._text(data["sensitivity_ceiling"], "sensitivity"),
            tuple(deterministic),
            tuple(reference),
            float(cast(float, thresholds["min_reference_pass_rate"])),
            BudgetLimits(**cast(dict[str, int], budget)),
            tuple(cases),
        )

    def _path(self, relative: str) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise EvaluationConfigurationError("Evaluation path must be safe and relative.")
        path = (self._root / candidate).resolve()
        if self._evals != path and self._evals not in path.parents:
            raise EvaluationConfigurationError("Evaluation path escapes evals directory.")
        return path

    @staticmethod
    def _read(path: Path) -> bytes:
        try:
            raw = path.read_bytes()
        except OSError as error:
            raise EvaluationConfigurationError("Evaluation file cannot be read.") from error
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
            raise EvaluationConfigurationError(
                "Evaluation YAML requires LF and exactly one final LF."
            )
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise EvaluationConfigurationError("Evaluation YAML must be UTF-8.") from error
        return raw

    @staticmethod
    def _mapping(raw: bytes, keys: set[str]) -> JsonObject:
        try:
            value = yaml.safe_load(raw)
        except yaml.YAMLError as error:
            raise EvaluationConfigurationError("Evaluation YAML is malformed.") from error
        return FilesystemEvaluationSuiteRepository._strict_object(value, keys, "evaluation file")

    @staticmethod
    def _strict_object(value: object, keys: set[str], label: str) -> JsonObject:
        if not isinstance(value, dict) or set(value) != keys:
            raise EvaluationConfigurationError(f"Strict {label} keys are invalid.")
        return cast(JsonObject, value)

    @staticmethod
    def _text(value: object, label: str) -> str:
        if not isinstance(value, str) or not value:
            raise EvaluationConfigurationError(f"Evaluation {label} is invalid.")
        return value

    @staticmethod
    def _hash(raw: bytes, expected: str) -> None:
        if FilesystemEvaluationSuiteRepository._digest(raw) != expected:
            raise EvaluationIntegrityError("Evaluation raw-byte hash does not match registry.")

    @staticmethod
    def _digest(raw: bytes) -> str:
        return "sha256:" + hashlib.sha256(raw).hexdigest()
