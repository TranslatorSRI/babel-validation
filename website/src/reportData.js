/*
  reportData.js - everything about report.json that is not rendering: how to
  fetch it, how to label a row, which rows are worth looking at, and how to
  build the outbound links.

  Everything here ultimately comes from untrusted input (GitHub issue bodies,
  Google Sheet cells, service responses). The generator escapes and validates it
  server-side; components must still render it as text via {{ }} interpolation
  only - no v-html anywhere - and links must be constructed from validated parts
  as they are below, never taken verbatim from report text. The Google Sheet IDs
  and links to the sheets must never appear on this site.

  Not in a lib/ subdirectory: the root .gitignore's Python-template `lib/`
  pattern silently swallows any directory of that name.
*/

export const KIND_ORDER = { issue: 0, gsheet: 1, other: 2, blocklist: 3 };

export const KIND_HEADINGS = {
  issue: 'GitHub issues',
  gsheet: 'Babel Validation Google Sheet',
  other: 'Other tests',
  blocklist: 'Blocklist',
};

export const ALL_KINDS = ['issue', 'gsheet', 'other', 'blocklist'];

export const ALL_OUTCOMES = [
  'passed',
  'failed',
  'xfailed',
  'xpassed',
  'skipped',
  'error',
];

export const OUTCOME_LABELS = {
  passed: 'pass',
  failed: 'FAIL',
  xfailed: 'xfail',
  xpassed: 'XPASS',
  skipped: 'skip',
  error: 'ERR',
};

// One character per outcome, so a row's behaviour across every environment fits
// in a short string: "pppppF" is "passes everywhere except prod". Compact
// enough for a URL, and the alphabet is closed, so ?sig= can be validated.
export const OUTCOME_CODES = {
  passed: 'p',
  failed: 'F',
  xfailed: 'x',
  xpassed: 'X',
  skipped: 's',
  error: 'E',
};

export const SIGNATURE_PATTERN = /^[pFxXsE-]{1,32}$/;

export function signature(result, targetNames) {
  return targetNames
    .map((target) => OUTCOME_CODES[result.outcomes[target]?.o] ?? '-')
    .join('');
}

// Rendering thousands of all-passing rows at once freezes the browser, so the
// matrix is paginated. The default page size is large enough that the
// interesting rows normally fit on one page.
export const DEFAULT_PAGE_SIZE = 100;
export const PAGE_SIZES = [25, 100, 500];

export function formatCount(value) {
  return typeof value === 'number' ? value.toLocaleString('en-US') : null;
}

// One row per /status value; adding a row here is all it takes to show a new
// one. `value` receives one entry of report.targets; null renders as an em
// dash. `href` may return a generator-validated URL to link the value to.
//
// `compare` marks the rows where environments are *supposed* to agree, and so
// where a minority value is a finding. Record counts, index sizes and latencies
// differ between environments by nature; shading them made every row amber and
// taught the reader to ignore the colour.
export const STATUS_ROWS = [
  {
    label: 'Babel version',
    value: (t) => t.nodenorm_status.babel_version,
    href: (t) => t.nodenorm_status.babel_version_url,
    compare: true,
  },
  {
    label: 'Biolink model',
    value: (t) => t.nodenorm_status.biolink_version,
    compare: true,
  },
  {
    label: 'NodeNorm status',
    value: (t) => t.nodenorm_status.error ?? t.nodenorm_status.status,
    danger: (t) => Boolean(t.nodenorm_status.error),
    compare: true,
  },
  {
    label: 'NodeNorm records',
    value: (t) => formatCount(t.nodenorm_status.databases?.eq_id_to_id_db?.count),
  },
  {
    label: 'NodeNorm memory',
    value: (t) => t.nodenorm_status.databases?.eq_id_to_id_db?.used_memory_rss_human,
  },
  {
    label: 'NameRes status',
    value: (t) => t.nameres_status.error ?? t.nameres_status.status,
    danger: (t) => Boolean(t.nameres_status.error),
    compare: true,
  },
  {
    label: 'NameRes version',
    value: (t) => t.nameres_status.nameres_version,
    compare: true,
  },
  {
    label: 'Solr documents',
    value: (t) => formatCount(t.nameres_status.solr?.numDocs),
  },
  { label: 'Solr index size', value: (t) => t.nameres_status.solr?.size },
  {
    label: 'NameRes p95 latency',
    value: (t) => {
      const p95 = t.nameres_status.recent_queries?.p95_ms;
      return p95 == null ? null : `${p95} ms`;
    },
  },
];

