"""Strict client. Policy code receives observation only; diagnostics stay separate."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

PROTOCOL = "erl/1.0"


class ProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class Action:
    forward: float = 0.0
    strafe: float = 0.0
    turn: float = 0.0
    look: float = 0.0

    def payload(self) -> dict[str, float]:
        values = asdict(self)
        for key, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 1:
                raise ValueError(f"{key} must be finite and within [-1, 1]")
        return values


class Policy(Protocol):
    """Replace with any ML implementation. No engine diagnostics are passed here."""
    def act(self, observation: dict[str, Any]) -> Action: ...


class Client:
    def __init__(self, token: str, port: int = 8765, timeout: float = 120):
        self.base = f"http://127.0.0.1:{port}/v1"
        self.token = token.strip()
        self.timeout = timeout
        self.episode: str | None = None
        self.index: int | None = None
        self.uncertain = False
        self.done = False
        self.opener = build_opener(ProxyHandler({}))

    def request(self, operation: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        request = Request(f"{self.base}/{operation}", data=data, headers={
            "X-ERL-Token": self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                value = json.loads(response.read())
        except HTTPError as exc:
            if exc.code == 409:
                self.uncertain = True
            raise ProtocolError(f"HTTP {exc.code}: {exc.read(4096).decode(errors='replace')}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            if body is not None:
                self.uncertain = True
            raise ProtocolError("Transport/response failure; do not retry a mutation. Reset before continuing.") from exc
        if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
            if body is not None:
                self.uncertain = True
            raise ProtocolError("Unsupported protocol response")
        return value

    def spec(self) -> dict:
        return self.request("spec")

    @staticmethod
    def validate_transition(value: dict) -> None:
        if not isinstance(value.get("episode_id"), str) or not value["episode_id"]:
            raise ProtocolError("Missing episode_id")
        index = value.get("step_index")
        if type(index) is not int or index < 0:
            raise ProtocolError("Invalid step index")
        for key in ("sim_time_s", "reward"):
            number = value.get(key)
            if type(number) not in (int, float) or not math.isfinite(number):
                raise ProtocolError(f"Invalid {key}")
        if not math.isclose(value["sim_time_s"], index * 0.1, abs_tol=1e-6):
            raise ProtocolError("Unexpected simulation clock")
        for key in ("terminated", "truncated"):
            if type(value.get(key)) is not bool:
                raise ProtocolError(f"Invalid {key}")
        observation = value.get("observation")
        if not isinstance(observation, dict) or set(observation) != {"rgb", "proprioception", "contacts"}:
            raise ProtocolError("Unexpected policy observation fields")
        proprio = observation["proprioception"]
        if not isinstance(proprio, dict) or set(proprio) != {"heading_deg", "look_pitch_deg", "local_velocity_cm_s"}:
            raise ProtocolError("Invalid proprioception")
        scalars = [proprio["heading_deg"], proprio["look_pitch_deg"]]
        velocity = proprio["local_velocity_cm_s"]
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ProtocolError("Invalid velocity")
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in scalars + velocity):
            raise ProtocolError("Non-finite proprioception")
        contacts = observation["contacts"]
        if not isinstance(contacts, dict) or set(contacts) != {"blocked"} or type(contacts["blocked"]) is not bool:
            raise ProtocolError("Invalid contacts")

    def reset(self, seed: int = 0) -> dict:
        if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be a nonnegative int32")
        self.uncertain = True
        value = self.request("reset", {"seed": seed})
        self.validate_transition(value)
        if value["step_index"] != 0:
            raise ProtocolError("Reset did not return step zero")
        self.episode, self.index = value["episode_id"], 0
        self.done = value["terminated"] or value["truncated"]
        self.uncertain = False
        return value

    def observe(self) -> dict:
        value = self.request("observe")
        self.validate_transition(value)
        return value

    def step(self, action: Action) -> dict:
        if self.uncertain or self.episode is None or self.done:
            raise ProtocolError("Reset required before stepping")
        payload = action.payload()
        value = self.request("step", {"episode_id": self.episode, "expected_step": self.index, "action": payload})
        try:
            self.validate_transition(value)
            if value["episode_id"] != self.episode or value["step_index"] != self.index + 1:
                raise ProtocolError("Unexpected episode or transition order")
        except ProtocolError:
            self.uncertain = True
            raise
        self.index += 1
        self.done = value["terminated"] or value["truncated"]
        return value
