"""Market-implied point forecast from prediction-market order book state.

Prediction markets price RANGES. A five-bucket EPS market says "38% chance EPS
lands between $4.33 and $4.62"; it never says "EPS will be $4.47". This module
inverts that. Given the order books across every bucket of one market, it
produces the single number the book is collectively implying, together with how
tightly the book pins that number down.

    market says            ->   this module says
    "34% between 2.40-2.63"     "2.43, margin of error 0.02"

How it works
------------
A market is N buckets, each its own query_id and its own binary book, and the
outer two are open-ended:

    bucket 1  (-inf, B1)      bucket 2  [B1, B2)   ...   bucket N  [Bn-1, +inf)

Bounds are HALF-OPEN, matching how the markets are actually created
(`market_generator.py`: `value < upper`, `value >= lower AND value < upper`,
`value >= lower`). So the buckets are mutually exclusive and exhaustive, and a
value landing exactly on a boundary resolves the UPPER bucket only.

1. Each bucket's book implies a probability. Two-sided is the mid, with
   confidence from how tight the spread is. One-sided takes the quoted side and
   steps across by the market's own median half-spread, at reduced confidence:
   on real books the open tail buckets are often bid-only at a penny, and
   treating that as the midpoint of [0.01, 1.0] calls a dead tail a coin flip.
   That single mistake handed MSFT's two tails 27% each and buried the real
   distribution, so the rule matters more than it looks.

2. Bucket probabilities are normalised to sum to 1, since independent books
   never sum to exactly 1 on their own because of spreads and staleness. A
   bucket with no orders at all takes the residual the quoted buckets leave
   behind rather than an invented value.

3. Those give the implied CDF at each interior boundary: the probability the
   outcome lands at or below B_k is the sum of the buckets up to k.

4. A normal is fitted through those CDF points by weighted least squares on the
   probit scale, so B_k ~= mu + sigma * z_k. The fit is what makes the open
   tails tractable: no assumption is needed about how far bucket 1 extends,
   because the tail buckets constrain the fit through their probability mass
   rather than through any assumed value. Fitting a normal is also consistent
   with how these markets are constructed, since the bucket boundaries are laid
   out on z-scores in the first place.

The point estimate is the MEDIAN read directly off that CDF (rank method):
walk up the cumulative probabilities until they cross 50% and interpolate
within the bucket where the crossing happens. No distribution shape is
assumed for anything interior. The published band is P10..P90 read the same
way. When a requested percentile falls inside an OPEN-ENDED outer bucket the
books contain no information about how far out it lies, so an exponential
tail matched to the adjacent bucket's density supplies a number, and the
result is flagged (`value_basis` / `p10_basis` / `p90_basis` = "tail") so
consumers can decide whether to show it. Markets struck so that the mass
stays between the outer boundaries never need the tail model at all.

A normal fit was the previous method and remains in the file as a diagnostic
only. Its known failures (confidently wrong on bimodal books, grid-dependent
near expiry) are what the rank method replaces.

`confidence` per bucket is (1 - spread) * min(1, n / median(n)) with n the
thinner side's committed dollars, standardised against the market's own
depth so no external constant is needed. It does not move the median; it is
published as book quality and drives warnings.
"""

# Ported verbatim from truflation/prediction-bots @ main 21fe4f3 (PR #37),
# whose last change to this file was fafe52b. Upstream path:
# market-maker-bot/src/market_maker_bot/forecast.py
#
# Kept byte-identical on purpose: the algorithm is validated against live
# mainnet books there and is still moving fast, so re-syncing must stay a diff
# rather than a re-write. Change it upstream first, then copy the file across.
# To check for drift, diff this file against upstream ignoring this header.

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import List, Optional, Sequence

__all__ = [
    "BucketBook",
    "BucketEstimate",
    "MarketForecast",
    "BookLevel",
    "BucketDepth",
    "bucket_probability",
    "bucket_estimate_from_depth",
    "typical_half_spread",
    "forecast_from_buckets",
    "forecast_from_depth",
]

# Probabilities are clamped this far away from 0 and 1 before the probit
# transform, since Phi^-1(0) and Phi^-1(1) are infinite.
_EPS = 1e-4

# A bracket at least this wide contributes essentially nothing to the fit.
_MIN_CONFIDENCE = 1e-3

# Half-spread used to complete a one-sided quote when the market gives us
# nothing better. Bounds keep a pathological book from imputing a silly step.
_DEFAULT_HALF_SPREAD = 0.06
_MIN_HALF_SPREAD = 0.01
_MAX_HALF_SPREAD = 0.20

# A quote below this notional is treated as absent. Size does not enter the
# forecast itself, so without a floor a single tiny order at a silly price moves
# the published number as much as a real one: one 90c bid on a dead tail shifted
# a bimodal market by 8 units, for 90c of risk. Only applied when sizes are
# supplied; callers that pass none keep the old behaviour.
MIN_QUOTE_NOTIONAL_CENT_SHARES = 100

