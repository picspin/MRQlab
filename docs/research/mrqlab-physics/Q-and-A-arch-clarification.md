GPT Answer：**MRQLab 不应该围绕“sequence 类型”组织，而应该围绕“MR experiment + physics operator + objective”组织。**

换句话说，SE/TSE/GRE、Dixon、flow、MRF、CEST、MRS 都只是某个实验的不同组合。真正长期稳定的是：

\\text{Experiment} = \\text{Sequence} + \\text{Spin/Tissue Model} + \\text{Scanner Model} + \\text{Physics Engine} + \\text{Objective} + \\text{Readout}

我会据此采用 **microkernel + capability plugins + workspace frontend**。这能同时满足教学、正向仿真、逆向优化和未来复杂物理模型。

先纠正一个很关键的概念：**EPG 本身不是“逆向计算算法”**。EPG/EPG-X/ssEPG 是高效的 forward model；所谓“给定 dark-blood contrast，反推 TI/FA/TE/TR”，实际上是：

\\theta^\\\*= \\arg\\min\_{\\theta} \\mathcal L \\left( S\_{\\mathrm{EPG}}(\\theta),S\_{\\mathrm{target}} \\right)

其中 \\theta=(TR,TE,TI,\\alpha\_1,\\alpha\_2,\\ldots)。经典 EPG 可以套 grid search、Bayesian optimization、CMA-ES；可微 EPG 才可以直接使用 \\nabla\_\\theta \\mathcal L 做 gradient-based optimization。Stanford Hargreaves 的 EPG materials 很清楚地把 EPG定位成 RF rotation、relaxation、dephasing/coherence-state propagation 的高效表示。

这个区别值得直接写进 MRQLab architecture。

* * *

**1\. 我会把 MRQLab 的中心从**
=======================

**`SimulationEngine`**
=========================================================================

**再提升一级**
==============================================================================================================================================================

之前我们讨论的是：

```text
Sequence
    ↓
SimulationEngine
    ↓
Result
```

现在看来还不够。

我会改成：

```text
                    MRQLab Experiment Kernel

                            │
      ┌─────────────────────┼──────────────────────┐
      │                     │                      │
      ↓                     ↓                      ↓
 Sequence Model        Sample Model           Scanner Model
      │                     │                      │
      └──────────────┬──────┴─────────────┬────────┘
                     │                    │
                     ↓                    ↓
              Physics Compiler      Constraint Engine
                     │
                     ↓
               Physics Engine
                     │
                     ↓
                Signal Model
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
       k-space     FID       State graph
          │          │          │
          ↓          ↓          ↓
       image      spectrum     EPG/PDG
                     │
                     ↓
                  Objective
                     │
              ┌──────┴──────┐
              ↓             ↓
          Forward       Optimizer
          simulate       inverse
```

**Kernel 不实现 Bloch、EPG、CEST 或 MRS。**

Kernel 只负责：

-   experiment lifecycle
-   typed state
-   operator scheduling
-   unit system
-   reproducibility
-   engine discovery
-   constraints
-   result graph
-   provenance

这就是 microkernel 真正应该承担的职责。

* * *

**2\. Sequence 不应该再只是一个时间线，而应该是**
=================================

**`ExperimentGraph`**
============================================================================================

这是我现在最建议你做的改变。

SE 可以写成：

```text
Excitation
   ↓
FreeEvolution
   ↓
Refocusing
   ↓
Readout
```

TSE：

```text
Excitation
   ↓
[ Refocus → Evolve → Echo ] × ETL
```

DCE：

```text
Contrast Injection
       ↓
 PK Model
       ↓
T1(t)
       ↓
Sequence
       ↓
Signal(t)
```

ASL：

```text
Label
 ↓
Transit
 ↓
Exchange
 ↓
PLD
 ↓
Readout
```

CEST：

```text
Saturation train
       ↓
Bloch-McConnell exchange
       ↓
Readout
       ↓
Z-spectrum
```

所以内部真正的数据结构最好是：

```text
ExperimentGraph

nodes:
    RF
    Gradient
    Delay
    ADC
    Preparation
    Exchange
    Flow
    Diffusion
    Injection
    Readout

edges:
    temporal
    dependency
    state-transition
```

而不是硬编码：

