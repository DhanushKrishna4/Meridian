"""Bounded local input validation and split-first preprocessing metadata."""
import csv
import hashlib
import io
import numpy as np

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 15


def validate_nodes(nodes):
    if not isinstance(nodes, (list, tuple)) or not 2 <= len(nodes) <= MAX_COLUMNS:
        raise ValueError('Select 2–15 numerical columns.')
    if any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in nodes):
        raise ValueError('Variable IDs must be nonempty strings of at most 80 characters.')
    if len(set(nodes)) != len(nodes):
        raise ValueError('Duplicate variable IDs are not allowed.')
    return list(nodes)


def parse_csv(text, columns=None):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('CSV exceeds the 5 MiB local import limit.')
    reader = csv.reader(io.StringIO(text.lstrip('\ufeff')))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError('CSV is empty; include a header row.') from None
    if not header or len(header) > 256 or len(set(header)) != len(header):
        raise ValueError('CSV needs distinct column headers (maximum 256 source columns).')
    nodes = validate_nodes(columns if columns is not None else header)
    if any(c not in header for c in nodes):
        raise ValueError('Selected columns must exist in the CSV header.')
    indices = [header.index(c) for c in nodes]
    rows = []
    for line, row in enumerate(reader, 2):
        if len(rows) >= MAX_ROWS:
            raise ValueError('CSV exceeds 5,000 rows; explicitly reduce the dataset before importing.')
        if len(row) != len(header):
            raise ValueError(f'CSV row {line} has {len(row)} cells; expected {len(header)}. No rows were dropped.')
        try:
            rows.append([float(row[i]) if row[i].strip() else np.nan for i in indices])
        except ValueError:
            raise ValueError(f'CSV row {line} contains a nonnumerical selected value. Select numerical columns only.') from None
    if len(rows) < 20:
        raise ValueError('Use at least 20 observations for the discovery/train/validation/evaluation split.')
    return np.asarray(rows, dtype=float), nodes


def diagnostics(data, nodes):
    x = np.asarray(data, dtype=float)
    report = {'rows': len(x), 'columns': len(nodes), 'missing': int(np.isnan(x).sum()),
              'nonfinite': int((~np.isfinite(x)).sum()), 'constant_columns': [],
              'dependent_columns': [], 'warnings': [], 'valid': True}
    if report['nonfinite']:
        report.update(valid=False)
        report['warnings'].append('Missing/nonfinite values are unsupported. Correct the source data; Meridian never imputes or drops rows.')
        return report
    scales = x.std(axis=0)
    report['constant_columns'] = [v for v, s in zip(nodes, scales) if s <= 1e-14]
    report['scales'] = {v: float(s) for v,s in zip(nodes,scales)}
    if report['constant_columns']:
        report['valid'] = False
        report['warnings'].append('Remove constant columns explicitly before discovery.')
        return report
    z = (x - x.mean(0))/scales
    report['condition_number'] = float(np.linalg.cond(z))
    corr = z.T @ z / len(z)
    report['dependent_columns'] = [[nodes[i], nodes[j]] for i in range(len(nodes)) for j in range(i) if abs(corr[i,j]) > 1-1e-10]
    if report['condition_number'] > 1e8 or report['dependent_columns']:
        report['warnings'].append('Duplicate or nearly dependent columns make conditional tests unstable. Remove redundant measurements explicitly.')
        report['valid'] = False
    return report


def split_indices(n, seed):
    order = np.random.default_rng(seed).permutation(n)
    a,b = int(.6*n),int(.8*n)
    return {'training': order[:a].tolist(), 'validation': order[a:b].tolist(), 'evaluation': order[b:].tolist(),
            'seed': seed, 'policy': '60/20/20; preprocessing, discovery and fitting use training only'}


def dataset_id(data, nodes):
    # JavaScript JSON serialization does not preserve the sign of zero. These
    # values are numerically identical, so keep identity portable across the
    # browser/native boundary without mutating the caller's observations.
    canonical=np.array(data,dtype='<f8',copy=True)
    canonical[canonical==0]=0
    return hashlib.sha256(canonical.tobytes() + '\0'.join(nodes).encode()).hexdigest()[:24]
