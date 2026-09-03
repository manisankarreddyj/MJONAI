from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from research.walk_forward.walk_forward_models import (
    WalkForwardWindow,
)


class WalkForwardWindowGenerator:

    def generate(
        self,
        *,
        start: datetime,
        end: datetime,
        training_years: int,
        validation_years: int,
        step_years: int = 1,
        embargo_days: int = 7,
    ) -> list[WalkForwardWindow]:

        """
        `embargo_days` separates training from validation so
        indicators/labels spanning the boundary cannot leak.
        """

        windows: list[WalkForwardWindow] = []

        train_start = start

        while True:

            train_end = (
                train_start +
                relativedelta(years=training_years)
            )

            validation_start = (
                train_end +
                timedelta(days=embargo_days)
            )

            validation_end = (
                validation_start +
                relativedelta(years=validation_years)
            )

            if validation_end > end:
                break

            windows.append(
                WalkForwardWindow(
                    train_start=train_start,
                    train_end=train_end,
                    validation_start=validation_start,
                    validation_end=validation_end,
                )
            )

            train_start = (
                train_start +
                relativedelta(years=step_years)
            )

        return windows

    def generate_cpcv_folds(
        self,
        *,
        start: datetime,
        end: datetime,
        n_partitions: int = 5,
        k_test_partitions: int = 2,
        embargo_days: int = 7,
        purge_days: int = 3,
    ) -> list[CPCVFold]:
        """
        Generate Combinatorial Purged Cross-Validation (CPCV) folds (López de Prado, 2018).
        Partitions the overall interval [start, end] into N equal contiguous blocks,
        and generates all nCk combinations of test blocks with purging and embargo margins.
        """
        import itertools
        from research.walk_forward.walk_forward_models import CPCVFold

        total_duration = end - start
        partition_duration = total_duration / max(1, n_partitions)

        partitions: list[tuple[datetime, datetime]] = []
        p_start = start
        for i in range(n_partitions):
            p_end = p_start + partition_duration if i < n_partitions - 1 else end
            partitions.append((p_start, p_end))
            p_start = p_end

        folds: list[CPCVFold] = []
        fold_id = 0

        for test_indices in itertools.combinations(range(n_partitions), k_test_partitions):
            fold_id += 1
            test_intervals = [partitions[idx] for idx in test_indices]
            embargo_intervals: list[tuple[datetime, datetime]] = []
            purged_intervals: list[tuple[datetime, datetime]] = []

            # Calculate embargo intervals right after each test interval
            for t_start, t_end in test_intervals:
                e_start = t_end
                e_end = min(end, t_end + timedelta(days=embargo_days))
                if e_end > e_start:
                    embargo_intervals.append((e_start, e_end))

                # Purge interval immediately before test window to avoid lookahead leakage
                p_lead = max(start, t_start - timedelta(days=purge_days))
                if t_start > p_lead:
                    purged_intervals.append((p_lead, t_start))

            # Train intervals are partitions NOT in test_indices, minus purged/embargoed spans
            raw_train_indices = [idx for idx in range(n_partitions) if idx not in test_indices]
            train_intervals: list[tuple[datetime, datetime]] = []

            for idx in raw_train_indices:
                p_s, p_e = partitions[idx]
                # Adjust boundaries if partition overlaps with embargo or purge
                cur_s = p_s
                cur_e = p_e

                for e_s, e_e in embargo_intervals:
                    if cur_s < e_e and cur_e > e_s:
                        if cur_s >= e_s:
                            cur_s = max(cur_s, e_e)
                        else:
                            cur_e = min(cur_e, e_s)

                for pu_s, pu_e in purged_intervals:
                    if cur_s < pu_e and cur_e > pu_s:
                        if cur_s >= pu_s:
                            cur_s = max(cur_s, pu_e)
                        else:
                            cur_e = min(cur_e, pu_s)

                if cur_e > cur_s:
                    train_intervals.append((cur_s, cur_e))

            folds.append(
                CPCVFold(
                    fold_id=fold_id,
                    train_intervals=train_intervals,
                    test_intervals=test_intervals,
                    purged_intervals=purged_intervals,
                    embargo_intervals=embargo_intervals,
                )
            )

        return folds