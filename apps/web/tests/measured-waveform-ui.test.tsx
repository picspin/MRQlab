import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createScientificRecord, fetchMeasuredWaveformExample, getScientificRecord, listScientificRecords } from "../lib/api";
import { DeriveWaveformStudy, DerivedWaveformEvidence, parseWaveformEvidence } from "../components/research/DerivedWaveformStudy";
import RecordsPage from "../app/research/records/page";
import type { ScientificRecord, ScientificResponse } from "../lib/scientific-records";

vi.mock("../lib/api", () => ({ createScientificRecord: vi.fn(), fetchMeasuredWaveformExample: vi.fn(), getScientificRecord: vi.fn(), importScientificRecord: vi.fn(), listScientificRecords: vi.fn(), replayScientificRecord: vi.fn() }));
const id="a".repeat(64), childId="b".repeat(64);
const parent={record_sha256:id,summary:{study_id:"lab-1",mode:"measured_tse",research_question:"T2 lab",input_origins:["synthetic"]}} as unknown as ScientificRecord;
const template={study:{search:{scales:[.1,.5,1]},max_parent_work:1000000},parent:{tissue_ids:["white","gray"],origin:"synthetic",source_ref:"synthetic:cpmg"},scope:"synthetic"};
const evidence={measurement:{origin:"synthetic",source_ref:"synthetic:cpmg",raw_file_sha256:null},
 parent_revalidation:{passed:true,calibration_and_holdout_passed:true,parent_search_complete:true,estimated_work:100,reserved_work:1000,within_max_parent_work:true},
 bindings:[{tissue_id:"white",value:.04,standard_uncertainty_s:.001,stress_interval_s:[.038,.042]},{tissue_id:"gray",value:.12,standard_uncertainty_s:.002,stress_interval_s:[.116,.124]}],
 stress_scenarios:[{id:"nominal",t2_s:[.04,.12]}],stress_runs:[{id:"nominal",result:{candidates:[{index:0,scenarios:[{id:"nominal",target_passed:true,refinement_passed:true,max_signal_difference:1e-9,max_image_difference:2e-9,refined:{validation:{image_target:{measured:.04}}}}]}]}}],
 candidates:[{index:0,scale:.5,executed:true,eligible:false,reasons:["corner failed"],stress_outcomes:[{id:"nominal",executable:true,eligible:true,reasons:[]},{id:"corner_0",executable:true,eligible:false,reasons:["target failed"]}]}],
 selected_index:null,validation:{passed:false,calibration_and_holdout_passed:true,complete_grid:true,reasons:[]},work:{total_voxel_steps:1000,preflight_voxel_steps:1000,max_total_voxel_steps:2000}};
const record={...parent,record_sha256:childId,request_json:"{}",payload_json:JSON.stringify({derivation:evidence}),request_sha256:"1",payload_sha256:"2",api_source_hash:"3",sources:{sha256:"4",files:{}},runtime:{},stages:[],summary:{...parent.summary,mode:"measured_waveform_image",kind:"measured_waveform_image",selected_index:null,model_reported_passed:false,parent_record_sha256:id,candidate_count:1,scope:"research only",candidates:[{index:0,executable:true,model_reported_passed:false,reasons:["corner failed"]}]}} as unknown as ScientificRecord;
const view={images:[{label:"Synthetic reconstruction",width:2,height:2,values:[0,1,2,3]}],curves:[],x_label:"Time",y_label:"Signal",metrics:{},validation:{passed:false,calibration_and_holdout_passed:true,complete_grid:true,reasons:[]}};
const response={record,verification:{integrity_passed:true,computational_replay_performed:false},view} as unknown as ScientificResponse;
beforeEach(()=>{vi.resetAllMocks();vi.mocked(fetchMeasuredWaveformExample).mockResolvedValue(template);vi.mocked(createScientificRecord).mockResolvedValue(response);});
afterEach(()=>cleanup());