# The buckets are mutually exclusive and exhaustive, so the asks must cost at
# least 1 and the bids must not pay more than 1. Outside these, someone is
# giving money away. Warned on rather than normalised silently.
_DUTCH_BOOK_TOLERANCE = 0.02

# Depth path only. A side whose ENTIRE ladder holds less than this many dollars
# is treated as absent: with the full book summed, dust cannot hide in front of
# a real order, so a small floor is enough to make sub-dollar griefing quotes
# weightless. Tunable.
DEPTH_MIN_SIDE_NOTIONAL_USD = 5.0

# Disclosure threshold only, never part of the math: a market whose books hold
# less than this in total gets a warning attached, because relative
# standardisation cannot see absolute poverty.
LOW_TOTAL_NOTIONAL_WARN_USD = 50.0

# A second density peak only counts as real multimodality if it reaches this
# fraction of the tallest peak; below it is quote noise.
PEAK_PROMINENCE = 0.20

_NORM = NormalDist()


@dataclass(frozen=True)
class BucketBook:
    """One bucket's bounds and its best two-sided quote, in cents.

    ``lower``/``upper`` are None for the open-ended outer buckets. Prices are
    the positive 1-99 cent convention for the bucket's YES side; None means no
    resting order on that side.
    """

    lower: Optional[float]
    upper: Optional[float]
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    query_id: Optional[int] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None

    def _usable(self, price: Optional[float], size: Optional[float]) -> Optional[float]:
        """Drop a top-of-book quote too small to mean anything.

        LIMITATION: this only sees the best level. If a dust order is sitting in
        front of a real one, dropping it here marks the whole bucket unpriced
        rather than falling back to the real quote behind it, which can be worse
        than not filtering at all. Callers that hold the full book should instead
        pass the best level whose size clears the floor, and leave these
        arguments unset. This is a backstop, not the fix.
        """
        if price is None or size is None:
            return price
        return price if price * size >= MIN_QUOTE_NOTIONAL_CENT_SHARES else None

    def usable_bid(self) -> Optional[float]:
        return self._usable(self.best_bid, self.bid_size)

    def usable_ask(self) -> Optional[float]:
        return self._usable(self.best_ask, self.ask_size)


@dataclass(frozen=True)
class BookLevel:
    """One resting level: price in cents (positive, 1-99), size in shares."""

    price: float
    size: float


@dataclass(frozen=True)
class BucketDepth:
    """One bucket's FULL ladders on all four sides.

    The YES and NO books are consolidated inside this module because the
    inversion is executable, not merely informative. Verified on testnet
    (2026-08-03): the protocol's fill hierarchy matches EXACT inverses. A
    resting BUY NO at p mint-matches an incoming BUY YES at 100-p (one pair
    minted for $1), and a resting SELL NO at p burn-matches an incoming SELL
    YES at 100-p (one pair merged for $1). So:

        consolidated bids = yes_bids + (100 - p for every NO ask)
        consolidated asks = yes_asks + (100 - p for every NO bid)

    both sides hittable at exactly the inverted price. There is no
    price-improvement crossing: near-inverses (sums other than 100) rest.
    """

    lower: Optional[float]
    upper: Optional[float]
    yes_bids: Sequence[BookLevel] = ()
    yes_asks: Sequence[BookLevel] = ()
    no_bids: Sequence[BookLevel] = ()
    no_asks: Sequence[BookLevel] = ()
    query_id: Optional[int] = None

    def consolidated_bids(self) -> List[BookLevel]:
        lv = [l for l in self.yes_bids if l.size > 0]
        lv += [BookLevel(round(100.0 - l.price, 4), l.size)
               for l in self.no_asks if l.size > 0]
        return sorted(lv, key=lambda l: -l.price)

    def consolidated_asks(self) -> List[BookLevel]:
        lv = [l for l in self.yes_asks if l.size > 0]
        lv += [BookLevel(round(100.0 - l.price, 4), l.size)
               for l in self.no_bids if l.size > 0]
        return sorted(lv, key=lambda l: l.price)

    def best_view(self) -> "BucketBook":
        """The consolidated best quotes, for spread/dutch-book helpers."""
        bids, asks = self.consolidated_bids(), self.consolidated_asks()
        return BucketBook(
            self.lower, self.upper,
            bids[0].price if bids else None,
            asks[0].price if asks else None,
            self.query_id,
        )


@dataclass(frozen=True)
class BucketEstimate:
    """What one bucket's book implies about its probability."""

    query_id: Optional[int]
    lower: Optional[float]
    upper: Optional[float]
    probability: float          # normalised, sums to 1 across the market
    raw_probability: float      # before normalisation
    confidence: float           # 0 = no usable quote, 1 = tight two-sided
    one_sided: bool
    quoted: bool


