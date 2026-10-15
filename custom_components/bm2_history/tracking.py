"""Freshness and recovery decisions shared across all receivers for a battery."""


def should_recover(state, freshest, now, offline_after, sync_interval):
    last_seen = state.get("last_seen", 0)
    if last_seen and now - last_seen > offline_after:
        state["pending"] = True
    if freshest > last_seen:
        if last_seen and freshest - last_seen > offline_after:
            state["pending"] = True
        state["last_seen"] = freshest
    reachable = freshest > 0 and now - freshest <= offline_after
    due = now - state.get("last_sync", 0) >= sync_interval
    return reachable and (state.get("pending", False) or due)


def freshest_source(sources):
    """Select a finite, plausibly decoded voltage; allow flat batteries."""
    import math

    valid = []
    for source in sources:
        try:
            voltage = float(source.state)
        except (ValueError, TypeError):
            continue
        if math.isfinite(voltage) and 0 <= voltage <= 40.95:
            valid.append(source)
    return max(valid, key=lambda source: source.last_reported, default=None)
