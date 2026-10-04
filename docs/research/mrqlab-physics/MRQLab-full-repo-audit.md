# MRQLab 全仓库架构与实现审计

## 一、结论先行

**MRQLab 已经不是一个“只有几条 Bloch 曲线的教学 Demo”了。**  
它已经形成了相当有价值的技术骨架：

- 以 `ExperimentGraph` 为产品中心，而不是把产品锁死在某个 sequence class 或 simulator class 上。
- 已经存在 `Experiment IR → Sequence IR → Physics IR → Observation` 的分层思路。
- 有 Bloch、EPG、EPG-X、Spectral、ssEPG、PDG 等表示/引擎路径，具备 capability negotiation、fail-closed、work cap 和 provenance 的雏形。
- Web 端已经具备临床问题入口、序列事件编辑、参数调节、对比/优化视图和后端运行闭环。
- 物理代码、实验模型、重建、API、前端的模块边界总体是正确的。

但同时：

> **当前它仍是一个“有临床方向的高级研究/教学原型”，还不是一个真正可交付的临床序列设计与调参产品。**

我对当前成熟度的粗略判断是：

| 维度 | 当前成熟度 | 说明 |
|---|---:|---|
| 教学与物理可视化产品 | **70–80%** | 已有较完整的前后端体验和大量测试 |
| MRI 物理研究原型 | **55–65%** | 多引擎和多池模型有实质代码，但覆盖与验证深度仍有限 |
| 临床 contrast/protocol planning 工具 | **30–40%** | 已有临床 recipe 和 tissue/objective 抽象，但临床参数链尚未真正闭合 |
| 高保真本地 GPU simulator | **10–20%** | 当前是 NumPy-first、单进程、同步 API，并没有 GPU worker/runtime |
| 标准化序列导出与 scanner translation | **<10%** | 尚无 Pulseq、厂商格式、ISMRMRD 等真正 export adapter |
| 可商业化授权与部署平台 | **<10%** | 当前无身份认证、entitlement、lease、worker registration、审计或持久化 |
| 医疗器械/临床决策支持级产品 | **<5%** | 明确没有验证体系、风险管理、临床证据链和法规工程 |

所以核心建议不是推倒重做，而是：

> **保留现有 experiment kernel 和三层 IR，把“教育 Web App”升级成“临床问题驱动的 protocol engineering platform”；本地高保真执行器、标准导出与 License Control Plane 应作为新边界添加，而不是塞进 physics kernel。**

---

# 二、我看到的现有架构

## 1. 领域抽象方向是对的

当前架构把一次 MRI 工作定义为：

```text
Experiment
  = Sequence
  + Spin/Tissue
  + Scanner
  + Physics Engine
  + Objective
  + Readout
```

这比“选择 TSE，然后调 TE/TR”的页面模型先进得多，也更适合未来做临床目标优化、不同保真度执行、sequence translation 和 protocol comparison。项目文档也明确把 `ExperimentGraph`、`PhysicsOperator`、`StateRepresentation`、`ObjectiveFunction`、`Observation` 作为五个稳定合同。docs/ARCHITECTURE.md:3-31

实际模型中也已经有：

- `TissueModel`
  - T1/T2/T2*
  - proton density
  - flow
  - exchange
  - pool fraction
  - diffusion ADC
  - chemical shift
- `PhysiologyModel`
  - cardiac/respiratory phase
  - RR interval
  - flow waveform
  - contrast concentration
- `ScannerModel`
  - B0
  - gradient/slew constraints
  - ADC bandwidth
- `EngineRef`
  - preferred engine
  - required capabilities
  - engine options
- `ObjectiveFunction`
- `DisturbanceStack`
- `ReadoutSpec`
- `ConstraintSet`

这些字段已经进入 `ExperimentGraph`，说明它不是纯 UI 概念，而是有可序列化、可验证的后端合同。packages/mrqlab_experiment/mrqlab_experiment/models.py:44-78packages/mrqlab_experiment/mrqlab_experiment/models.py:88-126

这是整个项目目前最重要、最值得保留的资产。

---

## 2. 三层 IR 是未来高级 MRI 产品的正确基础

项目明确划分了：

```text
Experiment IR
    ↓
Sequence IR
    ↓
Physics IR
    ↓
StateRepresentation + PhysicsOperator
    ↓
Observation
```

其中：

- Experiment IR 保存临床意图与实验语义。
- Sequence IR 保存扫描事件语义。
- Physics IR 保存具体传播算子语义。
- Observation 保存信号、图像、echo train、configuration、SAR、objective 等结果。

这个分层允许以后：

