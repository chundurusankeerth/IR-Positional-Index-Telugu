"""Build SQLite positional postings with memory bounded by one article."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from tokenizer import tokenize

SCHEMA = '''
CREATE TABLE documents(doc_id INTEGER PRIMARY KEY, title TEXT NOT NULL, token_count INTEGER NOT NULL);
CREATE TABLE postings(term TEXT NOT NULL, doc_id INTEGER NOT NULL REFERENCES documents(doc_id),
 tf INTEGER NOT NULL CHECK(tf>0), positions TEXT NOT NULL,
 PRIMARY KEY(term,doc_id)) WITHOUT ROWID;
CREATE TABLE vocabulary(term TEXT PRIMARY KEY, df INTEGER NOT NULL, cf INTEGER NOT NULL) WITHOUT ROWID;
CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''

def build(articles, database):
    database = Path(database)
    if database.exists():
        raise FileExistsError('Refusing to overwrite ' + str(database))
    database.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    digest = hashlib.sha256()
    docs = tokens_total = 0
    db = sqlite3.connect(str(database))
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA cache_size=-32768')
        db.execute('PRAGMA temp_store=FILE')
        db.executescript(SCHEMA)
        with open(articles, 'rb') as source:
            for line in source:
                digest.update(line)
                article = json.loads(line)
                tokens = tokenize(article['text'])
                positions = defaultdict(list)
                for pos, term in enumerate(tokens):
                    positions[term].append(pos)
                db.execute('INSERT INTO documents VALUES(?,?,?)', (article['id'], article['title'], len(tokens)))
                db.executemany('INSERT INTO postings VALUES(?,?,?,?)',
                    ((term, article['id'], len(pos), json.dumps(pos, separators=(',', ':'))) for term, pos in positions.items()))
                docs += 1
                tokens_total += len(tokens)
                if docs % 500 == 0:
                    db.commit()
                if docs % 10000 == 0:
                    print('Indexed', docs, 'articles;', tokens_total, 'tokens', flush=True)
        db.commit()
        db.execute('INSERT INTO vocabulary SELECT term,COUNT(*),SUM(tf) FROM postings GROUP BY term')
        db.commit()
        # Stream every row, rather than materializing all positions to validate them.
        posting_rows = 0
        for tf, raw in db.execute('SELECT tf,positions FROM postings'):
            positions = json.loads(raw)
            if len(positions) != tf or not positions or positions[0] < 0 or any(a >= b for a, b in zip(positions, positions[1:])):
                raise ValueError('Invalid positional posting')
            posting_rows += 1
        mismatch = db.execute('''SELECT COUNT(*) FROM vocabulary v LEFT JOIN
            (SELECT term,COUNT(*) df,SUM(tf) cf FROM postings GROUP BY term) p ON v.term=p.term
            WHERE p.term IS NULL OR v.df!=p.df OR v.cf!=p.cf''').fetchone()[0]
        if mismatch or db.execute('SELECT SUM(cf) FROM vocabulary').fetchone()[0] != tokens_total:
            raise ValueError('DF/CF validation failed')
        integrity = db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise ValueError(integrity)
        stats = {'documents': docs, 'tokens': tokens_total,
                 'vocabulary_size': db.execute('SELECT COUNT(*) FROM vocabulary').fetchone()[0],
                 'posting_rows': posting_rows, 'articles_sha256': digest.hexdigest(),
                 'positions_base': 0, 'validation': 'PASS', 'integrity_check': integrity,
                 'elapsed_seconds': round(time.monotonic() - started, 3)}
        db.execute('INSERT INTO metadata VALUES(?,?)', ('build', json.dumps(stats)))
        db.commit()
        database.with_suffix('.stats.json').write_text(json.dumps(stats, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(stats), flush=True)
        return stats
    finally:
        db.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--articles', default='data/articles.jsonl')
    p.add_argument('--db', default='index/positional.sqlite')
    a = p.parse_args()
    build(a.articles, a.db)

if __name__ == '__main__':
    main()
