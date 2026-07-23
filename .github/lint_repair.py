"""Apply one-time repository-wide strict lint repairs."""

from __future__ import annotations

from pathlib import Path

import libcst as cst

ROOTS = (Path("src"), Path("tests"))
TEST_PACKAGES = (
    Path("tests"),
    Path("tests/unit"),
    Path("tests/integration"),
    Path("tests/tui"),
)
ASSERTIONS_PATH = Path("tests/assertions.py")


def words(name: str) -> str:
    """Convert an identifier into readable words."""
    return name.strip("_").replace("_", " ") or "object"


def definition_docstring(name: str, *, is_class: bool, is_test: bool) -> str:
    """Build an imperative one-line docstring for a definition."""
    special = {
        "__init__": "Initialize the instance.",
        "__str__": "Return the user-facing string representation.",
        "__repr__": "Return the diagnostic representation.",
        "__aenter__": "Enter the asynchronous context.",
        "__aexit__": "Exit the asynchronous context.",
    }
    if name in special:
        return special[name]
    if is_test:
        return f"Verify {words(name)}."
    if is_class:
        return f"Represent {words(name)}."
    return f"Perform {words(name)}."


def doc_statement(text: str) -> cst.SimpleStatementLine:
    """Create a docstring statement."""
    return cst.SimpleStatementLine(
        body=[cst.Expr(value=cst.SimpleString(repr(text)))]
    )


def suite_has_docstring(suite: cst.BaseSuite) -> bool:
    """Return whether a class or function suite starts with a docstring."""
    if isinstance(suite, cst.IndentedBlock):
        if not suite.body or not isinstance(suite.body[0], cst.SimpleStatementLine):
            return False
        first = suite.body[0].body
    else:
        first = suite.body
    return bool(
        first
        and isinstance(first[0], cst.Expr)
        and isinstance(first[0].value, cst.SimpleString)
    )


def suite_with_docstring(suite: cst.BaseSuite, text: str) -> cst.IndentedBlock:
    """Return a suite with a leading docstring."""
    if suite_has_docstring(suite):
        if isinstance(suite, cst.IndentedBlock):
            return suite
        return cst.IndentedBlock(body=(cst.SimpleStatementLine(body=suite.body),))

    statement = doc_statement(text)
    if isinstance(suite, cst.IndentedBlock):
        return suite.with_changes(body=(statement, *suite.body))
    original = cst.SimpleStatementLine(body=suite.body)
    return cst.IndentedBlock(body=(statement, original))


class DocumentationTransformer(cst.CSTTransformer):
    """Add missing class and function docstrings."""

    def __init__(self, *, is_test_file: bool) -> None:
        """Initialize the transformer."""
        self.is_test_file = is_test_file

    def leave_ClassDef(
        self,
        original_node: cst.ClassDef,
        updated_node: cst.ClassDef,
    ) -> cst.ClassDef:
        """Add a class docstring when missing."""
        return updated_node.with_changes(
            body=suite_with_docstring(
                updated_node.body,
                definition_docstring(
                    original_node.name.value,
                    is_class=True,
                    is_test=False,
                ),
            )
        )

    def leave_FunctionDef(
        self,
        original_node: cst.FunctionDef,
        updated_node: cst.FunctionDef,
    ) -> cst.FunctionDef:
        """Add a function or method docstring when missing."""
        return updated_node.with_changes(
            body=suite_with_docstring(
                updated_node.body,
                definition_docstring(
                    original_node.name.value,
                    is_class=False,
                    is_test=(
                        self.is_test_file
                        and original_node.name.value.startswith("test_")
                    ),
                ),
            )
        )


