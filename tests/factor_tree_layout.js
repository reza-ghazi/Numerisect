// Exercises the interface's own factor-tree layout against a known chain.
//
// The layout and SVG code are read out of app.js rather than copied here, so this
// checks what ships. A tree drawing is only honest if the picture matches the chain the
// server returned: every edge present, every box inside the canvas, children below
// their parent, and no two leaves in the same column.
//
// Usage: node tests/factor_tree_layout.js
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

// escapeHtml and shortNumber, then the layout and the drawing: all read out of app.js,
// so nothing here is a second implementation of what ships.
const helpers = regionBefore('const escapeHtml =', 'function statusLabel');
const layout = regionBefore('const TREE_COLUMN =', 'async function drawFactorTree');

const build = new Function(`
  ${helpers}
  ${layout}
  return { layoutFactorTree, factorTreeSvg };
`);
const { layoutFactorTree, factorTreeSvg } = build();

// 3 * 1009 * 1013 peeled in that order: two internal cofactors, four leaves.
const tree = {
  number: '3066351',
  complete: true,
  remaining: '1',
  ordered_by: 'discovery time',
  engine: 'PARI/GP',
  note: 'PARI/GP divided out each factor in turn.',
  nodes: [
    { id: 0, parent: null, value: '3066351', digits: 7, kind: 'input', status: 'input', engine: '', first_seen_seconds: null, child_job_id: null },
    { id: 1, parent: 0, value: '3', digits: 1, kind: 'factor', status: 'prime', engine: 'YAFU', first_seen_seconds: 0.25, child_job_id: null },
    { id: 2, parent: 0, value: '1022117', digits: 7, kind: 'cofactor', status: 'composite', engine: '', first_seen_seconds: null, child_job_id: 'child001' },
    { id: 3, parent: 2, value: '1009', digits: 4, kind: 'factor', status: 'prime', engine: 'YAFU', first_seen_seconds: 1.5, child_job_id: null },
    { id: 4, parent: 2, value: '1013', digits: 4, kind: 'cofactor', status: 'prime', engine: '', first_seen_seconds: null, child_job_id: null },
    { id: 5, parent: 4, value: '1013', digits: 4, kind: 'factor', status: 'prime', engine: 'YAFU', first_seen_seconds: 1.5, child_job_id: null },
  ],
};

const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

const placed = layoutFactorTree(tree.nodes);
const byId = new Map(placed.nodes.map((node) => [node.id, node]));

// Every child sits strictly below its parent, and inside the canvas.
for (const node of placed.nodes) {
  check(node.x >= 0 && node.x <= placed.width, `node ${node.id} is outside the width`);
  check(node.y >= 0 && node.y <= placed.height, `node ${node.id} is outside the height`);
  if (node.parent === null) continue;
  check(node.y > byId.get(node.parent).y, `node ${node.id} is not below its parent`);
}

// Leaves occupy distinct columns, so no two boxes overlap.
const leafIds = placed.nodes
  .filter((node) => !placed.nodes.some((other) => other.parent === node.id))
  .map((node) => node.id);
const leafColumns = new Set(leafIds.map((id) => byId.get(id).x));
check(leafColumns.size === leafIds.length, 'two leaves share a column');
check(leafIds.length === 3, `expected 3 leaves, found ${leafIds.length}`);

// An internal node is centred over its children rather than placed arbitrarily.
const kids = placed.nodes.filter((node) => node.parent === 0).map((node) => node.x);
check(
  Math.abs(byId.get(0).x - (Math.min(...kids) + Math.max(...kids)) / 2) < 1e-9,
  'the root is not centred over its children',
);

const svg = factorTreeSvg(tree);
check(svg.startsWith('<svg'), 'the drawing is not an svg element');
check((svg.match(/<line /g) || []).length === 5, 'one edge per non-root node is expected');
check((svg.match(/<g class="tree-node/g) || []).length === 6, 'one box per node is expected');
check(svg.includes('data-job="child001"'), 'the continued cofactor is not clickable');
check(svg.includes('tree-node cofactor composite linked'), 'the linked cofactor lost its classes');
check(svg.includes('0.250 s'), 'a discovery time is missing from the drawing');
check(svg.includes('>1022117<'), 'the cofactor value is missing from the drawing');
check(!svg.includes('undefined'), 'the drawing contains undefined');

// A chain with one factor still draws: input and leaf, one edge.
const single = factorTreeSvg({
  number: '4', complete: false, remaining: '2', ordered_by: 'recorded order',
  engine: 'PARI/GP', note: '',
  nodes: [
    { id: 0, parent: null, value: '4', digits: 1, kind: 'input', status: 'input', engine: '', first_seen_seconds: null, child_job_id: null },
    { id: 1, parent: 0, value: '2', digits: 1, kind: 'factor', status: 'prime', engine: 'PARI/GP', first_seen_seconds: null, child_job_id: null },
  ],
});
check((single.match(/<line /g) || []).length === 1, 'a two-node chain needs one edge');

// Markup in a value is escaped rather than injected.
const hostile = factorTreeSvg({
  number: '<img>', complete: false, remaining: '1', ordered_by: 'x', engine: 'y', note: '',
  nodes: [{ id: 0, parent: null, value: '<script>x</script>', digits: 1, kind: 'input', status: 'input', engine: '<b>', first_seen_seconds: null, child_job_id: null }],
});
check(!hostile.includes('<script>'), 'a value is not escaped');
check(!hostile.includes('<b>'), 'an engine name is not escaped');

console.log(`checks=${failures.length === 0 ? 'passed' : 'failed'} failures=${failures.length}`);
failures.forEach((message) => console.log(`  - ${message}`));
process.exit(failures.length === 0 ? 0 : 1);
