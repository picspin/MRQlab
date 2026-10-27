# ISMRM 本地审阅包

状态：ISMRM 2027 温哥华软件 / 教学原型审阅包。四项执行阻断已修复；409 Python + 82 web 测试通过，TypeScript exit 0。摘要数值已按新代码重跑；用户仍需完成类别、作者等门户字段、图表终选和最终审阅，亲自提交。截止按用户确认：2026-10-28 23:59 UTC（北京时间 2026-10-29 07:59）。未核对门户格式或宣称已提交，B/C 保持 parked。

- [摘要草稿](abstract-draft.md)
- [图表与检查表](submission-checklist.md)
- [实际输出摘要](evidence/summary.json)、原始请求 / 计划 / API 响应、逐组织诊断和 SVG 位于 `evidence/`
- `evidence/fix-*.txt` 是本轮门禁及失败复现；integration / targeted 日志仅为历史记录。

## 代码与环境

基础 `3239a6594561bb9af24015f7c004d15217477f00`；生产代码集成提交 `3d699432ed3b8e54d1c98fb02840e0168fcdb021`，组合 `f678cbf` 和 `3bdc1da`。材料起点 `00b72e2`。本轮在新 `ismrm-fix` worktree / `ismrm/fix` 分支修复；以 `git log` 查看本轮代码与材料提交。没有改动原始修复 worktree。

本地运行：macOS（完整平台见 `evidence/environment.json`），Python 3.15.0，Node v26.11.1，npm 11.20.0；Python 依赖来自主检出的现有 `.venv`，前端依赖通过被 Git 忽略的 `apps/web/node_modules` 软链接复用。`reproduce.py` 显式把本 worktree 的源码放到 sys.path 首位并断言导入路径，避免主检出的 editable install 污染结果。pytest 使用本 worktree 的 pyproject pythonpath。不要把复用依赖等同于独立重装验证。

完整已安装版本记录在 `environment.json`；`requirements-observed.txt` 固定本次 Python 环境版本（排除了指向主检出的 editable mrqlab）；前端使用仓库 `apps/web/package-lock.json`。版本快照是本次观察结果，跨系统可安装性尚未验证。

## 离线复核（当前机器，已实际运行）

在 `/Users/hilbert/work/MRQlab-worktrees/ismrm-fix` 根目录：

```bash
PYTHON=/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python \
  bash docs/ismrm/verify.sh /private/tmp/mrqlab-ismrm-checks
```

脚本依次执行完整 `pytest tests/ -q`、`apps/web npm test`、`npx --no-install tsc --noEmit` 和两个场景的 FastAPI TestClient 路径。TestClient 使用真实应用路由、Pydantic 校验、内核和结果序列化，不启动 TCP 服务，不代表浏览器或部署测试。失败即退出。输出目录参数可避免覆盖归档。

单独重生成数据和两幅 SVG：

```bash
/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python \
  docs/ismrm/reproduce.py /private/tmp/mrqlab-ismrm-replay
```

逐项路径为 `GET /protocol-recipes` → `build_protocol_experiment(id)` → `plan_experiment` → `POST /experiments/validate` → `POST /experiments/run` → 五类 Observation（含命名组织对比与目标评分）。另行执行逐组织重放，用于核对已执行命名指标和默认等权复数聚合。

API 对引擎选项填默认值并抑制未请求的快照，所以直接规划 fingerprint 与 API fingerprint 不同；两者均归档，不能把差异直接称为非确定性。脚本检查同输入直接计划 fingerprint 可重复。API provenance 带 seed=0，但并未自动含 Git commit；环境记录补上代码提交、工作树状态、源码 SHA256 和导入路径。

## 新环境重建（命令提供，未实际联网运行）

```bash
python3.15 -m venv .venv
.venv/bin/python -m pip install -r docs/ismrm/requirements-observed.txt
.venv/bin/python -m pip install --no-deps -e .
npm --prefix apps/web ci
PYTHON="$PWD/.venv/bin/python" bash docs/ismrm/verify.sh /private/tmp/mrqlab-ismrm-clean
```

这些安装命令需要可用的包源或事先准备的 wheel/npm 缓存。本次没有执行网络安装，独立干净环境重建仍未验证；本摘要仅陈述当前环境的复跑结果。

## 手动界面演示（尚未验证）

按 README 启动 API 和 Next.js，明确让所有源码来自此 worktree：

```bash
export PYTHONPATH="$PWD/packages/sequence-ir:$PWD/packages/physics:$PWD/packages/recon:$PWD/packages/mrqlab_experiment:$PWD/services/api:$PWD/services/local_agent"
/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python -m uvicorn mrqlab_api.main:app --host 127.0.0.1 --port 8000
# 第二终端：
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm --prefix apps/web run dev
```

浏览 `http://localhost:3000`，Explore → 脑 / 膝配方 → RUN → 检查结果和未接线控件标记。此路径只是待执行的人工检查说明；现有 Explore 临床配方不应未经证据视为与 `build_protocol_experiment` 的 A 合同完全相同。两个 A 场景的权威演示目前是上述离线脚本；GUI 与 A 合同桥接、录屏、公开演示链接均待核实。没有部署或外部访问验证。
