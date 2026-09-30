from django.conf import settings
from django.db import transaction
from django.utils import timezone

from desk.models import OffsetSubmission, ShiftSnapshot, ShiftSnapshotItem


# 未办结＝在途：待复核与复核中。已完成不进留影。
IN_FLIGHT_STATUSES = (
    OffsetSubmission.Status.PENDING,
    OffsetSubmission.Status.PROCESSING,
)


class SnapshotReconciliationError(Exception):
    """冻结明细与留影当刻在途集合对账不一致，本次留影已回滚。"""


def evaluate_verdict(offset_um: int) -> str:
    if abs(offset_um) <= settings.OFFSET_TOLERANCE_UM:
        return OffsetSubmission.Verdict.PASS
    return OffsetSubmission.Verdict.FAIL


def apply_verdict(submission: OffsetSubmission) -> None:
    submission.verdict = evaluate_verdict(submission.offset_um)
    submission.status = OffsetSubmission.Status.DONE
    submission.reviewed_at = timezone.now()
    submission.save(
        update_fields=["verdict", "status", "reviewed_at"],
    )


def in_flight_submissions(lock: bool = False):
    """留影当刻的在途集合（待复核＋复核中）。

    lock=True 时以 SELECT ... FOR UPDATE 取行锁，与 worker 的
    SKIP LOCKED 认领以及办结 UPDATE 互斥，保证冻结期间集合静止。
    """
    qs = OffsetSubmission.objects.filter(status__in=IN_FLIGHT_STATUSES).order_by(
        "created_at", "id"
    )
    if lock:
        qs = qs.select_for_update()
    return qs


def create_shift_snapshot(captured_by):
    """一键留影：锁定当刻在途集合，值拷贝冻结成只读明细并对账。

    任一笔在留影期间被办结、新增或删除，冻结编号集合与在途集合对不上，
    整笔留影回滚并抛 SnapshotReconciliationError，调用方应提示重试。
    """
    with transaction.atomic():
        locked_rows = list(in_flight_submissions(lock=True))
        frozen_ids = [row.id for row in locked_rows]

        snapshot = ShiftSnapshot.objects.create(
            captured_by=captured_by,
            captured_at=timezone.now(),
            item_count=len(locked_rows),
        )
        ShiftSnapshotItem.objects.bulk_create(
            ShiftSnapshotItem(
                snapshot=snapshot,
                seq=seq,
                submission_id=row.id,
                submission_no=row.id,
                tool_code=row.tool_code,
                offset_um=row.offset_um,
                status_at_capture=row.status,
            )
            for seq, row in enumerate(locked_rows, start=1)
        )

        # 与留影当刻在途集合对账：编号集合必须全等（无多笔、无缺笔、无串单）。
        current_ids = set(
            in_flight_submissions(lock=True).values_list("id", flat=True)
        )
        if current_ids != set(frozen_ids):
            raise SnapshotReconciliationError(
                "留影明细与当刻在途集合对账不一致，请重新留影"
            )

    return snapshot
