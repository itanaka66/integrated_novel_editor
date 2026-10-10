"""Build a downloadable export of a project's episodes.

Deliberately dependency-free: text/markdown are just string building, and
the EPUB is a minimal valid EPUB3 assembled by hand with the stdlib
`zipfile` rather than pulling in an ebook-authoring library for what is,
structurally, a handful of static XML files plus one XHTML file per
episode.
"""
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