@dataclass
class MarketForecast:
    """The single value a market's order books imply.

    ``value`` is the MEDIAN of the implied distribution. ``p10``/``p90`` are
    the published band. Each carries a basis flag: "interior" means it was
    read between real strikes with no shape assumption; "tail" means it fell
    inside an open-ended outer bucket and rests on the exponential tail model;
    "unresolved" means the market has too few strikes to place it at all.

    ``margin_of_error`` is kept for downstream compatibility as half the
    P10..P90 band; ``sigma`` as the band scaled to a normal-equivalent
    standard deviation (band / 2.5631). Prefer the quantiles directly.
    """

    value: float
    margin_of_error: float
    sigma: float
    method: str                 # "rank" or "discrete"
    buckets: List[BucketEstimate] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    p10: Optional[float] = None
    p90: Optional[float] = None
    value_basis: str = "interior"
    p10_basis: str = "interior"
    p90_basis: str = "interior"
    multimodal: bool = False
    n_peaks: int = 1

    @property
    def low(self) -> float:
        return self.value - self.margin_of_error

    @property
    def high(self) -> float:
        return self.value + self.margin_of_error

    def as_dict(self) -> dict:
        """Flat form for SDKs and the indexer."""
        return {
            "value": self.value,
            "value_basis": self.value_basis,
            "p10": self.p10,
            "p90": self.p90,
            "p10_basis": self.p10_basis,
            "p90_basis": self.p90_basis,
            "margin_of_error": self.margin_of_error,
            "low": self.low,
            "high": self.high,
            "sigma": self.sigma,
            "method": self.method,
            "multimodal": self.multimodal,
            "probabilities": [b.probability for b in self.buckets],
            "warnings": list(self.warnings),
        }


def typical_half_spread(buckets: Sequence["BucketBook"]) -> float:
    """Half the market's median two-sided spread, as a probability.

    Used to complete one-sided quotes. A missing side is usually an artifact of
    our own quoting (no inventory to sell, or the self-cross guard suppressing
    a leg) rather than a statement about probability, so the other side is
    still informative once shifted by the spread this market actually trades.
    """
    spreads = [
        (b.best_ask - b.best_bid) / 100.0
        for b in buckets
        if b.best_bid is not None
        and b.best_ask is not None
        and b.best_ask >= b.best_bid
    ]
    if not spreads:
        return _DEFAULT_HALF_SPREAD
    spreads.sort()
    mid = len(spreads) // 2
    median = (
        spreads[mid]
        if len(spreads) % 2
        else (spreads[mid - 1] + spreads[mid]) / 2.0
    )
    return max(_MIN_HALF_SPREAD, min(median / 2.0, _MAX_HALF_SPREAD))


def bucket_probability(
    best_bid: Optional[float],
    best_ask: Optional[float],
    half_spread: float = _DEFAULT_HALF_SPREAD,
) -> tuple[Optional[float], float, bool, bool]:
    """Turn one bucket's best quote into (probability, confidence, one_sided, quoted).

    Two-sided is the easy case: the mid, with confidence from how tight the
    spread is.

    One-sided needs care. Treating a lone 1c bid as the midpoint of [0.01, 1.0]
    would call it a coin flip, which is badly wrong: on real mainnet books the
    open tail buckets are frequently bid-only at a penny, and the midpoint rule
    handed them 27% each and buried the actual distribution. The quoted side is
    the only real information, so we take it and step across by the market's own
    half-spread, then mark the confidence down.

    An unquoted bucket returns None. It is NOT 0.5: the caller assigns it the
    residual probability the quoted buckets leave behind, which is what the
    market actually implies about it.
    """
    quoted = best_bid is not None or best_ask is not None
    if not quoted:
        return None, 0.0, False, False

    one_sided = best_bid is None or best_ask is None

    if not one_sided:
        lo = max(0.0, min(1.0, best_bid / 100.0))
        hi = max(0.0, min(1.0, best_ask / 100.0))
        if hi < lo:
            # Crossed book: bid above ask. Either stale, or free money. The old
            # code kept the midpoint at low confidence, but confidence only
            # affects the FIT WEIGHT -- the bogus probability still entered the
            # normalisation and shifted every CDF point. Treat it as unquoted so
            # the caller can assign it the residual instead.
            return None, 0.0, one_sided, quoted
        return (lo + hi) / 2.0, 1.0 - (hi - lo), one_sided, quoted

    if best_bid is not None:
        p = best_bid / 100.0 + half_spread
    else:
        p = best_ask / 100.0 - half_spread
    p = max(0.0, min(1.0, p))
    # Confidence of a two-sided book at this spread, halved: we inferred one
    # side rather than observing it.
    return p, max(_MIN_CONFIDENCE, (1.0 - 2.0 * half_spread) / 2.0), one_sided, quoted


