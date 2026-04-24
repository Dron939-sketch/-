"""Regression guard: importing api.auth_routes must succeed in CI.

Catches missing optional dependencies like `email-validator` that
pydantic.EmailStr needs at class-definition time. Without this test
the production instance was failing to boot because CI only imported
auth/security.py directly, not the route module.
"""

from __future__ import annotations

import pytest

# The whole point of these tests is to exercise the FastAPI / pydantic
# import chain as CI would see it. When fastapi isn't available (e.g. a
# minimal local pytest env), skip rather than false-fail.
pytest.importorskip("fastapi")
pytest.importorskip("pydantic")


def test_auth_routes_module_imports_cleanly():
    # Importing the module triggers pydantic BaseModel class construction
    # for LoginRequest / RegisterRequest, which in turn loads the
    # `email-validator` package via pydantic.EmailStr. If that dep
    # isn't installed, this test will fail at import time with
    # `ImportError: email-validator is not installed`.
    import api.auth_routes as m

    # Sanity-check a couple of exports exist so the import actually
    # succeeded end-to-end (rather than being stubbed or no-op'd).
    assert hasattr(m, "router")
    assert hasattr(m, "LoginRequest")
    assert hasattr(m, "RegisterRequest")
    assert hasattr(m, "require_user")
    assert hasattr(m, "require_role")


def test_auth_main_module_imports_cleanly():
    # Same idea for api.main — make sure the whole FastAPI factory imports
    # without side effects like unregistered optional deps.
    import api.main as m

    assert hasattr(m, "create_app")
    assert hasattr(m, "app")
