# Session expires too early

`is_session_expired` reports true before `SESSION_TTL_SECONDS` has elapsed. Expected: false at 29 minutes. Actual: true. Check the session timestamp calculation.
