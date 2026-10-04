"""Validate Sigma rules using pySigma's validation framework."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Validators that work reliably on a single rule (no collection context needed)
_VALIDATOR_SPECS: list[tuple[str, str, str]] = [
    # (module_path, class_name, description)
    ("sigma.validators.core.metadata", "IdentifierExistenceValidator", "Missing UUID identifier"),
    ("sigma.validators.core.metadata", "DuplicateReferencesValidator", "Duplicate references"),
    ("sigma.validators.core.metadata", "CustomAttributesValidator", "Misspelled field name"),
    ("sigma.validators.core.condition", "DanglingDetectionValidator", "Detection not used in condition"),
    ("sigma.validators.core.condition", "DanglingConditionValidator", "Condition references undefined detection"),
    ("sigma.validators.core.condition", "AllOfThemConditionValidator", "Use 'all of selection*' instead of 'all of them'"),
    ("sigma.validators.core.condition", "ThemConditionWithSingleDetectionValidator", "'them' with single detection"),
    ("sigma.validators.core.tags", "TagFormatValidator", "Invalid tag format"),
    ("sigma.validators.core.tags", "ATTACKTagValidator", "Invalid MITRE ATT&CK tag"),
    ("sigma.validators.core.tags", "DuplicateTagValidator", "Duplicate tags"),
    ("sigma.validators.core.tags", "NamespaceTagValidator", "Invalid tag namespace"),
    ("sigma.validators.core.modifiers", "InvalidModifierCombinationsValidator", "Invalid modifier combination"),
    ("sigma.validators.core.values", "DoubleWildcardValidator", "Consecutive wildcards (**)"),
    ("sigma.validators.core.values", "NumberAsStringValidator", "Number expressed as string"),
    ("sigma.validators.core.values", "WildcardsInsteadOfModifiersValidator", "Use contains/startswith/endswith modifier"),
]


@dataclass
class ValidationResult:
    valid: bool
    parse_error: str | None
    issues: list[dict[str, str]]


def validate_rule(rule_yaml: str) -> dict[str, Any]:
    """Parse and validate a Sigma rule YAML string. Returns a dict with results."""
    result = _validate(rule_yaml)
    return {
        "valid": result.valid,
        "parse_error": result.parse_error,
        "issues": result.issues,
        "summary": _summarize(result),
    }


def _validate(rule_yaml: str) -> ValidationResult:
    try:
        from sigma.rule import SigmaRule  # type: ignore[import-untyped]
        from sigma.validation import SigmaValidator  # type: ignore[import-untyped]
    except ImportError as exc:
        return ValidationResult(
            valid=False,
            parse_error=f"pySigma not installed: {exc}",
            issues=[],
        )

    # Step 1: Parse
    try:
        rule = SigmaRule.from_yaml(rule_yaml)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(valid=False, parse_error=str(exc), issues=[])

    # Step 2: Collect available validators
    validator_classes = _load_validators()
    if not validator_classes:
        return ValidationResult(valid=True, parse_error=None, issues=[])

    # Step 3: Run validators
    try:
        validator = SigmaValidator(validators=validator_classes)
        raw_issues = validator.validate_rule(rule)
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(valid=False, parse_error=f"Validator error: {exc}", issues=[])

    issues = [
        {
            "severity": issue.severity.name,
            "message": str(issue),
        }
        for issue in raw_issues
    ]
    has_high = any(i["severity"] == "HIGH" for i in issues)
    return ValidationResult(valid=not has_high, parse_error=None, issues=issues)


def _load_validators() -> list[type]:
    """Dynamically load available validator classes, skipping unavailable ones."""
    classes: list[type] = []
    for module_path, class_name, _ in _VALIDATOR_SPECS:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            classes.append(cls)
        except (ImportError, AttributeError):
            pass
    return classes


def _summarize(result: ValidationResult) -> str:
    if result.parse_error:
        return f"❌ Parse error: {result.parse_error}"
    if not result.issues:
        return "✅ Rule is valid – no issues found."

    high = [i for i in result.issues if i["severity"] == "HIGH"]
    medium = [i for i in result.issues if i["severity"] == "MEDIUM"]
    low = [i for i in result.issues if i["severity"] == "LOW"]

    lines = []
    if high:
        lines.append(f"❌ {len(high)} HIGH severity issue(s) – must fix:")
        for i in high:
            lines.append(f"  • {i['message']}")
    if medium:
        lines.append(f"⚠️  {len(medium)} MEDIUM severity issue(s):")
        for i in medium:
            lines.append(f"  • {i['message']}")
    if low:
        lines.append(f"ℹ️  {len(low)} LOW severity issue(s):")
        for i in low:
            lines.append(f"  • {i['message']}")

    status = "❌ Invalid" if not result.valid else "⚠️  Valid with warnings"
    lines.insert(0, status)
    return "\n".join(lines)