def _boundaries(buckets: Sequence[BucketBook]) -> List[float]:
    """Interior boundaries, i.e. the upper edge of every bucket but the last."""
    return [b.upper for b in buckets[:-1] if b.upper is not None]


def _fit_normal(
    boundaries: Sequence[float],
    cumulative: Sequence[float],
    weights: Sequence[float],
) -> Optional[tuple[float, float, float]]:
    """Weighted least-squares fit of B_k = mu + sigma * z_k.

    Weights combine quote quality with PROBIT LEVERAGE. A boundary out in the
    tail carries a cumulative probability near 0 or 1, where dz/dC = 1/phi(z) is
    enormous, so a 1c quote error there swings z far more than the same error at
    the centre. Weighting by quote tightness alone let those noisy tail points
    dominate: on a near-resolved book (1/1/1/96/1) the fit returned a value
    OUTSIDE the 96% bucket. Scaling by phi(z)^2 is the delta-method correction
    and puts it back inside (0.634 -> 1.119).

    Returns (mu, sigma, standard_error_of_mu), or None if the points cannot
    support a fit.
    """
    # Two different weightings, deliberately kept apart. `ws` drives the
    # regression and carries the phi(z)^2 leverage correction. `confs` stays on
    # the original 0..1 quote-quality scale and is the only thing the confidence
    # floor below may use: folding phi(z)^2 into it would read a perfectly good
    # book as near-zero confidence, since phi(z)^2 <= 0.16 by construction.
    zs, bs, ws, confs = [], [], [], []
    for b, c, w in zip(boundaries, cumulative, weights):
        if w <= _MIN_CONFIDENCE:
            continue
        c = min(max(c, _EPS), 1.0 - _EPS)
        z = _NORM.inv_cdf(c)
        zs.append(z)
        bs.append(b)
        ws.append(w * _NORM.pdf(z) ** 2)
        confs.append(w)
    if ws and max(ws) <= 0:
        return None

    n = len(zs)
    if n < 2:
        return None

    sw = sum(ws)
    mean_z = sum(w * z for w, z in zip(ws, zs)) / sw
    mean_b = sum(w * b for w, b in zip(ws, bs)) / sw
    szz = sum(w * (z - mean_z) ** 2 for w, z in zip(ws, zs))
    if szz <= 0:
        # Every usable boundary carries the same implied probability, so the
        # book says nothing about the spread and the slope is unidentifiable.
        return None
    szb = sum(w * (z - mean_z) * (b - mean_b) for w, z, b in zip(ws, zs, bs))

    sigma = szb / szz
    mu = mean_b - sigma * mean_z
    if not (sigma > 0) or not math.isfinite(mu):
        return None

    # Standard error of the intercept under weighted least squares. With only
    # two points the fit is exact and the residual variance is zero, so fall
    # back to a spread-based floor rather than claiming infinite precision.
    dof = n - 2
    if dof > 0:
        resid = sum(
            w * (b - (mu + sigma * z)) ** 2 for w, z, b in zip(ws, zs, bs)
        )
        s2 = resid / dof
        se = math.sqrt(max(s2, 0.0) * (1.0 / sw + mean_z**2 / szz))
    else:
        se = 0.0

    # However well the points line up, we cannot pin the centre tighter than
    # the quotes themselves allow. Confidence-weighted so a wide or one-sided
    # book widens the band instead of flattering it.
    avg_conf = sum(confs) / max(len(confs), 1)
    floor = sigma * (1.0 - avg_conf) / max(math.sqrt(n), 1.0)
    return mu, sigma, max(se, floor)


def _discrete_fallback(
    estimates: Sequence[BucketEstimate], boundaries: Sequence[float]
) -> tuple[float, float]:
    """Probability-weighted bucket midpoints, for when the fit cannot run.

    The open tails have no midpoint, so they are represented by their finite
    edge pushed out by half the average interior width. Cruder than the fit and
    biased toward the centre, which is why it is only a fallback.
    """
    widths = [
        hi - lo
        for lo, hi in zip(boundaries, boundaries[1:])
        if hi is not None and lo is not None
    ]
    pad = (sum(widths) / len(widths) / 2.0) if widths else 0.0

    points, probs = [], []
    for est in estimates:
        if est.lower is None and est.upper is None:
            continue
        if est.lower is None:
            point = est.upper - pad
        elif est.upper is None:
            point = est.lower + pad
        else:
            point = (est.lower + est.upper) / 2.0
        points.append(point)
        probs.append(est.probability)

    total = sum(probs)
    if total <= 0 or not points:
        return float("nan"), float("nan")

    mean = sum(p * x for p, x in zip(probs, points)) / total
    var = sum(p * (x - mean) ** 2 for p, x in zip(probs, points)) / total
    return mean, math.sqrt(max(var, 0.0))