// --- Loading -------------------------------------------------------------

// Fetched whole on both pages: report.json is ~1.8 MB. No sessionStorage memo,
// because there is nothing to fix — GitHub Pages serves it with
// `cache-control: max-age=600` (measured 2026-08-31), so a navigation between
// the Dashboard and Results inside ten minutes is served from the browser cache
// and never reaches the network. Re-measure before adding one.
export async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return await response.json();
}

export const fetchReport = fetchJson;

export async function fetchHistory(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const text = await response.text();
  return text
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => {
      // Per line, not over the whole file: a truncated last line — a partial
      // CDN response, a deploy interrupted mid-write — must cost one run, not
      // the entire page.
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter((run) => run && typeof run === 'object')
    .reverse();
}

// --- Rows ----------------------------------------------------------------

// A row is worth looking at if something failed anywhere, or if the
// environments disagree - which is the signal this dashboard exists for.
export function isInteresting(result) {
  const outcomes = Object.values(result.outcomes).map((cell) => cell.o);
  if (outcomes.some((o) => o === 'failed' || o === 'xpassed' || o === 'error')) {
    return true;
  }
  return new Set(outcomes).size > 1;
}

export function rowLabel(key, result) {
  if (result.kind === 'gsheet') {
    // A sheet row can carry neither a label nor an ID, and rendered as "row 53:"
    // trailing off into nothing. The row number is the whole label in that case.
    const label = result.query_label || result.query_id;
    return label ? `row ${result.row}: ${label}` : `row ${result.row}`;
  }
  if (result.kind === 'issue') return result.issue;
  if (result.kind === 'blocklist') return 'blocklist entry (details withheld)';
  // Trim the test-file path down to module::test[param].
  return key.replace(/^.*\//, '');
}

// --- Link construction, from validated parts only. -----------------------
// The regexes and the encodeURIComponent calls below are the security
// boundary, not style. Do not tidy them.

export function issueLink(result) {
  // result.issue was validated against the repository allowlist by the generator.
  const match = /^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#([0-9]+)$/.exec(result.issue ?? '');
  if (!match) return null;
  return `https://github.com/${match[1]}/issues/${match[2]}`;
}

export function milestoneLink(milestone) {
  // Same shape and same re-validation as issueLink: the generator emitted
  // org/repo#N only after checking it against targets.ini's allowlist, and the
  // URL is built from the captured parts, never from milestone.repo as text.
  const match = /^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#([0-9]+)$/.exec(milestone.milestone ?? '');
  if (!match) return null;
  return `https://github.com/${match[1]}/milestone/${match[2]}`;
}

export function isNodeNorm(key) {
  return key.startsWith('nodenorm/') || key.startsWith('github_issues/');
}

export function serviceLinks(key, result, report, targetNames) {
  // Direct query links to each environment's service for this test's query.
  const links = [];
  for (const target of targetNames) {
    if (!(target in result.outcomes)) continue;
    const urls = report.targets[target];
    if (result.query_id && isNodeNorm(key) && urls.nodenorm_url) {
      links.push({
        label: `NodeNorm ${target}`,
        url: `${urls.nodenorm_url}get_normalized_nodes?curie=${encodeURIComponent(result.query_id)}`,
      });
    }
    if (result.query_label && key.startsWith('nameres/') && urls.nameres_url) {
      links.push({
        label: `NameRes ${target}`,
        url: `${urls.nameres_url}lookup?string=${encodeURIComponent(result.query_label)}`,
      });
    }
  }
  return links;
}

export function explorerLink(key, result, targetNames) {
  const targets = targetNames
    .filter((t) => t in result.outcomes)
    .map((t) => `target=${encodeURIComponent(t)}`)
    .join('&');
  if (result.query_id && isNodeNorm(key)) {
    return `https://translatorsri.github.io/babel-explorer/nodenorm/?curie=${encodeURIComponent(result.query_id)}&${targets}`;
  }
  if (result.query_label && key.startsWith('nameres/')) {
    const term = result.query_id
      ? `${result.query_label} [[${result.query_id}]]`
      : result.query_label;
    return `https://translatorsri.github.io/babel-explorer/nameres/?term=${encodeURIComponent(term)}&${targets}`;
  }
  return null;
}

export function runLink(runId) {
  if (!/^[0-9]+$/.test(runId ?? '')) return null;
  return `https://github.com/TranslatorSRI/babel-validation/actions/runs/${runId}`;
}
