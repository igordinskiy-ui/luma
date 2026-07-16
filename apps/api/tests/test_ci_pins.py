import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from check_ci_pins import CONTAINER_FILES, WORKFLOW, unpinned_actions, unpinned_container_images  # noqa: E402


def test_all_remote_ci_actions_are_pinned_to_full_sha():
    assert unpinned_actions(WORKFLOW.read_text(encoding="utf-8")) == []


def test_mutable_action_tags_are_rejected():
    assert unpinned_actions("      - uses: actions/checkout@v4\n") == ["line 1: actions/checkout@v4"]


def test_all_remote_container_images_are_pinned_to_digest():
    failures = [
        failure
        for path in CONTAINER_FILES
        for failure in unpinned_container_images(path.read_text(encoding="utf-8"), str(path.relative_to(ROOT)))
    ]
    assert failures == []


def test_mutable_container_tags_are_rejected():
    assert unpinned_container_images("image: redis:7.4-alpine\n", "compose.yml") == [
        "compose.yml:1: redis:7.4-alpine"
    ]
