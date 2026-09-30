from django.conf import settings
from django.db import transaction
from django.utils import timezone

from desk.models import OffsetSubmission, ShiftSnapshot, ShiftSnapshotItem, User

INFLIGHT_STATUSES = (
    OffsetSubmission.Status.PENDING,
    OffsetSubmission.Status.PROCESSING,
)


class SnapshotReconcileError(Exception):
    """留影落库期间在途集合发生变化，对账不一致。"""


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


def create_shift_snapshot(user: User) -> ShiftSnapshot:
    """把当刻在途（待复核/复核中）刀补的编号、刀号、刀补冻进一份留影。

    同一事务内冻结后重新对账：若在途编号集合与已冻结集合不一致，
    抛 SnapshotReconcileError 回滚整份留影，由调用方提示重试。
    """
    with transaction.atomic():
        rows = list(
            OffsetSubmission.objects.filter(status__in=INFLIGHT_STATUSES)
            .order_by("id")
            .values("id", "tool_code", "offset_um", "status")
        )
        snapshot = ShiftSnapshot.objects.create(
            created_by=user,
            item_count=len(rows),
        )
        ShiftSnapshotItem.objects.bulk_create(
            [
                ShiftSnapshotItem(
                    snapshot=snapshot,
                    submission_id=row["id"],
                    tool_code=row["tool_code"],
                    offset_um=row["offset_um"],
                    status=row["status"],
                )
                for row in rows
            ]
        )
        recheck = set(
            OffsetSubmission.objects.filter(status__in=INFLIGHT_STATUSES).values_list(
                "id", flat=True
            )
        )
        if recheck != {row["id"] for row in rows}:
            raise SnapshotReconcileError("留影期间在途集合已变化")
    return snapshot
