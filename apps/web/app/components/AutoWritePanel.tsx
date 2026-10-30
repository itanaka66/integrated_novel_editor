"use client";
import { useEffect, useRef, useState } from "react";
import { api, post, streamSSE } from "../lib/api";
import { ensureNotificationPermission, notify } from "../lib/notify";
import { getLanguage, t } from "../lib/i18n";

const LOCALE_INSTRUCTIONS: Record<string, string> = {
  en: "Write in English.",
  "zh-CN": "请用简体中文撰写。",
  "zh-TW": "請用繁體中文撰寫。",
  ko: "한국어로 작성해주세요。",
  es: "Escribe en español.",
  fr: "Rédigez en français.",
  de: "Schreibe auf Deutsch.",
};

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
  const [startEpisode, setStartEpisode] = useState(1);
  const [endEpisode, setEndEpisode] = useState(500);
  // Default the range to the work's own episode goal (not a fixed 500).
  useEffect(() => { api(`/projects/${projectId}`).then((p) => { if (p?.episode_goal) setEndEpisode(p.episode_goal); }).catch(() => {}); }, [projectId]);
  const [premise, setPremise] = useState("");
  const [overwrite, setOverwrite] = useState(false);
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

  async function createJob() {
    setBusy(true);
    ensureNotificationPermission();
    const localeInstruction = LOCALE_INSTRUCTIONS[getLanguage()] ?? "";
    const finalPremise = localeInstruction ? (premise ? `${premise}\n${localeInstruction}` : localeInstruction) : premise;
    try {
      const x = await post("/auto-write/start", {
        project_id: projectId, start_episode: startEpisode, end_episode: endEpisode, premise: finalPremise, overwrite,
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
        <b>{t("500話 自動執筆（Anna AI OS）")}</b>
        <p>{t("Anna AI OS が自動執筆を実行します。Series → Arc → Mini Arc → Episode の階層計画を立て、Writer が EP 単位で本文を生成し、Controller が時系列・人物・世界観・プロットを監査します。")}</p>
        <div className="card autoWriteAnnaHint">
          <b>▶ {t("実行方法")}</b>
          <ol>
            <li>{t("下のフォームでジョブを作成してください。")}</li>
            <li>{t("Anna に「auto_write_step でジョブ {id} を実行してください」と依頼してください。", { id: job ? `ID: ${job.id}` : "（作成後に ID が表示されます）" })}</li>
            <li>{t("Anna が完了するまで auto_write_step を繰り返し呼び出します。")}</li>
          </ol>
        </div>
        <div className="autoWriteFields">
          <label>{t("開始EP")}<input type="number" value={startEpisode} min={1} onChange={(x) => setStartEpisode(Number(x.target.value))} disabled={!!active} /></label>
          <label>{t("終了EP")}<input type="number" value={endEpisode} min={startEpisode} onChange={(x) => setEndEpisode(Number(x.target.value))} disabled={!!active} /></label>
          <label className="autoWriteOverwrite"><input type="checkbox" checked={overwrite} onChange={(x) => setOverwrite(x.target.checked)} disabled={!!active} /> {t("既存エピソードを上書き")}</label>
        </div>
        <textarea className="instruction" value={premise} onChange={(x) => setPremise(x.target.value)} placeholder={t("追加方針（任意）：世界観の補足や外せない大筋があれば入力")} disabled={!!active} />
        {active ? (
          <button className="check" disabled style={{ opacity: 0.4, cursor: "not-allowed" }}>{t("■ 停止する（EP.{n}）", { n: job.current_episode })}</button>
        ) : (
          <button className="add" disabled style={{ opacity: 0.4, cursor: "not-allowed" }}>{busy ? t("作成中...") : t("＋ ジョブを作成")}</button>
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
