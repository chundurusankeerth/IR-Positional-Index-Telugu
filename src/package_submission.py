"""Package only source, README and actual output; verify archive member lists."""
import argparse
from pathlib import Path
import zipfile

ROLL = 'S20240010050'

def package(root):
    root = Path(root).resolve()
    reports = {'README.txt': root / 'README.txt',
               'rare_terms.txt': root / 'output/rare_terms/rare_terms.txt',
               'test_results.txt': root / 'output/test_results/test_results.txt'}
    for path in reports.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    inner = root / (ROLL + '-src.zip')
    outer = root / (ROLL + '-A1-PostIndex-IR-M2026.zip')
    files = sorted((root / 'src').glob('*.py')) + [root / 'src/requirements.txt']
    with zipfile.ZipFile(inner, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, str(path.relative_to(root)))
    expected = ['README.txt', inner.name, 'rare_terms.txt', 'test_results.txt']
    reports[inner.name] = inner
    with zipfile.ZipFile(outer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in expected:
            archive.write(reports[name], name)
    with zipfile.ZipFile(inner) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist()) == sorted(str(p.relative_to(root)) for p in files)
        print('Source ZIP members:', archive.namelist())
    with zipfile.ZipFile(outer) as archive:
        assert archive.testzip() is None
        assert archive.namelist() == expected
        for name in expected:
            assert archive.read(name) == reports[name].read_bytes()
        print('Final ZIP members:', archive.namelist())
    print('Verified archive structure and bytes:', outer)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    package(parser.parse_args().root)

if __name__ == '__main__':
    main()
