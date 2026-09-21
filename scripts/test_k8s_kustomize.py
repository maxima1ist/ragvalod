"""Validate Kubernetes kustomize builds (stage 11.2+)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KUSTOMIZE_DIRS = [
    ROOT / "k8s" / "base",
    ROOT / "k8s" / "overlays" / "ha",
    ROOT / "k8s" / "overlays" / "monitoring",
    ROOT / "k8s" / "overlays" / "observability",
]


def _kubectl_available() -> bool:
    return shutil.which("kubectl") is not None


@pytest.mark.skipif(not _kubectl_available(), reason="kubectl not installed")
@pytest.mark.parametrize("path", KUSTOMIZE_DIRS, ids=lambda p: p.name)
def test_kustomize_build(path: Path) -> None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "kind:" in result.stdout


def test_k8s_base_manifests_exist() -> None:
    base = ROOT / "k8s" / "base"
    for name in (
        "namespace.yaml",
        "qdrant.yaml",
        "gateway.yaml",
        "ingress.yaml",
        "kustomization.yaml",
    ):
        assert (base / name).is_file(), name
