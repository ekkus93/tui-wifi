"""Apply systematic documentation fixes to the repository."""

from __future__ import annotations

import ast
from pathlib import Path

ROOTS = (Path("src"), Path("tests"))
PACKAGES = (Path("tests/unit"), Path("tests/integration"), Path("tests/tui"))


def sentence(name: str, kind: str) -> str:
    """Return an imperative one-line docstring for a definition."""
    words = name.strip("_").replace("_", " ") or "object"
    special = {
        "__init__": "Initialize the instance.",
        "__str__": "Return the user-facing string representation.",
        "__repr__": "Return the diagnostic representation.",
        "__aenter__": "Enter the asynchronous context.",
        "__aexit__": "Exit the asynchronous context.",
    }
    if name in special:
        return special[name]
    if kind == "test":
        return f"Verify {words}."
    if kind == "class":
        return f"Represent {words}."
    return f"Perform {words}."


def add_docstrings(path: Path) -> None:
    """Add missing module and definition docstrings to one source file."""
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    lines = text.splitlines()
    insertions: list[tuple[int, str]] = []
    if ast.get_docstring(tree, clean=False) is None:
        label = path.stem.replace("_", " ")
        if path.name == "__init__.py":
            module_doc = f'"""Provide the {path.parent.name} package."""'
        elif path.parts[0] == "tests":
            module_doc = f'"""Verify {label} behavior."""'
        else:
            module_doc = f'"""Provide {label} functionality."""'
        insertions.append((0, module_doc))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if ast.get_docstring(node, clean=False) is not None or not node.body:
            continue
        if node.body[0].lineno == node.lineno:
            continue
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        if path.parts[0] == "tests" and kind == "function":
            kind = "test"
        index = node.body[0].lineno - 1
        indent = " " * (node.col_offset + 4)
        insertions.append((index, f'{indent}"""{sentence(node.name, kind)}"""'))

    for index, content in sorted(insertions, reverse=True):
        lines.insert(index, content)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """Apply documentation updates to all source and test modules."""
    for package in PACKAGES:
        init = package / "__init__.py"
        if not init.exists():
            init.write_text(
                f'"""Provide the {package.name} test package."""\n',
                encoding="utf-8",
            )
    for root in ROOTS:
        for source in sorted(root.rglob("*.py")):
            add_docstrings(source)


if __name__ == "__main__":
    main()
