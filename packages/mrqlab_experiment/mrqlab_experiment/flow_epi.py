"""Persistent pressure-driven spins, causal DIR and motion-encoded EPI images.

Research/teaching only. Fixed transverse voxel centers, through-plane Womersley
trajectories and finite slice RF; sample-and-hold gradient commands and point ADC.
No scanner execution, clinical certification, coils, noise or transverse motion.
"""
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_recon.spatial import ifft_image,image_quality
from .flow_imaging import MovingBlochEnsemble,selective_sinc,GAMMA
from .pulsatile_flow import WomersleyPipe
from .causal_gating import plan_prospective_readouts
from .spatial_imaging import _hash
from .study_records import _checked_sources,runtime_manifest


class SpatialMovingEnsemble(MovingBlochEnsemble):
    """Exact xy phase for fixed centers; exact analytic z motion per gradient hold."""
    def __init__(self,z,xy,**kwargs):
        super().__init__(z,0.,**kwargs)
        self.xy=np.array(xy,float,copy=True)
        if self.xy.shape!=(len(z),2) or not np.isfinite(self.xy).all():
            raise ValueError('finite fixed xy coordinates for every moving spin required')

    def advance(self,dt_s,*,b1_uT=0j,gz_t_m=0.,gx_t_m=0.,gy_t_m=0.):
        if not np.isfinite([gx_t_m,gy_t_m]).all(): raise ValueError('finite xy gradients required')
        if b1_uT!=0 and (gx_t_m!=0 or gy_t_m!=0):
            raise ValueError('RF may overlap slice Gz only; transverse RF gradients unsupported')
        # Reserve both operations before mutating state.
        operations=2 if gx_t_m!=0 or gy_t_m!=0 else 1
        if self.work+operations*len(self.z0)>self.max_work: raise ValueError('spatial Bloch work budget exceeded')
        super().advance(dt_s,b1_uT=b1_uT,gz_t_m=gz_t_m)
        if operations==2:
            self._charge();phase=GAMMA*dt_s*(gx_t_m*self.xy[:,0]+gy_t_m*self.xy[:,1])
            m=(self.state[:,0]+1j*self.state[:,1])*np.exp(1j*phase)
            self.state[:,0]=m.real;self.state[:,1]=m.imag


