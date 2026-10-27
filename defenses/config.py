"""Named defense configs. Each layer has its own switch so the benchmark can compare them."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DefenseConfig:
    policy: bool = False   # layer 1: tool-call policy (defenses/policy.py)
    risk: bool = False     # layer 2: transaction risk score + cooling-off (defenses/risk.py)
    filter: bool = False   # output filter (defenses/output_filter.py)
    risk_threshold: int = 50
    session_hour: int = 14  # mock clock for the timing signal; fixed so runs are deterministic


CONFIGS = {
    "off": DefenseConfig(),
    "policy": DefenseConfig(policy=True),
    "policy+risk": DefenseConfig(policy=True, risk=True),
    "policy+risk+filter": DefenseConfig(policy=True, risk=True, filter=True),
}
