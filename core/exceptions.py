class AppError(Exception):
    pass


class NotFoundError(AppError):
    pass


class InvalidInputError(AppError):
    pass


class DatabaseOperationError(AppError):
    pass


class AuthenticationError(AppError):
    pass


class ConfigurationError(AppError):
    pass


class ExternalServiceError(AppError):
    pass
