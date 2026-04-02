"""Alpha360 — Scheduler (threading.Timer, zero deps extra)."""

import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

logger = logging.getLogger("alpha360.scheduler")


class Alpha360Scheduler:
    def __init__(self, analysis_fn: Callable, config: dict = None):
        self.analysis_fn = analysis_fn
        self.config = config or {}
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self.enabled = self.config.get("enabled", True)
        self.interval = self.config.get("interval_minutes", 60) * 60
        self.market_only = self.config.get("market_hours_only", False)
        self.last_run: Optional[str] = None
        self.run_count = 0
        self.error_count = 0
        self._last_result = None

    def start(self):
        if not self.enabled:
            logger.info("[Scheduler] Disabled")
            return
        self._running = True
        logger.info(f"[Scheduler] Started — interval {self.interval}s")
        self._schedule(delay=15)

    def stop(self):
        self._running = False
        if self._timer:
            self._timer.cancel()
        logger.info("[Scheduler] Stopped")

    def trigger_now(self) -> dict:
        return self._execute(force=True)

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled, "running": self._running,
            "interval_minutes": self.interval // 60,
            "last_run": self.last_run,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "market_hours_only": self.market_only,
        }

    def _schedule(self, delay=None):
        if not self._running: return
        d = delay if delay is not None else self.interval
        self._timer = threading.Timer(d, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self):
        try:
            self._execute()
        except Exception as e:
            logger.error(f"[Scheduler] Error: {e}\n{traceback.format_exc()}")
            self.error_count += 1
        finally:
            self._schedule()

    def _execute(self, force=False) -> dict:
        now = datetime.now()
        self.last_run = now.isoformat()
        self.run_count += 1

        if self.market_only and not force and not self._is_market_time(now):
            return {"status": "skipped", "reason": "fuori orari mercato"}

        logger.info(f"[Scheduler] Cycle #{self.run_count}")
        try:
            result = self.analysis_fn()
            self._last_result = {"status": "ok", "count": len(result) if result else 0,
                                 "timestamp": now.isoformat()}
            return self._last_result
        except Exception as e:
            self.error_count += 1
            return {"status": "error", "error": str(e)}

    def _is_market_time(self, now):
        if now.weekday() >= 5: return False
        return 8 <= now.hour <= 22
