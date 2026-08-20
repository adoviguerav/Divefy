"""Smoke test del esqueleto: el paquete importa. Los tests reales llegan con cada fase."""

def test_package_imports():
    import divefy  # noqa: F401
