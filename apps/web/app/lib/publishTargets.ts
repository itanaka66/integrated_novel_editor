// Where a finished work can be published, with the research notes about each
// site (languages, how the language is chosen, translation, cautions). The
// notes are descriptive text supplied by the project owner and may go out of
// date — the dialog tells readers to confirm on the official pages.
export type PublishTarget = {
  name: string;
  officialUrl: string;
  postUrl: string;
  helpUrl: string;
  method: string;
  languages: string;
  languageSetting: string;
  translation: string;
  caution: string;
};

export const PUBLISH_TARGETS: PublishTarget[] = [
  {
    name: "Kindle Direct Publishing (KDP)",
    officialUrl: "https://kdp.amazon.co.jp/ja_JP/",
    postUrl: "https://kdp.amazon.co.jp/ja_JP/",
    helpUrl: "https://kdp.amazon.co.jp/ja_JP/help/topic/G200673300",
    method: "電子書籍・紙書籍のセルフ出版",
    languages: "日本語、英語、スペイン語、フランス語、ドイツ語、ポルトガル語に対応。簡体字中国語は非対応（中国語は繁体字が電子書籍のみ）。韓国語は対応リストに掲載なし",
    languageSetting: "KDP本棚で本の詳細を設定する際に原稿の主言語を選択。選択言語・本文・ファイルのメタデータを一致させる",
    translation: "Kindle Translateは招待制ベータ。現在の公開言語ペアを確認。日本語原稿は現時点で翻訳元として対象外",
    caution: "作品ごとに主言語を指定。非対応言語での出版は避け、最新の公式対応言語一覧を確認",
  },
  {
    name: "小説家になろう",
    officialUrl: "https://syosetu.com/",
    postUrl: "https://syosetu.com/useradd/",
    helpUrl: "https://syosetu.com/",
    method: "Web小説投稿",
    languages: "日本語向け。英語・簡体字中国語・韓国語・スペイン語・フランス語・ドイツ語・ブラジルポルトガル語の多言語投稿機能は確認できず",
    languageSetting: "日本語小説の投稿を前提に利用。8言語の作品言語を選択・切替する投稿機能は確認できず",
    translation: "サイト内で8言語に自動翻訳・配信する機能は確認できず",
    caution: "翻訳版は別サイト等で公開する方法を検討",
  },
  {
    name: "NovelMint",
    officialUrl: "https://novelmint.ai/ja",
    postUrl: "https://novelmint.ai/ja",
    helpUrl: "https://novelmint.ai/ja/capabilities",
    method: "連載小説プラットフォーム。執筆・公開・AI翻訳",
    languages: "8言語すべて対応：日本語、英語、簡体字中国語、韓国語、スペイン語、フランス語、ドイツ語、ポルトガル語（ブラジル）",
    languageSetting: "執筆言語・公開言語・翻訳先言語を対応言語リストから選択。読者は作品ページや読書中に言語を切り替え可能",
    translation: "対応。公式サイトでは21言語での執筆・公開・翻訳を案内",
    caution: "翻訳版の公開手順、料金・クレジット条件を確認",
  },
  {
    name: "Unwall Library",
    officialUrl: "https://www.unwall.ai/",
    postUrl: "https://www.unwall.ai/register",
    helpUrl: "https://www.unwall.ai/creators/",
    method: "原文投稿を起点にした多言語小説プラットフォーム",
    languages: "多言語対応を掲げるが、今回の8言語すべてについて現在投稿・配信可能かは要確認。40以上の言語への対応を案内",
    languageSetting: "原文の言語で投稿し、プラットフォーム側の翻訳・多言語配信機能を利用する構想。ベータ／クリエイター登録後に実際の選択肢を確認",
    translation: "多言語配信を掲げるが、利用可能な言語と一般投稿の開始状況は要確認",
    caution: "初期クリエイタープログラム／ベータ段階の可能性あり。登録・投稿開始の可否を確認",
  },
  {
    name: "Novela.work",
    officialUrl: "https://novela.work/about?lang=en",
    postUrl: "https://novela.work/",
    helpUrl: "https://novela.work/about?lang=en",
    method: "多言語コンテンツ・小説プラットフォーム",
    languages: "確認できた説明では日本語、英語、簡体字中国語、韓国語、スペイン語、ポルトガル語（ブラジル）の6言語。フランス語・ドイツ語は未確認",
    languageSetting: "サイト表示言語の切替は可能。作品の投稿言語を選ぶ機能・自由投稿の登録手順は要確認",
    translation: "サイトコンテンツの多言語対応を案内。ユーザー投稿作品の翻訳方法は要確認",
    caution: "8言語すべてへの投稿対応は確認できていない",
  },
];