```python
SpinEchoSequence
TurboSpinEchoSequence
CESTSequence
ASLSequence
```

后者迟早 class explosion。

* * *

**3\. Physics engine 应该进一步拆成 Operator System**
==============================================

这也是 EPG 思想真正适合 microkernel 的地方。

经典 EPG 本质上就是几个算子：

\\mathcal R\_{\\alpha,\\phi}

RF transition；

\\mathcal E\_{\\Delta t}

relaxation；

\\mathcal S\_{\\Delta k}

gradient-induced state shift。

因此我不会让：

```python
EPGEngine.simulate()
```

变成一个黑盒。

而会设计：

```text
PhysicsOperator

apply(state, event, context) → state
```

然后：

```text
RFOperator
RelaxationOperator
GradientOperator
ExchangeOperator
DiffusionOperator
OffResonanceOperator
FlowOperator
ChemicalShiftOperator
```

这样 EPG-X 就自然变成：

```text
EPG state
+
ExchangeOperator
```

而不是另起炉灶。

EPG-X 的确把 EPG 扩展到了 coupled exchanging systems，并提供 Bloch–McConnell 和 binary spin-bath/MT 两类交换模型。

* * *

**4\. 我建议 physics 不要形成一棵树，而形成一张“能力矩阵”**
=======================================

比如 Bloch 和 EPG 不是“初级/高级”关系。

它们只是不同表示：

```text
Spin domain                Configuration domain
     │                              │
   Bloch                         EPG
     │                              │
     └──────────── dual ────────────┘
```

而最近一些工作实际上越来越明确地把 Bloch 与 phase-graph 看成可互换、可混合的描述。

所以未来：

```text
Bloch
EPG
PDG
ssEPG
Bloch-McConnell
Density Matrix
Floquet
```

不应该继承：

```text
BaseSimulator
   ↓
AdvancedSimulator
```

而应该声明 capability：

```text
supports:
    shaped_rf
    exchange
    diffusion
    flow
    off_resonance
    spatial_encoding
    steady_state
    differentiable
    multi_pool
    multi_species
```

然后 Kernel 根据实验自动选择 engine。

例如：

```text
TSE + hard RF
→ EPG

TSE + shaped slice RF
→ ssEPG / hybrid Bloch-EPG

CEST
→ Bloch-McConnell

MRF + gradient crushers + slice profile
→ ssEPG

2D GRE + arbitrary field map
→ Bloch / PDG

periodic heteronuclear steady state
→ density matrix / Floquet
```

这比用户自己选 simulator 更符合教学体验。

* * *

**5\. ssEPG 应该进入 roadmap，但不要作为普通 EPG 的 feature flag**
=====================================================

你的理解基本正确。

传统 EPG 对 RF 的处理本质上假设每个 configuration order 内局部 mixing，而 shaped slice-selective RF 同时遇到 slice gradient 后，RF propagator 在空间方向发生变化。

Ostenson 等提出的 ssEPG 就是专门处理 gradient-crushed transient-state sequence 中这种 slice-profile effect，并用于 MRF；论文也指出 \\Delta B\_0 与 slice profile/crusher 的相互作用会带来定量偏差。

甚至 2026 年又出现了很值得 MRQLab 关注的新方向：**slice-profile-enabled PDG**。它把一个序列切成 RF-sensitive Bloch spans 和 phase-graph spans，对 RF 部分计算空间依赖 propagator，再把其 Fourier coefficient 编译进 PDG graph，形成跨 k\_z order 的 sparse coupling。

这跟 MRQLab 的哲学几乎完全一致：

```text
不坚持一个 simulator 吃掉整个序列

而是：

segment sequence
      ↓
choose best representation
      ↓
compile operators
      ↓
propagate state
```

所以我会直接设计：

**Physics Compiler**
====================

例如：

```text
RF + Gslice
→ BlochSpan

crusher + relaxation
→ EPGSpan

encoding
→ PDGSpan
```

这比单纯做：

```text
BlochEngine
EPGEngine
ssEPGEngine
```

更有未来。

* * *

**6\. 甚至可以引入一个 MRQLab Intermediate Representation**
===================================================

我建议分成三层 IR。

```text
Experiment IR
     ↓
Sequence IR
     ↓
Physics IR
```

