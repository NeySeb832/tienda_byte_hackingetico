"""Architecture guard-rails (ADR-0001): every app follows the layered layout."""

import importlib
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from django.conf import settings

APPS_DIR = Path(settings.BASE_DIR) / "apps"
REQUIRED_FILES = (
    "__init__.py",
    "apps.py",
    "models.py",
    "services.py",
    "selectors.py",
    "forms.py",
    "views.py",
    "permissions.py",
    "migrations/__init__.py",
    "tests/__init__.py",
)
APP_DIRS = sorted(path.parent.name for path in APPS_DIR.glob("*/apps.py"))


def _modules() -> list[str]:
    modules = []
    for path in sorted(APPS_DIR.rglob("*.py")):
        parts = path.relative_to(settings.BASE_DIR).with_suffix("").parts
        if "migrations" in parts or "tests" in parts:
            continue
        modules.append(".".join(parts).removesuffix(".__init__"))
    return modules


def test_every_app_directory_is_installed():
    installed = {cfg.label for cfg in django_apps.get_app_configs() if cfg.name.startswith("apps.")}
    assert installed == set(APP_DIRS)


@pytest.mark.parametrize("app", APP_DIRS)
def test_app_follows_layered_structure(app):
    missing = [name for name in REQUIRED_FILES if not (APPS_DIR / app / name).is_file()]
    assert not missing, f"apps/{app} is missing: {missing}"


@pytest.mark.parametrize("module", _modules())
def test_module_imports_cleanly(module):
    importlib.import_module(module)
