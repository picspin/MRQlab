export type ChannelName =
  | "rf_amp"
  | "rf_phase"
  | "gx"
  | "gy"
  | "gz"
  | "adc_gate"
  | "nco_freq"
  | "nco_phase";

export interface SequenceEvent {
  time: number;
  value: number;
}

export interface SequenceChannel {
  name: ChannelName | string;
  events: SequenceEvent[];
}

export interface SequenceIR {
  name: string;
  duration: number;
  channels: SequenceChannel[];
  metadata?: Record<string, unknown>;
}

export const TEACHING_CHANNELS: ChannelName[] = ["rf_amp", "gx", "gy", "gz", "adc_gate"];
