from .phase_two import build_phase_two_dashboard
from .phase_three import build_phase_three_dashboard


def build_indicator_dashboard(key: str, params):
    return build_phase_two_dashboard(key, params) or build_phase_three_dashboard(key, params)


__all__ = ["build_indicator_dashboard", "build_phase_two_dashboard", "build_phase_three_dashboard"]
