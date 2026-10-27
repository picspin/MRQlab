# ISMRM 投稿就绪审计

审计日：2026-10-28（Asia/Shanghai）。证据限仓库和本地实际运行；不把文档愿景当成功能验收，不进行外部新颖性检索或会议规则核验。

结论：**集成门禁通过，投稿尚未就绪**。目前足以制作诚实的软件架构 / 教学研究原型草稿；不足以主张已验证的临床优化、诊断收益、扫描仪可执行性或相对于现有工作的优先性。下列必要项完成前不得把草稿改成完成态。B/C 继续 parked；本审计没有证明它们是该有限范围投稿的必需条件，也没有解锁或实现 B/C。

## 1. 集成证据

在 `/Users/hilbert/work/MRQlab-worktrees/ismrm-integration` 从 `3239a65` 新建 `ismrm/integration`。用 `git cherry-pick --no-commit f678cbf 3bdc1da` 集成并生成独立提交 `3d699432ed3b8e54d1c98fb02840e0168fcdb021`，无冲突。该提交只改原两修复对应的四个文件：单位校验与计划映射 `|=` 禁写及其回归测试。未修改两个原始修复 worktree，也未改主检出或 MRQlab-pr53。

| 实测命令 | 结果 | 持久证据 |
| --- | --- | --- |
| `.venv/bin/python -m pytest tests/ -q`（复用主检出 Python） | 400 passed，1 warning | `evidence/integration-pytest.txt` |
| `cd apps/web && npm test` | 12 files，82 tests passed | `evidence/integration-web.txt` |
| `cd apps/web && npx tsc --noEmit` | exit 0，无诊断 | `evidence/integration-tsc.txt` |
| 具名合同和物理子集 `pytest ... -v` | 27 passed；是完整 400 的子集，不额外计数 | `evidence/targeted.txt` |

双端合计 **482 个通过的测试用例**（400 Python + 82 web），另有 TypeScript 静态检查；不把文件数或重复复核的运行再加到总数。警告为现有 Starlette TestClient/httpx 弃用提示，不是物理验证失败。`verify.sh` 新统一脚本也已实际执行通过，输出在 `/private/tmp/mrqlab-ismrm-checks`；归档证据仍指第一次完整集成运行。

## 2. Novelty：可陈述的贡献与不可陈述的结论

对照 `docs/ARCHITECTURE.md` 的五合同、三层 IR、能力选择和 Observation provenance；`docs/PHYSICS.md` 的状态 / 算子分离、单位及近似；`docs/superpowers/specs/2026-09-27-protocol-platform.md` 的 Milestone A 临床合同、参数诚实性与 B/C 人工门禁。

通用 Bloch / EPG 传播器回答给定脉冲与组织下的磁化 / 配置态演化。MRQlab 的仓库级区别是把临床问题、目标 / 参考 / 混杂组织、组织先验和扫描仪配置，连到实验图、解析执行计划、能力协商和带来源的结果图；同时向用户暴露控件是否真正进入计算。新增价值在**可审查的实验组织与参数来源契约**，并非新 Bloch 方程、新 EPG 算法或已证明优于其他软件。

| 内容 | 已有证据 | 投稿可用表述 |
| --- | --- | --- |
| 临床语义合同与版本化先验 | `clinical.py`、`clinical_catalog.py`；具名 `test_brain_and_knee_roles_are_clinically_explicit`、`test_tissue_roles_enforce_role_agreement` | 目标 / 参考 / 混杂角色可验证；先验数值尚缺临床来源，不能称患者真值 |
| 单位校验、冻结计划与规范哈希 | `resolution.py`；`test_parameter_state_rejects_unknown_units`、`test_acquisition_constraint_rejects_incompatible_units`、`test_resolved_mappings_reject_in_place_union`、`test_fingerprint_is_canonical_and_changes_with_resolved_input` | 测试覆盖的普通变更路径被拒绝、同输入哈希可重复；不是对恶意 Python 调用的安全隔离证明 |
| 结果来源 | `observations.py`；`test_every_observation_carries_resolved_plan_and_parameter_provenance`；两个实际 API 响应 | 每个结果带计划、引擎、先验和参数来源；完整软件 commit 需由环境快照补充 |
| EPG 前向计算 | `tests/physics/test_epg_engine.py::test_three_echo_cpmg_train_matches_independent_t2_envelope` 实际通过 | 有理想 CPMG 与独立指数包络的一致性测试，绝对容差 `1e-10`；不能由此推导患者准确性 |
| 未接线参数诚实性 | web `protocol-parameter-honesty.test.tsx`、wave-f/wave-h 在完整门禁中通过 | UI 测试覆盖未接线标签和 payload 排除；不等于人工浏览器验收 |
| 教学演示 | 硬 RF、默认无量纲梯度、相对 SAR、FFT 示意 image | 仅展示状态与对比机制，不称临床图像 / SAR 安全认证 |

