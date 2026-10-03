from tessera.api.limits import RateLimiter, SpendCeiling


class Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_allows_up_to_the_limit_then_refuses():
    lim = RateLimiter(max_calls=3, per_seconds=60, clock=Clock())
    assert [lim.allow("a") for _ in range(4)] == [True, True, True, False]


def test_the_window_slides():
    clock = Clock()
    lim = RateLimiter(max_calls=2, per_seconds=60, clock=clock)
    assert lim.allow("a") and lim.allow("a")
    assert not lim.allow("a")
    clock.t = 61
    assert lim.allow("a")


def test_callers_are_limited_independently():
    lim = RateLimiter(max_calls=1, per_seconds=60, clock=Clock())
    assert lim.allow("a")
    assert lim.allow("b")
    assert not lim.allow("a")


def test_refused_calls_do_not_extend_the_window():
    """A crawler hammering a closed door must not keep it closed forever."""
    clock = Clock()
    lim = RateLimiter(max_calls=1, per_seconds=60, clock=clock)
    assert lim.allow("a")
    clock.t = 30
    assert not lim.allow("a")
    clock.t = 61
    assert lim.allow("a")


DAY = 86_400


def test_ceiling_is_not_exceeded_below_budget():
    ceiling = SpendCeiling(lambda since: 0.49, usd_per_day=0.50, clock=Clock(DAY * 10 + 5))
    assert not ceiling.exceeded()


def test_ceiling_is_exceeded_at_budget():
    ceiling = SpendCeiling(lambda since: 0.50, usd_per_day=0.50, clock=Clock(DAY * 10 + 5))
    assert ceiling.exceeded()


def test_ceiling_counts_only_since_utc_midnight():
    seen = []
    ceiling = SpendCeiling(lambda since: seen.append(since) or 0.0,
                           usd_per_day=0.50, clock=Clock(DAY * 10 + 3600))
    ceiling.exceeded()
    assert seen == [DAY * 10]


def test_idle_callers_are_forgotten_so_rotating_keys_cannot_grow_memory_forever():
    clock = Clock()
    lim = RateLimiter(max_calls=1, per_seconds=60, clock=clock, sweep_every=10)
    for i in range(10):
        lim.allow(f"spoofed-{i}")
    clock.t = 120
    lim.allow("fresh")
    assert lim.tracked() <= 1