def _discrete_margin(sigma: float, estimates: Sequence["BucketEstimate"]) -> float:
    """A margin of error for the discrete fallback.

    The old code published `sigma` here, which the module docstring explicitly
    warns against: sigma is how uncertain the OUTCOME is, not how well the book
    pins our estimate. The fallback also represents each open tail by an invented
    point, so its centre is genuinely less trustworthy than a fitted one. Scale
    sigma down by the number of buckets we could actually read, and floor it so a
    fallback can never claim to be tighter than a real fit.
    """
    quoted = sum(1 for e in estimates if e.quoted) or 1
    conf = sum(e.confidence for e in estimates) / max(len(estimates), 1)
    return sigma * (1.0 - 0.5 * conf) / math.sqrt(quoted)


def _dutch_book_warning(buckets: Sequence["BucketBook"]) -> Optional[str]:
    """Mutually exclusive and exhaustive buckets bound the book.

    Buying YES in every bucket guarantees exactly 1, so the asks must sum to at
    least 1. Minting a pair in every bucket and selling all the YES also settles
    at 1, so the bids must not sum to more than 1. A violation is risk-free money
    against us, and the previous +/-15% tolerance on the MIDS let a 14c box pass
    with no warning at all.
    """
    asks = [b.usable_ask() for b in buckets]
    bids = [b.usable_bid() for b in buckets]
    if all(a is not None for a in asks):
        total = sum(asks) / 100.0
        if total < 1.0 - _DUTCH_BOOK_TOLERANCE:
            return (f"DUTCH BOOK: asks sum to {total:.3f}; buying every bucket costs "
                    f"{total:.3f} and settles at 1.000, a risk-free "
                    f"{(1.0 - total) * 100:.1f}c per dollar against us")
    if all(b is not None for b in bids):
        total = sum(bids) / 100.0
        if total > 1.0 + _DUTCH_BOOK_TOLERANCE:
            return (f"DUTCH BOOK: bids sum to {total:.3f}; minting and selling every "
                    f"bucket pays {total:.3f} against a cost of 1.000, a risk-free "
                    f"{(total - 1.0) * 100:.1f}c per dollar against us")
    return None


def _rank_quantile(
    bounds: Sequence[float], probs: Sequence[float], q: float
) -> tuple[Optional[float], str]:
    """Percentile q read directly off the piecewise-linear implied CDF.

    Interior crossings interpolate between real strikes and assume nothing
    beyond uniform density within the bucket. A crossing inside an open-ended
    outer bucket needs a shape for the tail; we use an exponential decay
    matched to the adjacent interior bucket's density, and flag the result
    "tail" so consumers know it rests on that assumption. With fewer than two
    boundaries there is no interior at all and no density to anchor a tail,
    so the answer is (None, "unresolved").
    """
    k = len(probs)
    cum: List[float] = []
    run = 0.0
    for p in probs[:-1]:
        run += p
        cum.append(run)
    if len(bounds) < 2:
        return None, "unresolved"
    for i in range(1, k - 1):                      # interior buckets
        lo_c = cum[i - 1]
        hi_c = cum[i]
        if lo_c <= q <= hi_c:
            lo_b, hi_b = bounds[i - 1], bounds[i]
            if hi_c <= lo_c:
                return (lo_b + hi_b) / 2.0, "interior"
            frac = (q - lo_c) / (hi_c - lo_c)
            return lo_b + frac * (hi_b - lo_b), "interior"
    widths = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
    if q < cum[0]:                                  # lower open tail
        dens = probs[1] / widths[0] if widths[0] > 0 else 0.0
        if dens <= 0 or cum[0] <= 0:
            return None, "unresolved"
        lam = dens / cum[0]
        return bounds[0] + math.log(q / cum[0]) / lam, "tail"
    upper_mass = probs[-1]                          # upper open tail
    dens = probs[-2] / widths[-1] if widths[-1] > 0 else 0.0
    if dens <= 0 or upper_mass <= 0:
        return None, "unresolved"
    lam = dens / upper_mass
    return bounds[-1] - math.log(max((1.0 - q), 1e-12) / upper_mass) / lam, "tail"


def _count_peaks(bounds: Sequence[float], probs: Sequence[float]) -> int:
    """Prominent local maxima of the interior density profile.

    A peak only counts if it reaches PEAK_PROMINENCE of the tallest one, so a
    penny-noise bump next to a 96% bucket does not read as bimodality. Open
    tails carry no density profile, so tail-heavy bimodality is seen through
    the interior buckets adjacent to the tails.
    """
    widths = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
    dens = [probs[i + 1] / w if w > 0 else 0.0 for i, w in enumerate(widths)]
    if not dens:
        return 1
    top = max(dens)
    if top <= 0:
        return 1
    peaks = 0
    for i, d in enumerate(dens):
        is_max = (i == 0 or d > dens[i - 1]) and (i == len(dens) - 1 or d >= dens[i + 1])
        if is_max and d >= PEAK_PROMINENCE * top:
            peaks += 1
    return max(peaks, 1)