**Experiment IR** 是用户意义：

```text
T2-weighted dark blood
3T
carotid
blood suppression
wall signal preservation
```

**Sequence IR** 是 scanner 意义：

```text
IR preparation
90 RF
TSE ETL 16
refocusing train
TEeff 80 ms
Cartesian readout
```

**Physics IR** 则是计算意义：

```text
RF_ROTATION(...)
FREE_EVOLUTION(...)
EXCHANGE(...)
EPG_SHIFT(...)
DIFFUSION(...)
READOUT(...)
```

于是：

```text
Experiment
      ↓
Sequence Compiler
      ↓
Sequence IR
      ↓
Physics Compiler
      ↓
Physics IR
      ↓
Bloch / EPG / PDG / BM / Floquet
```

这会成为 MRQLab 最强的 architecture boundary。

* * *

**7\. 这也为 inverse sequence design 铺路**
======================================

用户不一定要说：

FA=120°, TE=85 ms。

高级模式可以直接说：

```text
Objective

blood     < 5%
muscle    > 45%
wall      > 60%

scan time < 4 min
SAR       < limit
```

于是：

```text
ObjectiveSpec
```

可能是：

J(\\theta) = w\_1 S\_{\\rm blood} - w\_2 S\_{\\rm wall} + w\_3 T\_{\\rm scan} + \\lambda C\_{\\rm SAR}

然后 optimizer plugin：

```text
GridSearch
RandomSearch
BayesianOptimizer
CMAES
GradientOptimizer
```

而 physics model 是 interchangeable：

```text
EPG
        ↓
CMA-ES

Differentiable EPG
        ↓
Adam / LBFGS
```

所以 **Optimizer 也应该是一等公民 plugin**，不能藏在 AI Lab 里。

AI 应该帮助定义 objective，而不是替代 optimizer。

* * *

**8\. DPG/PDG 对 MRQLab 特别重要**
=============================

因为它正好处于：

```text
EPG            Bloch
 fast           spatially explicit
 abstract       expensive
   │               │
   └───── PDG ─────┘
```

PDG 的价值不是只模拟 F0 echo。

而是把：

```text
coherence pathway
+
position
+
k-space
+
image formation
```

连接起来。

所以你规划的四维 UI：

sequence → rotating frame → EPG/PDG → MRI image

我会稍微调整成：

```text
SYSTEM
   Sequence timeline

PHYSICS
   Spin / rotating-frame view

STATE
   EPG / PDG / exchange-state graph

OBSERVATION
   signal / k-space / image / spectrum
```

这样连 MRS 都能放进去。

因为 MRS 的 Observation：

```text
FID → spectrum
```

并不需要 image。

* * *

**9\. 关于 Floquet：我会用，但不会把它作为“MRS engine 本身”**
=============================================

这一点值得稍微收紧。

Floquet theory 非常适合：

-   periodic Hamiltonians
-   repeated RF modules
-   steady-state dynamics
-   frequency-domain reasoning
-   effective Hamiltonian
-   long-term periodic response

它在 NMR 里已有成熟理论体系。

甚至已有工作明确讨论利用连续 Floquet 表示做 pulse-sequence optimization 和从 desired effective Hamiltonian 反推 RF irradiation。

但普通 MRS 更一般的基础应该是：

```text
Hamiltonian
+
density matrix
+
Liouville-von Neumann propagation
```

例如：

\\dot{\\rho} = -i\[\\mathcal H,\\rho\] -\\mathcal R(\\rho-\\rho\_{eq})

然后 Floquet 是：

```text
PeriodicSequenceAccelerator
```

或者：

```text
SteadyStateSolver
```

而不是：

```text
MRSEngine = Floquet
```

这样以后：

```text
PRESS
STEAM
semi-LASER
J-coupled systems
x-nuclei
31P
13C
23Na
```

都会更自然。

* * *

**10\. 因此我会把 Physics Microkernel 设计成这样**
========================================

