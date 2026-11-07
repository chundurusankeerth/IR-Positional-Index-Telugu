"""Stream a bzip2 MediaWiki dump into cleaned, stable-ID JSONL records."""
import argparse
import bz2
from collections import Counter
import json
from pathlib import Path
import time
import unicodedata
import xml.etree.ElementTree as ET
import mwparserfromhell
from tokenizer import tokenize

def extract(dump, output, limit=0):
    if limit < 0:
        raise ValueError('limit must be nonnegative')
    output = Path(output)
    if output.exists():
        raise FileExistsError('Refusing to overwrite ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    started = time.monotonic()
    exhausted = True
    with bz2.open(dump, 'rb') as source, output.open('x', encoding='utf-8') as dest:
        events = ET.iterparse(source, events=('start', 'end'))
        _, root = next(events)
        ns = root.tag.split('}')[0] + '}'
        for event, page in events:
            if event != 'end' or page.tag != ns + 'page':
                continue
            counts['pages_seen'] += 1
            if page.findtext(ns + 'ns') != '0':
                counts['skipped_non_main_namespace'] += 1
            elif page.find(ns + 'redirect') is not None:
                counts['skipped_redirect'] += 1
            else:
                raw = page.findtext(ns + 'revision/' + ns + 'text') or ''
                if not raw.strip():
                    counts['skipped_empty_wikitext'] += 1
                else:
                    code = mwparserfromhell.parse(raw)
                    # Remove reference bodies and non-prose media/category links.
                    for tag in list(code.filter_tags(recursive=True)):
                        if str(tag.tag).lower() in ('ref', 'references', 'gallery', 'math', 'syntaxhighlight', 'source', 'timeline'):
                            try:
                                code.remove(tag)
                            except ValueError:
                                pass  # already removed along with its parent
                    for link in list(code.filter_wikilinks(recursive=True)):
                        prefix = str(link.title).split(':', 1)[0].strip().lower()
                        if prefix in ('file', 'image', 'category', 'దస్త్రం', 'బొమ్మ', 'వర్గం'):
                            try:
                                code.remove(link)
                            except ValueError:
                                pass
                    text = unicodedata.normalize('NFC', code.strip_code(normalize=True, collapse=True))
                    text = ' '.join(text.split())
                    if not tokenize(text):
                        counts['skipped_no_tokens'] += 1
                    else:
                        record = {'id': int(page.findtext(ns + 'id')), 'title': page.findtext(ns + 'title'), 'text': text}
                        dest.write(json.dumps(record, ensure_ascii=False) + '\n')
                        counts['accepted'] += 1
            root.clear()
            if counts['pages_seen'] % 10000 == 0:
                print('Extraction:', dict(counts), flush=True)
            if limit and counts['accepted'] >= limit:
                exhausted = False
                break
    stats = {'dump': str(dump), 'document_limit': limit, 'dump_exhausted': exhausted,
             'counts': dict(counts), 'elapsed_seconds': round(time.monotonic() - started, 3)}
    output.with_suffix('.stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False), flush=True)
    return stats

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dump', default='data/tewiki-latest-pages-articles-multistream.xml.bz2')
    p.add_argument('--output', default='data/articles.jsonl')
    p.add_argument('--limit', type=int, default=0, help='accepted articles; 0 means entire dump')
    a = p.parse_args()
    extract(a.dump, a.output, a.limit)

if __name__ == '__main__':
    main()