def _assemble(
    meta: Sequence[tuple],
    bids_cents: Sequence[Optional[float]],
    raw: List[Optional[float]],
    confs: List[float],
    one_sided_flags: List[bool],
    quoted_flags: List[bool],
    warnings: List[str],
) -> Optional[MarketForecast]:
    """Shared back half of the pipeline: normalise the per-bucket estimates,
    build the implied CDF, fit, or fall back. ``meta`` is (lower, upper,
    query_id) per bucket; ``bids_cents`` is each bucket's best bid, used only
    to bound what an unpriced bucket could claim."""
    if not any(quoted_flags):
        return None
    n_missing = sum(1 for p in raw if p is None)
    n_unquoted = sum(1 for q in quoted_flags if not q)
    n_crossed = n_missing - n_unquoted
    if n_unquoted:
        warnings.append(f"{n_unquoted} of {len(meta)} buckets unquoted")
    if n_crossed:
        warnings.append(
            f"{n_crossed} bucket(s) crossed (bid above ask); treated as unpriced"
        )
    if any(one_sided_flags):
        warnings.append(
            f"{sum(one_sided_flags)} bucket(s) one-sided; margin of error widened"
        )

    quoted_total = sum(p for p in raw if p is not None)
    if quoted_total <= 0:
        return None
    if abs(quoted_total - 1.0) > _DUTCH_BOOK_TOLERANCE:
        # Independent books never sum to exactly 1. Report the SIGNED deviation
        # rather than a wide dead band: the direction says whether the book is
        # over- or under-priced, and the old +/-15% window hid real boxes.
        warnings.append(
            f"bucket mids sum to {quoted_total:.3f} "
            f"({(quoted_total - 1.0) * 100:+.1f}c per dollar) before normalising"
        )

    filled = list(raw)
    if n_missing:
        # An unpriced bucket is UNKNOWN, not impossible. Its probability is
        # bounded above by whatever the other buckets' BIDS do not already
        # claim, since bids are a lower bound on their true probabilities.
        # Take the midpoint of that interval. Asserting zero (the old
        # behaviour whenever quoted mids summed above 1) is a strong claim
        # the book never made.
        bid_claim = sum(
            (bc or 0.0) / 100.0
            for bc, p in zip(bids_cents, raw)
            if p is not None
        )
        headroom = max(0.0, 1.0 - bid_claim)
        est = headroom / (2.0 * n_missing)
        filled = [est if p is None else p for p in raw]

    total = sum(p for p in filled if p is not None)
    if total <= 0:
        return None
    probs = [(p or 0.0) / total for p in filled]

    estimates = [
        BucketEstimate(
            query_id=m[2],
            lower=m[0],
            upper=m[1],
            probability=p,
            raw_probability=(r if r is not None else 0.0),
            confidence=c,
            one_sided=o,
            quoted=q,
        )
        for m, p, r, c, o, q in zip(
            meta, probs, raw, confs, one_sided_flags, quoted_flags
        )
    ]

    bounds = [m[1] for m in meta[:-1] if m[1] is not None]
    if len(bounds) != len(meta) - 1:
        warnings.append("bucket bounds incomplete; falling back to discrete estimate")
        value, sigma = _discrete_fallback(estimates, bounds)
        if math.isnan(value):
            return None
        return MarketForecast(
            value, _discrete_margin(sigma, estimates), sigma, "discrete",
            estimates, warnings,
        )

    # Rank method: read the percentiles straight off the implied CDF.
    med, med_basis = _rank_quantile(bounds, probs, 0.50)
    p10, p10_basis = _rank_quantile(bounds, probs, 0.10)
    p90, p90_basis = _rank_quantile(bounds, probs, 0.90)

    if med is None:
        warnings.append(
            "median unresolvable from these strikes; falling back to discrete estimate"
        )
        value, sigma = _discrete_fallback(estimates, bounds)
        if math.isnan(value):
            return None
        return MarketForecast(
            value, _discrete_margin(sigma, estimates), sigma, "discrete",
            estimates, warnings,
        )

    if med_basis == "tail":
        outside = probs[0] if probs[0] >= 0.5 else probs[-1]
        warnings.append(
            f"median lies beyond the outer strikes ({outside * 100:.0f}% of mass "
            f"in an open-ended bucket); value depends on the assumed tail shape"
        )
    for nm, basis in (("p10", p10_basis), ("p90", p90_basis)):
        if basis == "tail":
            warnings.append(f"{nm} falls in an open tail; tail-model dependent")
        elif basis == "unresolved":
            warnings.append(f"{nm} unresolvable from these strikes")

    n_peaks = _count_peaks(bounds, probs)
    multimodal = n_peaks >= 2
    if multimodal:
        warnings.append(
            f"market shows {n_peaks} probability clusters; a single point "
            f"forecast misrepresents it, publish the clusters instead"
        )

    if p10 is not None and p90 is not None:
        band = max(p90 - p10, 0.0)
        margin = band / 2.0
        sigma = band / 2.5631          # P10..P90 of a normal spans 2.5631 sigma
    else:
        margin = sigma = 0.0
        warnings.append("band unresolvable; margin and sigma reported as 0")

    return MarketForecast(
        med, margin, sigma, "rank", estimates, warnings,
        p10=p10, p90=p90, value_basis=med_basis,
        p10_basis=p10_basis, p90_basis=p90_basis,
        multimodal=multimodal, n_peaks=n_peaks,
    )


