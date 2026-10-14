"""Build a downloadable export of a project's episodes.

Deliberately dependency-free: text/markdown are just string building, and
the EPUB is a minimal valid EPUB3 assembled by hand with the stdlib
`zipfile` rather than pulling in an ebook-authoring library for what is,
structurally, a handful of static XML files plus one XHTML file per
episode.
"""
import csv
import html
import io
import uuid
import zipfile


# Per-language wording for the fixed strings an export emits. The project's
# `language` (set by 翻訳 / defaulting to 'ja') picks the set, so a translated
# novel doesn't come out with Japanese headings or a `ja` EPUB language tag.
LABELS = {
    'ja': ('第{n}話 {t}', '(本文未入力)', '目次'),
    'en': ('Episode {n}: {t}', '(No text)', 'Contents'),
    'zh-CN': ('第{n}话 {t}', '(尚无正文)', '目录'),
    'ko': ('제{n}화 {t}', '(본문 없음)', '목차'),
    'es': ('Episodio {n}: {t}', '(Sin texto)', 'Índice'),
    'fr': ('Épisode {n} : {t}', '(Aucun texte)', 'Table des matières'),
    'de': ('Episode {n}: {t}', '(Kein Text)', 'Inhaltsverzeichnis'),
    'pt-BR': ('Episódio {n}: {t}', '(Sem texto)', 'Sumário'),
}


def _lang(project) -> str:
    lang = getattr(project, 'language', None) or 'ja'
    return lang if lang in LABELS else 'ja'


def _episode_heading(e, lang='ja'):
    return LABELS[lang][0].format(n=e.number, t=e.title or '').strip()


def build_text(project, episodes) -> str:
    parts = [project.name, '']
    if project.description:
        parts += [project.description, '']
    lang = _lang(project)
    for e in episodes:
        parts += [_episode_heading(e, lang), '', e.content or LABELS[lang][1], '', '']
    return '\n'.join(parts)


def build_markdown(project, episodes) -> str:
    parts = [f'# {project.name}', '']
    if project.description:
        parts += [project.description, '']
    lang = _lang(project)
    for e in episodes:
        parts += [f'## {_episode_heading(e, lang)}', '']
        if e.summary:
            parts += [f'> {e.summary}', '']
        parts += [e.content or f'*{LABELS[lang][1]}*', '', '']
    return '\n'.join(parts)


# ---- KDP package: EPUB + cover + the details the KDP form asks for ----------

# KDP's own names for the languages this app can produce.
KDP_LANGUAGE = {'ja': '日本語 (Japanese)', 'en': '英語 (English)', 'zh-CN': '中国語・簡体字 (Chinese)', 'ko': '韓国語 (Korean)',
                'es': 'スペイン語 (Spanish)', 'fr': 'フランス語 (French)', 'de': 'ドイツ語 (German)', 'pt-BR': 'ポルトガル語・ブラジル (Portuguese)'}


def kdp_rows(project, pub: dict, episodes, ai: dict) -> list[tuple[str, str]]:
    """(item, value) rows in the order the KDP "Kindle eBook details" and
    "content" pages ask for them."""
    chars = sum(len(e.content or '') for e in episodes)
    return [
        ('書籍の言語', KDP_LANGUAGE.get(project.language or 'ja', project.language or 'ja')),
        ('本のタイトル', pub.get('title', '')),
        ('サブタイトル', pub.get('subtitle', '')),
        ('著者名（ペンネーム可）', pub.get('author', '')),
        ('内容紹介（説明文・4000文字まで）', pub.get('description', '')),
        ('キーワード（最大7つ）', ' / '.join(pub.get('keywords') or [])),
        ('カテゴリー', pub.get('category', '')),
        ('成人向けコンテンツ', 'はい' if pub.get('adult') else 'いいえ'),
        ('読者対象年齢（下限）', pub.get('age_min') or '（指定なし）'),
        ('読者対象年齢（上限）', pub.get('age_max') or '（指定なし）'),
        ('原稿ファイル', 'book.epub'),
        ('表紙ファイル', ai.get('cover_file') or '（表紙が未選択です。表紙パネルで採用する画像を選んでください）'),
        ('話数 / 文字数', f'{len(episodes)}話 / {chars:,}文字'),
        ('AI生成コンテンツ: テキスト（下書き）', ai['text']),
        ('AI生成コンテンツ: 画像（下書き）', ai['images']),
        ('AI生成コンテンツ: 翻訳（下書き）', ai['translation']),
    ]


def build_kdp_csv(rows) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator='\r\n')
    w.writerow(['項目', '値'])
    w.writerows(rows)
    return '\ufeff' + out.getvalue()  # BOM so Excel opens the Japanese text correctly


