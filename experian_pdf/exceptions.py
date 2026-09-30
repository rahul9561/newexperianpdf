class ExperianPDFError(Exception):
    """Base class for all engine errors."""


class InvalidReportError(ExperianPDFError, ValueError):
    """Input is not valid JSON or does not contain an Experian ``INProfileResponse``."""


class RenderError(ExperianPDFError):
    """HTML/PDF rendering failed."""


class ConfigurationError(ExperianPDFError, ValueError):
    """Invalid engine option, e.g. an unknown renderer name."""
