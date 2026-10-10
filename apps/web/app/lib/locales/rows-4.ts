import type { Row } from "./types";

// ja, en, zh-CN, zh-TW, ko, es, fr, de
export const ROWS_4: Row[] = [
  // WritePanel
  ["⏱ 時系列チェック", "⏱ Timeline check", "⏱ 时间线检查", "⏱ 時間軸檢查", "⏱ 시계열 점검", "⏱ Revisión de cronología", "⏱ Vérification chronologique", "⏱ Zeitleisten-Check"],
  ["♟ 人物状態チェック", "♟ Character state check", "♟ 人物状态检查", "♟ 人物狀態檢查", "♟ 인물 상태 점검", "♟ Revisión de estados de personajes", "♟ Vérification des états des personnages", "♟ Figurenzustands-Check"],
  ["🌐 世界観チェック", "🌐 World-building check", "🌐 世界观检查", "🌐 世界觀檢查", "🌐 세계관 점검", "🌐 Revisión del mundo", "🌐 Vérification de l'univers", "🌐 Welt-Check"],
  ["◎ 伏線チェック", "◎ Foreshadowing check", "◎ 伏笔检查", "◎ 伏筆檢查", "◎ 복선 점검", "◎ Revisión de presagios", "◎ Vérification des indices", "◎ Foreshadowing-Check"],
  ["◆ プロット整合", "◆ Plot consistency", "◆ 情节一致性", "◆ 情節一致性", "◆ 플롯 정합성", "◆ Coherencia de la trama", "◆ Cohérence de l'intrigue", "◆ Handlungs-Konsistenz"],
  ["✎ 文章品質チェック", "✎ Writing quality check", "✎ 文章质量检查", "✎ 文章品質檢查", "✎ 문장 품질 점검", "✎ Revisión de la calidad del texto", "✎ Vérification de la qualité rédactionnelle", "✎ Textqualitäts-Check"],
  ["選択した{n}件のエピソードを削除しますか？残りのエピソードの話数は自動的に詰められます。", "Delete the {n} selected episodes? The numbering of the remaining episodes will be closed up automatically.", "要删除所选的 {n} 个章节吗？其余章节的话数会自动顺延补齐。", "要刪除所選的 {n} 個章節嗎？其餘章節的話數會自動遞補。", "선택한 에피소드 {n}건을 삭제하시겠습니까? 나머지 에피소드의 화수는 자동으로 당겨집니다.", "¿Eliminar los {n} episodios seleccionados? La numeración de los restantes se ajustará automáticamente.", "Supprimer les {n} épisodes sélectionnés ? La numérotation des épisodes restants sera réajustée automatiquement.", "Die {n} ausgewählten Episoden löschen? Die Nummerierung der übrigen Episoden rückt automatisch nach."],
  ["エピソードタイトル", "Episode title", "章节标题", "章節標題", "에피소드 제목", "Título del episodio", "Titre de l'épisode", "Episodentitel"],
  ["この版に復元しますか？現在の内容は履歴として保存されます。", "Restore this version? The current content will be saved to the history.", "要恢复到此版本吗？当前内容会保存到历史记录中。", "要還原到此版本嗎？目前內容會儲存到歷史記錄中。", "이 버전으로 복원하시겠습니까? 현재 내용은 이력으로 저장됩니다.", "¿Restaurar esta versión? El contenido actual se guardará en el historial.", "Restaurer cette version ? Le contenu actuel sera enregistré dans l'historique.", "Diese Version wiederherstellen? Der aktuelle Inhalt wird im Verlauf gespeichert."],
  ["エピソードがまだありません。", "There are no episodes yet.", "还没有章节。", "尚無章節。", "아직 에피소드가 없습니다.", "Todavía no hay episodios.", "Il n'y a pas encore d'épisode.", "Es gibt noch keine Episoden."],
  ["＋ エピソードを追加", "+ Add episode", "＋ 添加章节", "＋ 新增章節", "+ 에피소드 추가", "+ Añadir episodio", "+ Ajouter un épisode", "+ Episode hinzufügen"],
  ["＋ 新規エピソード", "+ New episode", "＋ 新章节", "＋ 新章節", "+ 새 에피소드", "+ Nuevo episodio", "+ Nouvel épisode", "+ Neue Episode"],
  ["削除中...", "Deleting...", "删除中...", "刪除中...", "삭제 중...", "Eliminando...", "Suppression...", "Wird gelöscht..."],
  ["選択した{n}件を削除（話数を自動調整）", "Delete {n} selected (renumber automatically)", "删除所选的 {n} 项（自动调整话数）", "刪除所選的 {n} 項（自動調整話數）", "선택한 {n}건 삭제(화수 자동 조정)", "Eliminar {n} seleccionados (renumerar automáticamente)", "Supprimer les {n} sélectionnés (renumérotation automatique)", "{n} ausgewählte löschen (automatisch neu nummerieren)"],
  ["品質チェック", "Quality check", "质量检查", "品質檢查", "품질 점검", "Revisión de calidad", "Contrôle qualité", "Qualitätsprüfung"],
  ["🕘 履歴", "🕘 History", "🕘 历史", "🕘 歷史", "🕘 이력", "🕘 Historial", "🕘 Historique", "🕘 Verlauf"],
  ["スタイルガイドと照合し、差分を1件ずつ確認しながら修正します", "Checks against the style guide and lets you review and fix the differences one by one", "与风格指南核对，并逐条确认差异后进行修改", "與風格指南核對，並逐條確認差異後進行修改", "스타일 가이드와 대조하여 차이를 한 건씩 확인하며 수정합니다", "Compara con la guía de estilo y permite revisar y corregir las diferencias una por una", "Compare avec le guide de style et permet de relire et corriger les différences une par une", "Gleicht mit dem Styleguide ab und lässt Sie Abweichungen einzeln prüfen und korrigieren"],
  ["📐 文章校正", "📐 Proofread", "📐 文章校对", "📐 文章校對", "📐 문장 교정", "📐 Revisar texto", "📐 Relecture", "📐 Textkorrektur"],
  ["保存中", "Saving", "保存中", "儲存中", "저장 중", "Guardando", "Enregistrement", "Speichert"],
  ["保存＋人物状態更新", "Save + update character states", "保存＋更新人物状态", "儲存＋更新人物狀態", "저장 + 인물 상태 갱신", "Guardar + actualizar estados de personajes", "Enregistrer + mettre à jour les états des personnages", "Speichern + Figurenzustände aktualisieren"],
  ["太字", "Bold", "粗体", "粗體", "굵게", "Negrita", "Gras", "Fett"],
  ["斜体", "Italic", "斜体", "斜體", "기울임", "Cursiva", "Italique", "Kursiv"],
  ["見出し", "Heading", "标题", "標題", "제목", "Encabezado", "Titre", "Überschrift"],
  ["引用", "Quote", "引用", "引用", "인용", "Cita", "Citation", "Zitat"],
  ["編集に戻る", "Back to editing", "返回编辑", "返回編輯", "편집으로 돌아가기", "Volver a editar", "Retour à l'édition", "Zurück zum Bearbeiten"],
  ["プレビュー", "Preview", "预览", "預覽", "미리보기", "Vista previa", "Aperçu", "Vorschau"],
  ["Context Builder：本文、人物、世界観、プロット、伏線、RAGを統合", "Context Builder: combines text, characters, world, plot, foreshadowing and RAG", "Context Builder：整合正文、人物、世界观、情节、伏笔和 RAG", "Context Builder：整合正文、人物、世界觀、情節、伏筆與 RAG", "Context Builder: 본문·인물·세계관·플롯·복선·RAG를 통합", "Context Builder: integra texto, personajes, mundo, trama, presagios y RAG", "Context Builder : combine texte, personnages, univers, intrigue, indices et RAG", "Context Builder: vereint Text, Figuren, Welt, Handlung, Foreshadowing und RAG"],
  ["⚠ 連続性を監査", "⚠ Audit continuity", "⚠ 审查连贯性", "⚠ 審查連貫性", "⚠ 연속성 감사", "⚠ Auditar continuidad", "⚠ Auditer la continuité", "⚠ Kontinuität prüfen"],
  ["▶ 続きを書く", "▶ Continue writing", "▶ 续写", "▶ 續寫", "▶ 이어 쓰기", "▶ Seguir escribiendo", "▶ Continuer à écrire", "▶ Weiterschreiben"],
  ["◆ 次の展開", "◆ Next development", "◆ 下一步发展", "◆ 下一步發展", "◆ 다음 전개", "◆ Siguiente desarrollo", "◆ Suite possible", "◆ Nächste Wendung"],
  ["要約", "Summarize", "摘要", "摘要", "요약", "Resumir", "Résumer", "Zusammenfassen"],
  ["校正", "Proofread", "校对", "校對", "교정", "Revisar", "Relire", "Korrigieren"],
  ["ボタンを押すと専用プロンプトを送信", "Pressing a button sends a dedicated prompt", "点击按钮会发送专用提示词", "點選按鈕會傳送專用提示詞", "버튼을 누르면 전용 프롬프트를 전송합니다", "Al pulsar un botón se envía un prompt específico", "Un clic sur un bouton envoie un prompt dédié", "Ein Klick auf eine Schaltfläche sendet einen eigenen Prompt"],
  ["AIへの指示", "Instruction for the AI", "给 AI 的指示", "給 AI 的指示", "AI에게 보낼 지시", "Instrucción para la IA", "Consigne pour l'IA", "Anweisung an die KI"],
  ["AI処理中...", "AI is working...", "AI 处理中...", "AI 處理中...", "AI 처리 중...", "La IA está trabajando...", "L'IA travaille...", "KI arbeitet..."],
  ["結果がここに表示されます", "Results will appear here", "结果将显示在这里", "結果將顯示在這裡", "결과가 여기에 표시됩니다", "Los resultados aparecerán aquí", "Les résultats s'afficheront ici", "Ergebnisse erscheinen hier"],
  ["＋ 本文に追加", "+ Add to text", "＋ 添加到正文", "＋ 加入正文", "+ 본문에 추가", "+ Añadir al texto", "+ Ajouter au texte", "+ Zum Text hinzufügen"],
  ["タイトルの空欄・重複・話数の不一致、本文への英単語の混在を、保存操作なしでその場でチェックします。クリックすると該当エピソードを開きます。", "Checks on the spot, without saving, for empty or duplicate titles, mismatched episode numbers and English words mixed into the text. Click an item to open the episode.", "无需保存，即时检查标题为空或重复、话数不一致、正文中混入英文单词等问题。点击即可打开对应章节。", "無需儲存，即時檢查標題為空或重複、話數不一致、正文中混入英文單字等問題。點選即可開啟對應章節。", "저장하지 않고 그 자리에서 제목 누락·중복, 화수 불일치, 본문 속 영단어 혼입을 점검합니다. 클릭하면 해당 에피소드를 엽니다.", "Comprueba al instante, sin guardar, títulos vacíos o repetidos, números de episodio incoherentes y palabras en inglés mezcladas en el texto. Haz clic para abrir el episodio.", "Vérifie immédiatement, sans enregistrer, les titres vides ou en double, les numéros d'épisode incohérents et les mots anglais mêlés au texte. Cliquez pour ouvrir l'épisode.", "Prüft sofort und ohne Speichern auf leere oder doppelte Titel, abweichende Episodennummern und eingemischte englische Wörter. Ein Klick öffnet die Episode."],
  ["問題は見つかりませんでした。", "No problems found.", "未发现问题。", "未發現問題。", "문제를 찾지 못했습니다.", "No se encontraron problemas.", "Aucun problème trouvé.", "Keine Probleme gefunden."],
  ["変更履歴", "Revision history", "修改历史", "修改歷史", "변경 이력", "Historial de cambios", "Historique des modifications", "Änderungsverlauf"],
  ["本文を上書き保存するたびに、直前の版が最大20件まで保存されます。", "Each time the text is overwritten and saved, the previous version is kept, up to 20 versions.", "每次覆盖保存正文时，都会保留上一版本，最多保存 20 个。", "每次覆蓋儲存正文時，都會保留上一版本，最多保存 20 個。", "본문을 덮어써서 저장할 때마다 직전 버전이 최대 20건까지 저장됩니다.", "Cada vez que se sobrescribe y guarda el texto, se conserva la versión anterior (hasta 20).", "À chaque enregistrement qui écrase le texte, la version précédente est conservée (jusqu'à 20).", "Bei jedem Überschreiben des Textes wird die vorherige Version gesichert (bis zu 20)."],
  ["まだ履歴はありません（本文が変更されて保存されると記録されます）。", "There is no history yet (it is recorded when the text is changed and saved).", "还没有历史记录（正文被修改并保存后会记录）。", "尚無歷史記錄（正文被修改並儲存後會記錄）。", "아직 이력이 없습니다(본문이 변경되어 저장되면 기록됩니다).", "Aún no hay historial (se registra cuando el texto cambia y se guarda).", "Aucun historique pour l'instant (il est enregistré lorsque le texte est modifié puis sauvegardé).", "Noch kein Verlauf (er wird aufgezeichnet, wenn der Text geändert und gespeichert wird)."],
  ["この版に復元", "Restore this version", "恢复到此版本", "還原到此版本", "이 버전으로 복원", "Restaurar esta versión", "Restaurer cette version", "Diese Version wiederherstellen"],

  // llmActivity
  ["続きを書いています", "Continuing the story", "正在续写", "正在續寫", "이어 쓰는 중", "Continuando la historia", "Poursuite de l'histoire", "Setzt die Geschichte fort"],
  ["次の展開を考えています", "Thinking up the next development", "正在构思下一步发展", "正在構思下一步發展", "다음 전개를 생각하는 중", "Pensando en el siguiente desarrollo", "Réflexion sur la suite", "Überlegt die nächste Wendung"],
  ["要約しています", "Summarizing", "正在生成摘要", "正在產生摘要", "요약하는 중", "Resumiendo", "Résumé en cours", "Fasst zusammen"],
  ["校正しています", "Proofreading", "正在校对", "正在校對", "교정하는 중", "Revisando", "Relecture en cours", "Korrigiert"],
  ["AIが指示を処理しています", "The AI is processing your instruction", "AI 正在处理指示", "AI 正在處理指示", "AI가 지시를 처리하는 중", "La IA está procesando tu instrucción", "L'IA traite votre consigne", "Die KI verarbeitet Ihre Anweisung"],
  ["AIが本文を生成しています", "The AI is generating text", "AI 正在生成正文", "AI 正在產生正文", "AI가 본문을 생성하는 중", "La IA está generando texto", "L'IA génère le texte", "Die KI erzeugt Text"],
  ["矛盾・連続性を監査しています", "Auditing contradictions and continuity", "正在审查矛盾与连贯性", "正在審查矛盾與連貫性", "모순·연속성을 감사하는 중", "Auditando contradicciones y continuidad", "Audit des contradictions et de la continuité", "Prüft Widersprüche und Kontinuität"],
  ["登場人物の状態を更新しています", "Updating character states", "正在更新人物状态", "正在更新人物狀態", "등장인물 상태를 갱신하는 중", "Actualizando los estados de los personajes", "Mise à jour des états des personnages", "Aktualisiert die Figurenzustände"],
  ["文章を校正しています", "Proofreading the text", "正在校对文章", "正在校對文章", "문장을 교정하는 중", "Revisando el texto", "Relecture du texte", "Korrigiert den Text"],
  ["スタイルガイドを生成しています", "Generating the style guide", "正在生成风格指南", "正在產生風格指南", "스타일 가이드를 생성하는 중", "Generando la guía de estilo", "Génération du guide de style", "Erzeugt den Styleguide"],
  ["AIが回答を考えています", "The AI is working on an answer", "AI 正在思考回答", "AI 正在思考回答", "AI가 답변을 생각하는 중", "La IA está preparando una respuesta", "L'IA prépare une réponse", "Die KI überlegt eine Antwort"],
  ["表紙のプロンプトを作成しています", "Creating the cover prompt", "正在创建封面提示词", "正在建立封面提示詞", "표지 프롬프트를 만드는 중", "Creando el prompt de portada", "Création du prompt de couverture", "Erstellt den Cover-Prompt"],
  ["意味検索の準備（埋め込み生成）をしています", "Preparing semantic search (generating embeddings)", "正在准备语义搜索（生成嵌入）", "正在準備語意搜尋（產生嵌入）", "의미 검색을 준비하는 중(임베딩 생성)", "Preparando la búsqueda semántica (generando embeddings)", "Préparation de la recherche sémantique (génération d'embeddings)", "Bereitet die semantische Suche vor (Embeddings werden erzeugt)"],

  // qualityCheck
  ["第{n}話：タイトルが空です", "Episode {n}: the title is empty", "第 {n} 话：标题为空", "第 {n} 話：標題為空", "제{n}화: 제목이 비어 있습니다", "Episodio {n}: el título está vacío", "Épisode {n} : le titre est vide", "Episode {n}: Der Titel ist leer"],
  ["第{n}話「{title}」：タイトル中の話数（{m}）が実際の話数（{n}）と一致していません", "Episode {n} “{title}”: the episode number in the title ({m}) does not match the actual number ({n})", "第 {n} 话“{title}”：标题中的话数（{m}）与实际话数（{n}）不一致", "第 {n} 話「{title}」：標題中的話數（{m}）與實際話數（{n}）不一致", "제{n}화 ‘{title}’: 제목의 화수({m})가 실제 화수({n})와 일치하지 않습니다", "Episodio {n} «{title}»: el número del título ({m}) no coincide con el real ({n})", "Épisode {n} « {title} » : le numéro dans le titre ({m}) ne correspond pas au numéro réel ({n})", "Episode {n} „{title}“: Die Nummer im Titel ({m}) stimmt nicht mit der tatsächlichen ({n}) überein"],
  [" 他", " and more", " 等", " 等", " 외", " y más", " et autres", " und weitere"],
  ["第{n}話「{title}」：本文に英単語が混在しています（{shown}）", "Episode {n} “{title}”: English words are mixed into the text ({shown})", "第 {n} 话“{title}”：正文中混入了英文单词（{shown}）", "第 {n} 話「{title}」：正文中混入了英文單字（{shown}）", "제{n}화 ‘{title}’: 본문에 영단어가 섞여 있습니다({shown})", "Episodio {n} «{title}»: hay palabras en inglés mezcladas en el texto ({shown})", "Épisode {n} « {title} » : des mots anglais sont mêlés au texte ({shown})", "Episode {n} „{title}“: Im Text sind englische Wörter eingemischt ({shown})"],
  ["（無題）", "(untitled)", "（无标题）", "（無標題）", "(제목 없음)", "(sin título)", "(sans titre)", "(ohne Titel)"],
  ["タイトル「{title}」が第{nums}話で重複しています", "The title “{title}” is duplicated in episodes {nums}", "标题“{title}”在第 {nums} 话重复", "標題「{title}」在第 {nums} 話重複", "제목 ‘{title}’이(가) 제{nums}화에서 중복됩니다", "El título «{title}» está repetido en los episodios {nums}", "Le titre « {title} » est en double aux épisodes {nums}", "Der Titel „{title}“ kommt in den Episoden {nums} doppelt vor"],
  ["話・第", ", ", "、", "、", ", ", ", ", ", ", ", "],

  ["更新", "Update", "更新", "更新", "업데이트", "Actualizar", "Mettre à jour", "Aktualisieren"],

  // CoverPanel (styles / auto-save)
  ["どんなイメージにしますか？", "What look do you want?", "想要什么样的画面风格？", "想要什麼樣的畫面風格？", "어떤 이미지로 만들까요?", "¿Qué aspecto quieres?", "Quel rendu souhaitez-vous ?", "Welchen Look wünschen Sie?"],
  ["表紙のイメージ", "Cover look", "封面风格", "封面風格", "표지 이미지", "Aspecto de la portada", "Rendu de la couverture", "Cover-Look"],
  ["イメージを自由に記入（例：水彩画、浮世絵、ドット絵）", "Describe the look freely (e.g. watercolor, ukiyo-e, pixel art)", "请自由填写风格（例如：水彩画、浮世绘、像素画）", "請自由填寫風格（例如：水彩畫、浮世繪、像素畫）", "이미지를 자유롭게 입력하세요(예: 수채화, 우키요에, 도트 그림)", "Describe el aspecto libremente (p. ej., acuarela, ukiyo-e, pixel art)", "Décrivez librement le rendu (ex. aquarelle, ukiyo-e, pixel art)", "Look frei beschreiben (z. B. Aquarell, Ukiyo-e, Pixel-Art)"],
  ["自動保存しました", "Saved automatically", "已自动保存", "已自動儲存", "자동 저장했습니다", "Guardado automáticamente", "Enregistré automatiquement", "Automatisch gespeichert"],
  ["編集は自動保存されます", "Edits are saved automatically", "编辑内容会自动保存", "編輯內容會自動儲存", "편집 내용은 자동 저장됩니다", "Los cambios se guardan automáticamente", "Les modifications sont enregistrées automatiquement", "Änderungen werden automatisch gespeichert"],
  ["クリックで拡大", "Click to enlarge", "点击放大", "點擊放大", "클릭하면 확대", "Haz clic para ampliar", "Cliquer pour agrandir", "Zum Vergrößern klicken"],
  ["生成した画像はサーバーのディスクに自動保存されます。クリックで拡大します。", "Generated images are saved automatically to the server's disk. Click one to enlarge it.", "生成的图片会自动保存到服务器磁盘。点击可放大。", "產生的圖片會自動儲存到伺服器磁碟。點擊可放大。", "생성한 이미지는 서버 디스크에 자동 저장됩니다. 클릭하면 확대됩니다.", "Las imágenes generadas se guardan automáticamente en el disco del servidor. Haz clic para ampliarlas.", "Les images générées sont enregistrées automatiquement sur le disque du serveur. Cliquez pour agrandir.", "Erzeugte Bilder werden automatisch auf der Festplatte des Servers gespeichert. Zum Vergrößern anklicken."],

  // cover lettering
  ["著者名", "Author", "作者", "作者", "저자", "Autor", "Auteur", "Autor"],
  ["表紙画像に入れる名前", "Name shown on the cover image", "显示在封面图片上的名字", "顯示在封面圖片上的名字", "표지 이미지에 넣을 이름", "Nombre que aparece en la imagen de portada", "Nom affiché sur l'image de couverture", "Name auf dem Titelbild"],
  ["タイトルと著者名を画像に入れる", "Put the title and author name on the image", "在图片上加入标题和作者名", "在圖片上加入標題和作者名", "제목과 저자명을 이미지에 넣기", "Poner el título y el autor en la imagen", "Ajouter le titre et l'auteur sur l'image", "Titel und Autor ins Bild setzen"],

  // studio
  ["確認中...", "Checking...", "确认中...", "確認中...", "확인 중...", "Comprobando...", "Vérification...", "Wird geprüft..."],

  // cover settings
  ["表紙画像", "Cover image", "封面图片", "封面圖片", "표지 이미지", "Imagen de portada", "Image de couverture", "Titelbild"],
  ["読み込めませんでした", "Could not load", "无法读取", "無法讀取", "불러오지 못했습니다", "No se pudo cargar", "Chargement impossible", "Konnte nicht geladen werden"],
  ["保存しました。次の生成から反映されます。", "Saved. Applies from the next generation.", "已保存。下次生成时生效。", "已儲存。下次產生時生效。", "저장했습니다. 다음 생성부터 적용됩니다.", "Guardado. Se aplica desde la próxima generación.", "Enregistré. Appliqué dès la prochaine génération.", "Gespeichert. Gilt ab der nächsten Erzeugung."],
  ["保存できませんでした", "Could not save", "无法保存", "無法儲存", "저장하지 못했습니다", "No se pudo guardar", "Enregistrement impossible", "Speichern fehlgeschlagen"],
  ["イメージごとに使う ComfyUI / Higgsfield の設定です。空欄は共通設定を使います。", "ComfyUI / Higgsfield settings used for each look. Blank fields use the common settings.", "每种风格使用的 ComfyUI / Higgsfield 设置。留空则使用通用设置。", "每種風格使用的 ComfyUI / Higgsfield 設定。留空則使用共通設定。", "이미지 스타일별로 사용하는 ComfyUI / Higgsfield 설정입니다. 비워 두면 공통 설정을 사용합니다.", "Ajustes de ComfyUI / Higgsfield para cada estilo. Los campos vacíos usan los ajustes comunes.", "Réglages ComfyUI / Higgsfield pour chaque style. Un champ vide utilise les réglages communs.", "ComfyUI-/Higgsfield-Einstellungen für jeden Stil. Leere Felder nutzen die gemeinsamen Einstellungen."],
  ["共通設定", "Common settings", "通用设置", "共通設定", "공통 설정", "Ajustes comunes", "Réglages communs", "Gemeinsame Einstellungen"],
  ["チェックポイント", "Checkpoint", "检查点", "檢查點", "체크포인트", "Checkpoint", "Checkpoint", "Checkpoint"],
  ["幅", "Width", "宽度", "寬度", "너비", "Ancho", "Largeur", "Breite"],
  ["高さ", "Height", "高度", "高度", "높이", "Alto", "Hauteur", "Höhe"],
  ["ステップ数", "Steps", "步数", "步數", "스텝 수", "Pasos", "Étapes", "Schritte"],
  ["CFG", "CFG", "CFG", "CFG", "CFG", "CFG", "CFG", "CFG"],
  ["サンプラー", "Sampler", "采样器", "取樣器", "샘플러", "Sampler", "Échantillonneur", "Sampler"],
  ["スケジューラ", "Scheduler", "调度器", "排程器", "스케줄러", "Scheduler", "Planificateur", "Scheduler"],
  ["ネガティブプロンプト", "Negative prompt", "负面提示词", "負面提示詞", "네거티브 프롬프트", "Prompt negativo", "Prompt négatif", "Negativ-Prompt"],
  ["モデル", "Model", "模型", "模型", "모델", "Modelo", "Modèle", "Modell"],
  ["解像度", "Resolution", "分辨率", "解析度", "해상도", "Resolución", "Résolution", "Auflösung"],
  ["縦横比", "Aspect ratio", "宽高比", "長寬比", "종횡비", "Relación de aspecto", "Format", "Seitenverhältnis"],
  ["プロンプトの方向づけ", "Prompt direction", "提示词方向", "提示詞方向", "프롬프트 방향", "Dirección del prompt", "Orientation du prompt", "Prompt-Richtung"],
  ["プロンプト末尾に付ける語句", "Words appended to the prompt", "附加在提示词末尾的词语", "附加在提示詞末尾的詞語", "프롬프트 끝에 붙일 문구", "Texto añadido al final del prompt", "Termes ajoutés à la fin du prompt", "An den Prompt angehängte Wörter"],
  ["ネガティブに追加", "Added to negative", "追加到负面提示词", "追加到負面提示詞", "네거티브에 추가", "Añadido al negativo", "Ajouté au négatif", "Zum Negativ hinzugefügt"],

  // comfyui connection
  ["ComfyUI 接続先URL", "ComfyUI server URL", "ComfyUI 服务器地址", "ComfyUI 伺服器網址", "ComfyUI 서버 URL", "URL del servidor ComfyUI", "URL du serveur ComfyUI", "ComfyUI-Server-URL"],
  ["空欄の場合は環境変数 COMFYUI_URL（既定 http://localhost:8188）", "If blank, the COMFYUI_URL environment variable is used (default http://localhost:8188)", "留空则使用环境变量 COMFYUI_URL（默认 http://localhost:8188）", "留空則使用環境變數 COMFYUI_URL（預設 http://localhost:8188）", "비워 두면 환경 변수 COMFYUI_URL을 사용합니다(기본 http://localhost:8188)", "Si se deja vacío, se usa la variable COMFYUI_URL (por defecto http://localhost:8188)", "Si vide, la variable COMFYUI_URL est utilisée (par défaut http://localhost:8188)", "Leer: Umgebungsvariable COMFYUI_URL (Standard http://localhost:8188)"],
  ["接続テストに失敗しました", "Connection test failed", "连接测试失败", "連線測試失敗", "연결 테스트에 실패했습니다", "Falló la prueba de conexión", "Échec du test de connexion", "Verbindungstest fehlgeschlagen"],
  ["利用可能なチェックポイント", "Available checkpoints", "可用的检查点", "可用的檢查點", "사용 가능한 체크포인트", "Checkpoints disponibles", "Checkpoints disponibles", "Verfügbare Checkpoints"],

  // cover delete
  ["この画像を削除", "Delete this image", "删除此图片", "刪除此圖片", "이 이미지 삭제", "Eliminar esta imagen", "Supprimer cette image", "Dieses Bild löschen"],
  ["この画像を削除しますか？", "Delete this image?", "要删除此图片吗？", "要刪除此圖片嗎？", "이 이미지를 삭제할까요?", "¿Eliminar esta imagen?", "Supprimer cette image ?", "Dieses Bild löschen?"],
  ["削除できませんでした", "Could not delete", "无法删除", "無法刪除", "삭제하지 못했습니다", "No se pudo eliminar", "Suppression impossible", "Löschen fehlgeschlagen"],

  // checkpoint list
  ["共通設定を使用", "Use the common setting", "使用通用设置", "使用共通設定", "공통 설정 사용", "Usar el ajuste común", "Utiliser le réglage commun", "Gemeinsame Einstellung verwenden"],

  // translate all
  ["作品全編を{n}言語（{labels}）に順番に翻訳し、それぞれ新しい作品として作成します（元の作品は変更されません）。時間がかかります。よろしいですか？", "Translate the whole work into {n} languages ({labels}) one after another, creating a new work for each (the original is not changed). This takes a while. Continue?", "将作品全文依次翻译成 {n} 种语言（{labels}），各自创建为新作品（原作品不变）。需要较长时间。是否继续？", "將作品全文依序翻譯成 {n} 種語言（{labels}），各自建立為新作品（原作品不變）。需要較長時間。是否繼續？", "작품 전체를 {n}개 언어({labels})로 차례로 번역해 각각 새 작품으로 만듭니다(원본은 변경되지 않습니다). 시간이 걸립니다. 계속할까요?", "Se traducirá la obra completa a {n} idiomas ({labels}) uno tras otro, creando una obra nueva por cada uno (el original no cambia). Tardará un rato. ¿Continuar?", "L'œuvre entière sera traduite en {n} langues ({labels}) l'une après l'autre, avec une nouvelle œuvre pour chacune (l'original n'est pas modifié). Cela prend du temps. Continuer ?", "Das ganze Werk wird nacheinander in {n} Sprachen ({labels}) übersetzt, jeweils als neues Werk (das Original bleibt unverändert). Das dauert eine Weile. Fortfahren?"],
  ["翻訳に失敗した言語: {labels}", "Languages that failed to translate: {labels}", "翻译失败的语言：{labels}", "翻譯失敗的語言：{labels}", "번역에 실패한 언어: {labels}", "Idiomas con error de traducción: {labels}", "Langues dont la traduction a échoué : {labels}", "Sprachen mit fehlgeschlagener Übersetzung: {labels}"],
  ["全翻訳中 {i}/{n}（{label}）", "Translating all {i}/{n} ({label})", "全部翻译中 {i}/{n}（{label}）", "全部翻譯中 {i}/{n}（{label}）", "전체 번역 중 {i}/{n}({label})", "Traduciendo todo {i}/{n} ({label})", "Tout traduire {i}/{n} ({label})", "Alles übersetzen {i}/{n} ({label})"],
  ["全翻訳", "Translate all", "全部翻译", "全部翻譯", "전체 번역", "Traducir todo", "Tout traduire", "Alles übersetzen"],
];