def build_kdp_markdown(project, rows) -> str:
    lines = [f'# KDP 登録用情報シート: {project.name}', '',
             'Kindle Direct Publishing の登録画面に、上から順に貼り付けてください。', '']
    for k, v in rows:
        if '\n' in str(v) or len(str(v)) > 80:
            lines += [f'## {k}', '', str(v), '']
        else:
            lines += [f'- **{k}**: {v}']
    lines += ['', '## 注意', '',
              '- 「AI生成コンテンツ」の欄は、このアプリの記録からの**推定の下書き**です。実際の制作方法に合わせて、KDP の「内容」タブで本人が選択・申告してください。',
              '- AI が作ったテキスト・画像・翻訳は、人が手直ししても「AI生成」に含まれます（KDP の定義）。',
              '- 登録・公開の操作は、KDP の画面で本人が行います。']
    return '\n'.join(lines) + '\n'


def build_kdp_package(project, episodes, cover, pub: dict, ai: dict) -> bytes:
    """One ZIP per work: book.epub, cover.<ext>, kdp_info.csv, kdp_info.md."""
    ai = dict(ai)
    if cover:
        ai['cover_file'] = 'cover' + cover[1]
    rows = kdp_rows(project, pub, episodes, ai)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('book.epub', build_epub(project, episodes, cover))
        if cover:
            z.writestr('cover' + cover[1], cover[0])
        z.writestr('kdp_info.csv', build_kdp_csv(rows).encode('utf-8'))
        z.writestr('kdp_info.md', build_kdp_markdown(project, rows).encode('utf-8'))
    return buf.getvalue()


def _epub_xhtml(title, body, lang='ja'):
    escaped_title = html.escape(title)
    body_html = ''.join(f'<p>{html.escape(line)}</p>' for line in (body or '').split('\n') if line.strip())
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">
<head><title>{escaped_title}</title><meta charset="utf-8"/></head>
<body><h1>{escaped_title}</h1>{body_html or f'<p>{html.escape(LABELS[lang][1])}</p>'}</body>
</html>'''


_IMG_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}


def build_epub(project, episodes, cover=None) -> bytes:
    """`cover` is an optional (image_bytes, '.png'|'.jpg'|'.webp') embedded as the EPUB cover."""
    book_id = f'urn:uuid:{uuid.uuid4()}'
    lang = _lang(project)
    chapters = [(f'ch{i}', _episode_heading(e, lang), e.content) for i, e in enumerate(episodes, start=1)]

    cover_manifest = cover_meta = cover_spine = ''
    if cover:
        cover_ext = cover[1]
        cover_manifest = (f'<item id="cover-image" href="cover{cover_ext}" media-type="{_IMG_TYPES[cover_ext]}" properties="cover-image"/>'
                          '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>')
        cover_meta = '<meta name="cover" content="cover-image"/>'
        cover_spine = '<itemref idref="cover-page" linear="yes"/>'
    manifest_items = ''.join(f'<item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>' for cid, _, _ in chapters)
    spine_items = ''.join(f'<itemref idref="{cid}"/>' for cid, _, _ in chapters)
    nav_items = ''.join(f'<li><a href="{cid}.xhtml">{html.escape(title)}</a></li>' for cid, title, _ in chapters)

    content_opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{book_id}</dc:identifier>
<dc:title>{html.escape(project.name)}</dc:title>
{('<dc:creator>' + html.escape(project.author) + '</dc:creator>') if getattr(project, 'author', '') else ''}
<dc:language>{lang}</dc:language>
{cover_meta}
</metadata>
<manifest>
<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
{cover_manifest}{manifest_items}
</manifest>
<spine>{cover_spine}{spine_items}</spine>
</package>'''

    nav_xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{lang}" lang="{lang}">
<head><title>{html.escape(LABELS[lang][2])}</title><meta charset="utf-8"/></head>
<body><nav epub:type="toc"><ol>{nav_items}</ol></nav></body>
</html>'''

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        # The mimetype entry must be first and stored uncompressed for
        # readers that sniff the file before parsing the zip properly.
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', '''<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>''')
        z.writestr('OEBPS/content.opf', content_opf)
        z.writestr('OEBPS/nav.xhtml', nav_xhtml)
        if cover:
            z.writestr(f'OEBPS/cover{cover[1]}', cover[0])
            z.writestr('OEBPS/cover.xhtml', f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">
<head><title>{html.escape(project.name)}</title><meta charset="utf-8"/></head>
<body style="margin:0;text-align:center"><img src="cover{cover[1]}" alt="{html.escape(project.name)}" style="max-width:100%;max-height:100%"/></body>
</html>''')
        for cid, title, body in chapters:
            z.writestr(f'OEBPS/{cid}.xhtml', _epub_xhtml(title, body, lang))
    return buf.getvalue()
