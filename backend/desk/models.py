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
    """班次留影：换班前把未办结刀补队列冻成只读快照。"""

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shift_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    item_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"留影#{self.pk} ({self.item_count}笔)"


class ShiftSnapshotItem(models.Model):
    """留影明细行：编号/刀号/刀补均为留影当刻的冻结副本，不随原单办结而变化。"""

    snapshot = models.ForeignKey(
        ShiftSnapshot,
        on_delete=models.CASCADE,
        related_name="items",
    )
    submission_id = models.BigIntegerField(db_index=True)
    tool_code = models.CharField(max_length=32)
    offset_um = models.IntegerField()
    status = models.CharField(
        max_length=16,
        choices=OffsetSubmission.Status.choices,
    )

    class Meta:
        ordering = ["submission_id"]

    def __str__(self) -> str:
        return f"#{self.submission_id} {self.tool_code} {self.offset_um}µm"
