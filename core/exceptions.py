class ScraperError(RuntimeError):
    pass


class ScraperBlockedError(ScraperError):
    pass


class CloudflareBlockedError(ScraperBlockedError):
    pass


class CloudflareManualChallengeError(ScraperError):
    pass


class AXSAntiBotBlockedError(ScraperBlockedError):
    pass


class AXSRestrictedError(ScraperBlockedError):
    pass


class ScraperTimeoutError(ScraperError):
    pass
