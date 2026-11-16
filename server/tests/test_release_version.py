"""The desktop GUI rejects mismatched health versions even if inference works."""

from pathlib import Path
import re

from app.schemas import HealthResponse
from app.version import APP_VERSION
import desktop_runtime


def test_mobile_health_desktop_and_installer_share_product_version():
    root = Path(__file__).parents[2]
    mobile = re.search(r"^version: ([\d.]+)\+", (root / "pubspec.yaml").read_text(), re.M)[1]
    installer = re.search(
        r"^AppVersion=([\d.]+)",
        (root / "packaging/windows_server/VietLipServer.iss").read_text(),
        re.M,
    )[1]
    assert mobile == installer == APP_VERSION == desktop_runtime.APP_VERSION
    assert HealthResponse.model_fields["app_version"].default == APP_VERSION
