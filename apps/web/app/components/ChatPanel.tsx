"use client";
import { useState } from "react";
import { post } from "../lib/api";

type Msg = { role: "user" | "assistant"; text: string };

export default function ChatPanel({ projectId }: { projectId: number }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy(true);
    try {
      const x = await post("/ai/generate", { project_id: projectId, instruction: text, mode: "custom", rag_limit: 8 });
      setMessages((m) => [...m, { role: "assistant", text: x.text || x.detail || "(応答なし)" }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "エラーが発生しました。AIサービスの状態を確認してください。" }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel chatPanel">
      <small>AI CHAT</small>
      <h1>AIチャット</h1>
      <p>Context Builder（本文・人物・世界観・プロット・伏線・RAG）を踏まえた自由対話です。会話履歴はこの画面を閉じると失われます。</p>
      <div className="chatMessages">
        {messages.length === 0 && <div className="card"><b>質問してみましょう</b><p>例：「田中の現在の目標は？」「第3話の伏線はまだ回収されていない？」</p></div>}
        {messages.map((m, i) => <div className={`chatBubble ${m.role}`} key={i}><b>{m.role === "user" ? "あなた" : "AI"}</b><p>{m.text}</p></div>)}
        {busy && <div className="chatBubble assistant"><b>AI</b><p className="thinking">考えています...</p></div>}
      </div>
      <div className="chatInputRow">
        <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} placeholder="質問を入力..." disabled={busy} />
        <button onClick={send} disabled={busy}>送信</button>
      </div>
    </div>
  );
}
