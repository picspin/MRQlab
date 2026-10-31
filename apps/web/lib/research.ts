export interface TriggerEvent { trigger: number; decision_s: number; preparation_s: number; readout_s: number; rr_estimate_s: number; scheduled: boolean; accepted: boolean; rejection: string | null; cancelled_s: number | null; }
export type ResearchKind = "tse" | "noncartesian" | "flow" | "pulsatile_flow" | "flow_epi" | "cest" | "cest_solomon" | "cest_memory" | "mrs" | "mrs_press" | "mrs_quantum" | "radial_tse";
export interface ResearchRequest { kind: ResearchKind; parameters: Record<string, unknown>; expected_source_hash?: string; }
export interface ResearchRun {
  kind: ResearchKind;
  result: { clinical_question: string; scope: string; gates?: TriggerEvent[]; readout_status?: { trigger: number; encoding_sign: number; adc_samples: number; expected_samples: number; completed: boolean; stage: string }[];
    memory_diagnostics?: { coarse_steps: number; refined_steps: number; rf_peak_uT: number; numerical_refinement_passed: boolean; normalized_trace_difference: number; lag_kernel_error: number; retained_history_s: number; inter_pulse_reset: boolean };
    readout?: { adc_duration_s: number; dwell_s: number; peak_gradient_t_m: number; coils: number; field_origin: string };
    quantum_diagnostics?: { preparation: string; basis_mode: string; numerical_refinement_passed: boolean; timing: { echo_time_s: number; adc_end_s: number; recovery_s: number; repetition_s: number; adc_points: number; adc_interval_s: number }; minimum_density_eigenvalue: number; max_periodic_return_error: number; components: { name: string; authored_amount: number; recovered_amount: number; signal_fraction: number }[] };
    provenance: Record<string, unknown>; [key: string]: unknown };
  view: {
    images: { label: string; width: number; height: number; values: number[]; scale_group?: string }[];
    curves: { label: string; x: number[]; y: number[] }[];
    x_label: string; y_label: string; validation: { passed: boolean; [key: string]: number | boolean }; metrics: Record<string, number>;
  };
  replay_request: ResearchRequest; source_hash: string; result_hash: string; runtime: { python: string; numpy: string };
}
export interface ResearchSearch {
  replay_search: ResearchRequest & { candidates: Record<string, unknown>[] }; search_hash: string;
  candidates: { parameters: Record<string, unknown>; feasible: boolean; loss?: number; reason?: unknown; run?: ResearchRun }[];
  best: { parameters: Record<string, unknown>; loss: number; run: ResearchRun } | null; objective: string;
}
interface Study {
  title: string; question: string; limit: string; validation: string; defaults: Record<string, unknown>;
  fields: { key: string; label: string; step: number }[]; candidates: Record<string, unknown>[];
}
export const STUDIES: Record<ResearchKind, Study> = {
  tse: { title: "TSE / PSF", question: "回波串与排序怎样改变组织对比和空间分辨率？",
    limit: "周期稳态 EPG；每条 Fourier 读出保持回波中心幅度。窗内演化、真实梯度和运动仍缺失。",
    validation: "与理想均值权重图像的一致性；逐回波调制通常不通过此等式，PSF 预测一致性单独报告。",
    defaults: { echoes: 4, echo_spacing_s: .008, order: "centric", t2_s: [.04, .12] },
    fields: [{ key: "echoes", label: "回波数", step: 2 }, { key: "echo_spacing_s", label: "回波间隔 (s)", step: .001 }],
    candidates: [{ echoes: 2 }, { echoes: 4 }, { echoes: 8 }] },
  noncartesian: { title: "Radial inverse", question: "增加径向采样，能否恢复未缩放的真实图像幅度？",
    limit: "精确 DFT 参考 / FINUFFT 矩阵自由 CGLS；API 的 NUFFT 体模上限 64×64。欠采样与病态性仍限制恢复，线圈、噪声正则化和轨迹校准仍缺失。",
    validation: "图像 NRMSE ≤ 1e-6。采样残差收敛并不证明图像可辨识。",
    defaults: { spokes: 48, points: 32, reconstruction: "cgls", max_work: 10000000000, inverse_max_iterations: 1500 },
    fields: [{ key: "spokes", label: "径向 spoke 数", step: 2 }, { key: "inverse_max_iterations", label: "迭代上限", step: 100 }],
    candidates: [{ spokes: 2 }, { spokes: 24 }, { spokes: 48 }] },
  radial_tse: { title: "Radial TSE / echo model", question: "逐回波幅度怎样改变径向 TSE 图像？能否在 RF 与时长限制内恢复声明回波的对比？",
    limit: "回波中心模式使用已知 EPG 曲线和精确 DFT / FINUFFT。有限 ADC 模式以硬 180° CPMG、点采样、作者 B0/线圈图和理想平衡梯度计算窗内演化，仅提供精确 DFT 参考；没有实测校准、完整有限 RF 或真实梯度切换。",
    validation: "图像与组分 NRMSE 各 ≤1e-6，数据残差 ≤1e-10，幅度 ROI 对比 ≥0.005，RF 能量代理 ≤200；仅从通过全部目标的候选中选择低 RF 设计。",
    defaults: { echoes: 4, spokes: 96, points: 32, backend: "exact", readout_model: "echo_center", refocusing_angle: 180, refocusing_end_angle: 180, max_work: 20000000000 },
    fields: [{ key: "echoes", label: "回波串长度", step: 2 }, { key: "refocusing_angle", label: "起始重聚角 (°)", step: 10 }, { key: "refocusing_end_angle", label: "末次重聚角 (°)", step: 10 }],
    candidates: [{ refocusing_angle: 180, refocusing_end_angle: 180 }, { refocusing_angle: 140, refocusing_end_angle: 110 }, { refocusing_angle: 100, refocusing_end_angle: 80 }] },
  flow: { title: "Flow / slice / gates", question: "连续流入、有限选层 RF 和心动时机如何影响血液抑制？",
    limit: "规定的一维恒速轨迹；已知触发的回顾性门控。CFD、搏动速度、前瞻门控和成像读出仍缺失。",
    validation: "所有接受周期：血液 |Mz| ≤ 0.1，壁组织 |Mz| ≥ 0.7；默认双周期设计会失败。",
    defaults: { inversion_time_s: .9, blood_velocity_m_s: .025, r_peaks_s: [0, 1.2, 2.4] },
    fields: [{ key: "inversion_time_s", label: "反转时间 (s)", step: .05 }, { key: "blood_velocity_m_s", label: "穿层速度 (m/s)", step: .005 }],
    candidates: [{ inversion_time_s: .6 }, { inversion_time_s: .9 }, { inversion_time_s: 1.1 }] },
  pulsatile_flow: { title: "Pulsatile / causal DIR", question: "压力驱动的搏动剪切流与提前到达的触发，会怎样改变选层准备和血液抑制？",
    limit: "直刚性圆管 Womersley 周期流；只使用已到达触发进行决策。没有血管顺应性、ECG 检测或运动图像重建。中断的 RF 仍改变自旋状态。",
    validation: "完成读出中血液 |Mz| ≤ 0.1、壁 |Mz| ≥ 0.7，且中断比例 ≤ 声明上限；无完整读出直接失败。默认示例不通过目标。",
    defaults: { r_peaks_s: [0, .45, 1.65], observation_end_s: 2.8, inversion_time_s: .9, mean_gradient_pa_m: 100, oscillating_gradient_pa_m: 200, frequency_hz: 1, radial_rings: 4, axial_spins: 201 },
    fields: [{ key: "inversion_time_s", label: "反转时间 (s)", step: .05 }, { key: "mean_gradient_pa_m", label: "平均驱动压力梯度 (Pa/m)", step: 10 }, { key: "phase_rad", label: "压力波相位 (rad)", step: .1 }],
    candidates: [{ inversion_time_s: .6 }, { inversion_time_s: .9 }, { inversion_time_s: 1.1 }] },
  flow_epi: { title: "Flow / encoded EPI", question: "真实传播的选层准备、双极梯度与逐点 EPI 能否保留图像和流速信息？心动时刻不同会产生多大偏差？",
    limit: "刚性管 Womersley 轴向流；固定横向体素中心，有限 RF 与逐段梯度相位，点 ADC。异号编码来自不同触发时刻；没有线圈、噪声、梯度延迟、涡流或横向输运。无 DIR 是单独对照。",
    validation: "至少一个完整异号编码对；流速对梯度矩参考的 RMSE ≤0.002 m/s，复图像对冻结参考的 NRMSE ≤0.05，血液 |Mz| ≤0.1、壁 |Mz| ≥0.7，且无中断或参考速度超 VENC。默认示例失败，全部候选失败时不选设计。",
    defaults: { r_peaks_s: [0, 1.2], observation_end_s: 2.4, inversion_time_s: .9, preparation: "dir", matrix_size: 16, fov_m: .012, axial_spins: 401, rf_steps: 64, dwell_s: .00006, venc_m_s: .05 },
    fields: [{ key: "inversion_time_s", label: "反转时间 (s)", step: .05 }, { key: "venc_m_s", label: "流速编码 VENC (m/s)", step: .01 }, { key: "dwell_s", label: "EPI 采样间隔 (s)", step: .00001 }],
    candidates: [{ inversion_time_s: .6 }, { inversion_time_s: .9 }, { inversion_time_s: 1.1 }] },
  cest: { title: "CEST / MT / rNOE", question: "半固体 MT 与上场 rNOE 如何混杂 amide 信号和功率选择？",
    limit: "均匀联合池模型；rNOE 是有效交换池。微观交叉弛豫、空间成像和临床浓度校准仍缺失。",
    validation: "+3.5 ppm 无 amide 交换对照减完整模型的差 ≥ 0.005；MTR asymmetry 不代表纯 amide。",
    defaults: { b1_uT: 1, saturation_s: 1 },
    fields: [{ key: "b1_uT", label: "饱和 B1 (µT)", step: .1 }, { key: "saturation_s", label: "饱和时长 (s)", step: .1 }],
    candidates: [{ b1_uT: .5 }, { b1_uT: 1 }, { b1_uT: 2 }] },
  cest_solomon: { title: "CEST / Solomon relay", question: "分子距离和转动相关时间怎样改变双极 NOE 的符号，以及经桥接质子到水的中继信号？",
    limit: "各向同性高场 Solomon 成对质子模型，保留 CEST/MT。供体不与水直接交换；完整 Redfield 相干、分子自旋扩散和近零 SL MT 仍缺失。",
    validation: "amide 条件对比与供体处中继条件对比均 ≥ 0.005。快速转动可给出相反符号并失败，不截断负对比。",
    defaults: { b1_uT: 1, saturation_s: 1, distance_m: 2.5e-10, tau_c_s: 1e-8, bridge_exchange_s1: 1000 },
    fields: [{ key: "b1_uT", label: "饱和 B1 (µT)", step: .1 }, { key: "tau_c_s", label: "转动相关时间 (s)", step: 1e-9 }, { key: "bridge_exchange_s1", label: "桥接质子到水交换率 (s⁻¹)", step: 100 }],
    candidates: [{ b1_uT: .1 }, { b1_uT: 1 }, { b1_uT: 2 }] },
  cest_memory: { title: "CEST / finite-memory MT", question: "有限形状 RF 与半固体记忆怎样改变零频偏附近的 MT，以及经 Solomon 中继进入水的 NOE？",
    limit: "广义 Bloch 时间卷积保留全脉冲/间隙历史；零频偏无需替换线型。液体仍为均匀池和纵向 Solomon 对，分子参数为作者先验；不是完整 Redfield、实测校准或空间成像。",
    validation: "amide 与中继对比各 ≥0.005；全时序粗/细步归一化差 ≤0.0002，积分记忆核差 ≤1e-6。数值收敛和对比目标分别报告；只有全部通过才选择低 RF 候选。默认中继对比不足。",
    defaults: { b1_uT: 1, pulse_s: .02, gap_s: .04, n_pulses: 4, shape: "hann", phase_cycle_rad: [0], rf_bins: 16, steps_per_bin: 24 },
    fields: [{ key: "b1_uT", label: "峰值 B1 (µT)", step: .1 }, { key: "pulse_s", label: "单脉冲时长 (s)", step: .01 }, { key: "gap_s", label: "脉冲间隙 (s)", step: .01 }],
    candidates: [{ b1_uT: .5 }, { b1_uT: 1 }, { b1_uT: 2 }] },
  mrs_quantum: { title: "MRS / quantum TR", question: "有限 RF、多自旋量子弛豫和重复 TR 饱和怎样影响完整复频谱的信号量？",
    limit: "独立自旋 Lindblad 浴、显式有限 RF/ADC/恢复与理想独立去相位。T1/T2/J/极化为作者先验；未与三维 PRESS 选区耦合，不是分子 Redfield、实测校准或临床浓度。",
    validation: "信号量误差 ≤5%，复 FID 残差 ≤2%，相对完全恢复的每分量信号范数 ≥20%；RF 加密差 ≤0.2%，密度矩阵与周期返回误差 ≤1e-10。仅在全部通过的有限候选中选择最短 TR。",
    defaults: { echo_s: .03, repetition_s: .6, points: 256, dwell_s: .0005, preparation: "periodic", basis_mode: "matched", rf_steps: 32, refine_rf_steps: 64 },
    fields: [{ key: "echo_s", label: "回波时间 (s)", step: .005 }, { key: "repetition_s", label: "重复时间 TR (s)", step: .1 }],
    candidates: [{ repetition_s: .18 }, { repetition_s: .3 }, { repetition_s: .6 }, { repetition_s: .1 }] },
  mrs_press: { title: "PRESS / volume fit", question: "有限 RF 带宽和三维选区如何改变局域频谱？中心点基组会产生多大偏差？",
    limit: "PRESS [-1,+1,-1] 相干选择、三维复信号积分与扩展 FOV 检查。仍为教学 singlet/合成 AB、标量 T2；真实分子库、量子弛豫和扫描仪验证仍缺失。",
    validation: "更细网格样本的信号量误差 ≤5%，拟合残差 ≤2%，RF 加密检查 ≤0.2%，网格/FOV 检查各 ≤2%，选区外功率比例 ≤10%。",
    defaults: { echo_s: .03, rf_duration_s: .001, grid_size: 17, refine_grid: 25, basis_mode: "volume" },
    fields: [{ key: "echo_s", label: "回波时间 (s)", step: .005 }, { key: "rf_duration_s", label: "选层 RF 时长 (s)", step: .0001 }],
    candidates: [{ rf_duration_s: .0005 }, { rf_duration_s: .001 }, { rf_duration_s: .002 }] },
  mrs: { title: "MRS basis fit", question: "有限 RF 与 J 耦合失配怎样影响水参考相对信号量？",
    limit: "教学 singlet 与合成 AB；标量 T2。真实分子基组、完整 PRESS 空间积分和临床浓度校准仍缺失。",
    validation: "已知合成量的最大相对误差 ≤ 5%，全读出拟合残差 ≤ 2%。匹配基组恢复是闭合模型验证。",
    defaults: { echo_s: .03, basis_j_hz: 7, sample_j_hz: 7 },
    fields: [{ key: "echo_s", label: "回波时间 (s)", step: .005 }, { key: "basis_j_hz", label: "基组 J (Hz)", step: 1 }],
    candidates: [{ echo_s: .02 }, { echo_s: .03 }, { echo_s: .06 }] },
};

export const FINITE_ADC_CANDIDATES = [{ adc_duration_s: .001 }, { adc_duration_s: .002 }, { adc_duration_s: .004 }, { adc_duration_s: .008 }];
