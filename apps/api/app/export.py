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
import re
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


# ---- Word (.docx): 章 = 見出し1, 話 = 見出し2 --------------------------------

_W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
_BAD_XML = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')


def _x(text) -> str:
    """Escape for XML text and drop characters XML 1.0 cannot carry."""
    return html.escape(_BAD_XML.sub('', str(text or '')), quote=False)


def _para(text: str, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ''
    if not text:
        return f'<w:p>{ppr}</w:p>'
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{_x(text)}</w:t></w:r></w:p>'


def _docx_styles(lang: str) -> str:
    east = {'ja': '游明朝', 'zh-CN': '宋体', 'ko': '바탕'}.get(lang, '游明朝')
    fonts = f'<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="{east}" w:cs="Times New Roman"/>'
    head_fonts = f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="{"游ゴシック" if lang == "ja" else east}"/>'

    def heading(sid: str, name: str, level: int, size: int) -> str:
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
                f'<w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/>'
                f'<w:pPr><w:keepNext/><w:spacing w:before="360" w:after="120"/><w:outlineLvl w:val="{level}"/></w:pPr>'
                f'<w:rPr>{head_fonts}<w:b/><w:sz w:val="{size}"/><w:szCs w:val="{size}"/></w:rPr></w:style>')
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="{_W_NS}">'
            f'<w:docDefaults><w:rPrDefault><w:rPr>{fonts}<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="{lang}" w:eastAsia="{lang}"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            f'<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
            f'<w:pPr><w:spacing w:before="240" w:after="240"/><w:jc w:val="center"/></w:pPr><w:rPr>{head_fonts}<w:b/><w:sz w:val="44"/><w:szCs w:val="44"/></w:rPr></w:style>'
            + heading('Heading1', 'heading 1', 0, 32) + heading('Heading2', 'heading 2', 1, 28) + '</w:styles>')


def build_docx(project, episodes) -> bytes:
    """A Word document: the work's name as the title, each chapter (章) as
    見出し1 (Heading 1) and each episode (話) as 見出し2 (Heading 2), so Word's
    navigation pane and table of contents follow the story. A chapter heading is
    written whenever the chapter changes between consecutive episodes; episodes
    with no chapter get no 見出し1. Assembled by hand, like the EPUB."""
    lang = _lang(project)
    body = [_para(project.name, 'Title')]
    if getattr(project, 'author', ''):
        body.append(_para(project.author))
    if project.description:
        body += [_para(line) for line in project.description.split('\n')]
    last_chapter = None
    for e in episodes:
        chapter = (getattr(e, 'chapter', '') or '').strip()
        if chapter and chapter != last_chapter:
            body.append(_para(chapter, 'Heading1'))
        last_chapter = chapter
        body.append(_para(_episode_heading(e, lang), 'Heading2'))
        text = e.content or ''
        body += [_para(line) for line in (text.split('\n') if text else [LABELS[lang][1]])]
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{_W_NS}"><w:body>'
                + ''.join(body) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{_x(project.name)}</dc:title><dc:creator>{_x(getattr(project, "author", "") or "")}</dc:creator>'
            f'<dc:language>{lang}</dc:language></cp:coreProperties>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
             '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', types)
        z.writestr('_rels/.rels', rels)
        z.writestr('word/document.xml', document)
        z.writestr('word/_rels/document.xml.rels', doc_rels)
        z.writestr('word/styles.xml', _docx_styles(lang))
        z.writestr('docProps/core.xml', core)
    return buf.getvalue()


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
