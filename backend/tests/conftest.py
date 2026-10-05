"""
conftest.py — Shared test configuration for SCOS test suite.

Both test_main.py and test_phase2.py override app.dependency_overrides[get_db].
They use the SAME sqlite test database so module-level overrides don't conflict.
The per-test setup_db fixture (defined in each file) handles create_all/drop_all.
"""
