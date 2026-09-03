"""Harvest the BOE from the command line.

Runs in-process and sequentially, so it is also the safe way to drive the
backfill on a server where you would rather watch it than trust a queue.
"""

import datetime as dt
import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sources.models import Boletin, HarvestRun, default_backfill_start
from sources.tasks import _acquire_lock, _release_lock, harvest_day


class Command(BaseCommand):
    help = "Harvest BOE section II.B (oposiciones y concursos) for one day or a range."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--day", help="Single day, YYYY-MM-DD.")
        parser.add_argument("--days", type=int, help="The last N days, newest first.")
        parser.add_argument(
            "--since",
            help=(
                "Backfill from today back to this date (YYYY-MM-DD). "
                "Defaults to HARVEST_BACKFILL_START when --backfill is used."
            ),
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Walk backwards to --since (or HARVEST_BACKFILL_START).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help="Extra seconds to wait between days.",
        )
        parser.add_argument(
            "--skip-done",
            action="store_true",
            help="Skip days that already have a completed run.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = self._days_to_process(options)
        if not days:
            raise CommandError("Nothing to do: pass --day, --days or --backfill.")

        if not _acquire_lock():
            raise CommandError(
                "Another harvest holds the lock. Wait for it, or clear "
                "'sources:harvest:lock' in Redis if it is stale."
            )
        self.stdout.write(f"Harvesting {len(days)} day(s), newest first.")
        totals = {"seen": 0, "imported": 0, "duplicate": 0, "failed": 0}
        try:
            for index, day in enumerate(days):
                if options["skip_done"]:
                    run = HarvestRun.objects.filter(boletin=Boletin.BOE, fecha=day).first()
                    if run and run.is_complete:
                        continue
                if index and options["delay"]:
                    time.sleep(options["delay"])
                run = harvest_day(day)
                totals["seen"] += run.items_seen
                totals["imported"] += run.items_imported
                totals["duplicate"] += run.items_duplicate
                totals["failed"] += run.items_failed
                self.stdout.write(
                    f"  {day}  {run.status:<10} "
                    f"seen={run.items_seen} imported={run.items_imported} "
                    f"dup={run.items_duplicate} failed={run.items_failed}"
                )
        finally:
            _release_lock()

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {totals['seen']} items seen, {totals['imported']} imported, "
                f"{totals['duplicate']} duplicate, {totals['failed']} failed."
            )
        )

    def _days_to_process(self, options: dict[str, Any]) -> list[dt.date]:
        today = timezone.localdate()
        if options["day"]:
            return [dt.date.fromisoformat(options["day"])]
        if options["days"]:
            return [today - dt.timedelta(days=n) for n in range(1, options["days"] + 1)]
        if options["backfill"] or options["since"]:
            stop = (
                dt.date.fromisoformat(options["since"])
                if options["since"]
                else default_backfill_start()
            )
            if stop > today:
                raise CommandError("--since is in the future.")
            span = (today - stop).days
            return [today - dt.timedelta(days=n) for n in range(1, span + 1)]
        return []