“首次”“唯一”“优于现有模拟器”均**未验证**。当前文献对照仅有仓库参考条目，不能建立领域新颖性。需要后续基于用户选定投稿范围做文献比较；本次未联网。

文档自身也有遗留不一致：ARCHITECTURE 能力表标 ssEPG / EPG-X / PDG 可用，而其第 7 节教学例仍写 unavailable/provider seam；PHYSICS 对 PDG 的路径和 provider seam 也有需澄清处。保留这些边界并列为文档待修；摘要不宣称已全面验证这些高级引擎。

## 3. Validation：两个实际垂直场景

`reproduce.py` 在集成源码上调用真实 FastAPI 应用。`GET /protocol-recipes` 成功；两个 ID 分别经过配方构建、直接解析计划、`POST /experiments/validate` 与 `POST /experiments/run`（均 HTTP 200），输出 signal / k_trajectory / image。归档每一步输入输出，路径见 README。没有浏览器、HTTP 服务进程、患者、扫描仪或外部参照数据参与。

| 实测项 | Brain lesion T2/TSE | Knee cartilage/meniscus PD/T2 TSE |
| --- | --- | --- |
| recipe ID | `brain_lesion_t2_tse` | `knee_cartilage_meniscus_pd_t2_tse` |
| 输入 te / tr（s） | 0.010 / 3.0 | 0.045 / 2.5 |
| 输入重聚焦角 | 150° | 140° |
| 声明 echo_count / 实际派生 echoes | 16 / 4 | 16 / 4 |
| 引擎 / 表示 | epg / epg | epg / epg |
| ADC 样本数 | 8 | 8 |
| 默认 signal 首 / 均 / 末幅值（a.u.） | 0.761841649 / 0.698521282 / 0.632159547 | 0.235073781 / 0.097271165 / 0.026886953 |
| n_ops / estimated_work | 81 / 31347 | 81 / 31347 |
| 临床 graph.objective | null | null |

数值来自 `evidence/summary.json`，完整精度在 JSON。8 个 ADC 样本不等于 8 个回波；模板有 4 个 ADC gate，每个 gate 可有多个样本。te 在当前 TSE builder 中用于回波中心间隔，不能直接解释为临床有效 TE。

逐组织额外前向诊断（同配方、每次单独 Phantom；均值为 ADC 幅值均值，单位 a.u.）：

| 场景 | 组织均值 | 由命名组织显式计算的差值 |
| --- | --- | --- |
| Brain | lesion 0.747712922；WM 0.535119114；GM 0.643158404；CSF 0.951534856 | lesion–WM 0.212593809 |
| Knee | cartilage 0.094898698；tear 0.308589399；meniscus 0.008054369；fluid 0.868109640；fat 0.175452770 | tear–meniscus 0.300535030；cartilage–meniscus 0.086844329 |

这是教学信号差，不是临床 CNR。代码中的 proxy 用固定 0.05 作分母，没有测量噪声模型。CSF / joint fluid 均更亮，不能把亮度直接当病变证据。诊断脚本按组织 ID 计算的配对差值是审计补充，**不是应用已执行 ObjectiveVector 的证明**。

具名回归覆盖和实际输出的关联：目录 / 角色 / 图构建由 `test_protocol_verticals.py`；冻结 / 单位 / fingerprint 由 `test_resolved_execution_plan.py` 和 `test_clinical_contract_models.py`；来源由 `test_observations.py`；理想 EPG 参照由 `test_epg_engine.py`。这 27 项实际通过，完整名称在 `targeted.txt`。现有测试通过仍漏掉以下运行语义缺口：