- 同一个临床目标由多个 sequence family 实现。
- 同一个 SequenceIR 送到浏览端轻量引擎、本地 CPU 引擎或 GPU provider。
- 不同 scanner profile 对同一 logical sequence 做 lower/translation。
- 优化器只面向 `ObjectiveFunction` 和 constraints，不直接耦合 Bloch/EPG。
- Pulseq 或厂商导出只消费“已经解析并通过硬件/安全验证”的序列表示。

当前 SequenceIR 有八个明确的通道：

- `rf_amp`
- `rf_phase`
- `gx`
- `gy`
- `gz`
- `adc_gate`
- `nco_freq`
- `nco_phase`

架构文档已经把这些通道视为 scanner-level event source。docs/ARCHITECTURE.md:33-51

这个技术方向完全可以承载你所说的：

> 浏览端轻量交互模拟 + 本地高保真计算 + 标准序列导出 + 可选本地执行器。

---

## 3. 当前实现不是空架子

### 序列与事件编辑

目前已有：

- SE/GRE/TSE template builder。
- SequenceIR 的 build、patch、compose API。
- RF、gradient、ADC block。
- RF phase、flip angle、duration、TBW。
- physical gradient 的 mT/m 声明。
- gradient end-zero 和 RF end-zero。
- block overlap 检查。
- gradient hardware constraint 检查。
- compose 后的 event overlay / metadata 回写。

例如 compose 层已经对 RF、梯度和 ADC 建立有类型的 block contract，并禁止同一通道 block 重叠。packages/mrqlab_experiment/mrqlab_experiment/sequence_compose.py:13-46packages/mrqlab_experiment/mrqlab_experiment/sequence_compose.py:49-91

一旦存在物理梯度 block，当前实现会明确设置：

- `gradient_units="mt_m"`
- `fov_m`
- preferred EPG engine

这比把所有 gradient 都当成无量纲教学刻度要可靠得多。packages/mrqlab_experiment/mrqlab_experiment/sequence_compose.py:111-119

### 物理引擎

当前不是单一 Bloch solver，至少包含：

- Bloch
- classic EPG
- spectral pool
- hybrid
- ssEPG
- EPG-X
- PDG
- diffusion attenuation
- Bloch–McConnell exchange
- magnetization transfer
- Super-Lorentzian saturation
- CW / rectangular pulsed CEST Z-spectrum

项目还正确地区分了：

- **State representation**：Bloch、EPG、PDG、ssEPG、density matrix。
- **Operator**：RF、relaxation、gradient、exchange、diffusion、flow、off-resonance。

这避免了以后出现 `AdvancedSimulatorV7` 一类难以维护的继承树。物理文档也清楚说明目前只在 classic EPG + physical gradient 上接通了 isotropic diffusion；CEST 仍是 single-voxel、two-pool 范围，CEST imaging、multi-solute、shaped RF、MRS/COSY 尚未实现。docs/PHYSICS.md:84-88

### Capability negotiation 与 fail-closed

当前系统不会在缺失物理能力时偷偷降级。例如：

- slice profile 应路由到 ssEPG。
- exchange 应路由到 EPG-X。
- spatial B0 map 应路由到 PDG。
- 不可满足能力时返回明确错误。

这一原则对于临床工具非常重要。临床产品最危险的行为不是报错，而是“运行成功但物理不完整”。当前架构明确采用缺能力即失败的方式。docs/ARCHITECTURE.md:67-89docs/ARCHITECTURE.md:101-114

### API

FastAPI 已经有相对清晰的 canonical boundary：

- `POST /experiments/validate`
- `POST /experiments/run`
- `POST /experiments/run-from-recipe`
- `POST /sequences/build`
- `POST /sequences/patch`
- `POST /sequences/compose`
- `/simulate` compatibility endpoint
- gradients、trajectory、recon、optimizer、compare、cockpit 和 pulse inspector 等端点

项目文档也明确要求 `/simulate` 与 canonical experiment API 共用同一 application service，避免出现两个物理实现分叉。README.md:31-36

### Web 前端

当前 Web 已经不是单页 slider demo，而是：

- Explore
- Editor
- Signal Lab
- Workbench/Cockpit
- Compare
- Optimize
- Pulse Inspector
- Gradient Editor
- K-space Recon
- Sequence Lego
- shared workspace state

前端测试覆盖了 clinical Explore、recipe identity、event editing、write-back、CEST spectrum、Lego compose/run 等关键闭环。

---

# 三、当前最严重的问题

## 1. 产品定义仍然与目标冲突

README 和 package metadata 仍将项目定义为：

> teaching MRI simulator / web learning instrument / not a scanner console。

`pyproject.toml` 的 description 也仍是 teaching simulator。README.md:1-5pyproject.toml:1-6

