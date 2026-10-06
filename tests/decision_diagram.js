// Exercises the interface's own decision-path drawing against a real strategy result.
//
// The drawing code is read out of app.js rather than copied here. A diagram of a
// decision path is only honest if it draws the steps the engine returned and nothing
// else: one node per step, the engine's own answer on each, the consequence on the
// connector, and the terminal node marked as terminal.
//
// Usage: node tests/decision_diagram.js
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const app = fs.readFileSync(path.join(root, 'numerisect/static/app.js'), 'utf8');

function regionBefore(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  if (start < 0) throw new Error(`app.js is missing ${startMarker}`);
  const end = app.indexOf(endMarker, start);
  if (end < 0) throw new Error(`app.js is missing ${endMarker}`);
  return app.slice(start, end);
}

const helpers = regionBefore('const escapeHtml =', 'function statusLabel');
const diagram = regionBefore('function decisionDiagram', "bindFactorLab('#factor-lab-strategy-form'");
const build = new Function(`${helpers}\n${diagram}\nreturn { decisionDiagram };`);
const { decisionDiagram } = build();

// Captured from POST /api/factor-lab/strategy for 12 times a 59-digit composite, which
// is a path where the small-factor question answers yes.
const data = {
  value: '120000000000000000000000006715200000000000000000000020200356',
  digits: '60',
  recommended_engine: 'YAFU SIQS',
  small_factors: ['2^2', '3^1'],
  decision_path: [
    { question: 'Is the input prime?', answer: 'no', consequence: 'continue' },
    { question: 'Any factor below 10^6?', answer: 'yes', consequence: 'removed before heavy work' },
    { question: 'Is the cofactor a perfect power?', answer: 'no', consequence: 'continue' },
    { question: 'Cofactor decimal digits', answer: '59', consequence: 'selects the engine' },
    { question: 'ECM depth already completed', answer: '0', consequence: 'raises the expected size of any remaining factor' },
    { question: 'Recommended engine', answer: 'YAFU SIQS', consequence: 'final' },
  ],
};

const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

const html = decisionDiagram(data);
check((html.match(/class="decision-step"/g) || []).length === 6, 'one node per step is expected');
check((html.match(/class="decision-edge"/g) || []).length === 5, 'every step but the last needs a connector');
check((html.match(/decision-node terminal/g) || []).length === 1, 'exactly one terminal node');
check(html.includes('>YAFU SIQS<'), 'the recommended engine is missing');
check(html.includes('selects the engine'), 'a consequence is missing from the connectors');
check(html.includes('<code>2^2</code>') && html.includes('<code>3^1</code>'),
      'the small factors are not attached to the question that found them');
check(!html.includes('undefined'), 'the diagram contains undefined');

// An input that is prime stops at the first question, which is then the terminal node.
const prime = decisionDiagram({
  small_factors: [],
  decision_path: [
    { question: 'Is the input prime?', answer: 'yes', consequence: 'no factoring required' },
  ],
});
check((prime.match(/decision-node terminal/g) || []).length === 1, 'the early exit is not terminal');
check(!prime.includes('class="decision-edge"'), 'a single terminal node needs no connector');

// No path at all draws nothing rather than an empty frame.
check(decisionDiagram({ decision_path: [] }) === '', 'an empty path should draw nothing');

// Markup in an engine answer is escaped.
const hostile = decisionDiagram({
  small_factors: [],
  decision_path: [{ question: '<b>q</b>', answer: '<script>x</script>', consequence: 'final' }],
});
check(!hostile.includes('<script>'), 'an answer is not escaped');
check(!hostile.includes('<b>q</b>'), 'a question is not escaped');

console.log(`checks=${failures.length === 0 ? 'passed' : 'failed'} failures=${failures.length}`);
failures.forEach((message) => console.log(`  - ${message}`));
process.exit(failures.length === 0 ? 0 : 1);
