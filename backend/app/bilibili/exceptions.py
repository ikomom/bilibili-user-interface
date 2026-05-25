class BilibiliAPIError(Exception):
    pass


class AuthenticationError(BilibiliAPIError):
    pass


class RateLimitError(BilibiliAPIError):
    pass


class UploaderNotFoundError(BilibiliAPIError):
    pass


class NetworkError(BilibiliAPIError):
    pass
