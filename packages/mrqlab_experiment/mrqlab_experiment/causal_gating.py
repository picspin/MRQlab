"""A declared causal trigger controller, not ECG detection or scanner firmware."""
import numpy as np


def plan_prospective_readouts(r_peaks_s, *, delay_s, observation_end_s,
                               initial_rr_s=1.2, latency_s=.003, window_s=.006,
                               rr_range_s=(.5,1.5), history_length=4):
    """At each arriving trigger, use only previous RR intervals to schedule RF.

    An unexpected next trigger cancels an ongoing preparation/readout when it
    arrives. `scheduled` is the causal decision; `accepted` is the eventual
    completion outcome. Interrupted preparations must still be simulated.
    """
    peaks=np.asarray(r_peaks_s,float)
    if peaks.ndim!=1 or not 1<=len(peaks)<=1000 or not np.isfinite(peaks).all() or peaks[0]<0 or np.any(np.diff(peaks)<=0):
        raise ValueError('strictly increasing finite nonnegative trigger timestamps required')
    if len(rr_range_s)!=2 or not np.isfinite([delay_s,observation_end_s,initial_rr_s,latency_s,window_s,*rr_range_s]).all():
        raise ValueError('finite gating parameters required')
    if min(delay_s,initial_rr_s,window_s,*rr_range_s)<=0 or latency_s<0 or rr_range_s[0]>rr_range_s[1] or observation_end_s<=peaks[-1]:
        raise ValueError('positive timing, ordered RR limits and observation horizon after triggers required')
    if not rr_range_s[0]<=initial_rr_s<=rr_range_s[1]: raise ValueError('initial RR estimate must lie within declared RR range')
    if type(history_length) is not int or not 1<=history_length<=32: raise ValueError('bounded integer history length required')
    events=[]; history=[]; active=None
    for i,r in enumerate(peaks):
        r=float(r)
        if active is not None and active['readout_end_s']>r:
            active.update(accepted=False,cancelled_s=r,rejection='interrupted_by_trigger')
        previous=float(r-peaks[i-1]) if i else None
        valid=previous is None or rr_range_s[0]<=previous<=rr_range_s[1]
        if previous is not None and valid: history.append(previous)
        used=history[-history_length:]; estimate=float(np.median(used)) if used else initial_rr_s
        reason='previous_rr_outside_range' if not valid else 'window_exceeds_past_rr_estimate' if latency_s+delay_s+window_s>estimate else None
        event=dict(trigger=i,decision_s=r,preparation_s=r+latency_s,readout_s=r+latency_s+delay_s,
            readout_end_s=r+latency_s+delay_s+window_s,previous_rr_s=previous,
            rr_estimate_s=estimate,history_rr_s=list(used),scheduled=reason is None,
            accepted=reason is None,rejection=reason,cancelled_s=None)
        events.append(event); active=event if event['scheduled'] else None
    if active is not None and active['readout_end_s']>observation_end_s:
        active.update(accepted=False,cancelled_s=observation_end_s,rejection='observation_ended')
    return events
