"use client";
import {useEffect,useState} from "react";
export function Status(){const [text,setText]=useState("API OFFLINE");useEffect(()=>{fetch(`${process.env.NEXT_PUBLIC_API_URL||"http://localhost:8000"}/health`).then(r=>r.ok&&setText("BLOCH ENGINE READY")).catch(()=>{})},[]);return <div className="status"><i className={text.includes("READY")?"ready":""}/>{text}</div>}
