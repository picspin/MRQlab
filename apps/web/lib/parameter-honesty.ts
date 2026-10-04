export type UnwiredParameterState = {
  state: "visual_only";
  label: string;
};

export const UNWIRED_PARAMETER_STATES = {
  adc_bandwidth_hz: { state: "visual_only", label: "seed · not wired" },
  acceleration_factor: { state: "visual_only", label: "local only · not in execution plan" },
  readout_width_factor: { state: "visual_only", label: "local only · not in execution plan" },
  partial_fourier_fraction: { state: "visual_only", label: "local only · not in execution plan" },
} as const satisfies Record<string, UnwiredParameterState>;
