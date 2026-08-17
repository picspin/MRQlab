# MRQLab Architecture Clarification v2: Clinical MRI Experiment Workbench

**Date:** 2026-08-17  
**Status:** Canonical Clarification & Architecture North Star (v0.2+)  
**Role:** Canonical Specification for Clinical Execution Contract, Physical Fidelity Ladder, and Workbench Evolution  

---

## 总体评价与定位

MRQLab 不只是一个“EPG 教学模拟器”，而是正在形成一个更有潜力的：

> **面向临床任务的 MRI 实验设计、物理仿真、采集解释、重建与定量分析工作台（MRI Experiment Workbench）。**

系统的核心价值在于打破传统 “RF 脉冲 → Bloch/EPG → 图像” 的黑盒逻辑，建立如下完整的端到端解耦链路：

$$
\text{Clinical Intent}
\rightarrow
\text{Experiment}
\rightarrow
\text{Sequence}
\rightarrow
\text{Physics}
\rightarrow
\text{Acquisition}
\rightarrow
\text{Reconstruction}
\rightarrow
\text{Observation}
$$

该链路为未来平滑扩展到以下高级临床与物理领域奠定了基础架构：
- 黑血和血流增强 / 血管壁成像
- $T_1 / T_2 / T_2^*$ 定量 mapping
- CEST / MT / 多池化学交换
- ASL、DCE 与动态灌注
- DWI / DTI 与纤维各向异性
- 杂核 MRI (X-nuclei) 与 MRS
- Floquet 周期稳态序列
- Hybrid Bloch–EPG、PDG、EPG-X 等新表示

---

## 一、目前架构最成功的地方

### 1. Engine 不是产品分类，而是计算表示（Representation）
- **Bloch**：spin-domain representation（空间编码、非均匀场、真实旋转）
- **EPG**：configuration-state representation（回波链、相干态演化）
- **Spectral**：frequency/species representation（多化学位移成分）
- **Hybrid / PDG / EPG-X**：多表示协同与未来演进

用户在前端表达的是实验意图（如“理解 TSE stimulated echo”、“模拟 slice-selective refocusing pulse 影响”、“比较黑血与血管壁信号”），系统依据实验图与 capability/validity 自动裁决最合适的 representation。

### 2. ResultGraph 比单纯返回数组更有长期价值
实验返回的是具有完整溯源（Provenance）与派生（Derivation）关系的有向无环图谱：
```text
RF waveform
    ↓
magnetization evolution
    ↓
ADC samples
    ↓
k-space trajectory
    ↓
reconstructed image
    ↓
contrast metric
    ↓
parameter fit
```
当参数变动时，系统能够精确解释哪些路径改变、哪些采样时刻偏移、对比度如何变化。

### 3. Acquisition 被独立出来作为一等公民
区分了磁化状态与接收线圈信号、NCO/mixer、I/Q、ADC window、sampling timing、trajectory、k-space 与 reconstruction，为非笛卡尔采样、多通道线圈、流动与心动伪影分析提供了坚实基础。

---

## 二、关键警惕点与规范化解耦

### 1. “临床真实”的正交四层建模
严禁将所有现实因素粗暴塞入 `disturbances`：
- **`TissueModel`（组织与生物物理）**：$T_1, T_2, T_2^*, \rho$，exchange rate, pool fraction, diffusion tensor, bulk flow velocity, nuclear species。
- **`PhysiologyModel`（生理状态动态）**：cardiac phase, RR interval, respiratory phase, flow waveform, contrast agent concentration curve, motion field。
- **`ScannerModel`（硬件参数与场图）**：$B_0 / B_1^+$ map, gradient limits, slew rate, ADC bandwidth, coil sensitivity, noise covariance, SAR, PNS, eddy currents。
- **`DisturbanceModel` / `DisturbanceStack`**：**仅表示偏离理想模型的扰动因素**（如非理想 slice profile、$B_0/B_1$ 空间不均匀性、伴随梯度场等）。

### 2. 显式建立“模型适用范围”（Engine Validity Matrix）
每个物理引擎声明其多维度的保真度与适用边界：
```yaml
validity:
  spatial_encoding: none | limited | full
  shaped_rf: unsupported | approximate | exact
  off_resonance: unsupported | supported
  flow: unsupported | approximate | exact
  exchange: unsupported | multi_pool
  diffusion: unsupported | isotropic | anisotropic
  differentiable: true | false
  steady_state: unsupported | supported
```

