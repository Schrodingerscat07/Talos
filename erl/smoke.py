"""Integration checks against the live Unreal adapter, never a simulator substitute."""
import time

from .client import Action, Client, ProtocolError
from .recorder import checked_png


def check_live(client: Client, seed: int, allow_no_rgb: bool = False) -> dict:
    results = {}
    first = client.reset(seed)
    if not allow_no_rgb:
        checked_png(first["observation"]["rgb"])
        checked_png(first["privileged"]["observer_rgb"], (640,480))
    results["camera_png"] = "skipped_headless" if allow_no_rgb else "passed"
    time.sleep(0.15)
    idle = client.observe()
    assert idle["step_index"] == 0 and idle["privileged"]["position_cm"] == first["privileged"]["position_cm"]
    results["no_action_no_body_drift"] = "passed"
    path = []
    for action in [Action(forward=1)] * 5 + [Action(turn=1)] * 3 + [Action(strafe=1)] * 4:
        path.append(client.step(action)["privileged"]["position_cm"])
    assert path[4][0] > first["privileged"]["position_cm"][0] + 60, "Forward commands did not move the body"
    assert path[-1] != path[4], "Strafe commands did not move the body"
    results["nonzero_translation"] = "passed"
    reset = client.reset(seed)
    assert reset["episode_id"] != first["episode_id"]
    for key in ("position_cm", "obstacle_position_cm", "seed"):
        assert reset["privileged"][key] == first["privileged"][key]
    repeated = []
    for action in [Action(forward=1)] * 5 + [Action(turn=1)] * 3 + [Action(strafe=1)] * 4:
        repeated.append(client.step(action)["privileged"]["position_cm"])
    assert path == repeated
    results["seeded_kinematic_repetition"] = "passed"
    # A duplicate transition must be rejected rather than accidentally executed twice.
    try:
        client.request("step", {"episode_id": client.episode, "expected_step": 0, "action": Action().payload()})
    except ProtocolError as exc:
        assert "409" in str(exc)
    else:
        raise AssertionError("Stale step was accepted")
    results["stale_step_rejection"] = "passed"
    before = client.observe()
    for bad in [dict(forward=2, strafe=0, turn=0, look=0), dict(forward=True, strafe=0, turn=0, look=0), dict(forward="1", strafe=0, turn=0, look=0)]:
        try:
            client.request("step", {"episode_id": client.episode, "expected_step": client.index, "action": bad})
        except ProtocolError as exc:
            assert "400" in str(exc)
        else:
            raise AssertionError("Invalid action accepted")
    assert client.observe()["step_index"] == before["step_index"]
    results["invalid_actions_do_not_advance"] = "passed"
    client.reset(seed)
    contacts = []
    for _ in range(50):
        contacts.append(client.step(Action(forward=1)))
    assert any(x["observation"]["contacts"]["blocked"] for x in contacts)
    assert contacts[-1]["privileged"]["position_cm"][0] > 100, "Collision check never left the spawn point"
    assert contacts[-1]["privileged"]["position_cm"][0] < 560
    results["collision_sweep"] = "passed"
    old = client.episode
    client.reset(seed)
    try:
        client.request("step", {"episode_id": old, "expected_step": 0, "action": Action().payload()})
    except ProtocolError as exc:
        assert "409" in str(exc)
    else:
        raise AssertionError("Old episode was accepted")
    results["old_episode_rejection"] = "passed"
    client.reset(seed)
    # Exercise the episode boundary without expensive per-frame rasterization in structural runs.
    for _ in range(client.spec()["max_steps"]):
        final = client.step(Action())
    assert final["truncated"] and not final["terminated"]
    try:
        client.step(Action())
    except ProtocolError:
        pass
    else:
        raise AssertionError("Episode limit not enforced")
    results["episode_limit"] = "passed"
    try:
        Client(client.token + "incorrect", port=int(client.base.split(":")[2].split("/")[0]), timeout=10).spec()
    except ProtocolError as exc:
        assert "401" in str(exc)
    else:
        raise AssertionError("Unauthenticated request accepted")
    results["authentication"] = "passed"
    client.reset(seed)
    return {"backend": "live_unreal", "human_verification": "pending", "checks": results}
