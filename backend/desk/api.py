from datetime import datetime
from typing import Optional

from django.http import HttpRequest
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from desk.auth_utils import bearer_auth, create_access_token, verify_password
from desk.models import OffsetSubmission, ShiftSnapshot, User
from desk.services import SnapshotReconciliationError, create_shift_snapshot

api = NinjaAPI(title="数控刀补复核台", version="1.0")


class HealthOut(Schema):
    status: str


class LoginIn(Schema):
    username: str
    password: str


class LoginOut(Schema):
    token: str
    username: str
    role: str
    can_write: bool


class SubmissionIn(Schema):
    tool_code: str
    offset_um: int


class SubmissionOut(Schema):
    id: int
    tool_code: str
    offset_um: int
    status: str
    verdict: str
    created_at: datetime
    reviewed_at: Optional[datetime]


class SnapshotItemOut(Schema):
    seq: int
    submission_no: int
    tool_code: str
    offset_um: int
    status_at_capture: str


class SnapshotOut(Schema):
    id: int
    captured_at: datetime
    captured_by: Optional[str]
    item_count: int


class SnapshotDetailOut(SnapshotOut):
    items: list[SnapshotItemOut]


def _to_out(row: OffsetSubmission) -> SubmissionOut:
    return SubmissionOut(
        id=row.id,
        tool_code=row.tool_code,
        offset_um=row.offset_um,
        status=row.status,
        verdict=row.verdict or "",
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
    )


@api.get("/health", response=HealthOut)
def health(request: HttpRequest):
    return {"status": "ok"}


@api.post("/auth/login", response=LoginOut)
def login(request: HttpRequest, body: LoginIn):
    try:
        user = User.objects.get(username=body.username)
    except User.DoesNotExist:
        raise HttpError(401, "用户名或密码错误")
    if not verify_password(body.password, user.password):
        raise HttpError(401, "用户名或密码错误")
    token = create_access_token(user)
    return {
        "token": token,
        "username": user.username,
        "role": user.role,
        "can_write": user.can_write,
    }


@api.get("/submissions", response=list[SubmissionOut], auth=bearer_auth)
def list_submissions(request: HttpRequest):
    rows = OffsetSubmission.objects.all()[:200]
    return [_to_out(r) for r in rows]


@api.get("/submissions/{submission_id}", response=SubmissionOut, auth=bearer_auth)
def get_submission(request: HttpRequest, submission_id: int):
    try:
        row = OffsetSubmission.objects.get(pk=submission_id)
    except OffsetSubmission.DoesNotExist:
        raise HttpError(404, "刀补记录不存在")
    return _to_out(row)


@api.post("/submissions", response=SubmissionOut, auth=bearer_auth)
def create_submission(request: HttpRequest, body: SubmissionIn):
    user: User = request.auth
    if not user.can_write:
        raise HttpError(403, "当前账号只读，不能提交刀补")
    tool_code = body.tool_code.strip()
    if not tool_code:
        raise HttpError(400, "刀具编号不能为空")
    row = OffsetSubmission.objects.create(
        tool_code=tool_code,
        offset_um=body.offset_um,
        submitted_by=user,
        status=OffsetSubmission.Status.PENDING,
    )
    return _to_out(row)


def _snapshot_to_out(row: ShiftSnapshot) -> SnapshotOut:
    return SnapshotOut(
        id=row.id,
        captured_at=row.captured_at,
        captured_by=row.captured_by.username if row.captured_by else None,
        item_count=row.item_count,
    )


@api.get("/snapshots", response=list[SnapshotOut], auth=bearer_auth)
def list_snapshots(request: HttpRequest):
    """历史留影列表：写权限员与只读员均可翻阅。"""
    rows = ShiftSnapshot.objects.select_related("captured_by").all()[:200]
    return [_snapshot_to_out(r) for r in rows]


@api.get("/snapshots/{snapshot_id}", response=SnapshotDetailOut, auth=bearer_auth)
def get_snapshot(request: HttpRequest, snapshot_id: int):
    """留影明细：冻结的编号、刀号、刀补与留影时状态，只读不随原单变化。"""
    try:
        snapshot = ShiftSnapshot.objects.select_related("captured_by").get(
            pk=snapshot_id
        )
    except ShiftSnapshot.DoesNotExist:
        raise HttpError(404, "留影不存在")
    return SnapshotDetailOut(
        id=snapshot.id,
        captured_at=snapshot.captured_at,
        captured_by=snapshot.captured_by.username if snapshot.captured_by else None,
        item_count=snapshot.item_count,
        items=[
            SnapshotItemOut(
                seq=item.seq,
                submission_no=item.submission_no,
                tool_code=item.tool_code,
                offset_um=item.offset_um,
                status_at_capture=item.status_at_capture,
            )
            for item in snapshot.items.all()
        ],
    )


@api.post("/snapshots", response=SnapshotDetailOut, auth=bearer_auth)
def take_snapshot(request: HttpRequest):
    """一键留影：仅写权限员可操作，把当刻待复核与复核中的刀补冻结成留影。"""
    user: User = request.auth
    if not user.can_write:
        raise HttpError(403, "当前账号只读，不能留影")
    try:
        snapshot = create_shift_snapshot(captured_by=user)
    except SnapshotReconciliationError as exc:
        raise HttpError(409, str(exc))
    return get_snapshot(request, snapshot.id)
