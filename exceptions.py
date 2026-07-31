"""
NHPC Weather Warning System — Custom Exception Hierarchy.

Provides structured, catchable exception types for every failure domain
so that callers can handle specific failure modes without catching
broad `Exception`. All exceptions inherit from NHPCError for
catch-all safety nets.

This module is purely additive — existing code continues to work
unchanged. These exceptions are used incrementally as modules adopt them.
"""


class NHPCError(Exception):
    """Base exception for all NHPC Weather Warning System errors.

    All custom exceptions inherit from this class so that a single
    ``except NHPCError`` can act as a catch-all for system-specific
    failures while still allowing granular handling.
    """


# ---------------------------------------------------------------------------
# IMD / Scraper Errors
# ---------------------------------------------------------------------------

class IMDConnectionError(NHPCError):
    """Raised when the IMD Mausamgram API is unreachable.

    This covers DNS failures, TCP timeouts, and connection refused
    scenarios. Callers should fall back to cached data when available.
    """


class IMDResponseError(NHPCError):
    """Raised when the IMD API returns unparseable or unexpected data.

    This covers HTTP 4xx/5xx responses, malformed JSON, and schema
    changes in the upstream API.
    """


# ---------------------------------------------------------------------------
# Forecast Processing Errors
# ---------------------------------------------------------------------------

class ForecastAnalysisError(NHPCError):
    """Raised when forecast data cannot be analyzed.

    This covers missing required fields, all-NaN data arrays, or
    invalid time ranges in the forecast payload.
    """


class KMLParseError(NHPCError):
    """Raised when the KML/SHP boundary file cannot be parsed.

    This covers missing files, malformed XML, and missing coordinate
    elements in the spatial data.
    """


# ---------------------------------------------------------------------------
# Database Errors
# ---------------------------------------------------------------------------

class DatabaseError(NHPCError):
    """Raised when a database operation fails.

    This covers connection failures, schema initialization errors,
    and query execution failures. The original SQLite exception is
    chained via ``raise DatabaseError(...) from original``.
    """


# ---------------------------------------------------------------------------
# Configuration Errors
# ---------------------------------------------------------------------------

class ConfigurationError(NHPCError):
    """Raised when application configuration is invalid or missing.

    This covers missing required environment variables, out-of-range
    values, and type coercion failures during startup validation.
    """


# ---------------------------------------------------------------------------
# Notification Errors
# ---------------------------------------------------------------------------

class NotificationError(NHPCError):
    """Raised when an alert notification fails to deliver.

    This covers Telegram API errors, Slack webhook failures, and
    SMTP delivery errors. Non-fatal — the system should continue
    operating even if notifications fail.
    """