def epi_waveform(*,matrix_size=16,fov_m=.012,dwell_s=.00006,venc_m_s=.05,
                 ramp_steps=8,max_gradient_t_m=.04,max_nominal_slew_t_m_s=150.):
    """Bipolar +/- encoding and finite-ramp EPI, returned as actual DAC holds.

    k=-gamma_bar*integral(Gxy dt) matches the project's negative-sign Fourier
    acquisition. Positive flow phase is +gamma*integral(Gz z dt). VENC uses the
    actual sampled bipolar first moment, not an idealized rectangle formula.
    """
    if type(matrix_size) is not int or matrix_size not in (8,16,32): raise ValueError('matrix size 8, 16 or 32 required')
    if type(ramp_steps) is not int or not 2<=ramp_steps<=64: raise ValueError('bounded gradient ramp steps required')
    if (not np.isfinite([fov_m,dwell_s,venc_m_s,max_gradient_t_m,max_nominal_slew_t_m_s]).all() or
            min(fov_m,dwell_s,venc_m_s,max_gradient_t_m,max_nominal_slew_t_m_s)<=0):
        raise ValueError('positive finite geometry, dwell, encoding and gradient limits required')
    commands=[];nominal_slew=0.
    def hold(dt,g,kind,adc=None):
        commands.append(dict(duration_s=float(dt),gradient_t_m=np.asarray(g,float).tolist(),kind=kind,adc=adc))
    def ramp(a,b,dt,kind):
        nonlocal nominal_slew
        a=np.asarray(a,float);b=np.asarray(b,float)
        nominal_slew=max(nominal_slew,float(np.max(abs(b-a))/dt))
        for i in range(ramp_steps): hold(dt/ramp_steps,a+(b-a)*(i+.5)/ramp_steps,kind)
    def trapezoid(g,duration,rise,kind):
        ramp([0,0,0],g,rise,kind);hold(duration-2*rise,g,kind);ramp(g,[0,0,0],rise,kind)
    # A unit bipolar template calibrates actual M1 of sample-and-hold ramps.
    lobe=.002;rise=.0003
    trapezoid([0,0,-1.],lobe,rise,'velocity_encoding')
    trapezoid([0,0,1.],lobe,rise,'velocity_encoding')
    at=0.;unit_m1=0.
    for c in commands:
        dt=c['duration_s'];unit_m1+=c['gradient_t_m'][2]*(at*dt+dt*dt/2);at+=dt
    amplitude=np.pi/(2*GAMMA*venc_m_s*unit_m1)
    for c in commands: c['gradient_t_m'][2]*=amplitude
    nominal_slew*=amplitude
    n=matrix_size;gx=-1/(GAMMA_BAR_HZ_T*fov_m*dwell_s);ramp_s=.0003
    start_k=np.array([-n//2,-n//2],float)/fov_m
    pre_area=-start_k/GAMMA_BAR_HZ_T-np.array([gx*ramp_s/2,0.])
    trapezoid([*list(pre_area/(.001-ramp_s)),0.],.001,ramp_s,'epi_prephaser')
    for y in range(n):
        direction=1 if y%2==0 else -1;g=[direction*gx,0.,0.]
        ramp([0,0,0],g,ramp_s,'epi_readout_ramp')
        xs=list(range(n)) if direction==1 else list(range(n-1,-1,-1))
        commands[-1]['adc']=[y,xs[0]]
        for x in xs[1:]: hold(dwell_s,g,'epi_readout',[y,x])
        ramp(g,[0,0,0],ramp_s,'epi_readout_ramp')
        if y+1<n:
            blip=-1/(GAMMA_BAR_HZ_T*fov_m*(.0004-.0001))
            trapezoid([0.,blip,0.],.0004,.0001,'epi_phase_blip')
    area=np.sum([np.array(c['gradient_t_m'])*c['duration_s'] for c in commands],axis=0)
    trapezoid(list(-area/(.001-ramp_s)),.001,ramp_s,'epi_rewinder')
    at=0.;integral=np.zeros(3);m1=np.zeros(3);adc=[]
    for c in commands:
        dt=c['duration_s'];g=np.array(c['gradient_t_m'])
        c['start_s']=at;c['end_s']=at+dt
        integral+=g*dt;m1+=g*(at*dt+dt*dt/2);at+=dt
        if c['adc'] is not None: adc.append(dict(index=c['adc'],time_s=at,k_cycles_m=(-GAMMA_BAR_HZ_T*integral[:2]).tolist()))
    peak=float(np.max(abs(np.array([c['gradient_t_m'] for c in commands]))))
    if peak>max_gradient_t_m or nominal_slew>max_nominal_slew_t_m_s:
        raise ValueError('encoding/readout nominal gradient amplitude or finite-ramp slew exceeds declared design limit')
    expected=np.array([[(x-n//2)/fov_m,(y-n//2)/fov_m] for a in adc for y,x in [a['index']]])
    if not np.allclose(np.array([a['k_cycles_m'] for a in adc]),expected,atol=1e-8,rtol=0):
        raise ValueError('gradient-integrated ADC trajectory differs from the Cartesian grid')
    return dict(commands=commands,adc=adc,duration_s=at,m0_t_s_m=integral.tolist(),m1_t_s2_m=m1.tolist(),
        encoding_m1_t_s2_m=float(amplitude*unit_m1),delta_encoding_m1_t_s2_m=float(2*amplitude*unit_m1),
        venc_m_s=venc_m_s,peak_gradient_t_m=peak,nominal_slew_t_m_s=nominal_slew,
        ramp_steps=ramp_steps,gradient_hash=_hash(commands),
        scope='sample-and-hold approximation to nominal finite ramps; point ADC; ideal gradient/RF switching and immediate command cutoff on trigger; no eddy currents/gradient delay or hardware abort-ramp model')


def _phantom(pipe,n,fov,thickness,end,axial,max_work,off):
    p=(np.arange(n)-n//2)*fov/n;xx,yy=np.meshgrid(p,p);r=np.hypot(xx,yy)
    masks={'blood':r<pipe.radius,'wall':(r>=pipe.radius)&(r<pipe.radius+.001)}
    if min(m.sum() for m in masks.values())<3: raise ValueError('blood/wall spatial grid undersampled')
    ensembles={}
    for name,mask in masks.items():
        pixels=np.flatnonzero(mask);radii=np.repeat(r.ravel()[pixels],axial)
        xy=np.repeat(np.column_stack([xx.ravel()[pixels],yy.ravel()[pixels]]),axial,axis=0)
        if name=='blood':
            motion=pipe.motion(radii);low,high=motion.displacement_bounds(end)
            left=-high-2*thickness;right=-low+2*thickness
        else:
            motion=None;left=np.full(len(radii),-2*thickness);right=-left
        dz=(right-left)/axial;phase=np.tile(np.arange(axial)+.5,len(pixels))
        z=left+phase*dz
        spins=SpatialMovingEnsemble(z,xy,motion=motion,t1_s=1.6 if name=='blood' else 1.,
            t2_s=.15 if name=='blood' else .08,off_hz=off,max_work=max_work)
        ensembles[name]=dict(spins=spins,cell_width_m=dz,pixel_ids=np.repeat(pixels,axial),pixels=pixels)
    return ensembles,masks,r


def _project(item,n,thickness,*,longitudinal=False):
    spins=item['spins'];spins._charge()
    z=spins.positions();width=item['cell_width_m']
    overlap=np.maximum(0.,np.minimum(z+width/2,thickness/2)-np.maximum(z-width/2,-thickness/2))
    mask=overlap>0
    count=np.bincount(item['pixel_ids'][mask],minlength=n*n)
    if np.any(count[item['pixels']]<3): raise ValueError('receive slab undersampled in one or more spatial voxels')
    values=spins.state[:,2].astype(complex) if longitudinal else spins.state[:,0]+1j*spins.state[:,1]
    # Integrate the geometric cell/slab intersection, including boundary cells.
    # No measured-signal/density normalization is fitted after reception.
    values=values[mask]*overlap[mask]/thickness;ids=item['pixel_ids'][mask]
    projected=np.bincount(ids,weights=values.real,minlength=n*n)+1j*np.bincount(ids,weights=values.imag,minlength=n*n)
    return projected.reshape(n,n),int(mask.sum())


def _cycle(item,gate,waveform,inv,exc,n,thickness,sign,preparation):
    spins=item['spins'];cut=gate['cancelled_s'] if gate['cancelled_s'] is not None else gate['readout_end_s']
    energy=0.;started=False;stage='trigger_latency';samples=[];pre=None;frozen=None;encoding_start=None;applied=[];gradient_energy=0.
    def advance(dt,**kw):
        actual=min(dt,max(0.,cut-spins.time))
        if actual>1e-14: spins.advance(actual,**kw)
        return actual
    def wait(at,**kw): return advance(max(0.,at-spins.time),**kw)
    def pulse(rf):
        nonlocal energy
        for b1 in rf['b1_uT']:
            actual=advance(rf['dt_s'],b1_uT=complex(b1),gz_t_m=rf['gz_t_m']);energy+=float(b1*b1*actual)
            if spins.time>=cut-1e-14: break
    wait(gate['preparation_s'])
    if spins.time<cut-1e-14:
        started=True
        if preparation=='dir': spins.hard_rf(180.);stage='selective_reinversion';pulse(inv)
    if spins.time<cut-1e-14: stage='inversion_recovery';wait(gate['readout_s'])
    if spins.time<cut-1e-14:
        pre,count=_project(item,n,thickness,longitudinal=True);stage='excitation';pulse(exc)
    if spins.time<cut-1e-14: stage='slice_rephaser';advance(.002,gz_t_m=-exc['gz_t_m'])
    if spins.time<cut-1e-14: encoding_start=spins.time
    for command_index,c in enumerate(waveform['commands']):
        if spins.time>=cut-1e-14: break
        stage=c['kind'];g=list(c['gradient_t_m']);g[2]*=sign
        if frozen is None and c['kind']!='velocity_encoding': frozen,_=_project(item,n,thickness)
        dt=advance(c['duration_s'],gx_t_m=g[0],gy_t_m=g[1],gz_t_m=g[2])
        applied.append(dict(command_index=command_index,duration_s=dt))
        gradient_energy+=float(np.dot(g,g)*dt)
        if c['adc'] is not None and dt>=c['duration_s']-1e-14:
            projected,count=_project(item,n,thickness)
            # xy phase has already been physically propagated by the gradients;
            # summation is reception, not another Fourier encoding operation.
            value=complex(np.sum(projected))
            samples.append(dict(index=c['adc'],time_s=spins.time,value=[value.real,value.imag],receive_spins=count))
    complete=bool(gate['accepted'] and len(samples)==n*n)
    image=None;quality=None;grid=None
    if complete:
        grid=np.empty((n,n),complex)
        for a in samples: grid[tuple(a['index'])]=complex(*a['value'])
        image=ifft_image(grid);quality=image_quality(frozen,image,.05);stage='completed'
    return dict(samples=samples,grid_complete=len(samples)==n*n,completed=complete,image=image,
        kspace=grid,frozen_reference=frozen if complete else None,frozen_quality=quality,
        pre_excitation_mz=pre,encoding_start_s=encoding_start,stage=stage,end_s=spins.time,
        applied_readout_commands=applied,readout_gradient_energy_t2_s_m2=gradient_energy,
        preparation_started=started,finite_rf_energy_uT2_s=energy,
        state_hash=_hash(spins.state.tolist()),positions_hash=_hash(spins.positions().tolist()))


def run_flow_epi(*,r_peaks_s=(0.,1.2),observation_end_s=2.4,inversion_time_s=.9,
                 trigger_latency_s=.003,initial_rr_s=1.2,rr_range_s=(.5,1.5),
                 radius_m=.002,density_kg_m3=1060.,viscosity_pa_s=.0035,mean_gradient_pa_m=100.,
                 oscillating_gradient_pa_m=200.,frequency_hz=1.,phase_rad=0.,
                 thickness_m=.005,matrix_size=16,fov_m=.012,axial_spins=401,rf_steps=64,preparation='dir',
                 off_resonance_hz=0.,dwell_s=.00006,venc_m_s=.05,ramp_steps=8,
                 max_gradient_t_m=.04,max_nominal_slew_t_m_s=150.,
                 signal_floor=1e-5,target_velocity_rmse_m_s=.002,target_frozen_image_error=.05,
                 blood_target_max=.1,wall_target_min=.7,max_interrupted_fraction=0.,
                 max_work=200000000,max_memory_bytes=134217728,max_duration_s=10.):
    sources=_checked_sources()
    if preparation not in {'dir','none'}: raise ValueError('DIR preparation or explicitly labelled no-preparation control required')
    nums=[observation_end_s,inversion_time_s,thickness_m,fov_m,off_resonance_hz,signal_floor,
          target_velocity_rmse_m_s,target_frozen_image_error,blood_target_max,wall_target_min,max_interrupted_fraction,max_duration_s]
    if (not np.isfinite(nums).all() or min(observation_end_s,thickness_m,fov_m,signal_floor,target_velocity_rmse_m_s,target_frozen_image_error,max_duration_s)<=0 or
            inversion_time_s<=.008 or not 0<blood_target_max<1 or not 0<wall_target_min<=1 or not 0<=max_interrupted_fraction<=1):
        raise ValueError('finite positive imaging/timing/target inputs required')
    for value,lo,hi in [(axial_spins,33,1601),(rf_steps,16,256),(max_work,1,1000000000),(max_memory_bytes,1,268435456)]:
        if type(value) is not int or not lo<=value<=hi: raise ValueError('bounded integer spin/RF/work/memory settings required')
    if observation_end_s>max_duration_s: raise ValueError('observation duration budget exceeded')
    pipe=WomersleyPipe(radius_m=radius_m,density_kg_m3=density_kg_m3,viscosity_pa_s=viscosity_pa_s,
        mean_gradient_pa_m=mean_gradient_pa_m,oscillating_gradient_pa_m=oscillating_gradient_pa_m,frequency_hz=frequency_hz,phase_rad=phase_rad)
    if fov_m<=2*(radius_m+.001): raise ValueError('FOV must contain the blood and stationary wall cross-section')
    wave=epi_waveform(matrix_size=matrix_size,fov_m=fov_m,dwell_s=dwell_s,venc_m_s=venc_m_s,
        ramp_steps=ramp_steps,max_gradient_t_m=max_gradient_t_m,max_nominal_slew_t_m_s=max_nominal_slew_t_m_s)
    window=.006+wave['duration_s']
    gates=plan_prospective_readouts(r_peaks_s,delay_s=inversion_time_s,observation_end_s=observation_end_s,
        latency_s=trigger_latency_s,initial_rr_s=initial_rr_s,rr_range_s=rr_range_s,window_s=window)
    scheduled=[g for g in gates if g['scheduled']]
    # Conservative preflight before allocating trajectory/state buffers.
    n=matrix_size;p=(np.arange(n)-n//2)*fov_m/n;xx,yy=np.meshgrid(p,p)
    count=int(np.sum(np.hypot(xx,yy)<radius_m+.001))*axial_spins
    planned=(len(scheduled)*(2*rf_steps+2*len(wave['commands'])+n*n+15)+1)*count+len(scheduled)*int(32*n*n*np.log2(n))
    memory=count*512+len(scheduled)*(len(wave['commands'])*256+n*n*512)
    if planned>max_work or memory>max_memory_bytes: raise ValueError('flow-EPI spin/readout work or retained-memory budget exceeded before allocation')
    ensembles,masks,radius=_phantom(pipe,n,fov_m,thickness_m,observation_end_s,axial_spins,max_work,off_resonance_hz)
    inv=selective_sinc(180.,thickness_m=thickness_m,steps=rf_steps)
    exc=selective_sinc(90.,thickness_m=thickness_m,duration_s=.004,steps=rf_steps)
    work=0;executions=[];images=[]
    for i,gate in enumerate(scheduled):
        sign=1 if i%2==0 else -1;row=dict(gate=gate,encoding_sign=sign,tissues={})
        for name,item in ensembles.items():
            spins=item['spins'];before=spins.work;spins.max_work=before+max_work-work
            row['tissues'][name]=_cycle(item,gate,wave,inv,exc,n,thickness_m,sign,preparation);work+=spins.work-before
        if all(t['completed'] for t in row['tissues'].values()):
            image=sum(t['image'] for t in row['tissues'].values());reference=sum(t['frozen_reference'] for t in row['tissues'].values())
            quality=image_quality(reference,image,target_frozen_image_error)
            images.append(dict(trigger=gate['trigger'],encoding_sign=sign,encoding_start_s=row['tissues']['blood']['encoding_start_s'],
                image=image,frozen_reference=reference,quality=quality,
                kspace=sum(t['kspace'] for t in row['tissues'].values()),
                pre_blood_mz=float(np.mean(row['tissues']['blood']['pre_excitation_mz'][masks['blood']].real)),
                pre_wall_mz=float(np.mean(row['tissues']['wall']['pre_excitation_mz'][masks['wall']].real))))
            work+=int(32*n*n*np.log2(n))
        executions.append(row)
    for item in ensembles.values():
        spins=item['spins'];before=spins.work;spins.max_work=before+max_work-work
        if observation_end_s-spins.time>1e-14: spins.advance(observation_end_s-spins.time)
        work+=spins.work-before
    pairs=[]
    for a,b in zip(images,images[1:]):
        if a['encoding_sign']==b['encoding_sign']: continue
        plus=a if a['encoding_sign']==1 else b;minus=b if b['encoding_sign']==-1 else a
        valid=(abs(plus['image'])>=signal_floor)&(abs(minus['image'])>=signal_floor)
        velocity=np.zeros((n,n));velocity[valid]=np.angle(plus['image'][valid]*minus['image'][valid].conj())/(GAMMA*wave['delta_encoding_m1_t_s2_m'])
        reference=np.zeros((n,n));r=radius[masks['blood']];motion=pipe.motion(r)
        encoded=[]
        for snapshot in [plus,minus]:
            phase=np.zeros_like(r);start=snapshot['encoding_start_s']
            for c in wave['commands']:
                if c['kind']=='velocity_encoding':
                    phase+=GAMMA*c['gradient_t_m'][2]*motion.position_integral(np.zeros_like(r),start+c['start_s'],start+c['end_s'])
            encoded.append(phase)
        reference[masks['blood']]=(encoded[0]+encoded[1])/(GAMMA*wave['delta_encoding_m1_t_s2_m'])
        observed=valid&masks['blood'];wall=valid&masks['wall']
        rmse=float(np.sqrt(np.mean((velocity[observed]-reference[observed])**2))) if np.any(observed) else None
        pairs.append(dict(triggers=[plus['trigger'],minus['trigger']],encoding_times_s=[plus['encoding_start_s'],minus['encoding_start_s']],
            velocity_m_s=velocity,valid_mask=valid,gradient_moment_reference_m_s=reference,
            instantaneous_reference_m_s=np.where(masks['blood'],pipe.velocity(np.minimum(radius,pipe.radius),np.mean([plus['encoding_start_s'],minus['encoding_start_s']])),0.),
            velocity_rmse_m_s=rmse,observed_blood_fraction=float(observed.sum()/masks['blood'].sum()),
            measured_grid_flow_m3_s=float(np.sum(velocity[masks['blood']])*(fov_m/n)**2) if np.all(valid[masks['blood']]) else None,
            moment_reference_grid_flow_m3_s=float(np.sum(reference[masks['blood']])*(fov_m/n)**2),
            instantaneous_analytic_pipe_flow_m3_s=pipe.volume_flow_m3_s(np.mean([plus['encoding_start_s'],minus['encoding_start_s']])),
            max_abs_wall_velocity_m_s=float(abs(velocity[wall]).max()) if np.any(wall) else None,
            reference_exceeds_venc=bool(np.any(abs(reference[masks['blood']])>=venc_m_s))))
    fraction=sum(not g['accepted'] for g in scheduled)/len(scheduled) if scheduled else 0.
    validation=dict(passed=False,completed_images=len(images),completed_encoding_pairs=len(pairs),scheduled_preparations=len(scheduled),
        interrupted_fraction=fraction,max_interrupted_fraction=max_interrupted_fraction,
        target_velocity_rmse_m_s=target_velocity_rmse_m_s,target_frozen_image_error=target_frozen_image_error,
        blood_target_max=blood_target_max,wall_target_min=wall_target_min)
    if images:
        validation.update(max_frozen_image_error=max(a['quality']['nrmse'] for a in images),max_abs_blood_mz=max(abs(a['pre_blood_mz']) for a in images),
            min_abs_wall_mz=min(abs(a['pre_wall_mz']) for a in images))
    observed_pairs=bool(pairs and all(a['velocity_rmse_m_s'] is not None and a['observed_blood_fraction']==1. for a in pairs))
    if observed_pairs: validation['max_velocity_rmse_m_s']=max(a['velocity_rmse_m_s'] for a in pairs)
    validation['passed']=bool(observed_pairs and validation['max_velocity_rmse_m_s']<=target_velocity_rmse_m_s and
        validation['max_frozen_image_error']<=target_frozen_image_error and validation['max_abs_blood_mz']<=blood_target_max and
        validation['min_abs_wall_mz']>=wall_target_min and fraction<=max_interrupted_fraction and not any(p['reference_exceeds_venc'] for p in pairs))
    loss=validation.get('max_velocity_rmse_m_s',1.)+validation.get('max_frozen_image_error',1.)+fraction
    inputs=dict(r_peaks_s=list(r_peaks_s),observation_end_s=observation_end_s,inversion_time_s=inversion_time_s,trigger_latency_s=trigger_latency_s,
        initial_rr_s=initial_rr_s,rr_range_s=list(rr_range_s),**pipe.parameters,thickness_m=thickness_m,matrix_size=matrix_size,fov_m=fov_m,
        axial_spins=axial_spins,rf_steps=rf_steps,preparation=preparation,off_resonance_hz=off_resonance_hz,dwell_s=dwell_s,venc_m_s=venc_m_s,ramp_steps=ramp_steps,
        max_gradient_t_m=max_gradient_t_m,max_nominal_slew_t_m_s=max_nominal_slew_t_m_s,signal_floor=signal_floor,
        target_velocity_rmse_m_s=target_velocity_rmse_m_s,target_frozen_image_error=target_frozen_image_error,blood_target_max=blood_target_max,
        wall_target_min=wall_target_min,max_interrupted_fraction=max_interrupted_fraction,max_work=max_work,max_memory_bytes=max_memory_bytes,max_duration_s=max_duration_s)
    if _checked_sources()!=sources: raise ValueError('source changed during flow EPI')
    return dict(clinical_question='Can causal slice-selective DIR and bipolar encoding retain image fidelity and interpretable through-plane flow under pulsatile motion?',
        design=inputs,gates=gates,executions=executions,images=images,velocity_pairs=pairs,validation=validation,objective_loss=loss,
        readout_status=[dict(trigger=r['gate']['trigger'],encoding_sign=r['encoding_sign'],adc_samples=len(r['tissues']['blood']['samples']),
            expected_samples=n*n,completed=r['tissues']['blood']['completed'],stage=r['tissues']['blood']['stage']) for r in executions],
        scope='teaching/research rigid Newtonian pipe; fixed transverse voxel centers, finite slice RF and exact axial phase per gradient hold, point ADC EPI; paired images may come from different cardiac times; no coils/noise/eddy currents/transverse motion/clinical or scanner certification; B/C parked',
        provenance=dict(version='causal-flow-epi-v1',replay=inputs,input_hash=_hash(inputs),sources=sources,runtime=runtime_manifest(),
            waveform=wave,estimated_work=work,planned_work=planned,estimated_peak_memory_bytes=memory,
            masks={k:v.tolist() for k,v in masks.items()},reservoir='finite no-wrap voxel-specific bounds and cell/slab overlap divided by declared thickness; no receiver renormalization',
            final_state_hashes={k:_hash(v['spins'].state.tolist()) for k,v in ensembles.items()},
            actual_finite_rf_energy_uT2_s=sum(row['tissues']['blood']['finite_rf_energy_uT2_s'] for row in executions),
            actual_hard_inversions=sum(row['tissues']['blood']['preparation_started'] and preparation=='dir' for row in executions),
            actual_encoding_readout_gradient_energy_t2_s_m2=sum(row['tissues']['blood']['readout_gradient_energy_t2_s_m2'] for row in executions),
            inverse='unscaled centered inverse FFT of measured EPI kspace; no truth image, gain fit, static-amplitude or motion correction',
            velocity='wrapped phase of opposite-sign complete images / (gamma*delta M1); valid mask from measured magnitudes only; moment and instantaneous references evaluated separately'))
