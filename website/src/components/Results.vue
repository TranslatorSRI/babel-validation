<!--
  Results.vue - the tests-by-environment matrix, its filters, and the URL state
  that makes a view shareable.

  Report values are untrusted (GitHub issue bodies, Google Sheet cells, service
  responses). They are rendered as text via {{ }} only - never v-html - and
  every link is built from validated parts in reportData.js, never taken
  verbatim from report text. Blocklist rows must never show detail: the sheet
  they come from may not be public.

  URL parameters are untrusted too. `kinds`, `has` and `env` are filtered
  against known values; `cat` and `src` cannot be, because their valid values
  only exist after the report loads - so they are used solely as string
  equality tests and never reach markup or a URL.
-->
<script>
import { sortByDeploymentOrder } from '../deploymentOrder.js';
import FilterBar from './FilterBar.vue';
import {
  ALL_KINDS,
  ALL_OUTCOMES,
  DEFAULT_PAGE_SIZE,
  KIND_HEADINGS,
  KIND_ORDER,
  OUTCOME_LABELS,
  PAGE_SIZES,
  SIGNATURE_PATTERN,
  explorerLink,
  fetchReport,
  formatCount,
  isInteresting,
  issueLink,
  rowLabel,
  serviceLinks,
  signature,
} from '../reportData.js';

const NO_CATEGORY = '(none)';

function emptyFilters() {
  return {
    interestingOnly: true,
    q: '',
    kinds: [], // empty = all kinds
    has: [], // empty = any outcome; else row must have one of these
    cat: '',
    src: '',
    env: '', // restricts the outcome filter to one environment
    sig: '', // one outcome pattern across all environments, from the drift panel
  };
}