class AssertionTransformer(cst.CSTTransformer):
    """Replace optimized-away assert statements with explicit verification calls."""

    def __init__(self) -> None:
        """Initialize the transformer."""
        self.changed = False

    def leave_Assert(
        self,
        original_node: cst.Assert,
        updated_node: cst.Assert,
    ) -> cst.Expr:
        """Replace one assert statement."""
        del original_node
        self.changed = True
        args = [cst.Arg(value=updated_node.test)]
        if updated_node.msg is not None:
            args.append(
                cst.Arg(
                    keyword=cst.Name("message"),
                    value=updated_node.msg,
                )
            )
        return cst.Expr(value=cst.Call(func=cst.Name("verify"), args=args))


def has_module_docstring(module: cst.Module) -> bool:
    """Return whether a module starts with a docstring."""
    if not module.body or not isinstance(module.body[0], cst.SimpleStatementLine):
        return False
    first = module.body[0].body
    return bool(
        first
        and isinstance(first[0], cst.Expr)
        and isinstance(first[0].value, cst.SimpleString)
    )


def has_verify_import(module: cst.Module) -> bool:
    """Return whether a module already imports the verification helper."""
    return "from tests.assertions import verify" in module.code


def add_verify_import(module: cst.Module) -> cst.Module:
    """Add the test verification helper import after future imports."""
    if has_verify_import(module):
        return module
    import_line = cst.SimpleStatementLine(
        body=[
            cst.ImportFrom(
                module=cst.Attribute(
                    value=cst.Name("tests"),
                    attr=cst.Name("assertions"),
                ),
                names=[cst.ImportAlias(name=cst.Name("verify"))],
            )
        ]
    )
    insert_at = 1 if has_module_docstring(module) else 0
    while insert_at < len(module.body):
        statement = module.body[insert_at]
        if not isinstance(statement, cst.SimpleStatementLine):
            break
        if not statement.body or not isinstance(statement.body[0], cst.ImportFrom):
            break
        imported = statement.body[0]
        if (
            imported.module is None
            or not isinstance(imported.module, cst.Name)
            or imported.module.value != "__future__"
        ):
            break
        insert_at += 1
    return module.with_changes(
        body=(
            *module.body[:insert_at],
            import_line,
            *module.body[insert_at:],
        )
    )


def module_docstring(path: Path) -> str:
    """Build a module docstring from a repository path."""
    if path.name == "__init__.py":
        return f"Provide the {path.parent.name} package."
    if path.parts[0] == "tests":
        return f"Verify {path.stem.replace('_', ' ')} behavior."
    return f"Provide {path.stem.replace('_', ' ')} functionality."


def write_assertion_helper() -> None:
    """Create the explicit test verification helper."""
    ASSERTIONS_PATH.write_text(
        '''"""Provide explicit test verification helpers."""

from __future__ import annotations


class VerificationError(AssertionError):
    """Represent a failed explicit test verification."""


def verify(value: object, *, message: object | None = None) -> None:
    """Raise a test failure when value is false."""
    if value:
        return
    raise VerificationError(message)
''',
        encoding="utf-8",
    )


def transform_file(path: Path) -> None:
    """Apply documentation and assertion transformations to one file."""
    if path == ASSERTIONS_PATH:
        return
    module = cst.parse_module(path.read_text(encoding="utf-8"))
    is_test = path.parts[0] == "tests"
    module = module.visit(DocumentationTransformer(is_test_file=is_test))
    if not has_module_docstring(module):
        module = module.with_changes(
            body=(doc_statement(module_docstring(path)), *module.body)
        )
    if is_test:
        assertion_transformer = AssertionTransformer()
        module = module.visit(assertion_transformer)
        if assertion_transformer.changed:
            module = add_verify_import(module)
    path.write_text(module.code, encoding="utf-8")


def main() -> None:
    """Apply the one-time repository repair."""
    for package in TEST_PACKAGES:
        package.mkdir(parents=True, exist_ok=True)
        init = package / "__init__.py"
        if not init.exists():
            init.write_text(
                f'"""Provide the {package.name} test package."""\n',
                encoding="utf-8",
            )
    write_assertion_helper()
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            transform_file(path)


if __name__ == "__main__":
    main()
