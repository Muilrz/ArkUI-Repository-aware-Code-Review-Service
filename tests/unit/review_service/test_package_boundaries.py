from __future__ import annotations

import ast
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).parents[3] / "src" / "arkui_agent"
SERVICE_PACKAGE = "arkui_agent.review_service"
LAYERS = ("domain", "ports", "application", "adapters")
R0_C_PUBLIC_MODULES = {
    "application": ("arkui_agent.review_service.application.job_manager",),
    "domain": ("arkui_agent.review_service.domain.job",),
    "ports": (
        "arkui_agent.review_service.ports.engine",
        "arkui_agent.review_service.ports.errors",
        "arkui_agent.review_service.ports.gitcode",
        "arkui_agent.review_service.ports.knowledge",
        "arkui_agent.review_service.ports.models",
        "arkui_agent.review_service.ports.result_store",
    ),
}


def imported_modules(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(PACKAGE_ROOT)
    package_parts = ("arkui_agent", *relative.parent.parts)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.level == 0:
                modules.append(node.module)
                if node.module in {"arkui_agent", SERVICE_PACKAGE}:
                    modules.extend(
                        f"{node.module}.{alias.name}" for alias in node.names
                    )
                continue
            parent_count = len(package_parts) - (node.level - 1)
            resolved = (*package_parts[:parent_count], *node.module.split("."))
            modules.append(".".join(resolved))
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            parent_count = len(package_parts) - (node.level - 1)
            parent = package_parts[:parent_count]
            modules.extend(".".join((*parent, alias.name)) for alias in node.names)
    return tuple(modules)


def python_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


class ReviewServicePackageBoundaryTests(unittest.TestCase):
    def test_expected_layers_are_importable(self) -> None:
        for layer in LAYERS:
            with self.subTest(layer=layer):
                __import__(f"{SERVICE_PACKAGE}.{layer}")

    def test_r0_c_public_modules_are_owned_by_declared_layers(self) -> None:
        for layer, module_names in R0_C_PUBLIC_MODULES.items():
            for module_name in module_names:
                with self.subTest(layer=layer, module=module_name):
                    module = __import__(module_name, fromlist=("*",))
                    module_path = Path(module.__file__).resolve()
                    relative_parts = module_path.relative_to(PACKAGE_ROOT).parts
                    self.assertEqual(relative_parts[1], layer)

    def test_service_layers_only_point_inward(self) -> None:
        allowed_service_dependencies = {
            "domain": frozenset({"domain"}),
            "ports": frozenset({"domain", "ports"}),
            "application": frozenset({"application", "domain", "ports"}),
            "adapters": frozenset({"adapters", "domain", "ports"}),
        }

        service_root = PACKAGE_ROOT / "review_service"
        violations: list[str] = []
        for layer, allowed in allowed_service_dependencies.items():
            for path in python_files(service_root / layer):
                for module in imported_modules(path):
                    prefix = f"{SERVICE_PACKAGE}."
                    if not module.startswith("arkui_agent."):
                        continue
                    if not module.startswith(prefix):
                        if layer != "adapters":
                            violations.append(
                                f"{path.relative_to(PACKAGE_ROOT)}: "
                                f"{layer} imports legacy package {module}"
                            )
                        continue
                    dependency = module.removeprefix(prefix).split(".", 1)[0]
                    if dependency not in allowed:
                        violations.append(
                            f"{path.relative_to(PACKAGE_ROOT)}: "
                            f"{layer} imports disallowed layer {dependency}"
                        )

        self.assertEqual(violations, [])

    def test_existing_packages_do_not_depend_on_review_service(self) -> None:
        violations: list[str] = []
        for path in python_files(PACKAGE_ROOT):
            if "review_service" in path.relative_to(PACKAGE_ROOT).parts:
                continue
            for module in imported_modules(path):
                if module == SERVICE_PACKAGE or module.startswith(
                    f"{SERVICE_PACKAGE}."
                ):
                    violations.append(
                        f"{path.relative_to(PACKAGE_ROOT)} imports {module}"
                    )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
