"""Bucket bounds from a decoded prediction market's query components.

SDK-side glue, deliberately kept OUT of ``forecast.py``: that module is a
verbatim mirror of the upstream algorithm in truflation/prediction-bots and
must stay diffable against it. Nothing here is part of the forecast maths.
"""

from typing import Any


def bucket_bounds_from_market_data(
    market_data: dict[str, Any],
) -> tuple[float | None, float | None]:
    """Turn one bucket market's decoded data into its ``(lower, upper)`` bounds.

    ``None`` means open-ended, which is how the outer two buckets of a market
    are always struck. Bounds are half-open ``[lower, upper)`` upstream, so a
    value landing exactly on a boundary resolves the upper bucket only.

    Args:
        market_data: the result of ``TNClient.decode_market_data``.

    Returns:
        ``(lower, upper)``, either of which may be None.

    Raises:
        ValueError: if the market type cannot describe a bucket, or the
            thresholds needed for that type are missing.
    """
    market_type = market_data.get("type")
    thresholds = market_data.get("thresholds") or []

    def threshold(index: int) -> float:
        if len(thresholds) <= index:
            raise ValueError(
                f"a {market_type!r} market needs at least {index + 1} threshold(s), "
                f"got {len(thresholds)}"
            )
        return float(thresholds[index])

    if market_type == "below":
        return None, threshold(0)
    if market_type == "above":
        return threshold(0), None
    if market_type == "between":
        return threshold(0), threshold(1)
    if market_type == "equals":
        # thresholds are (target, tolerance), NOT (lower, upper). Reading them
        # positionally the way `between` is read would give an inverted bucket
        # and be silently wrong rather than loud.
        target, tolerance = threshold(0), threshold(1)
        return target - tolerance, target + tolerance

    raise ValueError(
        f"cannot derive bucket bounds from a {market_type!r} market"
    )
