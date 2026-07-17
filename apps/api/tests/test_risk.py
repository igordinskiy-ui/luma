from app.content import COPING, PRE_QUIT_STEPS, RECOVERY_STEPS, recovery_for

def test_default_coping_action_is_short_and_available():
    assert "5 минут" in COPING["default"]

def test_known_trigger_has_specific_intervention():
    assert COPING["coffee"] != COPING["default"]

def test_pre_quit_checklist_has_concrete_actions():
    assert len(PRE_QUIT_STEPS) >= 3

def test_recovery_mode_has_non_punitive_actions():
    assert len(RECOVERY_STEPS) >= 3

def test_recovery_changes_for_different_return_states():
    assert recovery_for("one") != recovery_for("days")
    assert recovery_for("afraid") != recovery_for("angry")