更重要的是，README 明确写着：

- 不连接真实硬件。
- 不做 scanner control。
- 不做 pulse safety validation。
- 不用于 clinical decision-making 或 diagnostic use。README.md:71-75

这些安全声明目前是正确的，不能贸然删除；但这也说明：

> **现有产品合同从根本上还没有接受你现在描述的商业产品目标。**

要升级，建议重新定义产品层级，而不是简单把 “teaching” 替换为 “clinical”：

### 建议的产品分层

1. **MRQLab Explore**
   - 浏览器端轻量交互。
   - 教学、概念探索、recipe 浏览。
   - 可匿名使用。

2. **MRQLab Protocol Studio**
   - 临床问题驱动的 sequence/protocol engineering。
   - 对比目标、组织模型、scanner profile、约束、A/B comparison。
   - 可连接本地 worker。

3. **MRQLab Compute**
   - 本地高保真执行器。
   - GPU/CPU provider。
   - 批量 sweep、优化、cache、artifact storage。

4. **MRQLab Export**
   - Pulseq 等标准导出。
   - scanner-specific validation。
   - 明确的“仿真通过”与“硬件可执行通过”两级状态。

5. **MRQLab Enterprise Control Plane**
   - 用户、组织、设备、license、entitlement、lease、审计。

这样可以保留教学入口，同时让高级能力成为明确的商业层，而不是让同一个匿名 FastAPI 应用同时扮演所有角色。

---

## 2. 临床 recipe 目前更像“预填 tissue 参数”，还不是临床知识模型

当前 `TissueModel` 和 `PhysiologyModel` 是很好的基础，但还缺少真正把“诊断点”转化为可优化目标的知识层。

一个临床协议不只是：

```text
T1, T2, PD + TE/TR/FA
```

它至少还需要：

```text
ClinicalQuestion
  ├─ anatomy / region
  ├─ pathology / differential
  ├─ target finding
  ├─ target tissue
  ├─ competing tissues / confounders
  ├─ desired contrast mechanism
  ├─ minimum spatial resolution
  ├─ coverage
  ├─ maximum scan time
  ├─ motion sensitivity
  ├─ robustness targets
  ├─ quantitative bias limits
  └─ scanner / coil / field-strength constraints
```

然后才生成：

```text
ProtocolDesignProblem
  = ClinicalQuestion
  + TissuePriorSet
  + AcquisitionConstraints
  + ObjectiveVector
  + RobustnessEnvelope
```

当前 `ExperimentGraph.intent` 只有 `teaching | clinical_contrast | physics | custom`，语义仍太粗；而 `ConstraintSet` 目前基本只有 `max_work` 和 `matrix`，还不足以表示 scan time、SAR/PNS、resolution、coverage、motion、echo spacing、bandwidth、SNR 等约束。packages/mrqlab_experiment/mrqlab_experiment/models.py:98-126

因此现在能做到的是：

- “这个组织在该参数下信号大约如何变化”；
- “TSE refocusing angle 对 echo train 的影响”；
- “CEST 参数如何影响 Z-spectrum”。

还不能可靠回答：

- “3T 膝关节半月板细小撕裂，在 4 分钟内、给定线圈和运动风险下，怎样选择 ETL、echo spacing、refocusing train、BW、matrix、slice thickness、parallel imaging？”
- “该方案为何优于另一方案，在哪些组织/场偏差/运动条件下会失效？”
- “从该参数集导出的序列是否满足目标 scanner 的 raster、RF、gradient、SAR/PNS 和 timing constraints？”

---

## 3. SequenceIR 仍不足以作为标准序列导出的源模型

当前 SequenceIR 的八个时间通道很适合：

- 浏览器时间轴。
- 轻量 simulation。
- 统一 scheduler。
- 当前 RF/gradient/ADC 的编辑。

但对标准化导出还不够。

目前缺少或没有成为 first-class contract 的内容包括：

- 任意 RF waveform samples。
- RF frequency/phase offsets 与明确 carrier semantics。
- slice-select gradient 与 RF 的组合关系。
- gradient arbitrary waveform 与梯形/扩展梯形的结构化表示。
- gradient raster、RF raster、ADC raster。
- ADC dwell time、sample count、delay、phase/frequency offset。
- block duration 与 dead time/ringdown。
- trigger、label、loop、conditional execution。
- hardware shape libraries/deduplication。
- exact timing quantization。
- vendor/scanner profile lowering information。
- RF spoiling、gradient spoiling 等结构化状态。
- 多通道 transmit/receive。
- concomitant field、eddy-current compensation 等高级约束。

当前 compose block 类型也只有：

- excite/refocus sinc
- trap gradient
- ADC gate

