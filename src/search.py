"""Load vocabulary in RAM; stream requested postings from read-only SQLite."""
import argparse
import json
from pathlib import Path
import sqlite3
from tokenizer import tokenize

class SearchIndex:
    def __init__(self, database):
        self.db = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
        self.db.execute('PRAGMA cache_size=-8192')
        self.vocabulary = {term: {'df': df, 'cf': cf} for term, df, cf in self.db.execute('SELECT term,df,cf FROM vocabulary')}

    def close(self):
        self.db.close()

    def postings(self, term):
        for doc, tf, raw in self.db.execute('SELECT doc_id,tf,positions FROM postings WHERE term=? ORDER BY doc_id', (term,)):
            yield {'doc_id': doc, 'tf': tf, 'positions': json.loads(raw)}

    def phrase(self, terms):
        if not terms or any(term not in self.vocabulary for term in terms):
            return
        # Merge sorted disk cursors: only one current posting per phrase token in RAM.
        streams = [iter(self.postings(term)) for term in terms]
        current = [next(stream, None) for stream in streams]
        while all(item is not None for item in current):
            target = max(item['doc_id'] for item in current)
            for i, stream in enumerate(streams):
                while current[i] is not None and current[i]['doc_id'] < target:
                    current[i] = next(stream, None)
            if any(item is None for item in current):
                break
            if len({item['doc_id'] for item in current}) != 1:
                continue
            starts = set(current[0]['positions'])
            for offset, item in enumerate(current[1:], 1):
                starts.intersection_update(pos - offset for pos in item['positions'])
            if starts:
                yield {'doc_id': target, 'positions': sorted(starts), 'tf': len(starts)}
            current = [next(stream, None) for stream in streams]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('query')
    p.add_argument('--db', default='index/positional.sqlite')
    p.add_argument('--phrase', action='store_true')
    p.add_argument('--limit', type=int, default=20, help='display rows; 0 displays all')
    a = p.parse_args()
    terms = tokenize(a.query)
    if not terms or (not a.phrase and len(terms) != 1) or a.limit < 0:
        p.error('provide one token, or use --phrase; limit must be nonnegative')
    idx = SearchIndex(a.db)
    try:
        print(json.dumps({'query_tokens': terms, 'metadata': {t: idx.vocabulary.get(t, {'df': 0, 'cf': 0}) for t in terms}}, ensure_ascii=False))
        rows = idx.phrase(terms) if a.phrase else idx.postings(terms[0])
        shown = 0
        for row in rows:
            if a.limit and shown >= a.limit:
                print('Display truncated; use --limit 0 for all postings.')
                break
            print(json.dumps(row, ensure_ascii=False))
            shown += 1
        if not shown:
            print('No matches.')
    finally:
        idx.close()

if __name__ == '__main__':
    main()
