"use client";
import { PUBLISH_TARGETS } from "../lib/publishTargets";
import { t } from "../lib/i18n";

// Popup with the details of each posting destination. Links open in a new tab;
// nothing is posted or logged into from here.
export default function PublishTargetsDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard" style={{ width: "min(900px, 96vw)", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{t("投稿先の詳細")}</h3>
        <p style={{ fontSize: 12, color: "#566273", margin: "4px 0 10px" }}>{t("各サービスの対応言語や注意事項のメモです。内容は変わることがあるため、最新情報は各公式ページで確認してください。")}</p>
        {PUBLISH_TARGETS.map((x) => (
          <div key={x.name} className="resultCard" style={{ marginBottom: 10 }}>
            <b>{x.name}</b>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "4px 0 8px" }}>
              <a href={x.postUrl} target="_blank" rel="noopener noreferrer">{t("登録・投稿ページ")}</a>
              <a href={x.officialUrl} target="_blank" rel="noopener noreferrer">{t("公式サイト")}</a>
              <a href={x.helpUrl} target="_blank" rel="noopener noreferrer">{t("公式ヘルプ")}</a>
            </div>
            <table className="entityTable" style={{ width: "100%" }}>
              <tbody>
                <tr><th style={{ width: 150, textAlign: "left" }}>{t("投稿方式")}</th><td>{x.method}</td></tr>
                <tr><th style={{ textAlign: "left" }}>{t("対応言語（8言語）")}</th><td>{x.languages}</td></tr>
                <tr><th style={{ textAlign: "left" }}>{t("言語指定方法")}</th><td>{x.languageSetting}</td></tr>
                <tr><th style={{ textAlign: "left" }}>{t("翻訳配信")}</th><td>{x.translation}</td></tr>
                <tr><th style={{ textAlign: "left" }}>{t("注意事項")}</th><td>{x.caution}</td></tr>
              </tbody>
            </table>
          </div>
        ))}
        <div className="modalActions"><button onClick={onClose}>{t("閉じる")}</button></div>
      </div>
    </div>
  );
}
