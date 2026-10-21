"""Reject faster results if their measured simulation trajectories differ."""
import argparse
import json
from pathlib import Path

def compare(before, after):
    for field in ('map_size', 'seed', 'turns_requested', 'profiled', 'python', 'numpy'):
        assert before[0][field] == after[0][field], f'Different benchmark setting: {field}'
    old = {(r['scenario'], r['initial_ants']): r for r in before[1:]}
    new = {(r['scenario'], r['initial_ants']): r for r in after[1:]}
    assert old and old.keys() == new.keys(), 'Missing or different benchmark cases'
    results, checkpoints = [], 0
    for key, a in old.items():
        b = new[key]
        assert a['fingerprints'] == b['fingerprints'], f'Behavior changed: {key}'
        assert a['populations'] == b['populations'], f'Population trajectory changed: {key}'
        for metric in ('final_ants', 'turns', 'attacks', 'births', 'ant_deaths', 'queenless', 'ended'):
            assert a[metric] == b[metric], f'{metric} changed: {key}'
        checkpoints += len(a['fingerprints'])
        results.append(dict(scenario=key[0], initial_ants=key[1], final_ants=a['final_ants'],
                            before_mean_ms=a['mean_ms_per_turn'], after_mean_ms=b['mean_ms_per_turn'],
                            mean_speedup=round(a['mean_ms_per_turn']/b['mean_ms_per_turn'], 3),
                            before_worst_ms=a['max_ms_per_turn'], after_worst_ms=b['max_ms_per_turn'],
                            worst_speedup=round(a['max_ms_per_turn']/b['max_ms_per_turn'], 3),
                            attacks=a['attacks'], births=a['births'], deaths=a['ant_deaths']))
    return dict(all_fingerprints_match=True, cases=len(results), checkpoints=checkpoints, results=results)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def read(path):
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    result = compare(read(args.before), read(args.after))
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