describe("measured waveform workflow",()=>{
 it("loads a labelled synthetic template and submits it against the selected parent",async()=>{
  const created=vi.fn();render(<DeriveWaveformStudy parent={parent} onCreated={created}/>);
  expect(screen.getByRole("button",{name:"计算并保存波形研究"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button",{name:"载入合成波形模板"}));await screen.findByText(/父数据：合成/);
  expect(fetchMeasuredWaveformExample).toHaveBeenCalledWith(id,expect.any(AbortSignal));
  fireEvent.change(screen.getByLabelText("波形目标依据"),{target:{value:"声明的合成对比度"}});
  fireEvent.click(screen.getByRole("button",{name:"计算并保存波形研究"}));await waitFor(()=>expect(created).toHaveBeenCalledWith(response));
  expect(createScientificRecord).toHaveBeenCalledWith(expect.objectContaining({execution:{type:"measured_waveform_image",parent_record_sha256:id,study:template.study}}),expect.any(AbortSignal));
 });
 it("aborts an in-flight template request on unmount",()=>{
  vi.mocked(fetchMeasuredWaveformExample).mockReturnValue(new Promise(()=>{}));const rendered=render(<DeriveWaveformStudy parent={parent} onCreated={vi.fn()}/>);
  fireEvent.click(screen.getByRole("button",{name:"载入合成波形模板"}));const signal=vi.mocked(fetchMeasuredWaveformExample).mock.calls[0][1];
  expect(signal?.aborted).toBe(false);rendered.unmount();expect(signal?.aborted).toBe(true);
 });
 it("shows failed corners without inventing a selected image",()=>{
  const parsed=parseWaveformEvidence(JSON.stringify({derivation:evidence}));expect(parsed).not.toBeNull();render(<DerivedWaveformEvidence evidence={parsed!}/>);
  expect(screen.getByText(/来源：合成数据/)).toBeInTheDocument();expect(screen.getByText(/corner_0：未通过/)).toBeInTheDocument();
  expect(screen.queryByText(/（已选）/)).not.toBeInTheDocument();expect(screen.getByText(/两种工作单位不相加/)).toBeInTheDocument();
 });
 it("rejects malformed nested evidence",()=>{
  const broken=structuredClone(evidence);(broken.stress_runs[0].result.candidates[0] as unknown as {scenarios:unknown}).scenarios=null;
  expect(parseWaveformEvidence(JSON.stringify({derivation:broken}))).toBeNull();
 });
 it("renders a linked record despite its nested validation fields",async()=>{
  vi.mocked(listScientificRecords).mockResolvedValue({total:1,offset:0,limit:20,records:[{record_sha256:childId,created_ns:1,bytes:1,summary:record.summary,integrity_checked:false,computational_replay_performed:false}]});
  const successfulEvidence={...evidence,selected_index:0,validation:{...evidence.validation,passed:true},candidates:evidence.candidates.map(c=>({...c,eligible:true}))};
  vi.mocked(getScientificRecord).mockResolvedValue({...response,record:{...record,payload_json:JSON.stringify({derivation:successfulEvidence})},view:{...view,validation:{...view.validation,passed:true}}} as unknown as ScientificResponse);render(<RecordsPage/>);fireEvent.click(await screen.findByRole("button",{name:/lab-1/}));
  await screen.findByRole("region",{name:"T2 校准与波形搜索证据"});expect(screen.getByRole("img",{name:"Synthetic reconstruction"})).toBeInTheDocument();
  expect(screen.queryByText("记录载荷缺少可安全显示的测量结构。")).not.toBeInTheDocument();expect(screen.getByText("尚未确认")).toBeInTheDocument();
 });
 it("hides an inconsistent preview when no candidate was selected",async()=>{
  vi.mocked(listScientificRecords).mockResolvedValue({total:1,offset:0,limit:20,records:[{record_sha256:childId,created_ns:1,bytes:1,summary:record.summary,integrity_checked:false,computational_replay_performed:false}]});
  vi.mocked(getScientificRecord).mockResolvedValue(response);render(<RecordsPage/>);fireEvent.click(await screen.findByRole("button",{name:/lab-1/}));
  expect(await screen.findByRole("alert")).toHaveTextContent("波形预览与验证结果不一致");expect(screen.queryByRole("img",{name:"Synthetic reconstruction"})).not.toBeInTheDocument();
 });
 it("does not render a preview when the study evidence is malformed",async()=>{
  vi.mocked(listScientificRecords).mockResolvedValue({total:1,offset:0,limit:20,records:[{record_sha256:childId,created_ns:1,bytes:1,summary:record.summary,integrity_checked:false,computational_replay_performed:false}]});
  vi.mocked(getScientificRecord).mockResolvedValue({...response,record:{...record,payload_json:'{"derivation":{}}'}});
  render(<RecordsPage/>);fireEvent.click(await screen.findByRole("button",{name:/lab-1/}));
  expect(await screen.findByRole("alert")).toHaveTextContent("波形研究证据结构不完整");
  expect(screen.queryByRole("img",{name:"Synthetic reconstruction"})).not.toBeInTheDocument();
 });
});
