"use client";
import { useEffect, useRef, useState } from "react";
import { api, post, streamSSE } from "../lib/api";
import { loadModelDefaults } from "../lib/modelDefaults";
import { ensureNotificationPermission, notify } from "../lib/notify";
import { t } from "../lib/i18n";

const PHASE_LABEL: any = {
  queued: t("待機中"), series_planner: t("Series Planner（全体構成）"), arc_planner: "Arc / Mini Arc / Episode Planner",
  controller_preflight: t("Controller 事前監査"), writer: t("Writer 執筆中"), controller_gate: t("Controller 最終監査"),
  completed: t("完了"), stopped: t("停止"), error: t("エラー"),
};
const ACTIVE_STATUSES = ["queued", "running", "stopping"];
const TERMINAL_STATUSES = ["completed", "stopped", "error"];

export default function AutoWritePanel({ projectId }: { projectId: number }) {
  const [jobs, setJobs] = useState<any[]>([]);
  const [job, setJob] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const defaults = loadModelDefaults();
  const [startEpisode, setStartEpisode] = useState(1);
  const [endEpisode, setEndEpisode] = useState(500);
  const [premise, setPremise] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [writerModel, setWriterModel] = useState(defaults.writer);
  const [controllerModel, setControllerModel] = useState(defaults.controller);
  const notifiedJobIds = useRef<Set<number>>(new Set());

  async function loadJobs() {
    const list = await api(`/projects/${projectId}/auto-write/jobs`);
    setJobs(list);
    const active = list.find((j: any) => ACTIVE_STATUSES.includes(j.status));
    if (active) setJob(active);
  }
  useEffect(() => { loadJobs(); }, [projectId]);
  useEffect(() => {
    if (!job || !ACTIVE_STATUSES.includes(job.status)) return;
    // Server-Sent Events instead of polling: the backend pushes an update
    // every ~1.5s while the job is active and closes the stream once it
    // finishes, so we don't need our own interval/cleanup logic here.
    const stop = streamSSE(`/auto-write/${job.id}/stream`, (data: any) => {
      if (data.error) return;
      setJob(data);
      setJobs((js) => js.map((j) => (j.id === data.id ? data : j)));
      if (TERMINAL_STATUSES.includes(data.status) && !notifiedJobIds.current.has(data.id)) {
        notifiedJobIds.current.add(data.id);
        notify(
          data.status === "completed" ? t("自動執筆が完了しました") : data.status === "error" ? t("自動執筆でエラーが発生しました") : t("自動執筆を停止しました"),
          t("EP.{from}–{to}（{n}話 完了）", { from: data.start_episode, to: data.end_episode, n: data.episodes_written }),
        );
      }
    });
    return stop;
  }, [job?.id]);

  async function start() {
    setBusy(true);
    ensureNotificationPermission();
    try {
      const x = await post("/auto-write/start", {
        project_id: projectId, start_episode: startEpisode, end_episode: endEpisode, premise, overwrite,
        writer_model: writerModel, controller_model: controllerModel,
      });
      setJob(x);
      setJobs((js) => [x, ...js]);
    } finally { setBusy(false); }
  }
  async function stop() { if (!job) return; setJob(await post(`/auto-write/${job.id}/stop`, {})); }

  const active = job && ACTIVE_STATUSES.includes(job.status);
  return (
    <div className="autoWrite">
      <div className="card autoWriteForm">
        <b>{t("500話 自動執筆（A770 Controller × RTX3090 Writer）")}</b>
        <p>{t("Series → Arc(100話) → Mini Arc(10話) → Episode Planner の階層計画をControllerが管理し、WriterがEP単位で本文を生成します。Controllerが時系列・人物・世界観・プロットを監査し、BLOCK時は自動で修正します。")}</p>
        <div className="autoWriteFields">
          <label>{t("開始EP")}<input type="number" value={startEpisode} min={1} onChange={(x) => setStartEpisode(Number(x.target.value))} disabled={!!active} /></label>
          <label>{t("終了EP")}<input type="number" value={endEpisode} min={startEpisode} onChange={(x) => setEndEpisode(Number(x.target.value))} disabled={!!active} /></label>
          <label>Writer<input value={writerModel} onChange={(x) => setWriterModel(x.target.value)} disabled={!!active} /></label>
          <label>Controller<input value={controllerModel} onChange={(x) => setControllerModel(x.target.value)} disabled={!!active} /></label>
          <label className="autoWriteOverwrite"><input type="checkbox" checked={overwrite} onChange={(x) => setOverwrite(x.target.checked)} disabled={!!active} /> {t("既存エピソードを上書き")}</label>
        </div>
        <textarea className="instruction" value={premise} onChange={(x) => setPremise(x.target.value)} placeholder={t("追加方針（任意）：世界観の補足や外せない大筋があれば入力")} disabled={!!active} />
        {active ? (
          <button className="check" onClick={stop}>{t("■ 停止する（EP.{n}）", { n: job.current_episode })}</button>
        ) : (
          <button className="add" onClick={start} disabled={busy}>{busy ? t("起動中...") : t("▶ 自動執筆を開始")}</button>
        )}
      </div>
      {job && (
        <div className="card autoWriteProgress">
          <div className="autoWriteStatus"><b>EP.{job.start_episode}–{job.end_episode}</b><span className={`badge ${job.status}`}>{job.status}</span></div>
          <div className="progress"><i style={{ width: `${job.progress_percent}%` }} /></div>
          <p>{t("{pct}% ・ {done}/{total}話 完了 ・ フェーズ：{phase}", { pct: job.progress_percent, done: job.completed_episodes, total: job.total_episodes, phase: PHASE_LABEL[job.current_phase] || job.current_phase })}</p>
          <div className="autoWriteStats">
            <div><small>SERIES</small><b>{job.series_planned ? t("済") : t("未")}</b></div>
            <div><small>ARCS</small><b>{job.arcs_planned}/5</b></div>
            <div><small>MINI ARCS</small><b>{job.mini_arcs_planned}/50</b></div>
            <div><small>EPISODE PLANS</small><b>{job.episodes_planned}</b></div>
            <div><small>WRITTEN</small><b>{job.episodes_written}</b></div>
          </div>
          <p className="autoWriteMessage">{job.last_message}</p>
        </div>
      )}
      {jobs.length > 0 && (
        <div className="card autoWriteHistory">
          <small>{t("直近のジョブ")}</small>
          {jobs.map((j) => <div className="autoWriteHistoryRow" key={j.id} onClick={() => setJob(j)}><span className={`badge ${j.status}`}>{j.status}</span><b>EP.{j.start_episode}–{j.end_episode}</b><span>{j.progress_percent}%</span></div>)}
        </div>
      )}
    </div>
  );
}
