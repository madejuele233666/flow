from flow_engine.state.machine import (
    IllegalTransitionError,
    TaskState,
    can_transition,
)


def test_can_transition_ready_to_in_progress() -> None:
    assert can_transition(TaskState.READY, TaskState.IN_PROGRESS) is True


def test_can_transition_done_to_ready_is_not_allowed() -> None:
    assert can_transition(TaskState.DONE, TaskState.READY) is False


def test_illegal_transition_error_contains_states() -> None:
    err = IllegalTransitionError(TaskState.DONE, TaskState.READY)
    text = str(err)
    assert "Done" in text
    assert "Ready" in text