def forecast_from_buckets(buckets: Sequence[BucketBook]) -> Optional[MarketForecast]:
    """Collapse one market's bucket books into a single implied value, from
    best quotes only.

    Buckets must be supplied in ascending order and span the whole line, with
    the first open below and the last open above. Returns None when the book
    carries no usable information at all. When full ladders are available,
    prefer :func:`forecast_from_depth`, which weights by committed notional.
    """
    warnings: List[str] = []

    if len(buckets) < 2:
        return None

    half = typical_half_spread(buckets)

    dutch = _dutch_book_warning(buckets)
    if dutch:
        warnings.append(dutch)

    raw: List[Optional[float]] = []
    confs: List[float] = []
    one_sided_flags: List[bool] = []
    quoted_flags: List[bool] = []
    for b in buckets:
        p, conf, one_sided, quoted = bucket_probability(
            b.usable_bid(), b.usable_ask(), half
        )
        raw.append(p)
        confs.append(conf)
        one_sided_flags.append(one_sided)
        quoted_flags.append(quoted)

    return _assemble(
        [(b.lower, b.upper, b.query_id) for b in buckets],
        [b.usable_bid() for b in buckets],
        raw, confs, one_sided_flags, quoted_flags, warnings,
    )


def _side_stats(levels: Sequence[BookLevel]) -> tuple[float, float, float]:
    """(vwap_cents, notional_usd, shares) over a full ladder.

    The full-ladder VWAP no longer prices anything (see _walk_price); dollars
    are the currency for confidence and the dust floors, since posting many
    shares of a cheap side is not the same commitment as posting the same
    dollars.
    """
    cent_shares = sum(l.price * l.size for l in levels)
    shares = sum(l.size for l in levels)
    return cent_shares / shares, cent_shares / 100.0, shares


def _walk_price(levels: Sequence[BookLevel], target_usd: float) -> float:
    """Dollar-weighted price of executing ``target_usd`` from the touch.

    Walk the ladder best-first, consuming each level's own notional until the
    target is reached; the last level fills partially. Each committed dollar
    carries the same weight regardless of the price it rests at, which is the
    whole point: per-dollar influence must not depend on denomination, or
    penny ladders (25 shares per dollar at 4c) out-vote real money.

    Callers guarantee the ladder holds at least ``target_usd`` in total (the
    side floor); if it somehow does not, the walk prices what is there.
    """
    remaining = target_usd * 100.0  # cent-shares
    weighted = taken = 0.0
    for l in levels:
        if remaining <= 0:
            break
        take = min(l.price * l.size, remaining)
        weighted += take * l.price
        taken += take
        remaining -= take
    return weighted / taken


