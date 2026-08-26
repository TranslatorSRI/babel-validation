<!--
  Dashboard.vue - renders report.json as per-target status cards plus a
  tests-by-environment matrix.

  Everything in report.json ultimately comes from untrusted input (GitHub issue
  bodies, Google Sheet cells, service responses). The generator escapes and
  validates it server-side, and this component only ever renders it as text via
  {{ }} interpolation - no v-html anywhere. Links are constructed here from
  validated parts (allowlisted org/repo#N ids, targets.ini URLs), never taken
  verbatim from report text. The Google Sheet ID and links to the sheet must
  never appear here: casual observers of this public site should not find it.
-->
<script>
const KIND_ORDER = { issue: 0, gsheet: 1, other: 2, blocklist: 3 };
const KIND_HEADINGS = {
  issue: 'GitHub issues',
  gsheet: 'Babel Validation Google Sheet',
  other: 'Other tests',
  blocklist: 'Blocklist',
};

export default {
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return {
      report: null,
      loadError: null,
      interestingOnly: true,
      textFilter: '',
      expandedKey: null,
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
  async mounted() {
    try {
      const response = await fetch(this.dataUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this.report = await response.json();
    } catch (e) {
      this.loadError = String(e);
    }
  },
  computed: {
    targetNames() {
      return Object.keys(this.report?.targets ?? {});
    },
    unreachableTargets() {
      return this.targetNames.filter((t) => this.report.targets[t].unreachable);
    },
    totalResults() {
      return Object.keys(this.report?.results ?? {}).length;
    },
    totalInteresting() {
      if (!this.report) return 0;
      return Object.values(this.report.results).filter(this.isInteresting).length;
    },
    rows() {
      if (!this.report) return [];
      const all = Object.entries(this.report.results).map(([key, result]) => ({
        key,
        result,
        label: this.rowLabel(key, result),
        interesting: this.isInteresting(result),
      }));
      const needle = this.textFilter.trim().toLowerCase();
      return all
        .filter((row) => !this.interestingOnly || row.interesting)
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
  },
  methods: {
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
    formatCount(value) {
      return typeof value === 'number' ? value.toLocaleString('en-US') : '—';
    },
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

    <div class="row g-3 mb-4">
      <div v-for="target in targetNames" :key="target" class="col-md-6 col-xl-4">
        <div class="card h-100" :class="{ 'border-warning': report.targets[target].unreachable }">
          <div class="card-header d-flex justify-content-between">
            <strong>{{ target }}</strong>
            <span>
              <a v-if="report.targets[target].nodenorm_status.babel_version_url"
                 :href="report.targets[target].nodenorm_status.babel_version_url">
                Babel {{ report.targets[target].nodenorm_status.babel_version }}
              </a>
              <template v-else-if="report.targets[target].nodenorm_status.babel_version">
                Babel {{ report.targets[target].nodenorm_status.babel_version }}
              </template>
              <template v-else>Babel version unknown</template>
            </span>
          </div>
          <div class="card-body small">
            <div v-if="report.targets[target].nodenorm_status.error" class="text-danger">
              NodeNorm status: {{ report.targets[target].nodenorm_status.error }}
            </div>
            <div v-else>
              NodeNorm: {{ formatCount(report.targets[target].nodenorm_status.databases?.eq_id_to_id_db?.count) }} identifiers
              <template v-if="report.targets[target].nodenorm_status.databases?.eq_id_to_id_db?.used_memory_rss_human">
                ({{ report.targets[target].nodenorm_status.databases.eq_id_to_id_db.used_memory_rss_human }})
              </template>
              <template v-if="report.targets[target].nodenorm_status.biolink_version">
                · Biolink {{ report.targets[target].nodenorm_status.biolink_version }}
              </template>
            </div>
            <div v-if="report.targets[target].nameres_status.error" class="text-danger">
              NameRes status: {{ report.targets[target].nameres_status.error }}
            </div>
            <div v-else>
              NameRes
              <template v-if="report.targets[target].nameres_status.nameres_version">
                {{ report.targets[target].nameres_status.nameres_version }}:
              </template>
              {{ formatCount(report.targets[target].nameres_status.solr?.numDocs) }} documents
              <template v-if="report.targets[target].nameres_status.solr?.size">
                ({{ report.targets[target].nameres_status.solr.size }})
              </template>
              <template v-if="report.targets[target].nameres_status.recent_queries?.p95_ms != null">
                · p95 {{ report.targets[target].nameres_status.recent_queries.p95_ms }} ms
              </template>
            </div>
            <div class="mt-2">
              <template v-for="(count, outcome) in report.targets[target].counts" :key="outcome">
                <span v-if="count > 0" class="badge me-1" :class="outcomeBadges[outcome]">
                  {{ count }} {{ outcome }}
                </span>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="d-flex align-items-center gap-3 mb-2 flex-wrap">
      <div class="form-check form-switch">
        <input id="interesting-only" v-model="interestingOnly" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="interesting-only">
          Interesting only ({{ totalInteresting }} of {{ totalResults }}):
          failing, unexpectedly passing, or differing across environments
        </label>
      </div>
      <input v-model="textFilter" type="search" class="form-control form-control-sm w-auto"
             placeholder="Filter by test, query or category…" />
    </div>

    <table class="table table-sm align-middle">
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
</style>