这对交互编辑器是合理的 MVP，但距离 sequence authoring/export 还有明显差距。packages/mrqlab_experiment/mrqlab_experiment/sequence_compose.py:13-46

### 建议

不要直接把现有 SequenceIR 替换成 Pulseq，也不要让前端直接 author Pulseq。

应增加一个更严格的中间层：

```text
ExperimentGraph
      ↓
LogicalSequenceIR
      ↓ protocol lowering
ExecutableSequenceIR
      ↓ scanner profile + raster quantization
ExportIR
      ├─ Pulseq adapter
      ├─ vendor research adapter
      └─ simulation scheduler adapter
```

现有 SequenceIR 可逐步演化成 `LogicalSequenceIR`，或者作为其兼容视图。

**序列导出必须在 lowering 后完成**，而不是把当前 UI 事件直接写成 `.seq` 文件。

---

## 4. “临床参数”和“真实计算参数”目前仍有脱节

Roadmap 自己已经很诚实地记录了若干未接线的 UI 参数：

- ADC bandwidth 是 seed/not-wired。
- clinical geometry 在 Lego 模式下禁用。
- acceleration、readout width、partial Fourier 是 local-only。
- TE/TR/FA 在 compose 后仍可能只是 seed 而非可重编译参数。
- shaped RF/custom waveform designer 尚未实现。docs/ROADMAP.md:27-34

这类诚实标注值得保留，但它意味着当前界面还不能被称为 protocol planning cockpit。

临床工具中每个参数必须有可追溯状态，例如：

| 状态 | 含义 |
|---|---|
| `authored` | 用户直接设置 |
| `derived` | 编译器计算 |
| `scanner_default` | 由 scanner profile 补充 |
| `estimated` | 近似计算 |
| `visual_only` | 只影响 UI，不影响运行 |
| `unsupported` | 当前执行器不支持 |
| `stale` | 上游改变后结果尚未重算 |

当前已经有 `stale_dependencies`、provenance、approximations 的雏形，因此不需要推倒重做；应该把这个思想扩展到每个参数与每个 observation。

---

## 5. 物理覆盖不错，但离“高保真”还很远

当前物理层的优点是抽象清晰，缺点是可验证范围仍窄。

### 已有价值

- Bloch/EPG 分离。
- EPG-X exchange/MT。
- single-voxel two-pool CEST。
- physical-gradient opt-in。
- diffusion 在有限路径上的接线。
- ssEPG/PDG 独立路径。
- engine plugin seam。
- work cap 与 event/sample cap。

### 仍缺的核心能力

- 任意 shaped RF 与真实 pulse waveform propagation。
- B1+、B0 spatial maps 在完整 imaging path 中传播。
- coil sensitivity 与 receive combination。
- noise model / SNR / g-factor。
- realistic multi-coil k-space。
- eddy current、gradient nonlinearity、concomitant fields。
- motion/flow 的真正传播，不只是 schema 字段。
- physiological gating/trigger execution。
- parallel imaging。
- partial Fourier。
- compressed sensing。
- multi-shot phase errors。
- EPI distortion/ghosting。
- quantitative mapping model fitting。
- multi-compartment diffusion。
- multi-pool CEST/MT imaging。
- MRS density-matrix path。
- GPU batch execution和自动微分。

项目文档明确承认 Bloch、hybrid、ssEPG、PDG、EPG-X、spectral 路径都没有普遍接入 diffusion，同时 CEST imaging、multi-solute CEST、shaped RF 和 MRS/COSY 尚不可用。docs/PHYSICS.md:84-88

因此，当前“高保真”更准确的称呼应是：

> **modular forward-model research kernel with selected high-fidelity paths**

而不是普遍意义上的 high-fidelity MRI simulator。

---

## 6. 优化目前是演示级，不是 protocol optimization engine

架构对 forward model 和 inverse search 的区分是正确的：

```text
theta* = argmin ObjectiveFunction(Observation(forward(theta)))
```

但现阶段：

- `ObjectiveFunction` 主要是 scalar score。
- optimizer 是有限的 Pareto/参数扫描逻辑。
- 没有统一的 parameter space contract。
- 没有 robust optimization。
- 没有 uncertainty propagation。
- 没有 optimizer job/resume/cache。
- 没有 gradient-based differentiable path。
- 没有把硬件、scan time、SAR/PNS、图像质量作为统一 constraints。

Roadmap 仍把 grid/Bayesian/CMA-ES 插件和 differentiable EPG 放在未来计划中。docs/ROADMAP.md:31-34

真正面向临床调参时，优化对象应至少支持：

