from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        MACHINIST = "machinist", "操作员"
        AUDITOR = "auditor", "复核员"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MACHINIST,
    )

    @property
    def can_write(self) -> bool:
        return self.role == self.Role.MACHINIST


class OffsetSubmission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待复核"
        PROCESSING = "processing", "复核中"
        DONE = "done", "已完成"

    class Verdict(models.TextChoices):
        PASS = "合格", "合格"
        FAIL = "超差", "超差"

    tool_code = models.CharField(max_length=32, db_index=True)
    offset_um = models.IntegerField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    verdict = models.CharField(
        max_length=8,
        choices=Verdict.choices,
        blank=True,
        default="",
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.tool_code} {self.offset_um}µm"


class ShiftSnapshot(models.Model):
    """班次留影：一键留影当刻全部未办结（在途）刀补的只读快照。

    明细以值拷贝形式冻结在 ShiftSnapshotItem 中，之后原单状态如何变化
    （办结、删除）都不影响留影内容。
    """

    captured_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shift_snapshots",
    )
    captured_at = models.DateTimeField(db_index=True)
    item_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-captured_at", "-id"]

    def __str__(self) -> str:
        return f"班次留影 #{self.id}（{self.item_count} 笔）"


class ShiftSnapshotItem(models.Model):
    """留影明细：冻结留影当刻单笔刀补的编号、刀号、刀补与状态。"""

    snapshot = models.ForeignKey(
        ShiftSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    seq = models.PositiveIntegerField()
    submission = models.ForeignKey(
        OffsetSubmission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshot_items",
    )
    # 以下字段为留影当刻的值拷贝，原单办结或删除后保持不变
    submission_no = models.BigIntegerField()
    tool_code = models.CharField(max_length=32)
    offset_um = models.IntegerField()
    status_at_capture = models.CharField(
        max_length=16,
        choices=OffsetSubmission.Status.choices,
    )

    class Meta:
        ordering = ["seq", "id"]
        unique_together = [("snapshot", "submission_no")]

    def __str__(self) -> str:
        return f"#{self.submission_no} {self.tool_code} {self.offset_um}µm"
