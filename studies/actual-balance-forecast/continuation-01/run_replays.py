"""Run the inspected equivalent-control scripts after all four submissions."""
import json
from pathlib import Path

from adjudicate import run

HERE = Path(__file__).resolve().parent
OBLIGATIONS = {
    'experimental-opt-in', 'dashboard-entry', 'monthly-recurring-values',
    'daily-projection', 'range-projection', 'persisted-widget', 'posted-activity',
}


def main():
    for approach in ('openspec', 'plan', 'prompt'):
        directory = HERE / 'runs' / approach
        output = directory / 'adjudication/attempt-01'
        if output.exists():
            raise RuntimeError(f'Inspect existing evidence before retrying: {output}')
        script = HERE / 'qa-scripts' / f'{approach}.mjs'
        bindings = json.loads(script.with_suffix('.json').read_text())
        result = run(directory / 'evaluation/candidate-tree', script, output, bindings)
        print(json.dumps({
            'approach': approach,
            'passed': result['passed'],
            'feature_checks_passed': sum(c['id'] in OBLIGATIONS and c['status'] == 'passed' for c in result['checks']),
            'source_unchanged': result['source_integrity']['unchanged'],
        }), flush=True)


if __name__ == '__main__':
    main()
