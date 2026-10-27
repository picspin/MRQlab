"""Offline evidence capture; run from any cwd with the recorded Python environment."""
import hashlib
import importlib.metadata as md
import json
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
for source in ('packages/sequence-ir', 'packages/physics', 'packages/recon', 'packages/mrqlab_experiment', 'services/api', 'services/local_agent'):
    sys.path.insert(0, str(ROOT / source))
import numpy as np
import mrqlab_experiment
from fastapi.testclient import TestClient
from mrqlab_api.main import app
from mrqlab_experiment import build_protocol_experiment, plan_experiment
from mrqlab_experiment.objectives import evaluate_multi_tissue_contrast
from mrqlab_experiment.compiler import compile_sequence

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'docs/ismrm/evidence'
OUT.mkdir(parents=True, exist_ok=True)

def write(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')

def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()

assert Path(mrqlab_experiment.__file__).resolve().is_relative_to(ROOT)
write('environment.json', {
    'code_commit': command('git', 'rev-parse', 'HEAD'),
    'working_tree_status': command('git', 'status', '--short'),
    'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for base in ('packages', 'services') for p in sorted((ROOT/base).rglob('*.py'))},
    'platform': platform.platform(), 'python': sys.version,
    'node': command('node', '--version'), 'npm': command('npm', '--version'),
    'python_packages': {d.metadata['Name']: d.version for d in md.distributions()},
    'source': str(Path(mrqlab_experiment.__file__).resolve()),
    'web_installed': json.loads(command('npm', '--prefix', 'apps/web', 'ls', '--depth=0', '--json')),
})
client = TestClient(app)
catalog = client.get('/protocol-recipes')
assert catalog.status_code == 200
write('catalog.json', catalog.json())
summary = {}
for recipe_id in ('brain_lesion_t2_tse', 'knee_cartilage_meniscus_pd_t2_tse'):
    graph = build_protocol_experiment(recipe_id)
    payload = graph.model_dump(mode='json')
    write(recipe_id + '-request.json', payload)
    plan = plan_experiment(graph)
    assert plan.fingerprint == plan_experiment(build_protocol_experiment(recipe_id)).fingerprint
    write(recipe_id + '-plan.json', plan.model_dump(mode='json'))
    validation = client.post('/experiments/validate', json=payload)
    response = client.post('/experiments/run', json=payload)
    assert validation.status_code == response.status_code == 200
    data = response.json()
    write(recipe_id + '-validation.json', validation.json())
    write(recipe_id + '-response.json', data)
    # Independent per-tissue replay of the named-pair calculation.
    contrast = evaluate_multi_tissue_contrast(graph)
    signals = [np.asarray(s, dtype=complex) for s in contrast.pop('tissue_signals')]
    contrast['tissue_signals'] = [[{'real': float(v.real), 'imag': float(v.imag)} for v in s] for s in signals]
    write(recipe_id + '-diagnostic.json', contrast)
    obs = data['observations']
    signal = next(o for o in obs if o['kind'] == 'signal')
    magnitudes = np.abs([complex(v['real'], v['imag']) for v in signal['data']])
    means = {t.id: float(np.mean(np.abs(s))) for t, s in zip(graph.tissue, signals)}
    pairs = {}
    for term in graph.clinical_recipe.objective.terms:
        delta = abs(means[term.target_tissue_id] - means[term.reference_tissue_id])
        pairs[term.id] = {'difference_au': delta, 'proxy_divided_by_0.05': delta / 0.05}
    summary[recipe_id] = {
        'http_validate': validation.status_code, 'http_run': response.status_code,
        'sequence_params': graph.sequence.params, 'plan_fingerprint': plan.fingerprint,
        'api_plan_fingerprint': signal['provenance']['plan_fingerprint'],
        'engine': plan.engine, 'representation': plan.representation,
        'products': [o['kind'] for o in obs], 'signal_samples': len(magnitudes),
        'signal_first_au': float(magnitudes[0]), 'signal_mean_au': float(np.mean(magnitudes)),
        'signal_last_au': float(magnitudes[-1]), 'tissue_mean_au': means,
        'named_pair_differences': pairs,
        'executed_pairs': next(o['data']['pairs'] for o in obs if o['kind'] == 'tissue_contrast'),
        'objective_score': next(o['data'] for o in obs if o['kind'] == 'objective_score'),
        'compiled_echoes': compile_sequence(graph).metadata['echoes'],
        'primary_pair_ids': [contrast['pairs'][0]['target_tissue_id'], contrast['pairs'][0]['reference_tissue_id']],
        'primary_pair_difference': contrast['contrast_difference'],
        'graph_objective': graph.objective.model_dump() if graph.objective else None,
        'provenance': signal['provenance'],
    }
    assert all(o['provenance']['clinical_recipe_id'] == recipe_id for o in obs)
    # Repo-native SVG, showing diagnostic per-tissue signals with explicit teaching labels.
    colors = ['#145c9e', '#c04a23', '#39834b', '#8b4f9e', '#777777']
    ymax = max(float(np.max(np.abs(s))) for s in signals)
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="460" viewBox="0 0 900 460">',
             '<rect width="900" height="460" fill="white"/>',
             f'<text x="30" y="28" font-family="sans-serif" font-size="18">{recipe_id}</text>',
             '<text x="30" y="52" font-family="sans-serif" font-size="14">Diagnostic forward signals (a.u.); teaching model, no clinical CNR</text>',
             '<path d="M60 80V360H620" fill="none" stroke="black"/>',
             f'<text x="10" y="90">{ymax:.3f}</text><text x="35" y="365">0</text>',
             '<text x="220" y="402">ADC sample index (not effective TE)</text>']
    for i, (t, s) in enumerate(zip(graph.tissue, signals)):
        points = ' '.join(f'{60+j*560/max(1,len(s)-1):.2f},{360-270*abs(v)/ymax:.2f}' for j,v in enumerate(s))
        lines += [f'<polyline points="{points}" fill="none" stroke="{colors[i]}" stroke-width="2"/>',
                  f'<text x="640" y="{110+i*40}" fill="{colors[i]}" font-family="sans-serif">{t.id}</text>']
    lines += ['</svg>']
    (OUT / (recipe_id + '.svg')).write_text('\n'.join(lines))
write('summary.json', summary)
write('sha256.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ('sha256.json',)})
print(json.dumps(summary, indent=2))
