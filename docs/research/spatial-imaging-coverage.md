# 空间成像覆盖审计（基线 8e5895f，实施前）

缺完整链不等于无实现。以下组件均复用；遍历和坐标不称为重建。

| 已有文件、函数与测试 | 缺口 | 本轮范围 |
|---|---|---|
| recon/trajectories.py: TrajectorySpec、generate_trajectory；test_v045_kspace.py、test_v052_fill_order.py | 坐标不构成采集或图像 | 明确 DFT 索引、采集数据和 FFT 逆变换 |
| sequence-ir/mrqlab_sequence/family_templates.py: partition_encodings；test_sequence_family_e2e.py::test_tse_partition_encoding_and_authored_flip_ramp | TSE kz 只有稀疏 echo/partition 编码 | 复用 TSE 信号生成组织图，再完整采集 ky/kz，恢复 3D 体积；不是原稀疏脉冲的完整成像读出 |
| recon/trajectories.py: gridding_recon_2d、_make_nema_like_phantom、undersampled_recon_demo | 二维网格化；stack-of-stars 演示折叠 kz，无三维图像 | 直接非均匀傅里叶采样、二维线性网格化、分区逆 FFT；误差及欠采样演示 |
| mrqlab_experiment/family_execution.py: simulate_family EPSE、adc_map；test_sequence_family_e2e.py::test_dwi_waveform_integrated_b_signal_attenuation_and_adc、test_voxelwise_multi_b_adc_map_and_failures | EPI 为遍历参照，ADC 未经过图像重建 | 复用 EPSE b/组织信号，逐 b 采集图像并拟合 ADC |
| mrqlab_experiment/family_recipes.py: cest_multi_pool_z_spectrum；test_sequence_family_e2e.py::test_four_liquid_pool_cest_and_no_exchange_control | 多池 Z 谱无空间编码，旧 image 产品仍拒绝 | 逐组织运行多池谱，逐 offset 采集图像，再计算 CEST 图 |
| clinical_search.py、family_search.py | 缺图像质量与空间采集 provenance | 独立空间链入口，临床问题、预算、质量阈值、输入及采集哈希与物理 provenance |

## 边界

教学/研究仿真，不是扫描仪验证或临床图像质量认证。采用独立体素信号和理想傅里叶编码，未实现并行成像、压缩感知、真实流动、选层、门控、运动、B0 畸变、线圈、噪声与梯度硬件约束。TSE 采用平均 echo 组织权重，未模拟 echo train 引起的空间 PSF。非笛卡尔是有限网格近似，径向圆盘覆盖不含方形 k 空间角部，可能模糊及条纹；欠采样不能称为干净图像。原 run_experiment 的 CEST image 产品限制保持有效，空间链显式逐组织运行谱。

## 实施结果与验证契约

新入口 `mrqlab_experiment.spatial_imaging.run_spatial_imaging`；重建模块
`mrqlab_recon.spatial`。不修改既有轨迹接口及其坐标约定。新模块以数组
(z,y,x)/(y,x) 和明确 DFT 索引编码；频率 x、相位 y、分区 z。

| 链 | 本轮实现 | 验证 |
|---|---|---|
| 2D Cartesian | 临床 TSE 问题 → 已有 EPG 组织信号 → 全 ky/kx Fourier 采集 → FFT 图像 | 组织图相对 L2 NRMSE ≤1e-10；另以随机复数、奇数/非方形体模验证幅相恢复 ≤1e-12 |
| 3D partition | 同上，设计 partitions 与 z 网格一致；完整 ky/kz 采集 → 3D FFT | 4 个不同组织分区逐体素恢复；3D 复数体模、centric/EPI 遍历恢复 |
| non-Cartesian | 复用 radial 坐标，直接离散 Fourier 采样；线性 splat，径向密度权重后局部权重归一；stack-of-stars 对 kz 做 Fourier 编码与逆变换 | 2D radial、3D stack-of-stars 组织图 NRMSE ≤0.4；独立几何体模 ≤0.2；稀疏 spokes 比稠密采样误差大且不满足 0.1 阈值 |
| CEST | 两种交换速率的三池 Bloch–McConnell Z 谱 → 每 offset 空间采集与重建 → Z(-3.5)-Z(+3.5) 图 | 每 offset 图逐体素回算；对比图逐体素恢复已模拟 Z 谱差（绝对误差 ≤1e-12） |
| ADC | 复用 EPSE 实际积分 b 和 b=0 信号 → 每 b 图像采集/重建 → 既有 adc_map | 所有体素恢复 0.0006/0.001 mm²/s（绝对误差 ≤1e-12） |

测试文件 `tests/experiment/test_spatial_imaging.py`，包含六个参数化临床链实例，
每例检查设计、物理 provenance、采集哈希、图像质量、完整输入回放。
错误编码、预算、网格、重复索引及非有限输入均失败关闭。
质量不达标返回 `quality.passed=False` 和实际误差，欠采样图只供演示。
预算是样本数、笛卡尔重建的 FFT 蝶形运算量和非笛卡尔直接 DFT 乘法量的保守上限，不代表扫描时间/SAR；物理仿真
继续采用已有引擎工作量限制。provenance 保存完整设计、label 网格、所有空间
参数及哈希、每次物理仿真来源、坐标与采集数据哈希。

本机数值：24² 几何体模 128 spokes ×96 点 NRMSE=0.165905；
4 spokes ×24 点 NRMSE=0.416888。组织图默认 radial=0.385848、
stack-of-stars=0.384360。0.4 是较宽的教学近似阈值，不能解释为临床图像质量合格。
不进行图像峰值重标定以掩盖幅度误差。径向密度权重经局部归一用于插值，
不是经过标定的 NUFFT/伴随积分密度补偿，无迭代逆解、过采样或 kernel 去卷积。

## 剩余缺口

- TSE echo-dependent k-space 调制/PSF 与完整时序成像读出尚缺；本轮是均值组织权重加独立理想 Fourier 采集。
- 非笛卡尔简单网格化有明显误差；尚无高精度 NUFFT、迭代重建或真实梯度时序。
- CEST 与 ADC 是已知分区组织、理想独立体素的合成参数图；不模拟交换组织空间混合、噪声底、多方向张量、EPI 畸变和运动。
- 没有新增前端成像 UI 或 API 产品；入口为可回放 Python 研究链，不放宽旧产品契约。
- 不包含真实扫描数据、并行成像、压缩感知、流动/选层/门控与临床认证。

## 全量验证

2026-10-28 提交锚定时在本 worktree 重新完成全量验证：
Python `/Users/hilbert/work/MRQlab-mainfix/.venv/bin/python -m pytest tests/`：
511 passed（1 条已有 Starlette 弃用警告）。当前 PATH 无 `pytest`，复用上一轮环境。
在 `apps/web` 运行普通 `npm test` 时，82 项测试通过后共享缓存
`node_modules/.vite/vitest/results.json` 写入被沙箱以 EPERM 拒绝，退出码为 1；
改用 `npm test -- --cache=false` 重跑：12 文件、82 tests passed，退出码为 0。
TypeScript `npx tsc --noEmit` 通过；`git diff --cached --check` 通过。
依赖仅复用本地既有 Python 环境与 node_modules 链接，没有下载或更改共享依赖。