```text
                         Experiment Kernel
                                │
                       Physics Compiler
                                │
                 ┌──────────────┴──────────────┐
                 ↓                             ↓
          State Representation             Operators
                 │                             │
   ┌─────────────┼─────────────┐        ┌──────┼──────────┐
   ↓             ↓             ↓        ↓      ↓          ↓
 Bloch          EPG          Density    RF   Relax     Exchange
 State          State        Matrix          │
   │             │             │             ├ Diffusion
   │             ├ PDG         │             ├ Gradient
   │             ├ ssEPG       │             ├ Flow
   │             └ EPG-X       │             └ ChemicalShift
   │                           │
   │                       Floquet
   │                       Accelerator
   │
   └──────────────────────────────────────────────
                                │
                                ↓
                         Observation Model
```

注意这里：

**Bloch/EPG/Density Matrix 是 representation。**

**RF/relaxation/exchange/diffusion 是 operator。**

这个区分非常重要。

* * *

**11\. Frontend 也不要做成传统 SPA**
=============================

我会把前端理解为：

**Workspace shell + microfrontends**
====================================

Kernel：

```text
MRQLab Shell

Router
Workspace manager
Experiment state
Undo/redo
Persistence
Plugin registry
Command palette
```

然后：

```text
workspaces/

dashboard/
editor/
signal-lab/
contrast-lab/
optimization-lab/
ai-lab/
```

每一个 workspace 都只消费统一 Experiment State。

这使：

```text
Dashboard → Editor
```

不是打开一个新的 simulator。

而是：

**换一个观察同一个实验的工作空间。**

* * *

**12\. Dashboard 不应该只是项目列表**
============================

我会把它设计成：

**Explore / Build / Resume**
----------------------------

其中 Explore 是临床问题入口，而不是 sequence 名称入口。

例如卡片不是：

```text
GRE
SE
TSE
```

而是：

```text
T1 Contrast

Why does white matter become bright?
→ Explore
```

```text
Dark Blood

Suppress flowing blood
while preserving vessel wall
→ Explore
```

```text
Dixon

Separate water and fat
→ Explore
```

```text
T2 Mapping

Estimate transverse relaxation
→ Explore
```

下面才显示：

```text
Uses:
IR / TSE / GRE / multi-echo...
```

这会让 MRQLab 与其他 MRI simulator 拉开非常大的距离。

**临床目标先于序列。**

* * *

**13\. Editor 应该是整个产品的“驾驶舱”**
=============================

你提出的拟物化非常适合这里。

但我不会做成 full skeuomorphism。

我建议：

**Instrumental skeuomorphism**
==============================

也就是：

-   rotary knob 真有连续参数意义；
-   toggle 像真实仪器；
-   meter 真显示 SAR / duty cycle；
-   oscilloscope-like timeline 真显示 waveform；
-   Bloch globe 真是状态观察器。

而不是为了装饰而：

```text
假金属边框
假螺丝
假皮革
```

MRQLab 应该更像：

精密 MRI console × high-end audio synthesizer × scientific workstation。

* * *

**14\. Golden Ratio 可以用，但不要机械套 1.618**
======================================

比如主 editor：

```text
┌─────────────────────────────────────────────────────┐
│ Header / Experiment context                         │
├────────────┬──────────────────────────────┬─────────┤
│            │                              │         │
│ Navigator  │        Main Canvas           │Inspector│
│            │                              │         │
│   19%      │           62%                │   19%   │
│            │                              │         │
└────────────┴──────────────────────────────┴─────────┘
```

Main Canvas 内部：

```text
Timeline
≈ 38%

Visualization
≈ 62%
```

这是比机械的：

```text
61.8 / 38.2 everywhere
```

更成熟的做法。

黄金比例只作为视觉 hierarchy 的设计 token。

* * *

**15\. Editor 中四层不应该永远同时占四块屏幕**
===============================

否则信息密度过高。

我会提供一个：

**Linked Lens System**
======================

正常：

```text
┌─────────────────────────────┐
│        Sequence             │
│                             │
├──────────────┬──────────────┤
│ Physics      │ Observation  │
│              │              │
└──────────────┴──────────────┘
```

点击：

```text
EPG lens
```

变成：

```text
┌─────────────────────────────┐
│ Sequence                    │
├─────────────────────────────┤
│                             │
│       EPG STATE SPACE       │
│                             │
├─────────────────────────────┤
│ signal                     │
└─────────────────────────────┘
```

点一个 RF pulse：

