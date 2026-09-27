"""Validate Kubernetes kustomize builds."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KUSTOMIZE_DIRS = [
    ROOT / "k8s" / "base",
    ROOT / "k8s" / "overlays" / "ha",
    ROOT / "k8s" / "overlays" / "local",
    ROOT / "k8s" / "overlays" / "local-ha",
    ROOT / "k8s" / "overlays" / "local-gpu",
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


@pytest.mark.skipif(not _kubectl_available(), reason="kubectl not installed")
def test_service_links_disabled_for_named_ports() -> None:
    """K8s injects VLLM_PORT/INFINITY_PORT as tcp://… unless service links are off."""
    result = subprocess.run(
        ["kubectl", "kustomize", str(ROOT / "k8s" / "base")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.count("enableServiceLinks: false") >= 2
    assert "name: VLLM_PORT" not in result.stdout
    assert "name: INFINITY_PORT" not in result.stdout


@pytest.mark.skipif(not _kubectl_available(), reason="kubectl not installed")
def test_local_overlays_mount_test_data() -> None:
    for overlay in ("local", "local-ha", "local-gpu"):
        result = subprocess.run(
            ["kubectl", "kustomize", str(ROOT / "k8s" / "overlays" / overlay)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "mountPath: /test_data" in result.stdout, overlay
        assert "path: /test_data" in result.stdout, overlay


@pytest.mark.skipif(not _kubectl_available(), reason="kubectl not installed")
def test_monitoring_overlay_runs_hourly_judge() -> None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(ROOT / "k8s" / "overlays" / "monitoring")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "kind: CronJob" in result.stdout
    assert "name: judge" in result.stdout
    assert "schedule: 0 * * * *" in result.stdout or "schedule: 0 * * * *" in result.stdout
    assert "JUDGE_KEEP_SERVICE_HOSTS" in result.stdout
    assert "http://langfuse:3000" in result.stdout
    assert "http://litellm:4000" in result.stdout
    assert "ragvalod/judge:latest" in result.stdout


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
