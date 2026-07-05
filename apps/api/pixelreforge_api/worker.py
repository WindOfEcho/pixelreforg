from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
import logging
import signal
from threading import Event, Thread
import time

from .job_store import JobStore, create_job_store
from .logging_config import configure_logging
from .models import JobMetadata
from .processing import process_job
from .sentry_config import configure_sentry
from .settings import ApiSettings, load_settings
from .storage import delete_job_files


logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, store: JobStore, settings: ApiSettings) -> None:
        self.store = store
        self.settings = settings
        self.stop_requested = Event()

    def request_stop(self) -> None:
        self.stop_requested.set()

    def recover(self) -> None:
        interrupted = self.store.recover_interrupted_jobs(worker_id=self.settings.worker_id)
        stale = self.store.requeue_stale_jobs(timeout_seconds=self.settings.job_timeout_seconds)
        if interrupted or stale:
            logger.info(
                "Worker recovered jobs.",
                extra={"event": "worker_jobs_recovered", "interrupted_count": interrupted, "stale_count": stale},
            )

    def run_once(self) -> bool:
        self.store.requeue_stale_jobs(timeout_seconds=self.settings.job_timeout_seconds)
        metadata = self.store.claim_next_queued_job(worker_id=self.settings.worker_id)
        if metadata is None:
            self.cleanup_expired_jobs()
            return False
        self._run_job(metadata.job_id)
        self.cleanup_expired_jobs()
        return True

    def run_forever(self) -> None:
        logger.info(
            "Worker started.",
            extra={
                "event": "worker_started",
                "worker_id": self.settings.worker_id,
                "concurrency": self.settings.worker_concurrency,
            },
        )
        self.recover()
        futures: dict[Future[None], str] = {}
        last_cleanup = 0.0
        last_stale_recovery = 0.0
        with ThreadPoolExecutor(max_workers=self.settings.worker_concurrency) as executor:
            while not self.stop_requested.is_set():
                for future in [future for future in futures if future.done()]:
                    job_id = futures.pop(future)
                    try:
                        future.result()
                    except Exception:
                        logger.exception("Worker job crashed.", extra={"event": "worker_job_crashed", "job_id": job_id})

                now = time.monotonic()
                if now - last_stale_recovery >= min(60.0, float(self.settings.job_timeout_seconds)):
                    self.store.requeue_stale_jobs(timeout_seconds=self.settings.job_timeout_seconds)
                    last_stale_recovery = now
                if now - last_cleanup >= 60.0:
                    self.cleanup_expired_jobs()
                    last_cleanup = now

                claimed = False
                while len(futures) < self.settings.worker_concurrency:
                    metadata = self.store.claim_next_queued_job(worker_id=self.settings.worker_id)
                    if metadata is None:
                        break
                    futures[executor.submit(self._run_job, metadata.job_id)] = metadata.job_id
                    claimed = True

                if not claimed and not futures:
                    self.stop_requested.wait(self.settings.worker_poll_interval_seconds)
                elif not claimed:
                    self.stop_requested.wait(min(0.5, self.settings.worker_poll_interval_seconds))

        logger.info("Worker stopped.", extra={"event": "worker_stopped", "worker_id": self.settings.worker_id})

    def cleanup_expired_jobs(self) -> None:
        for metadata in self.store.find_expired_terminal_jobs(limit=100):
            delete_job_files(metadata.job_id)
            self.store.delete_job(metadata.job_id)
            logger.info("Expired job deleted.", extra={"event": "job_expired_deleted", "job_id": metadata.job_id})

    def _run_job(self, job_id: str) -> None:
        stop_heartbeat = Event()
        heartbeat_thread = Thread(target=self._heartbeat_loop, args=(job_id, stop_heartbeat), daemon=True)
        heartbeat_thread.start()
        try:
            process_job(job_id, self.store)
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=1.0)

    def _heartbeat_loop(self, job_id: str, stop_heartbeat: Event) -> None:
        while not stop_heartbeat.wait(self.settings.worker_heartbeat_interval_seconds):
            updated = self.store.update_job(job_id, _touch_heartbeat)
            if updated is None or updated.status != "processing":
                return


def _touch_heartbeat(metadata: JobMetadata) -> JobMetadata:
    if metadata.status == "processing":
        metadata.heartbeat_at = datetime.now(UTC)
    return metadata


def main() -> None:
    settings = load_settings()
    configure_logging(settings)
    configure_sentry(settings)
    worker = JobWorker(create_job_store(settings), settings)

    def stop(_signum: int, _frame: object) -> None:
        worker.request_stop()

    signal.signal(signal.SIGINT, stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop)
    worker.run_forever()


if __name__ == "__main__":
    main()
