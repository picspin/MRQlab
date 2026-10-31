"""Exact finite-ADC/known-field/known-coil reference encoding, not a NUFFT.

No labels, spatial support, image reference, density compensation or gain fit.
Weights may be any full-rank temporal coordinates of independent complex maps.
"""
import numpy as np
from .noncartesian import _cgls


class ReadoutEncodingOperator:
    def __init__(self,coordinates,spatial_shape,weights,offsets_s,field_hz,coils,*,
                 max_work=20000000000,max_memory_bytes=134217728):
        if np.iscomplexobj(coordinates) or np.iscomplexobj(field_hz) or np.iscomplexobj(offsets_s): raise ValueError('real coordinates, time offsets and field map required')
        shape=tuple(spatial_shape);k=np.asarray(coordinates,float);w=np.asarray(weights,complex)
        times=np.asarray(offsets_s,float);field=np.asarray(field_hz,float);sens=np.asarray(coils,complex)
        if len(shape) not in (2,3) or any(type(n) is not int or n<2 for n in shape): raise ValueError('bounded 2D/3D spatial shape required')
        if k.ndim!=2 or k.shape[1]!=len(shape) or not len(k) or np.any(abs(k)>.5) or not np.isfinite(k).all():
            raise ValueError('finite centered coordinates in array-axis order within Nyquist required')
        if w.ndim!=2 or not 1<=len(w)<=4 or w.shape[1]!=len(k) or not np.isfinite(w).all(): raise ValueError('one-to-four compatible temporal weight rows required')
        singular=np.linalg.svd(w,compute_uv=False)
        if singular[-1]<=singular[0]*1e-10: raise ValueError('temporal basis is rank deficient')
        if times.shape!=(len(k),) or field.shape!=shape or sens.ndim!=len(shape)+1 or sens.shape[1:]!=shape or not 1<=len(sens)<=4 or not all(np.isfinite(a).all() for a in [times,field,sens]):
            raise ValueError('compatible finite ADC offsets, field in Hz and one-to-four complex coil maps required')
        if np.any(np.sum(abs(sens)**2,axis=0)<1e-12): raise ValueError('coil maps have a jointly unobservable voxel')
        for b in [max_work,max_memory_bytes]:
            if type(b) is not int or b<=0: raise ValueError('positive integer reference budgets required')
        m=len(k);v=int(np.prod(shape));components=len(w);nc=len(sens)
        self.estimated_memory_bytes=int(32*m*v+128*m*nc+128*components*v+64*nc*v+32*components*m+64*min(m,128)*v)
        self.operation_work=int(nc*components*(m*v+2*m+v));setup=int(8*m*v)
        if self.estimated_memory_bytes>max_memory_bytes: raise ValueError('finite-ADC dense reference memory budget exceeded before allocation')
        if setup+2*self.operation_work>max_work: raise ValueError('finite-ADC reference setup/validation work budget exceeded')
        self.max_work=max_work;self.work=setup;self.shape=(components,*shape);self.sample_shape=(nc,m)
        self.weights=w.copy();self.coils=sens.reshape(nc,v).copy();self.temporal_condition=float(singular[0]/singular[-1])
        positions=np.stack(np.meshgrid(*(np.arange(n)-n//2 for n in shape),indexing='ij'),axis=-1).reshape(v,len(shape))
        self.matrix=np.empty((m,v),complex)
        for start in range(0,m,128):
            stop=min(m,start+128)
            self.matrix[start:stop]=np.exp(-2j*np.pi*(k[start:stop]@positions.T)+2j*np.pi*times[start:stop,None]*field.ravel())
        self.matrix_h=self.matrix.conj().T
        for a in [self.matrix,self.matrix_h,self.weights,self.coils]: a.flags.writeable=False

    def _charge(self):
        if self.work+self.operation_work>self.max_work: raise ValueError('finite-ADC reference work budget exceeded')
        self.work+=self.operation_work

    def forward(self,coefficients):
        x=np.asarray(coefficients,complex)
        if x.shape!=self.shape or not np.isfinite(x).all(): raise ValueError('finite unrestricted complex coefficient maps required')
        self._charge();x=x.reshape(len(self.weights),-1)
        return np.array([sum(w*(self.matrix@(s*c)) for w,c in zip(self.weights,x)) for s in self.coils])

    def adjoint(self,samples):
        data=np.asarray(samples,complex)
        if data.shape!=self.sample_shape or not np.isfinite(data).all(): raise ValueError('compatible finite multicoil samples required')
        self._charge()
        return np.array([sum(s.conj()*(self.matrix_h@(w.conj()*row)) for s,row in zip(self.coils,data)) for w in self.weights]).reshape(self.shape)

    def diagnostics(self):
        return dict(backend='exact finite-ADC DFT reference',components=len(self.weights),coils=len(self.coils),temporal_condition=self.temporal_condition,
            model='sum_j weights[j,m] sum_r coil[c,r] coefficient[j,r] exp(-2pi i k_m.r +2pi i field[r] offset[m])',
            gain_fit=False,regularization=0.,spatial_support='not supplied',normalization='unnormalized complex sum; no coil/RSS normalization')


def readout_cgls(coordinates,samples,spatial_shape,weights,offsets_s,field_hz,coils,*,
                 max_iterations=6000,tolerance=1e-10,max_work=20000000000,max_memory_bytes=134217728):
    if type(max_iterations) is not int or max_iterations<1 or isinstance(tolerance,bool) or not np.isfinite(tolerance) or not 0<tolerance<1:
        raise ValueError('positive integer iterations and relative data tolerance required')
    op=ReadoutEncodingOperator(coordinates,spatial_shape,weights,offsets_s,field_hz,coils,max_work=max_work,max_memory_bytes=max_memory_bytes)
    data=np.asarray(samples,complex)
    if data.shape!=op.sample_shape or not np.isfinite(data).all(): raise ValueError('compatible finite multicoil data required')
    result,diagnostics=_cgls(op,data,max_iterations,tolerance,'exact finite-ADC multicoil reference CGLS')
    diagnostics['operator']=op.diagnostics();return result,diagnostics
