// Exercises the interface's real search code against concept queries.
//
// The scoring functions and the concept index are read out of app.js rather than
// duplicated here, so this checks what ships. Usage:
//   node tests/search_ranking.js '[["pell","pell-equation"], ...]'
// Prints one line per case and exits non-zero if any expected tool is not ranked first.
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const app = fs.readFileSync(path.join(root, 'numerisect/static/app.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'numerisect/static/index.html'), 'utf8');

function region(startMarker, endMarker) {
  const start = app.indexOf(startMarker);
  if (start < 0) throw new Error(`app.js is missing ${startMarker}`);
  const end = app.indexOf(endMarker, start);
  return app.slice(start, end + endMarker.length);
}

const aliasSource = region('const toolAliases = {', '\n};\n');
const sectionSource = region('const primeSections = {', '\n};\n');
const scoreStart = app.indexOf('function termPattern');
const scoreEnd = app.indexOf('function initializeCommandPalette');
if (scoreStart < 0 || scoreEnd < 0) throw new Error('app.js is missing the search functions');
const scoreSource = app.slice(scoreStart, scoreEnd);

const meta = {};
for (const match of html.matchAll(/<form id="([a-z0-9-]+-form)"[^>]*>([\s\S]*?)<\/form>/g)) {
  const eyebrow = /class="eyebrow">([^<]+)</.exec(match[2]);
  const heading = /<h2>([\s\S]*?)<\/h2>/.exec(match[2]);
  const description = /<p>([\s\S]*?)<\/p>/.exec(match[2]);
  if (!heading) continue;
  const clean = (value) => value.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
  meta[match[1]] = {
    eyebrow: eyebrow ? eyebrow[1].trim() : '',
    title: clean(heading[1]),
    description: description ? clean(description[1]) : '',
  };
}

const build = new Function('meta', `
  ${aliasSource}
  ${sectionSource}
  const primeTools = new Map();
  let index = 0;
  for (const [, details] of Object.entries(primeSections)) {
    for (const formId of details.forms) {
      const slug = formId.replace(/-form$/, '');
      const record = meta[formId] || { title: slug, description: '', eyebrow: '' };
      const aliases = toolAliases[slug] || '';
      primeTools.set(slug, Object.assign({}, record, {
        slug, aliases, group: details.label, index: index++,
        haystack: (record.title + ' ' + record.description + ' ' + record.eyebrow
                   + ' ' + details.label + ' ' + aliases).toLocaleLowerCase(),
      }));
    }
  }
  ${scoreSource}
  return { primeTools, searchTools };
`);

const { primeTools, searchTools } = build(meta);
const cases = JSON.parse(process.argv[2] || '[]');
let failures = 0;
for (const [query, expected] of cases) {
  const hits = searchTools(query).slice(0, 3).map((tool) => tool.slug);
  const first = hits[0] === expected;
  if (!first) failures += 1;
  console.log(`${first ? 'ok  ' : 'FAIL'} ${JSON.stringify(query)} -> ${hits.join(', ') || '(nothing)'}`);
}
console.log(`tools=${primeTools.size} cases=${cases.length} failures=${failures}`);
process.exit(failures ? 1 : 0);