```text
Sequence
 RF #17
   │
   ├→ Bloch rotation
   │
   ├→ EPG transition
   │
   └→ signal contribution
```

所有 view 通过统一的：

```text
cursorTime
selectedEvent
selectedState
selectedVoxel
selectedEcho
```

联动。

这是整个 UI 最值得投入工程的地方之一。

* * *

**16\. Signal Evolution Lab 会是你的 killer feature**
=================================================

进入：

```text
TSE experiment
```

后用户可以切换：

```text
Signal

Mxy(t)
Mz(t)

EPG

F0
F1
F2
...
Z0
Z1

Echo train

echo #1
echo #2
...

Tissue comparison

blood
muscle
fat
lesion
```

然后拖：

```text
refocusing FA

180°
 ↓
150°
 ↓
120°
```

EPG states 实时重排。

Echo envelope 改变。

Image contrast 改变。

SAR meter 下降。

这就是：

**parameter → physics → signal → contrast**

完整反馈链。

而不是传统：

```text
改参数 → Run → 看图片
```

* * *

**17\. Contrast Lab 则反过来**
==========================

用户选择：

```text
Target

Blood
████ 0.04

Vessel wall
██████████ 0.82

Fat
███ 0.22
```

点击：

```text
Optimize
```

显示：

```text
           objective landscape

        TE
         ↑

        ╭───────────╮
     ╭──╯ optimum ● ╰──╮
─────╯──────────────────╰──→ TI
```

旁边：

```text
Candidate A

TI     620 ms
TEeff   72 ms
TR    2100 ms
FA train
160 → 120°
```

最重要的是：

### **不要只给最优答案。**

应该展示：

```text
why this solution?
```

然后告诉学习者：

```text
TI moved here because blood Mz crosses zero.

Refocusing FA decreased because...

TEeffective moved because vessel-wall T2...
```

这样 optimization 本身也是教学。

* * *

**18\. 我会让 Optimization 产生 Pareto Frontier**
============================================

因为 MRI 几乎永远不是单目标。

例如：

\\max C\_{\\mathrm{lesion}}

同时：

\\min SAR

\\min T\_{\\mathrm{scan}}

\\max SNR

最终：

```text
contrast
  ↑
  │             ●
  │        ●
  │     ●
  │   ●
  │ ●
  └────────────────→ scan time
```

用户选择不同 Pareto solution。

这比“AI 给你最佳参数”科学得多。

* * *

**19\. Reality 不应该是一个 slider，而应该升级为 Disturbance Stack**
=======================================================

之前我建议一个 Reality Slider。

现在我认为你的 MRQLab 应该进一步发展成：

```text
Ideal

+ thermal noise
+ B0 map
+ B1+ map
+ gradient delay
+ eddy currents
+ gradient nonlinearity
+ motion
+ flow
+ diffusion
+ chemical exchange
+ susceptibility
+ coil sensitivities
+ ADC imperfection
```

每一个都是：

**Disturbance Plugin**
======================

例如：

```text
B0Inhomogeneity

type: field
domain: spatial
map: Hz
```

```text
Flow

type: motion
velocity: ...
direction: ...
```

```text
Exchange

type: tissue
model: Bloch-McConnell
```

这样用户可以从：

```text
Ideal experiment
```

逐层叠加 reality。

这与你原来的教学理念高度吻合。

* * *

**20\. 更漂亮的是：Disturbance Stack 可以改变 Engine Selection**
======================================================

例如：

```text
TSE
```

默认：

```text
EPG
```

加入：

```text
slice profile
```

Kernel 提示：

```text
EPG → ssEPG
```

再加入：

```text
exchange
```

变成：

```text
EPG-X / hybrid
```

再加入：

```text
spatial B0 field
```

可能：

```text
PDG
```

所以用户其实在学习：

为什么某种物理问题需要更复杂的 mathematical representation。

这是相当高阶的教学。

* * *

**21\. AI Lab 应该最后出现，而且角色不是“聊天机器人”**
====================================

AI Lab 应该看到完整 ExperimentGraph。

它拥有 tool：

```text
inspect_experiment
inspect_signal
compare_tissues
run_simulation
run_optimization
explain_epg_pathway
suggest_parameters
find_failure_mode
```

用户问：