### 3. `ExecutionPlan` 成为核心领域对象
执行主干形式化为：
```text
ExperimentGraph → Validation → Capability/Validity Resolution → ExecutionPlan → Compiled Sequence → Physics Blocks → Acquisition → Observation Assembly
```
`ExecutionPlan` 包含 `fingerprint`, `selected_engine`, `representation`, `validity`, `requested_observations`, `approximations`, `differentiability`, `cost_estimate`, `stale_dependencies`，服务于执行调度、增量编译、A/B 比较与优化器。

---

## 三、Pulse 架构：Physics IR 的一等 Block

Pulse 定义与响应编译管道：
```text
PulseDefinition → PulseCompiler → PulsePropagator / PulseResponse → Sequence Compiler
```
支持不同层级的传播子（Propagator）：
- **硬脉冲（Hard Pulse）**：$M^+ = R(\alpha, \phi) M^-$
- **小翻转角近似（Small-tip approximation）**：快速估算频响与 slice profile
- **空间 Bloch 传播子**：$M(z, t_1) = P_{\text{RF}}(z) M(z, t_0) + b(z)$
- **EPG/PDG 可消费算子**：configuration transition / Fourier coupling

---

## 四、Representation Ladder（表示阶梯）

- **Level 0: Analytical**（小翻转角、解析稳态）
- **Level 1: Hard-pulse Bloch**（单/少量 isochromats，极速教学预览）
- **Level 2: EPG**（回波链、受激光子、相干路径）
- **Level 3: Spatial Bloch / Slice profile**（shaped RF, off-resonance, 切片选择, B1 变化）
- **Level 4: Hybrid Bloch–EPG / PDG**（空间剖面 + 配置态，任意时序与空间编码）
- **Level 5: Extended Physics**（Bloch–McConnell 交换, Bloch–Torrey 扩散, 流动, 多核, Floquet 稳态）

---

## 五、Clinical Recipe 与目标函数

Clinical Recipe 从简单预设升级为严谨的任务规范（Task Specification）：
```yaml
clinical:
  anatomy: cardiac / brain
  target: vessel_wall
  task: wall_lumen_separation
tissues:
  - vessel_wall
  - blood
  - myocardium
sequence:
  family: TSE
  template: dark_blood_tse
objective:
  primary:
    type: cnr
    between: [vessel_wall, blood]
  secondary:
    - maximize: vessel_wall_signal
    - minimize: blood_signal
    - minimize: scan_time
    - minimize: sar
constraints:
  max_sar: 2.0 W/kg
  max_gradient: 45 mT/m
  max_scan_time: 180 s
```

---

## 六、保真度模式（Fidelity Modes）

- **教学模式（Teaching）**：理想 RF、单池组织、无场不均匀、无流动、极速概念理解。
- **研究模式（Research）**：slice profile, off-resonance, B1 variation, exchange, diffusion, flow, multi-pool。
- **临床鲁棒模式（Clinical Robustness）**：组织参数分布、心率波动、流速波形、场图扰动、噪声协方差、SAR/PNS 约束与门控失败评估。

---

## 七、Workbench 拓展：问题定位工具

六大联动透镜（Linked Lenses）：
1. **System**：扫描器实际执行了什么？
2. **Physics**：自旋/池/相干态发生了什么？
3. **Acquisition**：接收机到底测到了什么？
4. **Reconstruction**：原始数据如何变成图像？
5. **Compare**：两个序列或两种组织为什么不同？（对比 A/B）
6. **Optimize**：哪些参数能改善目标？（敏感性分析、Pareto 前沿、梯度反向传播）

统一定义 **`WorkbenchAddress`** 表达多维联动锚点（物理态、相干路径、ADC sample、k 空间坐标、空间 voxel、组织分量）。

---

## 八、路线图与演进优先级

- **P0: 稳定实验执行契约（已收敛/正在进行）**
  - `ExecutionPlan` 权威化、immutable resolution、engine selection 真实接入、requested observation 驱动计算、execution provenance、stale 状态依赖图。
- **P1: 完成完整 Vertical Slice**
  - **Clinical TSE / Dark-blood TSE** 完整贯通（Recipe → Graph → Plan → Pulse Compiler → EPG/Bloch → Echo Train → ADC/k-space → Recon → Tissue Contrast）。
- **P2: 引入 PulseResponse / Propagator**
  - Hard / Sinc / Slice Profile / RF 频谱 / B0/B1 变化。
- **P3: 引入 Compare 与 Optimize 模块**
  - Parameter sweep, tissue signal curves, contrast heatmap, 差分敏感性与优化器接口。
- **P4: 高级物理扩展**
  - Hybrid Bloch–EPG/PDG, Bloch–McConnell/EPG-X, Flow/Diffusion, Floquet 周期稳态, 多核。
