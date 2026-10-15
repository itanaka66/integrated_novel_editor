"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { getPendingLoads, subscribePageLoading } from "../lib/pageLoading";
import { t } from "../lib/i18n";

const SHOW_AFTER_MS = 350; // a fast load never flashes the overlay
const MIN_VISIBLE_MS = 400; // once shown, stay long enough to read as one step

// Centered progress bar over a click-blocking backdrop while the data a screen
// needs is being fetched, so it is clear nothing can be operated yet.
export default function PageLoadingOverlay() {
  const pending = useSyncExternalStore(subscribePageLoading, getPendingLoads, () => 0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (pending > 0) {
      if (visible) return;
      const timer = setTimeout(() => setVisible(true), SHOW_AFTER_MS);
      return () => clearTimeout(timer);
    }
    if (!visible) return;
    const timer = setTimeout(() => setVisible(false), MIN_VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [pending, visible]);

  if (!visible) return null;
  return (
    <div className="pageLoadingOverlay" role="status" aria-live="polite" aria-busy="true">
      <div className="pageLoadingCard">
        <b>{t("情報を取得中...")}</b>
        <small>{t("読み込みが終わるまで操作できません")}</small>
        <div className="pageLoadingBar"><i /></div>
      </div>
    </div>
  );
}
