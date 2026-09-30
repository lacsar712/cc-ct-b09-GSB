import { createSignal, onMount, Show, For, createEffect } from "solid-js";
import {
  clearSession,
  createSnapshot,
  createSubmission,
  fetchSnapshot,
  fetchSnapshots,
  fetchSubmission,
  fetchSubmissions,
  getUser,
  login,
  setSession,
} from "./api";

const statusLabel = {
  pending: "待复核",
  processing: "复核中",
  done: "已完成",
};

const roleLabel = {
  machinist: "操作员",
  auditor: "复核员",
};

function readHash() {
  const raw = (location.hash || "#/").replace(/^#/, "") || "/";
  const m = raw.match(/^\/detail\/(\d+)/);
  if (m) return { name: "detail", id: Number(m[1]) };
  if (raw === "/snapshots") return { name: "snapshots", id: null };
  return { name: "home", id: null };
}

function App() {
  const [user, setUser] = createSignal(getUser());
  const [rows, setRows] = createSignal([]);
  const [detail, setDetail] = createSignal(null);
  const [route, setRoute] = createSignal(readHash());
  const [error, setError] = createSignal("");
  const [loading, setLoading] = createSignal(false);

  const [loginUser, setLoginUser] = createSignal("machinist");
  const [loginPass, setLoginPass] = createSignal("machine123456");

  const [toolCode, setToolCode] = createSignal("");
  const [offsetUm, setOffsetUm] = createSignal("");

  const [snapshots, setSnapshots] = createSignal([]);
  const [snapshotDetail, setSnapshotDetail] = createSignal(null);
  const [snapshotMsg, setSnapshotMsg] = createSignal("");
  const [snapshotBusy, setSnapshotBusy] = createSignal(false);

  function goHome() {
    location.hash = "#/";
  }

  function goDetail(id) {
    location.hash = `#/detail/${id}`;
  }

  function goSnapshots() {
    location.hash = "#/snapshots";
  }

  async function loadRows() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSubmissions();
      setRows(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadDetail(id) {
    setLoading(true);
    setError("");
    try {
      setDetail(await fetchSubmission(id));
    } catch (e) {
      setError(e.message);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }

  async function loadSnapshots() {
    setLoading(true);
    setError("");
    try {
      const data = await fetchSnapshots();
      setSnapshots(data);
      const current = snapshotDetail();
      if (current && !data.some((s) => s.id === current.id)) {
        setSnapshotDetail(null);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadSnapshotDetail(id) {
    setError("");
    try {
      setSnapshotDetail(await fetchSnapshot(id));
    } catch (e) {
      setError(e.message);
      setSnapshotDetail(null);
    }
  }

  async function handleSnapshot() {
    setSnapshotBusy(true);
    setError("");
    setSnapshotMsg("");
    try {
      const created = await createSnapshot();
      setSnapshotMsg(`留影 #${created.id} 已生成，冻结 ${created.item_count} 笔在途刀补`);
      setSnapshotDetail(created);
      await loadSnapshots();
    } catch (e) {
      setError(e.message);
    } finally {
      setSnapshotBusy(false);
    }
  }

  onMount(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener("hashchange", onHash);
    if (user()) {
      if (route().name === "detail") loadDetail(route().id);
      else if (route().name === "snapshots") loadSnapshots();
      else loadRows();
    }
    return () => window.removeEventListener("hashchange", onHash);
  });

  createEffect(() => {
    const r = route();
    if (!user()) return;
    if (r.name === "detail" && r.id) loadDetail(r.id);
    if (r.name === "home") loadRows();
    if (r.name === "snapshots") loadSnapshots();
  });

  async function handleLogin(e) {
    e.preventDefault();
    setError("");
    try {
      const data = await login(loginUser(), loginPass());
      setSession(data.token, {
        username: data.username,
        role: data.role,
        can_write: data.can_write,
      });
      setUser(getUser());
      goHome();
      await loadRows();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    setRows([]);
    setDetail(null);
    setSnapshots([]);
    setSnapshotDetail(null);
    setSnapshotMsg("");
    goHome();
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    try {
      await createSubmission(toolCode(), offsetUm());
      setToolCode("");
      setOffsetUm("");
      await loadRows();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div class="page">
      <header class="topbar">
        <div class="brand">
          <h1>数控刀补复核台</h1>
          <p class="hint">刀补绝对值不超过十二微米判合格，否则超差。后台认领进程用行锁跳过已占行领取待复核。</p>
        </div>
        <Show when={user()}>
          <nav class="topnav">
            <a
              href="#/"
              class={route().name === "home" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goHome();
              }}
            >
              复核总览
            </a>
            <a
              href="#/snapshots"
              class={route().name === "snapshots" ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                goSnapshots();
              }}
            >
              班次留影台
            </a>
          </nav>
        </Show>
      </header>

      <Show when={error()}>
        <div class="banner error">{error()}</div>
      </Show>

      <Show
        when={user()}
        fallback={
          <section class="card">
            <h2>登录</h2>
            <form onSubmit={handleLogin} class="form">
              <label>
                用户名
                <input
                  value={loginUser()}
                  onInput={(e) => setLoginUser(e.currentTarget.value)}
                />
              </label>
              <label>
                密码
                <input
                  type="password"
                  value={loginPass()}
                  onInput={(e) => setLoginPass(e.currentTarget.value)}
                />
              </label>
              <button type="submit">进入系统</button>
            </form>
            <p class="hint">操作员 machinist / machine123456；复核员 auditor / audit123456（只读）</p>
          </section>
        }
      >
        <section class="card toolbar">
          <div>
            当前用户：<strong>{user().username}</strong>（{roleLabel[user().role] || user().role}）
          </div>
          <button type="button" class="ghost" onClick={handleLogout}>
            退出
          </button>
        </section>

        <Show when={route().name === "home"}>
          <Show when={user().can_write}>
            <section class="card">
              <h2>提交刀补</h2>
              <form onSubmit={handleSubmit} class="form inline">
                <label>
                  刀具编号
                  <input
                    placeholder="如 T01"
                    value={toolCode()}
                    onInput={(e) => setToolCode(e.currentTarget.value)}
                    required
                  />
                </label>
                <label>
                  刀补（微米）
                  <input
                    type="number"
                    value={offsetUm()}
                    onInput={(e) => setOffsetUm(e.currentTarget.value)}
                    required
                  />
                </label>
                <button type="submit">提交待复核</button>
              </form>
            </section>
          </Show>

          <section class="card">
            <div class="toolbar">
              <h2>复核列表</h2>
              <button type="button" class="ghost" onClick={loadRows} disabled={loading()}>
                {loading() ? "刷新中…" : "刷新"}
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>刀具</th>
                  <th>刀补 µm</th>
                  <th>状态</th>
                  <th>结论</th>
                  <th>提交时间</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <For each={rows()}>
                  {(row) => (
                    <tr>
                      <td>{row.tool_code}</td>
                      <td>{row.offset_um}</td>
                      <td>{statusLabel[row.status] || row.status}</td>
                      <td class={row.verdict === "合格" ? "pass" : row.verdict === "超差" ? "fail" : ""}>
                        {row.verdict || "—"}
                      </td>
                      <td>{new Date(row.created_at).toLocaleString()}</td>
                      <td>
                        <button type="button" class="ghost" onClick={() => goDetail(row.id)}>
                          详情
                        </button>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={!rows().length && !loading()}>
              <p class="hint">暂无记录</p>
            </Show>
          </section>
        </Show>

        <Show when={route().name === "detail"}>
          <section class="card">
            <div class="toolbar">
              <h2>刀补详情</h2>
              <button type="button" class="ghost" onClick={goHome}>
                返回总览
              </button>
            </div>
            <Show when={detail()} fallback={<p class="hint">{loading() ? "加载中…" : "未找到记录"}</p>}>
              {(d) => (
                <div class="detail-grid">
                  <p>编号：{d().id}</p>
                  <p>刀具：{d().tool_code}</p>
                  <p>刀补 µm：{d().offset_um}</p>
                  <p>状态：{statusLabel[d().status] || d().status}</p>
                  <p class={d().verdict === "合格" ? "pass" : d().verdict === "超差" ? "fail" : ""}>
                    结论：{d().verdict || "—"}
                  </p>
                  <p>提交时间：{new Date(d().created_at).toLocaleString()}</p>
                  <p>
                    复核时间：
                    {d().reviewed_at ? new Date(d().reviewed_at).toLocaleString() : "—"}
                  </p>
                </div>
              )}
            </Show>
          </section>
        </Show>
        <Show when={route().name === "snapshots"}>
          <section class="card">
            <div class="toolbar">
              <div>
                <h2>一键留影</h2>
                <p class="hint">
                  把当刻待复核与复核中的刀补（编号、刀号、刀补）冻进留影明细，并与留影当刻在途集合对账。
                </p>
              </div>
              <Show
                when={user().can_write}
                fallback={<p class="hint">只读账号可翻看留影，不能一键留影</p>}
              >
                <button type="button" onClick={handleSnapshot} disabled={snapshotBusy()}>
                  {snapshotBusy() ? "留影中…" : "一键留影"}
                </button>
              </Show>
            </div>
            <Show when={snapshotMsg()}>
              <p class="pass">{snapshotMsg()}</p>
            </Show>
          </section>

          <section class="card">
            <div class="toolbar">
              <h2>历史留影列表</h2>
              <button type="button" class="ghost" onClick={loadSnapshots} disabled={loading()}>
                {loading() ? "刷新中…" : "刷新"}
              </button>
            </div>
            <table>
              <thead>
                <tr>
                  <th>留影编号</th>
                  <th>留影时间</th>
                  <th>操作人</th>
                  <th>冻结笔数</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <For each={snapshots()}>
                  {(snap) => (
                    <tr>
                      <td>#{snap.id}</td>
                      <td>{new Date(snap.created_at).toLocaleString()}</td>
                      <td>{snap.created_by}</td>
                      <td>{snap.item_count}</td>
                      <td>
                        <button
                          type="button"
                          class="ghost"
                          onClick={() => loadSnapshotDetail(snap.id)}
                        >
                          明细
                        </button>
                      </td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
            <Show when={!snapshots().length && !loading()}>
              <p class="hint">暂无留影</p>
            </Show>
          </section>

          <section class="card">
            <h2>留影明细</h2>
            <Show
              when={snapshotDetail()}
              fallback={<p class="hint">在历史留影列表点「明细」查看某次留影冻结的刀补。</p>}
            >
              {(snap) => (
                <>
                  <p class="hint">
                    留影 #{snap().id} · {new Date(snap().created_at).toLocaleString()} · 操作人{" "}
                    {snap().created_by} · 冻结 {snap().item_count} 笔（留影当刻在途集合，只读不再变化）
                  </p>
                  <table>
                    <thead>
                      <tr>
                        <th>编号</th>
                        <th>刀号</th>
                        <th>刀补 µm</th>
                        <th>留影时状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <For each={snap().items}>
                        {(item) => (
                          <tr>
                            <td>{item.submission_id}</td>
                            <td>{item.tool_code}</td>
                            <td>{item.offset_um}</td>
                            <td>{statusLabel[item.status] || item.status}</td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                  <Show when={!snap().items.length}>
                    <p class="hint">该次留影时在途队列为空</p>
                  </Show>
                </>
              )}
            </Show>
          </section>
        </Show>
      </Show>
    </div>
  );
}

export default App;
