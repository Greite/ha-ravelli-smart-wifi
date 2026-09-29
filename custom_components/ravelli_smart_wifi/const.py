"""Constants of the Ravelli Smart Wi-Fi integration."""

from typing import Final

DOMAIN: Final = "ravelli_smart_wifi"
MANUFACTURER: Final = "Ravelli"
ISSUE_URL: Final = "https://github.com/Greite/ha-ravelli-smart-wifi/issues"

# Polling, in seconds.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 300
# System status and schedule change rarely.
SLOW_REFRESH_INTERVAL: Final = 600
# Gaps between the polls that follow a command: polls at 2, 5, 10, 20 and 30 s.
FAST_REFRESH_STEPS: Final = (2, 3, 5, 10, 10)

# Network scan of the config flow.
SCAN_TIMEOUT: Final = 1.5
SCAN_CONCURRENCY: Final = 32
SCAN_MIN_PREFIX: Final = 22

# Register categories dumped by the diagnostics download: 0 to 12.
DIAGNOSTIC_CATEGORIES: Final = 13