export default {
  components: { FilterBar },
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return {
      report: null,
      loadError: null,
      filters: emptyFilters(),
      expandedKey: null,
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
      pageSizes: PAGE_SIZES,
      // Watchers are registered before created(), so they see readUrl()'s
      // assignments as edits and reset the page. Ignore them until the
      // initial read has flushed.
      urlReady: false,
      allKinds: ALL_KINDS,
      allOutcomes: ALL_OUTCOMES,
      kindHeadings: KIND_HEADINGS,
      outcomeLabels: OUTCOME_LABELS,
    };
  },
  created() {
    this.readUrl();
    this.$nextTick(() => {
      this.urlReady = true;
    });
  },
  async mounted() {
    await this.load();
  },
  watch: {
    filters: {
      deep: true,
      handler() {
        if (!this.urlReady) return;
        this.page = 1;
        this.writeUrl();
      },
    },
    page() {
      if (!this.urlReady) return;
      this.writeUrl();
    },
    pageSize() {
      if (!this.urlReady) return;
      this.page = 1;
      this.writeUrl();
    },
    expandedKey() {
      if (!this.urlReady) return;
      this.writeUrl();
    },
  },
  computed: {
    targetNames() {
      return sortByDeploymentOrder(Object.keys(this.report?.targets ?? {}));
    },
    totalResults() {
      return Object.keys(this.report?.results ?? {}).length;
    },
    totalInteresting() {
      if (!this.report) return 0;
      return Object.values(this.report.results).filter(isInteresting).length;
    },
    // Facet values are report content, so blocklist rows are excluded here as
    // well as in the table: a dropdown is as public as a cell.
    categories() {
      return this.facet('category');
    },
    sources() {
      return this.facet('source');
    },
    filteredRows() {
      if (!this.report) return [];
      const needle = this.filters.q.trim().toLowerCase();
      return Object.entries(this.report.results)
        .map(([key, result]) => ({ key, result, label: rowLabel(key, result) }))
        .filter((row) => !this.filters.interestingOnly || isInteresting(row.result))
        .filter((row) => !this.filters.kinds.length || this.filters.kinds.includes(row.result.kind))
        .filter((row) => this.matchesOutcome(row.result))
        .filter(
          (row) =>
            !this.filters.cat ||
            (this.filters.cat === NO_CATEGORY
              ? !row.result.category
              : row.result.category === this.filters.cat)
        )
        .filter((row) => !this.filters.src || row.result.source === this.filters.src)
        .filter(
          (row) =>
            !this.filters.sig || signature(row.result, this.targetNames) === this.filters.sig
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
      // pin it on top rather than showing nothing. hasOwn, not a raw index:
      // ?test=constructor would otherwise pin an Object.prototype member.
      if (
        this.expandedKey &&
        Object.hasOwn(this.report?.results ?? {}, this.expandedKey) &&
        !rows.some((row) => row.key === this.expandedKey)
      ) {
        const result = this.report.results[this.expandedKey];
        rows.unshift({
          key: this.expandedKey,
          result,
          label: rowLabel(this.expandedKey, result),
        });
      }
      return rows;
    },
  },
  methods: {
    formatCount,
    issueLink,
    facet(field) {
      const seen = new Set();
      for (const result of Object.values(this.report?.results ?? {})) {
        if (result.kind !== 'blocklist' && result[field]) seen.add(result[field]);
      }
      return [...seen].sort((a, b) => a.localeCompare(b));
    },
    async load() {
      this.loadError = null;
      try {
        this.report = await fetchReport(this.dataUrl);
      } catch (e) {
        this.loadError = String(e);
      }
    },
    matchesOutcome(result) {
      // With an environment chosen, the outcome filter applies to that
      // environment only: "failing in dev" rather than "failing anywhere".
      if (this.filters.env) {
        // hasOwn, not a raw index, for the same reason as ?test= above:
        // ?env=constructor would otherwise find a truthy Object.prototype
        // member whose .o is undefined, and with no outcome filter set every
        // row would pass — the filter matching everything rather than nothing.
        if (!Object.hasOwn(result.outcomes ?? {}, this.filters.env)) return false;
        const cell = result.outcomes[this.filters.env];
        if (!cell) return false;
        return !this.filters.has.length || this.filters.has.includes(cell.o);
      }
      if (!this.filters.has.length) return true;
      return Object.values(result.outcomes).some((cell) => this.filters.has.includes(cell.o));
    },
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
      // Not allowlisted: the report has not loaded yet, so the valid values are
      // unknown. Only ever compared for equality, so an unknown value simply
      // matches no rows.
      this.filters.cat = (params.get('cat') ?? '').slice(0, 200);
      this.filters.src = (params.get('src') ?? '').slice(0, 200);
      this.filters.env = (params.get('env') ?? '').slice(0, 40);
      const sig = params.get('sig') ?? '';
      this.filters.sig = SIGNATURE_PATTERN.test(sig) ? sig : '';
      this.expandedKey = params.get('test');
      const page = parseInt(params.get('page') ?? '1', 10);
      if (Number.isInteger(page) && page > 1 && page <= 10000) this.page = page;
      const pageSize = parseInt(params.get('ps') ?? '', 10);
      if (PAGE_SIZES.includes(pageSize)) this.pageSize = pageSize;
    },
    writeUrl() {
      // Clamp before writing: ?page=9999 on a three-page result set renders page
      // 3, and the link we put in the address bar has to say 3 too. Safe here
      // because writeUrl only runs after urlReady, i.e. after a user edit, by
      // which time the report has loaded and pageCount is real.
      if (this.page !== this.currentPage) this.page = this.currentPage;
      const params = new URLSearchParams();
      if (!this.filters.interestingOnly) params.set('all', '1');
      if (this.filters.q.trim()) params.set('q', this.filters.q.trim());
      if (this.filters.kinds.length) params.set('kinds', this.filters.kinds.join(','));
      if (this.filters.has.length) params.set('has', this.filters.has.join(','));
      if (this.filters.cat) params.set('cat', this.filters.cat);
      if (this.filters.src) params.set('src', this.filters.src);
      if (this.filters.env) params.set('env', this.filters.env);
      if (this.filters.sig) params.set('sig', this.filters.sig);
      if (this.page > 1) params.set('page', String(this.page));
      if (this.pageSize !== DEFAULT_PAGE_SIZE) params.set('ps', String(this.pageSize));
      if (this.expandedKey) params.set('test', this.expandedKey);
      const query = params.toString();
      // Always absolute. replaceState resolves a relative URL against the
      // *document base*, and Layout.astro emits <base href="/babel-validation/">,
      // so a bare `?q=...` here rewrites the address bar from /results/ to the
      // Dashboard — which ignores every one of these parameters, so a reloaded
      // or copied link comes back empty.
      window.history.replaceState(null, '', `${window.location.pathname}${query ? `?${query}` : ''}`);
    },
    resetFilters() {
      this.filters = emptyFilters();
    },
    kindHeading(index) {
      const kind = this.rows[index].result.kind;
      if (index > 0 && this.rows[index - 1].result.kind === kind) return null;
      return KIND_HEADINGS[kind] ?? kind;
    },
    serviceLinks(key, result) {
      return serviceLinks(key, result, this.report, this.targetNames);
    },
    explorerLink(key, result) {
      return explorerLink(key, result, this.targetNames);
    },
    toggleExpanded(key) {
      this.expandedKey = this.expandedKey === key ? null : key;
    },
  },
};
</script>

