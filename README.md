# 数控刀补复核台

操作员提交刀具编号与刀补微米值；后台 worker 用 PostgreSQL 行锁（`select_for_update(skip_locked=True)`）认领待复核记录，按绝对值是否不超过 12 微米给出「合格」或「超差」。

## 技术栈

| 层 | 选型 |
|----|------|
| 后端 | Django 5 + django-ninja（ASGI / uvicorn） |
| 前端 | SolidJS + Vite，nginx 反代 `/api` |
| 数据库 | PostgreSQL 16 |
| 鉴权 | JWT（python-jose），令牌存浏览器 localStorage |

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3196 |
| 接口 | http://localhost:8196 |
| PostgreSQL | localhost:54396（库名 `cncoffset`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| machinist | machine123456 | 可提交刀补 |
| auditor | audit123456 | 只读列表 |

## 启动

```bash
cd projects/17-cnc-tool-offset-desk
docker compose up --build
```

健康检查：`GET http://localhost:8196/api/health` → `{"status":"ok"}`

## 验收

1. machinist 登录后，种子数据应显示刀具 T01 合格（刀补 5 µm）、T09 超差（刀补 20 µm）。
2. 提交一条新刀补后，状态先为「待复核」，数秒内 worker 处理为「已完成」并给出结论。
3. auditor 登录后只能看列表，没有提交表单。

## 班次留影台

班次切换前，把还没办结的刀补队列做成只读留影。专页（顶部导航「班次留影台」，路由 `#/snapshots`）分三块：

1. **一键留影**：仅写权限员（machinist）可见可用，把留影当刻在途集合（待复核＋复核中，已完成不入镜）的编号、刀号、刀补、当刻状态值拷贝冻结。
2. **历史留影列表**：留影编号、时刻、留影人、笔数。
3. **留影明细**：只读表格，随后原单办结或改动均不影响留影内容。

一致性：留影在单个事务内以 `SELECT … FOR UPDATE` 锁定在途集合，与 worker 的 `SKIP LOCKED` 认领互斥；提交前再以冻结编号集合与当刻在途集合对账，不一致整笔回滚（409，提示重新留影）。

权限：只读员（auditor）可翻阅历史留影与明细，但看不到也点不了「一键留影」（后端 `POST /api/snapshots` 对只读账号返回 403）。

留影不缺行验收：留两笔未办结 → 一键留影，明细列出这两笔 → 办结其中一笔 → 再打开那份留影，仍是留影当时的两笔，不会少一行。

接口：`POST /api/snapshots`（写权限）、`GET /api/snapshots`、`GET /api/snapshots/{id}`（登录即可）。

## 目录

```text
backend/          Django 工程（config/、desk/、worker.py）
frontend/         SolidJS 单页
docker-compose.yml
PRD.md
```
