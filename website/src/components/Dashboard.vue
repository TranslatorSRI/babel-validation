<!--
  Dashboard.vue - renders report.json as a status-by-environment table plus a
  tests-by-environment matrix, both in deployment order (exp first, prod last).

  Everything in report.json ultimately comes from untrusted input (GitHub issue
  bodies, Google Sheet cells, service responses). The generator escapes and
  validates it server-side, and this component only ever renders it as text via
  {{ }} interpolation - no v-html anywhere. Links are constructed here from
  validated parts (allowlisted org/repo#N ids, targets.ini URLs), never taken
  verbatim from report text. The Google Sheet IDs and links to the sheets must
  never appear here: casual observers of this public site should not find them.
  URL query parameters are also untrusted: they only ever feed string filters
  and key lookups, never markup or fetch targets.
-->
<script>
// Not in a lib/ subdirectory: the root .gitignore's Python-template `lib/`
// pattern silently swallows any directory of that name.
import { sortByDeploymentOrder } from '../deploymentOrder.js';

const KIND_ORDER = { issue: 0, gsheet: 1, other: 2, blocklist: 3 };
const KIND_HEADINGS = {
  issue: 'GitHub issues',
  gsheet: 'Babel Validation Google Sheet',
  other: 'Other tests',
  blocklist: 'Blocklist',
};
const ALL_KINDS = ['issue', 'gsheet', 'other', 'blocklist'];
const ALL_OUTCOMES = ['passed', 'failed', 'xfailed', 'xpassed', 'skipped', 'error'];

// One row per /status value; adding a row here is all it takes to show a new
// one. `value` receives one entry of report.targets; null renders as an em
// dash. `href` may return a generator-validated URL to link the value to.
const STATUS_ROWS = [
  {
    label: 'Babel version',
    value: (t) => t.nodenorm_status.babel_version,
    href: (t) => t.nodenorm_status.babel_version_url,
  },
  { label: 'Biolink model', value: (t) => t.nodenorm_status.biolink_version },
  {
    label: 'NodeNorm status',
    value: (t) => t.nodenorm_status.error ?? t.nodenorm_status.status,
    danger: (t) => Boolean(t.nodenorm_status.error),
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
  },
  { label: 'NameRes version', value: (t) => t.nameres_status.nameres_version },
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

// Rendering thousands of all-passing rows at once freezes the browser, so the
// matrix is paginated. The default page size is large enough that the
// interesting rows normally fit on one page.
const DEFAULT_PAGE_SIZE = 100;
const PAGE_SIZES = [25, 100, 500];

function formatCount(value) {
  return typeof value === 'number' ? value.toLocaleString('en-US') : null;
}

export default {
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return {
      report: null,
      loadError: null,
      filters: {
        interestingOnly: true,
        q: '',
        kinds: [], // empty = all kinds
        has: [], // empty = any outcome; else row must have one of these
      },
      filtersOpen: false,
      expandedKey: null,
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
      pageSizes: PAGE_SIZES,
      copyState: null, // null | 'copied' | 'failed'
      statusRows: STATUS_ROWS,
      allKinds: ALL_KINDS,
      allOutcomes: ALL_OUTCOMES,
      kindHeadings: KIND_HEADINGS,
      outcomeBadges: {
        passed: 'text-bg-success',
        failed: 'text-bg-danger',
        xfailed: 'text-bg-secondary',
        xpassed: 'text-bg-warning',
        skipped: 'text-bg-light',
        error: 'text-bg-dark',
      },
      outcomeLabels: {
        passed: 'pass',
        failed: 'FAIL',
        xfailed: 'xfail',
        xpassed: 'XPASS',
        skipped: 'skip',
        error: 'ERR',
      },
    };
  },
  created() {
    this.readUrl();
  },
  async mounted() {
    try {
      const response = await fetch(this.dataUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this.report = await response.json();
    } catch (e) {
      this.loadError = String(e);
    }
  },
  watch: {
    filters: {
      deep: true,
      handler() {
        this.page = 1;
        this.writeUrl();
      },
    },
    page() {
      this.writeUrl();
    },
    pageSize() {
      this.page = 1;
      this.writeUrl();
    },
    expandedKey() {
      this.writeUrl();
    },
  },
  computed: {
    targetNames() {
      return sortByDeploymentOrder(Object.keys(this.report?.targets ?? {}));
    },
    unreachableTargets() {
      return this.targetNames.filter((t) => this.report.targets[t].unreachable);
    },
    countRows() {
      // Always show the outcomes that carry meaning; the rarer ones only when
      // they occurred somewhere.
      return ALL_OUTCOMES.filter(
        (outcome) =>
          !['skipped', 'error'].includes(outcome) ||
          this.targetNames.some((t) => this.report.targets[t].counts[outcome] > 0)
      );
    },
    totalResults() {
      return Object.keys(this.report?.results ?? {}).length;
    },
    totalInteresting() {
      if (!this.report) return 0;
      return Object.values(this.report.results).filter(this.isInteresting).length;
    },
    filteredRows() {
      if (!this.report) return [];
      const needle = this.filters.q.trim().toLowerCase();
      return Object.entries(this.report.results)
        .map(([key, result]) => ({
          key,
          result,
          label: this.rowLabel(key, result),
        }))
        .filter((row) => !this.filters.interestingOnly || this.isInteresting(row.result))
        .filter((row) => !this.filters.kinds.length || this.filters.kinds.includes(row.result.kind))
        .filter(
          (row) =>
            !this.filters.has.length ||
            Object.values(row.result.outcomes).some((cell) => this.filters.has.includes(cell.o))
        )
        .filter(
          (row) =>
            !needle ||
            row.label.toLowerCase().includes(needle) ||
            row.key.toLowerCase().includes(needle) ||
            (row.result.category ?? '').toLowerCase().includes(needle)
        )
        .sort(
          (a, b) =>
            (KIND_ORDER[a.result.kind] ?? 9) - (KIND_ORDER[b.result.kind] ?? 9) ||
            (a.result.category ?? '').localeCompare(b.result.category ?? '') ||
            (a.result.row ?? 0) - (b.result.row ?? 0) ||
            a.key.localeCompare(b.key)
        );
    },
    pageCount() {
      return Math.max(1, Math.ceil(this.filteredRows.length / this.pageSize));
    },
    currentPage() {
      return Math.min(this.page, this.pageCount);
    },
    rows() {
      const start = (this.currentPage - 1) * this.pageSize;
      const rows = this.filteredRows.slice(start, start + this.pageSize);
      // A shared link may point at a test the current filters or page hide:
      // pin it on top rather than showing nothing.
      if (
        this.expandedKey &&
        this.report?.results[this.expandedKey] &&
        !rows.some((row) => row.key === this.expandedKey)
      ) {
        const result = this.report.results[this.expandedKey];
        rows.unshift({
          key: this.expandedKey,
          result,
          label: this.rowLabel(this.expandedKey, result),
        });
      }
      return rows;
    },
    activeFilterCount() {
      return (
        (this.filters.interestingOnly ? 0 : 1) +
        (this.filters.q.trim() ? 1 : 0) +
        (this.filters.kinds.length ? 1 : 0) +
        (this.filters.has.length ? 1 : 0)
      );
    },
  },
  methods: {
    // --- Shareable URLs: filters and the selected test live in the query
    // string, so copying the address (or the button below) reproduces the
    // view. Parsed values are untrusted and only ever used as filter strings.
    readUrl() {
      const params = new URLSearchParams(window.location.search);
      this.filters.interestingOnly = params.get('all') !== '1';
      this.filters.q = (params.get('q') ?? '').slice(0, 200);
      this.filters.kinds = (params.get('kinds') ?? '')
        .split(',')
        .filter((kind) => ALL_KINDS.includes(kind));
      this.filters.has = (params.get('has') ?? '')
        .split(',')
        .filter((outcome) => ALL_OUTCOMES.includes(outcome));
      this.expandedKey = params.get('test');
      const page = parseInt(params.get('page') ?? '1', 10);
      if (Number.isInteger(page) && page > 1 && page <= 10000) this.page = page;
      const pageSize = parseInt(params.get('ps') ?? '', 10);
      if (PAGE_SIZES.includes(pageSize)) this.pageSize = pageSize;
      if (this.activeFilterCount > 0) this.filtersOpen = true;
    },
    writeUrl() {
      const params = new URLSearchParams();
      if (!this.filters.interestingOnly) params.set('all', '1');
      if (this.filters.q.trim()) params.set('q', this.filters.q.trim());
      if (this.filters.kinds.length) params.set('kinds', this.filters.kinds.join(','));
      if (this.filters.has.length) params.set('has', this.filters.has.join(','));
      if (this.page > 1) params.set('page', String(this.page));
      if (this.pageSize !== DEFAULT_PAGE_SIZE) params.set('ps', String(this.pageSize));
      if (this.expandedKey) params.set('test', this.expandedKey);
      const query = params.toString();
      window.history.replaceState(null, '', query ? `?${query}` : window.location.pathname);
    },
    async copyLink() {
      try {
        await navigator.clipboard.writeText(window.location.href);
        this.copyState = 'copied';
      } catch {
        this.copyState = 'failed';
      }
      setTimeout(() => {
        this.copyState = null;
      }, 3000);
    },
    resetFilters() {
      this.filters = { interestingOnly: true, q: '', kinds: [], has: [] };
    },

    // --- Status table ---
    statusValue(statusRow, target) {
      return statusRow.value(this.report.targets[target]) ?? null;
    },
    statusHref(statusRow, target) {
      return statusRow.href?.(this.report.targets[target]) ?? null;
    },
    statusCellClass(statusRow, target) {
      const info = this.report.targets[target];
      if (statusRow.danger?.(info)) return 'table-danger';
      // Highlight the odd ones out when environments disagree, e.g. every
      // environment on Babel 2025sep1 except exp.
      const values = this.targetNames.map((t) => this.statusValue(statusRow, t));
      const distinct = new Set(values.filter((value) => value != null));
      if (distinct.size <= 1) return '';
      const tally = new Map();
      for (const value of values) {
        if (value != null) tally.set(value, (tally.get(value) ?? 0) + 1);
      }
      const majority = [...tally.entries()].sort((a, b) => b[1] - a[1])[0][0];
      return this.statusValue(statusRow, target) === majority ? '' : 'table-warning';
    },

    // --- Results matrix ---
    isInteresting(result) {
      const outcomes = Object.values(result.outcomes).map((cell) => cell.o);
      if (outcomes.some((o) => o === 'failed' || o === 'xpassed' || o === 'error')) return true;
      return new Set(outcomes).size > 1;
    },
    rowLabel(key, result) {
      if (result.kind === 'gsheet') {
        return `row ${result.row}: ${result.query_label || result.query_id || ''}`;
      }
      if (result.kind === 'issue') return result.issue;
      if (result.kind === 'blocklist') return 'blocklist entry (details withheld)';
      // Trim the test-file path down to module::test[param].
      return key.replace(/^.*\//, '');
    },
    kindHeading(index) {
      const kind = this.rows[index].result.kind;
      if (index > 0 && this.rows[index - 1].result.kind === kind) return null;
      return KIND_HEADINGS[kind] ?? kind;
    },

    // --- Link construction, from validated parts only. ---
    issueLink(result) {
      // result.issue was validated against the repository allowlist by the generator.
      const match = /^([A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+)#([0-9]+)$/.exec(result.issue ?? '');
      if (!match) return null;
      return `https://github.com/${match[1]}/issues/${match[2]}`;
    },
    isNodeNorm(key) {
      return key.startsWith('nodenorm/') || key.startsWith('github_issues/');
    },
    serviceLinks(key, result) {
      // Direct query links to each environment's service for this test's query.
      const links = [];
      for (const target of this.targetNames) {
        if (!(target in result.outcomes)) continue;
        const urls = this.report.targets[target];
        if (result.query_id && this.isNodeNorm(key) && urls.nodenorm_url) {
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
    },
    explorerLink(key, result) {
      const targets = this.targetNames
        .filter((t) => t in result.outcomes)
        .map((t) => `target=${encodeURIComponent(t)}`)
        .join('&');
      if (result.query_id && this.isNodeNorm(key)) {
        return `https://translatorsri.github.io/babel-explorer/nodenorm/?curie=${encodeURIComponent(result.query_id)}&${targets}`;
      }
      if (result.query_label && key.startsWith('nameres/')) {
        const term = result.query_id
          ? `${result.query_label} [[${result.query_id}]]`
          : result.query_label;
        return `https://translatorsri.github.io/babel-explorer/nameres/?term=${encodeURIComponent(term)}&${targets}`;
      }
      return null;
    },
    runLink(runId) {
      if (!/^[0-9]+$/.test(runId ?? '')) return null;
      return `https://github.com/TranslatorSRI/babel-validation/actions/runs/${runId}`;
    },
    toggleExpanded(key) {
      this.expandedKey = this.expandedKey === key ? null : key;
    },
    formatCount,
  },
};
</script>

<template>
  <div v-if="loadError" class="alert alert-danger">
    Could not load the test report: {{ loadError }}
  </div>
  <div v-else-if="!report" class="alert alert-info">Loading the test report…</div>
  <div v-else>
    <p class="text-muted">
      Generated {{ report.generated_at }}
      <template v-if="runLink(report.run.github_run_id)">
        by <a :href="runLink(report.run.github_run_id)">run {{ report.run.github_run_id }}</a>
      </template>
    </p>

    <div v-if="!report.github_issues_ran" class="alert alert-warning">
      The GitHub issue tests did not run (no results found) — probably a missing
      GitHub token. A green board proves nothing about them.
    </div>
    <div v-if="unreachableTargets.length" class="alert alert-warning">
      No test results for: {{ unreachableTargets.join(', ') }}. These
      environments may have been unreachable during the run.
    </div>

    <h2 class="h4">Environments</h2>
    <div class="table-responsive mb-4">
      <table class="table table-sm table-bordered w-auto align-middle">
        <thead>
          <tr>
            <th></th>
            <th v-for="target in targetNames" :key="target" class="text-center"
                :class="{ 'table-warning': report.targets[target].unreachable }">
              {{ target }}
              <span v-if="report.targets[target].unreachable" class="badge text-bg-warning">no results</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="statusRow in statusRows" :key="statusRow.label">
            <th class="text-nowrap fw-normal text-muted">{{ statusRow.label }}</th>
            <td v-for="target in targetNames" :key="target" class="text-center text-nowrap"
                :class="statusCellClass(statusRow, target)">
              <a v-if="statusHref(statusRow, target)" :href="statusHref(statusRow, target)">
                {{ statusValue(statusRow, target) }}
              </a>
              <template v-else>{{ statusValue(statusRow, target) ?? '—' }}</template>
            </td>
          </tr>
          <tr v-for="outcome in countRows" :key="outcome">
            <th class="text-nowrap fw-normal text-muted">{{ outcome }} tests</th>
            <td v-for="target in targetNames" :key="target" class="text-center">
              <span v-if="report.targets[target].counts[outcome] > 0"
                    class="badge" :class="outcomeBadges[outcome]">
                {{ formatCount(report.targets[target].counts[outcome]) }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
      <h2 class="h4 mb-0">Test results</h2>
      <div class="d-flex align-items-center gap-2">
        <span class="text-muted small">
          {{ formatCount(filteredRows.length) }} of {{ formatCount(totalResults) }} results<template
            v-if="filters.interestingOnly"> (interesting only)</template>
        </span>
        <button class="btn btn-sm btn-outline-secondary" @click="filtersOpen = !filtersOpen">
          Filters<span v-if="activeFilterCount"> ({{ activeFilterCount }})</span>
        </button>
      </div>
    </div>

    <div v-if="filtersOpen" class="card card-body mb-3">
      <div class="row g-3">
        <div class="col-md-4">
          <label class="form-label small mb-1" for="filter-q">Search test, query or category</label>
          <input id="filter-q" v-model="filters.q" type="search" class="form-control form-control-sm" />
          <div class="form-check form-switch mt-2">
            <input id="interesting-only" v-model="filters.interestingOnly" class="form-check-input" type="checkbox" />
            <label class="form-check-label small" for="interesting-only">
              Interesting only ({{ formatCount(totalInteresting) }} of
              {{ formatCount(totalResults) }}): failing, unexpectedly passing,
              or differing across environments.
            </label>
          </div>
        </div>
        <div class="col-md-3">
          <div class="form-label small mb-1">Test source</div>
          <div v-for="kind in allKinds" :key="kind" class="form-check">
            <input :id="`kind-${kind}`" v-model="filters.kinds" class="form-check-input" type="checkbox" :value="kind" />
            <label class="form-check-label small" :for="`kind-${kind}`">{{ kindHeadings[kind] }}</label>
          </div>
        </div>
        <div class="col-md-3">
          <div class="form-label small mb-1">Has outcome (in any environment)</div>
          <div v-for="outcome in allOutcomes" :key="outcome" class="form-check">
            <input :id="`has-${outcome}`" v-model="filters.has" class="form-check-input" type="checkbox" :value="outcome" />
            <label class="form-check-label small" :for="`has-${outcome}`">{{ outcome }}</label>
          </div>
        </div>
        <div class="col-md-2 d-flex flex-column gap-2">
          <button class="btn btn-sm btn-outline-primary" @click="copyLink">
            <template v-if="copyState === 'copied'">Copied!</template>
            <template v-else>Copy link to this view</template>
          </button>
          <div v-if="copyState === 'failed'" class="small text-danger">
            Could not access the clipboard — copy the address bar instead; it
            carries the same filters.
          </div>
          <button class="btn btn-sm btn-outline-secondary" @click="resetFilters">Reset filters</button>
        </div>
      </div>
    </div>

    <table class="table table-sm align-middle results-matrix">
      <thead>
        <tr>
          <th>Test</th>
          <th>Category</th>
          <th v-for="target in targetNames" :key="target" class="text-center">{{ target }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="(row, index) in rows" :key="row.key">
          <tr v-if="kindHeading(index)" class="table-light">
            <th :colspan="2 + targetNames.length">{{ kindHeading(index) }}</th>
          </tr>
          <tr role="button" @click="toggleExpanded(row.key)">
            <td>{{ row.label }}</td>
            <td class="text-muted">{{ row.result.category }}</td>
            <td v-for="target in targetNames" :key="target" class="text-center">
              <span v-if="row.result.outcomes[target]" class="badge"
                    :class="outcomeBadges[row.result.outcomes[target].o]">
                {{ outcomeLabels[row.result.outcomes[target].o] }}
              </span>
            </td>
          </tr>
          <tr v-if="expandedKey === row.key">
            <td :colspan="2 + targetNames.length" class="bg-light-subtle">
              <div class="small font-monospace text-muted mb-2">{{ row.key }}</div>
              <div class="mb-2">
                <a v-if="issueLink(row.result)" :href="issueLink(row.result)" class="me-3">Issue {{ row.result.issue }}</a>
                <a v-if="row.result.source_url" :href="row.result.source_url" class="me-3">Source: {{ row.result.source }}</a>
                <span v-else-if="row.result.source" class="me-3">Source: {{ row.result.source }}</span>
                <a v-if="explorerLink(row.key, row.result)" :href="explorerLink(row.key, row.result)" class="me-3">Babel Explorer</a>
                <a v-for="link in serviceLinks(row.key, row.result)" :key="link.label" :href="link.url" class="me-3">
                  {{ link.label }}
                </a>
              </div>
              <template v-for="target in targetNames" :key="target">
                <div v-if="row.result.outcomes[target]?.msg" class="mb-2">
                  <strong>{{ target }}:</strong>
                  <pre class="failure-message">{{ row.result.outcomes[target].msg }}</pre>
                </div>
              </template>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <p v-if="rows.length === 0" class="text-muted">No test results match the current filters.</p>
    <nav v-if="pageCount > 1" class="d-flex align-items-center gap-3 flex-wrap">
      <ul class="pagination pagination-sm mb-0">
        <li class="page-item" :class="{ disabled: currentPage <= 1 }">
          <button class="page-link" @click="page = currentPage - 1">&laquo; Previous</button>
        </li>
        <li class="page-item disabled">
          <span class="page-link">Page {{ currentPage }} of {{ formatCount(pageCount) }}</span>
        </li>
        <li class="page-item" :class="{ disabled: currentPage >= pageCount }">
          <button class="page-link" @click="page = currentPage + 1">Next &raquo;</button>
        </li>
      </ul>
      <label class="small text-muted">
        Rows per page:
        <select v-model.number="pageSize" class="form-select form-select-sm d-inline-block w-auto">
          <option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option>
        </select>
      </label>
    </nav>
  </div>
</template>

<style scoped>
.failure-message {
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(0, 0, 0, 0.05);
  padding: 0.5rem;
  margin-bottom: 0;
}
.results-matrix thead th {
  position: sticky;
  top: 0;
  background: var(--bs-body-bg, #fff);
}
</style>