1. **回波参数未接通**：`presets.py` 写 `echo_count=16`，`templates.py::_echo_count` 只读 `echoes` 并默认 4；`compiler.py` 直接透传。输入和派生参数同时被记录，但尚未拒绝此不一致。实测两场景均如此。
2. **目标与约束只是声明**：`build_protocol_experiment` 没有把 `clinical_recipe.objective` 接到执行目标；默认 `graph.objective=null`，未请求 objective_score 或 tissue_contrast。鲁棒性范围、扫描时间和分辨率合同也不能因 HTTP 200 视为经过评估；临床约束满足性**未验证**。
3. **旧版对比取前两个组织**：`objectives.py::evaluate_multi_tissue_contrast` 忽略 ObjectiveVector 的命名配对。Brain 恰为 lesion / WM；Knee 实际比较 cartilage / tear，差值 0.213690701，不能冒充 tear / meniscus。摘要只报审计诊断的命名组织差值，明确未接入目标。
4. **默认聚合信号不是多组织 EPG 结果**：`kernel.py::_phantom_from_sample` 把多组织变成 isochromats，同时顶层 T1/T2 取第一个组织，PD 取平均；`backends/epg.py` 只传播顶层 Phantom，未遍历该 isochromat 集合。逐组织诊断因此比默认聚合 signal 更适合教学比较，但也没有空间解剖或病灶模型。默认 image 不能当临床脑 / 膝图像。

本轮按任务范围记录这些新缺口，没有追加生产修复或推翻既有 A 审计。**门禁全绿不等于临床垂直场景语义全正确**。

## 4. Reproducibility

已补 `reproduce.py`、`verify.sh`、版本快照、固定 Python 环境清单、原始 JSON、两幅 SVG、具名日志和执行说明。统一复核脚本实际通过。另一次 replay 的 summary 与归档一致（见 README 中复核命令；比较结果在 `evidence/replay-comparison.txt`）。源码导入断言防止复用 venv 时误读主检出；没有进行网络安装。

证据边界：当前机器离线复跑已验证；干净环境独立重建、跨 OS / Python / Node 支持、浏览器端完整交互、部署和公开链接均**未验证**。README 提供待执行命令和手动路径，没有把它们写成验收结果。依赖不含供应缓存；离线新机安装尚缺 wheel/npm 物料。

## 5. 必须保留的限制

- Research-use-only / teaching；无患者队列、读片者研究、敏感性 / 特异性、临床效果或扫描仪对照。
- 默认梯度为 dimensionless teaching gradients；硬 RF、有限 EPG 阶数、单池近似。相对 SAR 不等于 W/kg，梯度 / RF / 时序声明不等于硬件安全审查。
- tissue prior 是合成设定，未在本包证实文献或测量出处。单次前向轨迹不等于稳态临床 PD/T2 协议；没有做噪声、运动或鲁棒性扫参验证。
- 默认 FFT image 是信号变换示意，未验证空间编码的临床保真度；本包不把它用作解剖图。
- B parked：不主张已完成可执行序列、完整物理时序约束或 Pulseq / 厂商导出验证；基线继承的相关代码不作为本次验收证据。
- C parked：不主张经本次验证的本地 job 生命周期、GPU 或商业计算闭环；本次只验证同步 Tier 1。
- 未接真实扫描仪；不存在扫描仪安全批准、诊断应用或临床就绪声明。

## 6. 投稿缺口分级

**投稿前必须补**：回波参数语义一致并有失败后通过回归；明确多组织 EPG 和临床命名指标的执行契约（修复或把投稿明确限缩到合同软件原型，不能维持现状却声称已执行临床优化）；为所保留的科学结果补独立解析 / 公开实现参照和误差量化；先验出处与适用边界；修正文档可用性矛盾；干净环境重建；摘要数值和图表随最终代码重跑冻结；新颖性文献对照；按用户选定会议 / 类别核对官方格式与规则。

**可以补**：更广泛的 TE / 重聚焦角 / B1 等参数扫查、误差和运行代价图、性能基准、教学可用性研究、自动化 GUI 合同桥接演示、录屏和公开只读演示。只有实际执行且范围合适才进入 Results。

**需要用户决定**：投稿年份 / 会议届次和类别、临床优化研究还是软件 / 教学原型叙事、作者顺序 / 通讯作者 / 单位、关键词、资助 / 利益冲突 / 伦理声明的实际内容、正式图表选择、演示是否公开及链接、是否安排额外科学验证。B/C 是否解锁需另行明确决定；本包不把解锁作为默认建议。
