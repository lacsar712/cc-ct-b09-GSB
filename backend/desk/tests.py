from unittest.mock import patch

from django.test import TestCase

from desk.auth_utils import create_access_token
from desk.models import OffsetSubmission, ShiftSnapshot, ShiftSnapshotItem, User
from desk.services import (
    SnapshotReconciliationError,
    apply_verdict,
    create_shift_snapshot,
)


class ShiftSnapshotAcceptanceTest(TestCase):
    def setUp(self):
        self.machinist = User.objects.create_user(
            username="machinist", password="machine123456", role=User.Role.MACHINIST
        )
        self.auditor = User.objects.create_user(
            username="auditor", password="audit123456", role=User.Role.AUDITOR
        )
        self.token_m = create_access_token(self.machinist)
        self.token_a = create_access_token(self.auditor)

    def auth(self, token):
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def seed_in_flight(self):
        pending = OffsetSubmission.objects.create(
            tool_code="T11",
            offset_um=4,
            status=OffsetSubmission.Status.PENDING,
            submitted_by=self.machinist,
        )
        processing = OffsetSubmission.objects.create(
            tool_code="T12",
            offset_um=20,
            status=OffsetSubmission.Status.PROCESSING,
            submitted_by=self.machinist,
        )
        done = OffsetSubmission.objects.create(
            tool_code="T01",
            offset_um=5,
            status=OffsetSubmission.Status.DONE,
            verdict=OffsetSubmission.Verdict.PASS,
            submitted_by=self.machinist,
        )
        return pending, processing, done

    def test_two_open_rows_snapshotted_then_one_completed_snapshot_keeps_both(self):
        """核心验收：两笔未办结入镜→办结一笔→重开留影仍是当时两笔，不缺一行。"""
        pending, processing, done = self.seed_in_flight()

        # 写权限员一键留影
        resp = self.client.post("/api/snapshots", **self.auth(self.token_m))
        self.assertEqual(resp.status_code, 200, resp.content)
        snap = resp.json()
        self.assertEqual(snap["item_count"], 2)
        self.assertEqual(
            sorted(i["submission_no"] for i in snap["items"]),
            sorted([pending.id, processing.id]),
        )
        # 明细必须含编号、刀号、刀补，并冻结留影时状态
        by_no = {i["submission_no"]: i for i in snap["items"]}
        self.assertEqual(by_no[pending.id]["tool_code"], "T11")
        self.assertEqual(by_no[pending.id]["offset_um"], 4)
        self.assertEqual(by_no[pending.id]["status_at_capture"], "pending")
        self.assertEqual(by_no[processing.id]["tool_code"], "T12")
        self.assertEqual(by_no[processing.id]["offset_um"], 20)
        self.assertEqual(by_no[processing.id]["status_at_capture"], "processing")
        # 已办结那笔不入镜
        self.assertNotIn(done.id, by_no)

        snapshot_id = snap["id"]

        # 办结其中一笔
        apply_verdict(pending)
        pending.refresh_from_db()
        self.assertEqual(pending.status, OffsetSubmission.Status.DONE)

        # 再打开那份留影：仍应是留影当时的两笔，字段不变
        resp = self.client.get(
            f"/api/snapshots/{snapshot_id}", **self.auth(self.token_a)
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        later = resp.json()
        self.assertEqual(later["item_count"], 2)
        self.assertEqual(len(later["items"]), 2)
        later_by_no = {i["submission_no"]: i for i in later["items"]}
        self.assertEqual(set(later_by_no), {pending.id, processing.id})
        # 已办结的那笔在留影里仍是留影当刻的待复核，刀号刀补不变
        self.assertEqual(later_by_no[pending.id]["status_at_capture"], "pending")
        self.assertEqual(later_by_no[pending.id]["tool_code"], "T11")
        self.assertEqual(later_by_no[pending.id]["offset_um"], 4)
        self.assertEqual(later_by_no[processing.id]["status_at_capture"], "processing")

        # 在途集合确实只剩一笔，证明留影是冻结副本而非实时视图
        live = self.client.get("/api/submissions", **self.auth(self.token_a)).json()
        live_in_flight = {r["id"] for r in live if r["status"] != "done"}
        self.assertEqual(live_in_flight, {processing.id})

    def test_read_only_role_can_browse_but_not_capture(self):
        """只读员能翻留影、看明细，但不能点一键留影。"""
        snap = create_shift_snapshot(self.machinist)

        resp = self.client.get("/api/snapshots", **self.auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)

        resp = self.client.get(
            f"/api/snapshots/{snap.id}", **self.auth(self.token_a)
        )
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post("/api/snapshots", **self.auth(self.token_a))
        self.assertEqual(resp.status_code, 403)

    def test_anonymous_must_login(self):
        resp = self.client.get("/api/snapshots")
        self.assertEqual(resp.status_code, 401)
        resp = self.client.post("/api/snapshots")
        self.assertEqual(resp.status_code, 401)

    def test_items_are_value_copies_independent_of_later_edits(self):
        """原单刀号刀补后续被改动，留影明细保持留影当刻的值。"""
        pending, processing, _ = self.seed_in_flight()
        snap = create_shift_snapshot(self.machinist)

        pending.tool_code = "T99"
        pending.offset_um = 999
        pending.save(update_fields=["tool_code", "offset_um"])

        items = list(
            ShiftSnapshotItem.objects.filter(snapshot=snap).order_by("submission_no")
        )
        frozen = {i.submission_no: i for i in items}
        self.assertEqual(frozen[pending.id].tool_code, "T11")
        self.assertEqual(frozen[pending.id].offset_um, 4)
        self.assertEqual(frozen[processing.id].tool_code, "T12")
        self.assertEqual(frozen[processing.id].offset_um, 20)

    def test_history_list_newest_first(self):
        first = create_shift_snapshot(self.machinist)
        OffsetSubmission.objects.create(
            tool_code="T30",
            offset_um=1,
            status=OffsetSubmission.Status.PENDING,
            submitted_by=self.machinist,
        )
        second = create_shift_snapshot(self.machinist)

        resp = self.client.get("/api/snapshots", **self.auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        ids = [s["id"] for s in resp.json()]
        self.assertEqual(ids, [second.id, first.id])
        self.assertEqual(ShiftSnapshot.objects.get(pk=second.id).item_count, 1)

    def test_reconciliation_mismatch_rolls_back(self):
        """对账集合不一致时整笔留影回滚，不落任何留影。"""
        from desk import services

        real = services.in_flight_submissions
        calls = {"n": 0}

        def patched(lock=False):
            qs = real(lock=lock)
            calls["n"] += 1
            # 第一次锁定取全量，第二次对账时模拟一笔在途被其他事务办结
            return qs.exclude(tool_code="T12") if calls["n"] >= 2 else qs

        self.seed_in_flight()
        before = ShiftSnapshot.objects.count()
        with patch("desk.services.in_flight_submissions", side_effect=patched):
            with self.assertRaises(SnapshotReconciliationError):
                create_shift_snapshot(self.machinist)

        self.assertEqual(ShiftSnapshot.objects.count(), before)
        self.assertEqual(ShiftSnapshotItem.objects.count(), 0)
