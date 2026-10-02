class TesseraError(Exception):
    """Base for every error Tessera raises deliberately."""


class UpstreamError(TesseraError):
    """Token Factory returned something we cannot use."""


class RateLimitedError(UpstreamError):
    """Token Factory rate-limited us. Distinct so callers can back off."""


class EvidenceMissing(TesseraError):
    """A claim had no resolvable supporting span. Never render past this."""