```text
ObjectiveVector:
  maximize target-reference CNR
  maximize lesion conspicuity
  minimize scan time
  minimize SAR
  minimize motion sensitivity
  minimize B0/B1 sensitivity
  constrain resolution / coverage / distortion / PNS
```

并且必须输出：

- Pareto front。
- robustness map。
- active constraints。
- 参数敏感度。
- 推荐方案的适用域和失效域。
- 与基准 protocol 的差异。

---

## 7. 当前部署方式无法直接承载 GPU 商业执行器

现有正式架构写的是：

```text
ONE Python process
ONE Next.js application
```

并明确把 microkernel 解释为进程内边界，而非微服务。docs/ARCHITECTURE.md:127-136

这对早期产品是好事，避免过早引入 Kafka/Celery/Kubernetes。但它同时说明当前没有：

- job scheduler
- durable job state
- GPU discovery
- GPU isolation
- worker lifecycle
- cancellation
- progress streaming
- retry/idempotency
- artifact store
- multi-user quota
- GPU memory admission control
- execution sandbox
- worker health and attestation

因此不建议直接把当前 `/experiments/run` 改成“有 GPU 就跑 GPU”。建议保留它作为同步轻量路径，另外增加异步 execution contract：

```text
POST /jobs
GET  /jobs/{id}
POST /jobs/{id}/cancel
GET  /jobs/{id}/events
GET  /artifacts/{id}
```

`ExperimentGraph` 和 resolved `ExecutionPlan` 作为 job payload；browser、cloud CPU、local GPU 只是不同 execution target。

---

# 四、你提出的云端 License Server + 本地 GPU Worker 是否可行？

## 结论：**可行，而且与这个项目的商业化形态很匹配。**

但建议不要把它理解为简单的“API Key 换一个 7 天 JWT”，而应该设计成：

```text
             Cloud Control Plane
┌───────────────────────────────────────────┐
│ Identity / Organization / Subscription    │
│ Device Registration                       │
│ License & Entitlement Service             │
│ Lease Issuer                              │
│ Revocation / Audit / Usage                │
└──────────────────────┬────────────────────┘
                       │ register / renew
                       ▼
              Local MRQLab Runtime
┌───────────────────────────────────────────┐
│ Local Gateway / Agent                     │
│  ├─ Lease verifier                        │
│  ├─ Entitlement policy                    │
│  ├─ Device-key store                      │
│  ├─ Job API                               │
│  └─ Audit buffer                          │
│                                           │
│ Worker Manager                            │
│  ├─ CPU lightweight worker                │
│  ├─ GPU Bloch/EPG/PDG worker              │
│  └─ Export/validation worker              │
│                                           │
│ Artifact/cache store                      │
└──────────────────────┬────────────────────┘
                       │ localhost / Unix socket
                       ▼
                  Web Application
```

## 关键设计建议

### 1. 使用 Ed25519，不需要 RSA

对于离线验证 lease：

- 服务端持有 signing private key。
- 本地 runtime 只内置 public key。
- Lease 使用 Ed25519 签名。
- key rotation 通过 `kid` 支持多个可信公钥。

优点：

- key 和 signature 较小。
- 实现简单。
- 验签快。
- 不需要把任何长期共享秘密放入客户端。

### 2. 不要把 API Key 长期保存在浏览器

推荐流程：

1. 管理员在本地 agent 中发起 device registration。
2. 浏览器跳转 cloud device authorization flow，或输入一次性 registration code。
3. 本地 agent 生成 device key pair。
4. 云端绑定 organization、device public key 和 fingerprint。
5. 云端签发短期 lease。
6. 后续 renewal 使用 device private key 做 proof-of-possession。

也就是说：

> API key 只适合首次 bootstrap，不应成为长期设备凭据，更不应进入前端 LocalStorage。

### 3. Lease 中应包含 entitlement，而不只是 expiry

建议 payload：

```json
{
  "iss": "mrqlab-license",
  "aud": "mrqlab-local-runtime",
  "lease_id": "...",
  "organization_id": "...",
  "device_id": "...",
  "device_public_key_hash": "...",
  "fingerprint_hash": "...",
  "issued_at": "...",
  "not_before": "...",
  "expires_at": "...",
  "offline_grace_until": "...",
  "product": "mrqlab-pro",
  "features": [
    "gpu.bloch",
    "gpu.epg",
    "optimization.batch",
    "export.pulseq"
  ],
  "limits": {
    "max_gpus": 1,
    "max_concurrent_jobs": 2,
    "max_matrix": 512
  },
  "software": {
    "min_version": "1.0.0",
    "max_major": 1
  },
  "key_id": "license-2026-01"
}
```

### 4. 硬件指纹不能只取 MAC 地址

建议由多个稳定因子构成、经 canonicalization 后 hash：

