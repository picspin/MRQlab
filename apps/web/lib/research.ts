export interface TriggerEvent { trigger: number; decision_s: number; preparation_s: number; readout_s: number; rr_estimate_s: number; scheduled: boolean; accepted: boolean; rejection: string | null; cancelled_s: number | null; }
export type ResearchKind = "tse" | "noncartesian" | "flow" | "pulsatile_flow" | "cest" | "cest_solomon" | "mrs";
export interface ResearchRequest { kind: ResearchKind; parameters: Record<string, unknown>; expected_source_hash?: string; }
export interface ResearchRun {
  kind: ResearchKind;
  result: { clinical_question: string; scope: string; gates?: TriggerEvent[]; provenance: Record<string, unknown>; [key: string]: unknown };
  view: {
    images: { label: string; width: number; height: number; values: number[] }[];
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
  mrs: { title: "MRS basis fit", question: "有限 RF 与 J 耦合失配怎样影响水参考相对信号量？",
    limit: "教学 singlet 与合成 AB；标量 T2。真实分子基组、完整 PRESS 空间积分和临床浓度校准仍缺失。",
    validation: "已知合成量的最大相对误差 ≤ 5%，全读出拟合残差 ≤ 2%。匹配基组恢复是闭合模型验证。",
    defaults: { echo_s: .03, basis_j_hz: 7, sample_j_hz: 7 },
    fields: [{ key: "echo_s", label: "回波时间 (s)", step: .005 }, { key: "basis_j_hz", label: "基组 J (Hz)", step: 1 }],
    candidates: [{ echo_s: .02 }, { echo_s: .03 }, { echo_s: .06 }] },
};
