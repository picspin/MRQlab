"""Research extensions of the existing hard-pulse templates.

Encoding gradients use teaching units except EPSE (mT/m). No hardware export.
"""
import math

from .models import Channel, Event, SequenceIR
from .templates import build_sequence, _finite_parameter, _echo_count


def _integer(p, key, default, maximum=512):
    value = p.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ValueError(f"{key} must be an integer in [1, {maximum}]")
    return value


def build_family_sequence(kind, p):
    tr = _finite_parameter(p, 'tr', .5 if kind == 'TSE3D' else .005 if kind == 'SSFP' else 1.)
    te = _finite_parameter(p, 'te', .008 if kind == 'TSE3D' else tr/2 if kind == 'SSFP' else .09 if kind == 'EPSE' else .03)
    if not 0 < te < tr:
        raise ValueError('require 0 < te < tr')
    events = {key: [] for key in ('rf_amp','rf_phase','gx','gy','gz','adc_gate','nco_freq','nco_phase')}
    def add(key, t, value):
        events[key].append((round(t, 12), value))
    meta = dict(template=kind, te=te, tr=tr, research_family=kind)
    if kind == 'TSE3D':
        count = _integer(p, 'partitions', 4, 64)
        echoes = _echo_count(p, 4)
        angle = _finite_parameter(p, 'refocusing_flip_angle', 140.)
        end_angle = _finite_parameter(p, 'refocusing_end_angle', angle)
        if not 0 < end_angle <= 180 or not 0 < angle <= 180:
            raise ValueError('refocusing angles must be in (0,180]')
        base = build_sequence('TSE', dict(te=te, tr=tr, echoes=echoes, refocusing_flip_angle=angle))
        # One ky train per kz partition, centric kz. This is a sparse encoded
        # acquisition, not a claim of a fully sampled 3D image.
        kz = sorted(range(-(count//2), count-count//2), key=lambda x:(abs(x), x))
        encodings, shifts = [], []
        for part, index in enumerate(kz):
            offset = part*tr
            for channel in base.channels:
                for event in channel.events:
                    value = event.value
                    if channel.name == 'rf_amp' and event.time > 0:
                        n = round((event.time+te/2)/te)-1
                        value = angle+(end_angle-angle)*n/max(echoes-1,1)
                    add(channel.name, offset+event.time, value)
            for n in range(echoes):
                center = offset+(n+1)*te
                # Equal and opposite kz lobes around the ADC; no residual
                # partition moment at the next echo or train boundary.
                add('gz', center-.002, index); add('gz', center-.001, 0)
                add('gz', center+.002, -index); add('gz', center+.003, 0)
                encodings.append(dict(time_s=center, ky=n, kz=index, moment_teaching_s=index*.001))
            shifts.extend(dict(time=e['time']+offset, dk=e['dk']) for e in base.metadata['epg_dk_events'])
        if echoes*te+.003 >= tr or te < .006:
            raise ValueError('partition encoding lobes must fit between echoes and TR')
        meta.update(preferred_engine='epg', echoes=echoes*count, partitions=count,
                    partition_encodings=encodings, epg_dk_events=shifts,
                    refocusing_flip_angle=angle, refocusing_end_angle=end_angle,
                    flip_strategy='linear ramp; ideal CPMG hard pulses; no vendor VFA optimization',
                    repetition_spoiling=True)
        duration=count*tr
    elif kind == 'SSFP':
        repetitions = _integer(p, 'repetitions', 256, 2048)
        flip = _finite_parameter(p,'flip_angle',40.)
        if not 0 < flip < 180 or abs(te-tr/2)>1e-10:
            raise ValueError('SSFP requires 0<flip<180 and TE=TR/2')
        gate=min(tr/10,.0002)
        ti = _finite_parameter(p,'inversion_time_s',.9)
        arrival = _finite_parameter(p,'inflow_fraction',1.)
        preparation=bool(p.get('double_inversion',False))
        if ti <= .00001 or not 0 <= arrival <= 1:
            raise ValueError('positive TI and inflow fraction in [0,1] required')
        delay=ti if preparation else 0.
        if preparation:
            add('rf_amp',0.,180); add('rf_phase',0.,0)
            add('rf_amp',.000001,180); add('rf_phase',.000001,0)
        for n in range(repetitions):
            t=delay+n*tr
            add('rf_amp', t, flip); add('rf_phase', t, (n%2)*180)
            add('adc_gate', t+te, 1); add('adc_gate', t+te+gate, 0)
            add('gx', t+te/4, -1); add('gx', t+te/2, 0)
            add('gx', t+te, 1); add('gx', t+te+te/4, 0)
        meta.update(preferred_engine='bloch', repetitions=repetitions, flip_angle=flip,
                    double_inversion=preparation, inversion_time_s=ti,
                    inflow_fraction=arrival, blood_compartment=bool(p.get('blood_compartment',False)), balanced=True,
                    preparation='180 nonselective at 0; 180 local at 1 us; incoming spins outside local slab')
        duration=delay+repetitions*tr
    elif kind == 'EPSE':
        g = _finite_parameter(p,'diffusion_gradient_mt_m',30.)
        delta = _finite_parameter(p,'delta_s',.02)
        separation = _finite_parameter(p,'separation_s',.04)
        lines=_integer(p,'epi_lines',16,128)
        if lines<16:
            raise ValueError('EPI geometric reference requires at least 16 lines')
        spacing=_finite_parameter(p,'echo_spacing_s',.001)
        start=.005
        if g < 0 or delta <= 0 or separation <= delta or spacing <= 0:
            raise ValueError('invalid diffusion/EPI design')
        if start+delta >= te/2 or start+separation <= te/2 or start+separation+delta >= te-(lines//2+1)*spacing:
            raise ValueError('diffusion lobes must bracket refocuser and precede EPI')
        if te+lines*spacing >= tr:
            raise ValueError('EPI readout must fit TR')
        add('rf_amp',0,90); add('rf_phase',0,0)
        add('rf_amp',te/2,180); add('rf_phase',te/2,90)
        for t in (start,start+separation):
            add('gz',t,g); add('gz',t+delta,0)
        for n in range(lines):
            t=te+(n-lines//2)*spacing
            add('gx',t,(-1)**n); add('gx',t+spacing*.4,0)
            add('gy',t+spacing*.5,1); add('gy',t+spacing*.6,0)
            add('adc_gate',t,1); add('adc_gate',t+spacing*.4,0)
        meta.update(preferred_engine='epg',gradient_units='mt_m',diffusion_gradient_mt_m=g,
                    delta_s=delta,separation_s=separation,epi_lines=lines,echo_spacing_s=spacing,
                    diffusion_model='isotropic Gaussian rectangular PGSE; EPI b contribution excluded')
        duration=tr
    else:  # PRESS: ideal rectangular spatial selection, explicit orthogonal axes.
        if te <= .002:
            raise ValueError('PRESS TE must exceed 2 ms')
        readout=_finite_parameter(p,'readout_s',.512)
        size=_finite_parameter(p,'voxel_size_m',.02)
        if readout <= 0 or size <= 0 or te+readout >= tr:
            raise ValueError('PRESS readout/voxel must be positive and fit TR')
        for t,angle,phase,axis in ((0,90,0,'gx'),(te/4,180,90,'gy'),(3*te/4,180,90,'gz')):
            add('rf_amp',t,angle); add('rf_phase',t,phase)
            add(axis,t,1); add(axis,t+.0005,0)
        add('adc_gate',te,1); add('adc_gate',te+readout,0)
        meta.update(preferred_engine='spectral',voxel_size_m=size,localization_axes=['x','y','z'],
                    localization='ideal intersecting top-hat slabs; no chemical shift displacement or J coupling',readout_s=readout)
        duration=tr
    channels=[Channel(name=k,events=[Event(time=t,value=v) for t,v in sorted(values)]) for k,values in events.items()]
    return SequenceIR(name=kind,duration=duration,channels=channels,metadata=meta)