- OS installation/device ID。
- machine-id。
- TPM-backed key/public key，如果可用。
- 主板/BIOS UUID。
- CPU identifier。
- GPU UUID。
- 系统盘 serial 的受控使用。

并设计容错策略：

- GPU 更换是否允许？
- OS 升级后是否触发重绑？
- 虚拟机 clone 如何处理？
- 容器部署时绑定 host 还是 container？
- 多 GPU 工作站如何授权？

最好把：

- **device key**
- **hardware fingerprint**
- **GPU inventory**

分开建模。Fingerprint 只是绑定信号，不应承担所有设备身份功能。

### 5. 必须考虑本地时钟回拨

单纯验证 `expires_at` 会受到系统时间回拨影响。可以组合：

- 保存最后一次可信 server time。
- 使用 monotonic clock 计算 lease elapsed time。
- 如果 wall clock 明显回退则进入 restricted/grace mode。
- 每次在线 renewal 更新 trusted time anchor。
- 高价值部署可利用 TPM sealed state。

不需要做��� DRM 绝对不可破解——本地软件最终都能被有权限的用户 patch。目标应该是：

- 阻止普通复制。
- 管理商业 entitlement。
- 支持离线临床网络。
- 保持良好用户体验。
- 让滥用成本高于购买成本。

### 6. Web App 不应自行判断授权

正确边界是：

```text
Web App → GET http://127.0.0.1:<port>/v1/capabilities
```

返回：

```json
{
  "runtime": "local",
  "license": {
    "state": "active",
    "expires_at": "...",
    "offline": true
  },
  "features": {
    "gpu.bloch": true,
    "export.pulseq": false
  },
  "workers": [
    {
      "id": "gpu0",
      "device": "NVIDIA ...",
      "status": "ready"
    }
  ]
}
```

真正的 enforcement 必须在本地后端：

```text
request
  → authentication
  → lease verification
  → feature entitlement
  → execution limits
  → job dispatch
```

前端“隐藏按钮”只能是 UX，不能是安全措施。

### 7. License boundary 应位于 execution gateway，不应污染 physics kernel

不要在 Bloch/EPG 算子中写：

```python
if not license.has_feature(...):
    ...
```

应该是：

```text
HTTP/RPC request
   ↓
EntitlementMiddleware
   ↓
ExecutionPlanner
   ↓
WorkerProvider
   ↓
Physics kernel
```

这样开源/light 版本仍可运行基础 engine，而商业 GPU engine、优化器、exporter 可以以独立 distribution/plugin 提供。现有项目已经有 physics engine plugin seam，这与商业高级 provider 很契合。docs/PHYSICS.md:62-82

### 8. 前端连接 localhost 时要特别注意安全

本地 agent 不能只因为请求来自 `localhost` 就信任它。需要防止任意网页调用本地服务：

- 严格 CORS origin allowlist。
- CSRF protection。
- 安装时生成 local pairing secret。
- WebSocket/SSE 也做 origin 与 token 验证。
- 只监听 loopback，默认不监听 `0.0.0.0`。
- 可选 Unix domain socket + desktop shell。
- 不允许浏览器提交任意文件路径。
- export 通过受控 download/artifact API。
- 禁止任意 plugin path、Python module、shell command 注入。

当前 API 只有有限的静态 CORS 配置，尚不是完整的本地 agent 安全模型。

---

# 五、商业化架构建议

## 1. 三个执行层，而不是前端/后端二分法

```text
Tier 0 — Browser Preview
  - 近似信号模型
  - 小矩阵
  - 低 isochromat 数
  - 参数即时反馈
  - 无 license 或基础账号

Tier 1 — Standard Compute
  - 当前 NumPy kernel
  - 云端 CPU 或本地 CPU
  - 可重复、带 provenance
  - clinical recipe evaluation

Tier 2 — High-Fidelity Local Compute
  - GPU Bloch/PDG/large batch
  - high-resolution field maps
  - optimization
  - standard export validation
  - lease-controlled
```

这里关键不是三个完全独立的 simulator，而是：

> **三个 execution profile，共享同一个 ExperimentGraph、resolved plan、Observation schema 和 provenance。**

## 2. 增加明确的 Runtime Provider 接口

建议未来合同类似：

```python
class ExecutionProvider(Protocol):
    descriptor: ProviderDescriptor

    def validate(self, plan: ResolvedExecutionPlan) -> ValidationReport: ...
    def estimate(self, plan: ResolvedExecutionPlan) -> ResourceEstimate: ...
    def submit(self, plan: ResolvedExecutionPlan) -> JobHandle: ...
    def cancel(self, job_id: str) -> None: ...
    def capabilities(self) -> CapabilitySet: ...
```

