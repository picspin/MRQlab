"use client";
import {useState} from "react";
export function Knob({label, value}:{label:string,value:string}) { return <div className="control"><div className="knob"><i /></div><b>{label}</b><output>{value}</output></div> }
export function RealitySlider(){const [v,setV]=useState(25);return <div className="reality"><label>REALITY</label><input aria-label="Reality, ideal to real" type="range" value={v} onChange={e=>setV(+e.target.value)}/><div><span>IDEAL</span><span>REAL</span></div></div>}
