"""Five real-data tests and ten rare examples, checked against JSONL tokens."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from search import SearchIndex
from tokenizer import is_telugu, tokenize


def write_separate_reports(report, output_directory):
    """Save the executed tests and rare examples in their own folders."""
    tests, separator, remaining = report.partition('Ten distinct rare Telugu terms')
    if not separator:
        raise ValueError('Rare-term section missing from report')
    rare, separator, summary = remaining.partition('Source validation errors:')
    if not separator:
        raise ValueError('Validation summary missing from report')
    summary_lines = ('Source validation errors:' + summary).strip().splitlines()
    test_report = tests.rstrip() + '\n\n' + '\n'.join(
        line for line in summary_lines if not line.startswith('Rare examples:')) + '\n'
    rare_report = ('Telugu Wikipedia positional index: rare terms\n'
                   'Roll number: S20240010050\n'
                   'Positions are zero-based in cleaned article body tokens.\n\n'
                   'Ten distinct rare Telugu terms' + rare.rstrip() + '\n\n'
                   + '\n'.join(line for line in summary_lines
                               if not line.startswith('Tests passed:')) + '\n')
    for folder, contents in [('test_results', test_report), ('rare_terms', rare_report)]:
        path = Path(output_directory) / folder / (folder + '.txt')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding='utf-8')


def generate(articles, database, output_directory):
    idx = SearchIndex(database)
    try:
        telugu = [t for t in idx.vocabulary if is_telugu(t) and len(t) >= 5]
        if len(telugu) < 10:
            raise ValueError('Collection has fewer than ten suitable Telugu terms')
        common = min(telugu, key=lambda t: (-idx.vocabulary[t]['df'], t))
        # Prefer recognisable names/terms from article titles, with repeated body
        # occurrences in exactly one document. Selection follows dump order.
        rare = []
        with open(articles, encoding='utf-8') as source:
            for line in source:
                article = json.loads(line)
                for term in tokenize(article['title']):
                    meta = idx.vocabulary.get(term)
                    if (term not in rare and is_telugu(term) and 5 <= len(term) <= 30
                            and meta and meta['df'] == 1 and meta['cf'] >= 2
                            and next(idx.postings(term))['doc_id'] == article['id']):
                        rare.append(term)
                        if len(rare) == 10:
                            break
                if len(rare) == 10:
                    break
        # Small collections may have too few title terms; still use real postings.
        if len(rare) < 10:
            for term in sorted(telugu, key=lambda t: (idx.vocabulary[t]['df'], idx.vocabulary[t]['cf'], t)):
                if term not in rare:
                    rare.append(term)
                if len(rare) == 10:
                    break
        missing = 'అసలులేనిపరీక్షాపదం'
        while missing in idx.vocabulary:
            missing += 'క'
        rare_doc = next(idx.postings(rare[0]))['doc_id']
        phrase = None
        with open(articles, encoding='utf-8') as source:
            for line in source:
                article = json.loads(line)
                if article['id'] == rare_doc:
                    tokens = tokenize(article['text'])
                    offset = tokens.index(rare[0])
                    if offset + 1 < len(tokens):
                        phrase = tokens[offset:offset + 2]
                    elif offset:
                        phrase = tokens[offset - 1:offset + 1]
                    break
        if phrase is None:
            raise ValueError('Could not select a two-token phrase')
        selected = set([common, missing] + rare + phrase)
        counts = {t: {'df': 0, 'cf': 0} for t in selected}
        errors = []
        phrase_expected = []
        common_sample = []
        repeated = None
        digest = hashlib.sha256()
        document_count = 0
        token_count = 0
        with open(articles, 'rb') as source:
            for line in source:
                digest.update(line)
                article = json.loads(line)
                tokens = tokenize(article['text'])
                document_count += 1
                token_count += len(tokens)
                expected = defaultdict(list)
                for pos, term in enumerate(tokens):
                    if term in selected:
                        expected[term].append(pos)
                for term, positions in expected.items():
                    counts[term]['df'] += 1
                    counts[term]['cf'] += len(positions)
                    stored = idx.db.execute('SELECT tf,positions FROM postings WHERE term=? AND doc_id=?', (term, article['id'])).fetchone()
                    if stored is None or stored[0] != len(positions) or json.loads(stored[1]) != positions:
                        errors.append('Source mismatch: ' + term + ' document ' + str(article['id']))
                if common in expected:
                    row = {'doc_id': article['id'], 'title': article['title'], 'tf': len(expected[common]), 'positions': expected[common]}
                    if len(common_sample) < 3:
                        common_sample.append(row)
                    if row['tf'] > 1 and (repeated is None or row['tf'] > repeated['tf']):
                        repeated = row
                starts = [p for p in expected.get(phrase[0], []) if p + 1 < len(tokens) and tokens[p + 1] == phrase[1]]
                if starts:
                    phrase_expected.append({'doc_id': article['id'], 'positions': starts, 'tf': len(starts)})
        build = json.loads(idx.db.execute("SELECT value FROM metadata WHERE key='build'").fetchone()[0])
        if digest.hexdigest() != build['articles_sha256']:
            errors.append('JSONL SHA-256 differs from indexed collection')
        if document_count != build['documents'] or token_count != build['tokens']:
            errors.append('Source document/token counts differ')
        for term in selected:
            if counts[term] != idx.vocabulary.get(term, {'df': 0, 'cf': 0}):
                errors.append('Source DF/CF mismatch: ' + term)
        phrase_actual = list(idx.phrase(phrase))
        phrase_expected.sort(key=lambda row: row['doc_id'])
        missing_rows = list(idx.postings(missing))
        tests = [
            ('Common Telugu term', common, 'Every posting position and DF/CF match the complete source token streams.',
             {'term': common, **idx.vocabulary[common], 'first_three_source_verified_postings': common_sample}, not errors and bool(common_sample)),
            ('Rare Telugu term', rare[0], 'Low-DF real Telugu term; all postings equal source occurrences.',
             {'term': rare[0], **idx.vocabulary[rare[0]], 'postings': list(idx.postings(rare[0]))}, not errors and counts[rare[0]]['df'] > 0),
            ('Nonexistent term', missing, 'DF=0, CF=0, no postings and no source occurrences.',
             {'term': missing, 'df': counts[missing]['df'], 'cf': counts[missing]['cf'], 'postings': missing_rows}, not errors and counts[missing]['cf'] == 0 and not missing_rows),
            ('Repeated occurrences', common, 'One document has TF > 1; complete positions exactly equal independently retokenized source.',
             repeated, not errors and repeated is not None),
            ('Two-term exact phrase', ' '.join(phrase), 'Disk cursor adjacency results equal all adjacent occurrences found in source tokens.',
             {'tokens': phrase, 'matching_documents': len(phrase_actual), 'postings': phrase_actual}, not errors and phrase_actual == phrase_expected and bool(phrase_actual))]
        lines = ['Telugu Wikipedia positional index: executed results', 'Roll number: S20240010050',
                 '', 'Build measurements:', json.dumps(build, ensure_ascii=False, indent=2),
                 '', 'Verification: retokenized every JSONL document; checked complete positions for all selected terms,',
                 'independent DF/CF totals, exact phrase occurrences, and the indexed source SHA-256.',
                 'Common-term display is limited to three documents; verification covers all its documents.',
                 'Positions are zero-based in cleaned article body tokens.']
        for i, (name, query, expected, actual, passed) in enumerate(tests, 1):
            lines.extend(['', 'Test {}: {}'.format(i, name), 'Query: ' + query, 'Expected: ' + expected,
                          'Actual: ' + json.dumps(actual, ensure_ascii=False, indent=2), 'Result: ' + ('PASS' if passed else 'FAIL')])
        lines.extend(['', 'Ten distinct rare Telugu terms (prefer title terms with DF=1 and CF>=2, in dump order):'])
        for i, term in enumerate(rare, 1):
            lines.append('Example {}: {}'.format(i, json.dumps({'term': term, **idx.vocabulary[term], 'postings': list(idx.postings(term))}, ensure_ascii=False)))
        lines.extend(['', 'Source validation errors: ' + json.dumps(errors, ensure_ascii=False),
                      'Tests passed: {}/5'.format(sum(bool(t[-1]) for t in tests)), 'Rare examples: ' + str(len(rare))])
        report = '\n'.join(lines) + '\n'
        write_separate_reports(report, output_directory)
        print(lines[-3:])
        if errors or not all(t[-1] for t in tests):
            raise AssertionError('Validation failed; inspect ' + str(Path(output_directory) / 'test_results/test_results.txt'))
    finally:
        idx.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--articles', default='data/articles.jsonl')
    p.add_argument('--db', default='index/positional.sqlite')
    p.add_argument('--output-dir', default='output', help='directory for separate test_results and rare_terms folders')
    a = p.parse_args()
    generate(a.articles, a.db, a.output_dir)

if __name__ == '__main__':
    main()