Provider 可以是：

- `in_process_numpy`
- `browser_wasm`
- `local_cuda`
- `local_torch`
- `cloud_cpu`
- `cloud_gpu`
- `external_pdg`
- `pulseq_export`

当前 `SimulationEngine` 仍然保留在 provider 内部。不要让 transport/runtime orchestration 侵入数值 engine。

## 3. 区分 Simulation Capability 与 Commercial Entitlement

例如：

```text
Capability:
  shaped_rf
  spatial_b0
  multi_pool
  gpu_batch
  pulseq_export

Entitlement:
  feature.gpu_advanced
  feature.optimization
  feature.export
```

Capability 回答：

> “这个 provider 能不能算？”

Entitlement 回答：

> “这个用户/设备是否有权使用？”

这两个概念绝不能混合。

---

# 六、从现在到目标产品的建议路线

## Phase 0：先统一产品合同

优先级最高，不是立刻写 License Server。

需要先明确：

- 产品不再只是 teaching simulator。
- 但仍不是 scanner controller。
- “临床应用”具体是 research-use-only protocol design，还是 clinical decision support。
- sequence export 是否只是文件生成，还是承诺 scanner executability。
- 哪些 advanced capability 必须本地运行。
- 开源核心与商业模块如何分界。

建议首个商业定位仍是：

> **Research-use-only MRI contrast and protocol engineering platform**

不要第一步就宣称 diagnostic/clinical-use product。

---

## Phase 1：收紧现有合同

建议优先做：

1. `ExperimentGraph v2`
   - ClinicalQuestion
   - AcquisitionIntent
   - ParameterDefinition
   - ScannerProfileRef
   - ReproducibilityPolicy

2. `ResolvedExecutionPlan`
   - 所有默认值解析完成。
   - 所有单位明确。
   - 所有 approximations 明确。
   - parameter provenance 明确。
   - immutable fingerprint。

3. `ParameterState`
   - authored/derived/default/unsupported/stale。

4. `Observation provenance`
   - software/version/commit。
   - engine/provider。
   - numerical precision。
   - input hash。
   - scanner profile version。
   - tissue database version。

5. 文档一致性修复  
   当前 `docs/ARCHITECTURE.md` 仍把 ssEPG 和 PDG 标成不可用，但 `docs/PHYSICS.md` 已把二者标为可用，这是明显的架构文档漂移。docs/ARCHITECTURE.md:81-89docs/PHYSICS.md:25-38

---

## Phase 2：做真正的 clinical problem layer

建立：

- ClinicalQuestion。
- TissuePriorSet。
- Target/Reference/Confounder。
- ContrastMetric。
- RobustnessScenario。
- AcquisitionConstraint。
- ClinicalProtocolRecipe。
- ScannerProfile。

先聚焦少数临床 vertical，不要铺满所有 MRI：

### 推荐的首批 vertical

1. Brain lesion T2/FLAIR/TSE。
2. Knee cartilage/meniscus PD/T2 TSE。
3. Liver fat/water multi-echo GRE。
4. TOF MRA inflow optimization。
5. CEST Z-spectrum 研究模式。

每个 vertical 都需要：

- 文献/phantom/reference implementation。
- 参数范围。
- expected trend。
- golden dataset。
- scanner comparison。
- “不适用”边界。

---

## Phase 3：完善 sequence compiler 与标准导出

顺序建议：

1. Shaped RF waveform contract。
2. Arbitrary gradient waveform contract。
3. ADC dwell/sample count contract。
4. raster quantization。
5. dead time/ringdown。
6. scanner constraint validation。
7. Pulseq importer/exporter。
8. round-trip tests。
9. independent interpreter comparison。
10. vendor research adapter，按合作条件逐个实现。

特别注意：

> Pulseq export 成功不等于临床可运行，更不等于临床安全。

输出状态应分为：

```text
SIMULATION_VALID
IR_VALID
EXPORTABLE
TARGET_PROFILE_VALID
HARDWARE_REVIEW_REQUIRED
```

---

## Phase 4：本地 execution runtime

在这一阶段再加入：

- local agent。
- GPU discovery。
- job queue。
- progress/cancel。
- artifact cache。
- provider plugin。
- local capability API。
- lease verifier。
- audit log。

仍然可以先保持单机，不必一开始用 Kubernetes。

推荐本地组件：

```text
mrqlab-agent
mrqlab-worker-cpu
mrqlab-worker-gpu
mrqlab-exporter
local SQLite metadata
local content-addressed artifact store
```

---

## Phase 5：License Control Plane

实现：

- organization。
- user。
- subscription。
- device registration。
- entitlement。
- lease issuance。
- key rotation。
- revocation。
- offline grace。
- audit。
- admin portal。