<template>
  <div v-if="loadError" class="card border-danger">
    <div class="card-body">
      <h2 class="h5 card-title">Could not load the test report</h2>
      <p class="mb-3"><code>{{ dataUrl }}</code> — {{ loadError }}</p>
      <button type="button" class="btn btn-sm btn-outline-danger" @click="load">Try again</button>
    </div>
  </div>

  <div v-else-if="!report" class="card placeholder-glow" aria-busy="true">
    <div class="card-body">
      <span class="placeholder col-3 mb-3"></span>
      <span v-for="n in 8" :key="n" class="placeholder col-12 mb-2"></span>
      <span class="visually-hidden">Loading the test report…</span>
    </div>
  </div>

  <div v-else>
    <div class="filter-bar">
      <FilterBar
        :filters="filters"
        :kinds="allKinds"
        :kind-headings="kindHeadings"
        :outcomes="allOutcomes"
        :categories="categories"
        :sources="sources"
        :target-names="targetNames"
        :shown="filteredRows.length"
        :total="totalResults"
        :interesting="totalInteresting"
        @reset="resetFilters"
      />
    </div>

    <div class="card">
      <table class="table table-dense table-hover align-middle sticky-head mb-0">
        <thead>
          <tr>
            <th>Test</th>
            <th class="d-none d-lg-table-cell">Category</th>
            <th v-for="target in targetNames" :key="target" class="text-center">{{ target }}</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="(row, index) in rows" :key="row.key">
            <tr v-if="kindHeading(index)" class="table-light">
              <th :colspan="2 + targetNames.length">{{ kindHeading(index) }}</th>
            </tr>
            <tr
              tabindex="0"
              role="button"
              :aria-expanded="expandedKey === row.key"
              @click="toggleExpanded(row.key)"
              @keydown.enter.prevent="toggleExpanded(row.key)"
              @keydown.space.prevent="toggleExpanded(row.key)"
            >
              <td>{{ row.label }}</td>
              <td class="d-none d-lg-table-cell text-body-secondary">{{ row.result.category }}</td>
              <td v-for="target in targetNames" :key="target" class="text-center">
                <span
                  v-if="row.result.outcomes[target]"
                  class="badge outcome"
                  :class="`outcome-${row.result.outcomes[target].o}`"
                >
                  {{ outcomeLabels[row.result.outcomes[target].o] }}
                </span>
              </td>
            </tr>
            <!-- Blocklist rows never show detail, whatever the report carries:
                 the sheet behind them may not be public. -->
            <tr v-if="expandedKey === row.key && row.result.kind !== 'blocklist'">
              <td :colspan="2 + targetNames.length" class="bg-body-tertiary">
                <div class="small font-monospace text-body-secondary mb-2">{{ row.key }}</div>
                <div class="mb-2 d-flex flex-wrap gap-3">
                  <a v-if="issueLink(row.result)" :href="issueLink(row.result)">
                    Issue {{ row.result.issue }}
                  </a>
                  <a v-if="row.result.source_url" :href="row.result.source_url">
                    Source: {{ row.result.source }}
                  </a>
                  <span v-else-if="row.result.source">Source: {{ row.result.source }}</span>
                  <a
                    v-if="explorerLink(row.key, row.result)"
                    :href="explorerLink(row.key, row.result)"
                  >
                    Babel Explorer
                  </a>
                  <a
                    v-for="link in serviceLinks(row.key, row.result)"
                    :key="link.label"
                    :href="link.url"
                  >
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
          <tr v-if="rows.length === 0">
            <td :colspan="2 + targetNames.length" class="text-center text-body-secondary py-4">
              No test results match the current filters.
              <button type="button" class="btn btn-sm btn-outline-secondary ms-2" @click="resetFilters">
                Reset filters
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <nav v-if="pageCount > 1" class="d-flex align-items-center gap-3 flex-wrap mt-3">
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
      <label class="small text-body-secondary">
        Rows per page:
        <select v-model.number="pageSize" class="form-select form-select-sm d-inline-block w-auto">
          <option v-for="size in pageSizes" :key="size" :value="size">{{ size }}</option>
        </select>
      </label>
    </nav>
  </div>
</template>