def bucket_estimate_from_depth(
    depth: BucketDepth,
    half_spread: float = _DEFAULT_HALF_SPREAD,
) -> tuple[Optional[float], float, float, bool, bool]:
    """One bucket's implied probability from its full consolidated ladders.

    Returns (probability, quality, notional_usd, one_sided, quoted).

    The probability is the midpoint of the two executable walk prices: the
    dollar-weighted price of selling DEPTH_MIN_SIDE_NOTIONAL_USD into the
    consolidated bids and of buying the same from the consolidated asks,
    clamped into [best bid, best ask]. A book only pins the truth to that
    interval, so the estimate must be a selection from it; depth beyond the
    first walk dollars is inventory, not opinion, and moves confidence only.

    This replaced a full-book share-weighted microprice, which let cheap
    ladders out-vote real money (a dollar at 4c is 25 shares, at 30c it is 3)
    and on live books pushed every sub-50c bucket above its own best ask
    (issue #36). Ladder imbalance moves the walk mid not at all: on this venue
    all resting flow is the market maker's own, so imbalance carries no
    information and would only be a free manipulation lever.

    ``quality`` is the spread component of confidence: (1 - spread) two-sided,
    halved for a one-sided book whose missing side was inferred. ``notional``
    is the committed dollars backing the estimate: the THINNER side when both
    exist, the quoted side otherwise. The caller standardises notional against
    the market's own median depth to finish the confidence; no external
    constant is involved.

    Sides whose whole ladder holds under DEPTH_MIN_SIDE_NOTIONAL_USD are
    treated as absent: with the full book summed, dust cannot hide in front
    of a real order. Trades are deliberately NOT used: resting depth is live,
    at-risk capital, and the venue's only taker is a designed noise trader.
    """
    bids = depth.consolidated_bids()
    asks = depth.consolidated_asks()
    b_vwap = b_ntl = b_sh = a_vwap = a_ntl = a_sh = None
    if bids:
        b_vwap, b_ntl, b_sh = _side_stats(bids)
        if b_ntl < DEPTH_MIN_SIDE_NOTIONAL_USD:
            bids, b_vwap, b_ntl, b_sh = [], None, None, None
    if asks:
        a_vwap, a_ntl, a_sh = _side_stats(asks)
        if a_ntl < DEPTH_MIN_SIDE_NOTIONAL_USD:
            asks, a_vwap, a_ntl, a_sh = [], None, None, None

    quoted = bool(bids or asks)
    if not quoted:
        return None, 0.0, 0.0, False, False
    one_sided = not (bids and asks)

    if not one_sided:
        best_bid, best_ask = bids[0].price, asks[0].price
        if best_bid >= best_ask:
            # Crossed at the consolidated touch: stale or free money.
            return None, 0.0, 0.0, one_sided, quoted
        walk_bid = _walk_price(bids, DEPTH_MIN_SIDE_NOTIONAL_USD)
        walk_ask = _walk_price(asks, DEPTH_MIN_SIDE_NOTIONAL_USD)
        p = (walk_bid + walk_ask) / 2.0
        p = max(best_bid, min(best_ask, p)) / 100.0
        spread = (best_ask - best_bid) / 100.0
        return (
            max(0.0, min(1.0, p)),
            max(1.0 - spread, _MIN_CONFIDENCE),
            min(b_ntl, a_ntl),
            one_sided,
            quoted,
        )

    if bids:
        p = _walk_price(bids, DEPTH_MIN_SIDE_NOTIONAL_USD) / 100.0 + half_spread
        n = b_ntl
    else:
        p = _walk_price(asks, DEPTH_MIN_SIDE_NOTIONAL_USD) / 100.0 - half_spread
        n = a_ntl
    quality = (1.0 - 2.0 * half_spread) / 2.0
    return max(0.0, min(1.0, p)), max(quality, _MIN_CONFIDENCE), n, one_sided, quoted


def forecast_from_depth(buckets: Sequence[BucketDepth]) -> Optional[MarketForecast]:
    """Collapse one market's bucket books into a single implied value, using
    FULL YES and NO ladders weighted by committed notional.

    This is the preferred entry point. The YES/NO consolidation happens here,
    per bucket, because the inversion is executable on this venue (exact
    inverse mint/burn matching, verified on testnet 2026-08-03), so callers
    should not have to know the rule.
    """
    warnings: List[str] = []

    if len(buckets) < 2:
        return None

    views = [b.best_view() for b in buckets]
    half = typical_half_spread(views)

    dutch = _dutch_book_warning(views)
    if dutch:
        warnings.append(dutch)

    raw: List[Optional[float]] = []
    qualities: List[float] = []
    notionals: List[float] = []
    one_sided_flags: List[bool] = []
    quoted_flags: List[bool] = []
    for b in buckets:
        p, quality, n_usd, one_sided, quoted = bucket_estimate_from_depth(b, half)
        raw.append(p)
        qualities.append(quality)
        notionals.append(n_usd)
        one_sided_flags.append(one_sided)
        quoted_flags.append(quoted)

    # Confidence = quality * min(1, n / median(n)), the market standardised
    # against its own depth. Median rather than max or sum so a single whale
    # bucket cannot crush its siblings' credibility.
    priced_n = sorted(n for p, n in zip(raw, notionals) if p is not None and n > 0)
    med_n = priced_n[len(priced_n) // 2] if len(priced_n) % 2 else (
        (priced_n[len(priced_n) // 2 - 1] + priced_n[len(priced_n) // 2]) / 2.0
    ) if priced_n else 0.0
    confs: List[float] = []
    for p, quality, n_usd in zip(raw, qualities, notionals):
        if p is None:
            confs.append(0.0)
        elif med_n > 0:
            confs.append(max(quality * min(1.0, n_usd / med_n), _MIN_CONFIDENCE))
        else:
            confs.append(quality)

    # Disclosure, never math: relative standardisation cannot see absolute
    # poverty, so a market that is thin EVERYWHERE gets a visible caveat.
    total_usd = 0.0
    for b in buckets:
        for side in (b.consolidated_bids(), b.consolidated_asks()):
            if side:
                total_usd += _side_stats(side)[1]
    if total_usd < LOW_TOTAL_NOTIONAL_WARN_USD:
        warnings.append(
            f"total resting notional only ${total_usd:,.0f} across all buckets"
        )

    return _assemble(
        [(b.lower, b.upper, b.query_id) for b in buckets],
        [v.best_bid for v in views],
        raw, confs, one_sided_flags, quoted_flags, warnings,
    )