**License service 本身不要处理患者数据、实验 payload 或图像。**  
它只需要看到：

- organization/device。
- software version。
- requested entitlement。
- coarse usage counters。

这样既降低隐私风险，也更适合医院隔离网络。

---

## Phase 6：验证与临床工程

如果要从 RUO 走向临床使用，需要建立独立工作流：

- physics verification。
- unit and convention verification。
- numerical convergence tests。
- cross-engine comparison。
- digital phantom validation。
- physical phantom validation。
- scanner comparison。
- regression baselines。
- clinical expert review。
- risk management。
- change control。
- traceability matrix。
- cybersecurity lifecycle。
- model limitation labeling。

现有 provenance 与 fail-closed 思路是很好的起点，但尚不足以替代验证体系。

---

# 七、我认为现在最不应该做的事情

1. **不要立刻重构整个 monorepo。**  
   当前模块边界总体正确。

2. **不要把 License 判断写入 physics engine。**

3. **不要直接把 FastAPI `/experiments/run` 改成 GPU RPC。**

4. **不要把当前 SequenceIR 直接宣称为 scanner-executable IR。**

5. **不要因为有 clinical recipe 就宣称临床可用。**

6. **不要同时推进 MRS、DCE、CEST imaging、full PDG、GPU、Pulseq 和 licensing。**  
   会把验证面扩大到不可控制。

7. **不要删除当前安全边界声明，直到验证、出口限制和法规定位真正建立。**

8. **不要让前端拥有任何 lease private key 或长期 API key。**

---

# 八、建议的最近三个里程碑

## Milestone A：Clinical Contract

目标：

- 选择 2–3 个临床 vertical。
- 建立 `ClinicalQuestion → ObjectiveVector → Constraints`。
- 每个 UI 参数都明确是否真正 wired。
- `ResolvedExecutionPlan` 成为不可变、可 hash 的执行合同。
- 清理架构文档漂移。

## Milestone B：Executable Sequence

目标：

- shaped RF。
- arbitrary gradient。
- ADC sampling contract。
- scanner raster/dead-time constraints。
- Pulseq export alpha。
- round-trip 和 reference tests。
- 明确 export validation state。

## Milestone C：Licensed Local Compute

目标：

- local agent + provider API。
- CPU/GPU job lifecycle。
- capability/entitlement 分离。
- Ed25519 lease。
- device registration。
- offline grace。
- localhost security。
- Web capability discovery。

这三个完成后，MRQLab 才真正形成你描述的：

```text
浏览器轻量交互
    +
本地/后端高保真计算
    +
临床目标驱动调参
    +
标准化序列导出
    +
可商业授权的高级能力
```

---

# 九、最终判断

**你提出的商业化方向是成立的，而且现有架构不需要推翻。**

当前真正有价值的，不是某个 Bloch 或 EPG 函数，而是已经逐渐形成的：

- experiment-centered domain model。
- IR 分层。
- capability negotiation。
- fail-closed behavior。
- typed observations。
- provenance。
- Web 与后端共享实验合同。
- 可插拔 physics provider 边界。

现阶段最大的风险也不是“物理代码太少”，而是：

> **产品叙事、临床问题模型、可执行序列模型、计算运行时和商业控制面尚未被明确拆开。**

我的建议是继续把现有核心视为：

> **MR experiment compiler + forward-model kernel**

在它上方增加 clinical design layer，在它下方增加 execution provider 和 export layer，在侧面增加 license control plane。这样既能保留开放教学入口，又能把高保真 GPU、批量优化和标准导出做成真正有商业价值的本地高级能力。

本轮严格按你的要求只做审计，没有修改仓库，因此没有创建提交或 PR；当前工作树保持干净。

## 审计与检查

* ✅ `find .. -name AGENTS.md -print`
* ✅ `find . -maxdepth 3 -type d ...`
* ✅ `find packages services -type f -name '*.py' | sort`
* ✅ `rg -n '^(class|def|async def) ' packages services`
* ✅ `rg -n -i 'license|lease|fingerprint|ed25519|rsa|worker|gpu|pulseq|ismrmrd|export|auth' ...`
* ✅ `git status --short --branch`
* ✅ `npm run typecheck`
* ✅ `npm test -- --run` — 11 个测试文件、80 个前端测试全部通过。
* ⚠️ `python -m pytest -q` — 当前系统 Python 环境缺少 `pydantic`、`numpy`、`fastapi` 等项目依赖，在测试收集阶段停止。
* ⚠️ `.venv/bin/python -m pytest -q` — 仓库现有 `.venv` 未安装 `pytest`，因此未能完成 Python 测试执行。