为什么我的 ETL=32 TSE vessel wall contrast 比 ETL=16 更差？

Agent 不应该靠语言模型猜。

而是：

```text
run experiment
↓
inspect echo train
↓
inspect EPG pathways
↓
inspect k-space ordering
↓
answer
```

未来再加 Internet：

```text
Literature agent
Pulseq examples
relaxometry database
scanner limits
```

但 simulator core 永远离线。

* * *

**22\. Backend 我会采用“Modular Monolith，而不是微服务”**
==============================================

这是很重要的一点。

Microkernel：

**是代码 architecture。**

不代表：

**一定要 microservices。**

MRQLab v1：

```text
ONE Python process

mrqlab-core
mrqlab-engines
mrqlab-recon
mrqlab-optimization
FastAPI
```

外面：

```text
Next.js
```

就够。

只有以后 GPU jobs 真正重起来：

```text
API
 ↓
Job scheduler
 ↓
GPU workers
```

再拆。

这样既获得：

```text
microkernel extensibility
```

又没有：

```text
distributed-system complexity
```

* * *

**23\. Repo 我现在会进一步改成这样**
=========================

```text
MRQLab/

apps/
    web/
    api/

core/
    experiment/
    sequence/
    sample/
    scanner/
    operators/
    objectives/
    results/
    provenance/

engines/
    bloch/
    epg/
    pdg/
    ssepg/
    bloch_mcconnell/
    density_matrix/

accelerators/
    floquet/
    differentiable/
    gpu/

disturbances/
    b0/
    b1/
    noise/
    motion/
    flow/
    diffusion/
    eddy_current/

optimization/
    grid/
    bayesian/
    evolutionary/
    gradient/

recon/
    fft/
    nufft/
    sense/

adapters/
    pulseq/
    ismrmrd/
    marcos/

plugins/
    cases/
    experiments/
    tissues/

packages/
    schemas/
    units/
    protocol/

docs/
    architecture/
    physics/
    adr/
```

这套结构我认为已经足够支撑你描述的 5 年路线。

* * *

**24\. 但是 MVP 依然必须忍住**
======================

即使 architecture 给未来留好了位置，**第一版不要写 Floquet、CEST、MRS、DCE。**

MRQLab v0.1只验证三件事：

**SE：**

```text
90 → 180 → echo
```

证明：

```text
timeline ↔ Bloch ↔ signal ↔ image
```

**GRE：**

证明：

```text
gradient ↔ k-space ↔ contrast
```

**TSE：**

证明：

```text
RF train ↔ EPG ↔ echo train ↔ image contrast
```

尤其是 TSE。

如果 TSE 能做到：

拉 refocusing FA → EPG 图实时变化 → echo train 改变 → k-space weighting 改变 → tissue contrast 改变

MRQLab 的核心 thesis 就成立了。

这比第一版支持 20 个 sequence 重要得多。

* * *

**因此我现在会把 MRQLab 定义成四个层次**
--------------------------

```text
                         MRQLab

             CLINICAL / EXPERIMENT INTENT
           "What contrast do I want?"
                         │
                         ↓
                   SYSTEM LAYER
               "What sequence does it?"
                         │
                         ↓
                  PHYSICS LAYER
        "What happens to magnetization?"
                         │
                         ↓
                   STATE LAYER
       "Which pathways/states produce it?"
                         │
                         ↓
               OBSERVATION LAYER
       "What signal/image/spectrum results?"
                         │
                         ↓
                OPTIMIZATION LOOP
       "How should I change the experiment?"
                         │
                         └──────────────→ top
```

**这最后的 optimization feedback loop 才是 MRQLab 与一般 MRI simulator 最大的区别。**

它不是：

Learn MRI by watching simulation.

而是：

**Form a hypothesis → design an MR experiment → understand its state evolution → observe its consequence → optimize it toward a clinical/physical objective.**

这也意味着“microkernel”里最重要的五个稳定 contract，我现在会正式定为：

`ExperimentGraph`、`PhysicsOperator`、`StateRepresentation`、`ObjectiveFunction`、`Observation`。

其中 **SequenceIR 反而退居其下**。因为做到 DCE、ASL、CEST、MRS 后，你真正模拟的已经不是 sequence，而是整个 **MR experiment**。
