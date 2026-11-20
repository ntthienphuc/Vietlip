"""The desktop GUI rejects mismatched health versions even if inference works."""

from pathlib import Path
import re

from app.schemas import HealthResponse
from app.version import APP_VERSION
import desktop_runtime


def test_companion_matches_installer_and_checks_the_bundled_engine_health_version():
    root = Path(__file__).parents[2]
    mobile = re.search(r"^version: ([\d.]+)\+", (root / "pubspec.yaml").read_text(), re.M)[1]
    installer = re.search(
        r"^AppVersion=([\d.]+)",
        (root / "packaging/windows_server/VietLipServer.iss").read_text(),
        re.M,
    )[1]
    assert mobile == installer == desktop_runtime.DESKTOP_VERSION
    assert APP_VERSION == desktop_runtime.APP_VERSION
    assert HealthResponse.model_fields["app_version"].default == APP_VERSION
