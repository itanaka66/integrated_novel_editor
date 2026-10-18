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

// Only http(s) links are rendered as links (a saved value could be anything).
export function safeUrl(u: string): string | undefined {
  return /^https?:\/\//i.test(u || "") ? u : undefined;
}

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
    name: "Wattpad（ワットパッド）",
    officialUrl: "https://www.wattpad.com/",
    postUrl: "https://www.wattpad.com/myworks",
    helpUrl: "https://support.wattpad.com/",
    method: "無料の投稿型プラットフォーム（連載・短編）。読者がコメント・投票できる",
    languages: "多言語対応を掲げ、利用者は世界各国にいる。8言語それぞれの読者規模は要確認（英語・スペイン語・フランス語・ドイツ語・ポルトガル語などは投稿が多い）",
    languageSetting: "作品ごとに言語を選んで投稿する。要確認",
    translation: "サイト内の自動翻訳配信は要確認。翻訳版は別作品として投稿する運用が一般的",
    caution: "【調査メモ（要確認）】登録・投稿ページのURLは変わることがある。成人向け内容・AI生成コンテンツの扱いは最新の規約を確認",
  },
  {
    name: "Royal Road（ロイヤル・ロード）",
    officialUrl: "https://www.royalroad.com/",
    postUrl: "https://www.royalroad.com/",
    helpUrl: "https://www.royalroad.com/",
    method: "英語のWeb小説（連載）投稿サイト。ファンタジー／LitRPG系が中心",
    languages: "英語が中心。英語以外の作品は想定されていない可能性が高く、8言語のうち投稿向きなのは英語のみ（要確認）",
    languageSetting: "英語での連載が前提。言語の選択機能は要確認",
    translation: "サイト内の翻訳配信は確認できていない（要確認）",
    caution: "【調査メモ（要確認）】英語版を投稿する用途。投稿方法・AI生成コンテンツの規則は最新の公式ルールを確認",
  },
  {
    name: "Inkitt（インキット）",
    officialUrl: "https://www.inkitt.com/",
    postUrl: "https://www.inkitt.com/",
    helpUrl: "https://www.inkitt.com/",
    method: "読者の反応で作品を選ぶ投稿プラットフォーム。選ばれた作品は出版契約の対象になることがある",
    languages: "英語が中心。ほかの言語の作品の扱いは要確認",
    languageSetting: "投稿時の言語指定は要確認",
    translation: "要確認",
    caution: "【調査メモ（要確認）】出版・契約の条件（独占性、収益配分）を必ず規約で確認",
  },
  {
    name: "Wuxiaworld（武侠ワールド）",
    officialUrl: "https://www.wuxiaworld.com/",
    postUrl: "https://www.wuxiaworld.com/",
    helpUrl: "https://www.wuxiaworld.com/",
    method: "英語で読む中国・韓国などのWeb小説（翻訳作品が中心）と、オリジナル作品の投稿・連載",
    languages: "英語が中心。8言語のうち投稿向きなのは英語（要確認）",
    languageSetting: "英語での公開が前提。要確認",
    translation: "翻訳作品の配信が主体。自作の翻訳版を載せられるかは要確認",
    caution: "【調査メモ（要確認）】作家の募集条件・審査の有無は公式の案内を確認",
  },
  {
    name: "Webnovel（ウェブノベル）",
    officialUrl: "https://www.webnovel.com/",
    postUrl: "https://www.webnovel.com/",
    helpUrl: "https://www.webnovel.com/",
    method: "英語を中心とするWeb小説プラットフォーム。作家契約（有料化）の仕組みがある",
    languages: "英語が中心。他言語の対応は要確認",
    languageSetting: "作品の言語指定と契約の対象言語は要確認",
    translation: "中国語作品の翻訳配信が多い。自作の多言語展開は要確認",
    caution: "【調査メモ（要確認）】契約条件・AI生成コンテンツの扱い・非英語作品の扱いは公式の案内を確認",
  },
  {
    name: "Chuangshi（創世中文網）",
    officialUrl: "https://chuangshi.qq.com/",
    postUrl: "https://chuangshi.qq.com/",
    helpUrl: "https://chuangshi.qq.com/",
    method: "中国語（簡体字）のWeb小説プラットフォーム（連載・有料化）",
    languages: "中国語（簡体字）。8言語のうち投稿向きなのは簡体字中国語のみ",
    languageSetting: "中国語での執筆・投稿が前提",
    translation: "要確認",
    caution: "【調査メモ（要確認）】登録に中国国内の電話番号・本人確認が必要になる可能性がある。海外居住者の投稿可否は公式を確認",
  },
  {
    name: "Munpia（문피아）",
    officialUrl: "https://www.munpia.com/",
    postUrl: "https://www.munpia.com/",
    helpUrl: "https://www.munpia.com/",
    method: "韓国語のWeb小説プラットフォーム（連載・有料化）",
    languages: "韓国語。8言語のうち投稿向きなのは韓国語のみ",
    languageSetting: "韓国語での執筆・投稿が前提",
    translation: "要確認",
    caution: "【調査メモ（要確認）】会員登録・本人確認の条件、海外居住者の投稿可否は公式を確認",
  },
  {
    name: "QQ 作家専区（write.qq.com）",
    officialUrl: "https://write.qq.com/",
    postUrl: "https://write.qq.com/",
    helpUrl: "https://write.qq.com/",
    method: "中国語（簡体字）のWeb小説の作家向け投稿ページ（Tencent系の作家向けサイト）",
    languages: "中国語（簡体字）。8言語のうち投稿向きなのは簡体字中国語のみ（要確認）",
    languageSetting: "中国語での執筆・投稿が前提",
    translation: "要確認",
    caution: "【調査メモ（要確認）】登録に中国国内の電話番号・本人確認が必要になる可能性がある。海外居住者の投稿可否、契約条件は公式を確認。創世中文網（chuangshi.qq.com）との関係も公式で確認",
  },
];
