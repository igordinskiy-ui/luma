import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from check_ci_pins import WORKFLOW, unpinned_actions  # noqa: E402


def test_all_remote_ci_actions_are_pinned_to_full_sha():
    assert unpinned_actions(WORKFLOW.read_text(encoding="utf-8")) == []


def test_mutable_action_tags_are_rejected():
    assert unpinned_actions("      - uses: actions/checkout@v4\n") == ["line 1: actions/checkout@v4"]
