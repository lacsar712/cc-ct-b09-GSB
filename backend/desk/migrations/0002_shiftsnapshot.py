# Generated for 班次留影台：留影主表与只读明细

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("desk", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShiftSnapshot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("captured_at", models.DateTimeField(db_index=True)),
                ("item_count", models.PositiveIntegerField(default=0)),
                (
                    "captured_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="shift_snapshots",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-captured_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="ShiftSnapshotItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("seq", models.PositiveIntegerField()),
                ("submission_no", models.BigIntegerField()),
                ("tool_code", models.CharField(max_length=32)),
                ("offset_um", models.IntegerField()),
                (
                    "status_at_capture",
                    models.CharField(
                        choices=[
                            ("pending", "待复核"),
                            ("processing", "复核中"),
                            ("done", "已完成"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "snapshot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="desk.shiftsnapshot",
                    ),
                ),
                (
                    "submission",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="snapshot_items",
                        to="desk.offsetsubmission",
                    ),
                ),
            ],
            options={
                "ordering": ["seq", "id"],
                "unique_together": {("snapshot", "submission_no")},
            },
        ),
    ]
