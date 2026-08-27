<!--
  Overview.vue - the landing page: is anything broken, and where?

  Environments read left to right in promotion order, so a failure that has
  reached prod but not exp is visible as a shape rather than as a number.

  Report values are untrusted: {{ }} only, never v-html. The links into the
  results page carry an environment name that came from targets.ini, and are
  built with URLSearchParams rather than string concatenation.
-->
<script>
import { sortByDeploymentOrder } from '../deploymentOrder.js';
import DriftPanel from './DriftPanel.vue';
import StatusMatrix from './StatusMatrix.vue';
import { fetchReport, formatCount, isInteresting, runLink } from '../reportData.js';

export default {
  components: { DriftPanel, StatusMatrix },
  props: {
    dataUrl: { type: String, required: true },
    resultsUrl: { type: String, required: true },
  },
  data() {
    return { report: null, loadError: null };
  },
  async mounted() {
    await this.load();
  },
  computed: {
    targetNames() {
      return sortByDeploymentOrder(Object.keys(this.report?.targets ?? {}));
    },
    unreachableTargets() {
      return this.targetNames.filter((t) => this.report.targets[t].unreachable);
    },
    totalResults() {
      return Object.keys(this.report?.results ?? {}).length;
    },
    totalInteresting() {
      if (!this.report) return 0;
      return Object.values(this.report.results).filter(isInteresting).length;
    },
    unattributed() {
      const counts = this.report?.unattributed_counts ?? {};
      const total = Object.values(counts).reduce((sum, n) => sum + (n || 0), 0);
      return total;
    },
  },
  methods: {
    formatCount,
    runLink,
    async load() {
      this.loadError = null;
      try {
        this.report = await fetchReport(this.dataUrl);
      } catch (e) {
        this.loadError = String(e);
      }
    },
    counts(target) {
      return this.report.targets[target].counts;
    },
    babelVersion(target) {
      return this.report.targets[target].nodenorm_status.babel_version;
    },
    resultsLink(params) {
      return `${this.resultsUrl}?${new URLSearchParams(params).toString()}`;
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
      <span class="placeholder col-4 mb-3"></span>
      <span v-for="n in 5" :key="n" class="placeholder col-12 mb-2"></span>
      <span class="visually-hidden">Loading the test report…</span>
    </div>
  </div>

  <div v-else>
    <p class="text-body-secondary small">
      Generated {{ report.generated_at }}
      <template v-if="runLink(report.run.github_run_id)">
        by <a :href="runLink(report.run.github_run_id)">run {{ report.run.github_run_id }}</a>
      </template>
      <template v-if="report.run.git_sha">
        · {{ report.run.git_sha.slice(0, 8) }}
      </template>
    </p>

    <div v-if="!report.github_issues_ran" class="alert alert-warning">
      The GitHub issue tests did not run (no results found) — probably a missing GitHub token. A
      green board proves nothing about them.
    </div>
    <div v-if="unreachableTargets.length" class="alert alert-warning">
      No test results for: {{ unreachableTargets.join(', ') }}. These environments may have been
      unreachable during the run.
    </div>

    <p class="small text-body-secondary mb-2">
      Environments in promotion order — a new Babel version reaches
      {{ targetNames[0] }} first and {{ targetNames[targetNames.length - 1] }} last.
    </p>
    <!-- A grid, not a flex row: the cards must stay one per environment across,
         so the pipeline reads left to right rather than wrapping mid-sequence. -->
    <div class="row row-cols-2 row-cols-md-3 row-cols-xl-6 g-3 mb-4">
      <div v-for="target in targetNames" :key="target" class="col">
        <div class="card h-100">
          <div class="card-body py-2 px-3">
            <div class="d-flex justify-content-between align-items-baseline">
              <span class="fw-semibold">{{ target }}</span>
              <span class="small text-body-secondary">{{ babelVersion(target) ?? '—' }}</span>
            </div>
            <template v-if="report.targets[target].unreachable">
              <div class="fs-5 fw-semibold text-body-secondary">no results</div>
              <div class="small text-body-secondary">unreachable during the run</div>
            </template>
            <template v-else>
              <div class="fs-5 fw-semibold">
                <a
                  class="link-danger text-decoration-none"
                  :href="resultsLink({ env: target, has: 'failed' })"
                >
                  {{ formatCount(counts(target).failed) }} failed
                </a>
              </div>
              <div class="small">
                <a
                  class="link-warning text-decoration-none"
                  :href="resultsLink({ env: target, has: 'xpassed' })"
                >
                  {{ formatCount(counts(target).xpassed) }} unexpectedly passing
                </a>
              </div>
              <div class="small text-body-secondary">
                {{ formatCount(counts(target).passed) }} passed ·
                {{ formatCount(counts(target).xfailed) }} xfailed ·
                {{ formatCount(counts(target).skipped) }} skipped
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>

    <DriftPanel
      :results="report.results"
      :target-names="targetNames"
      :results-url="resultsUrl"
    />

    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center flex-wrap gap-2">
        <span>Environments</span>
        <a class="btn btn-sm btn-outline-secondary" :href="resultsUrl">
          {{ formatCount(totalInteresting) }} of {{ formatCount(totalResults) }} tests need a look →
        </a>
      </div>
      <div class="card-body">
        <StatusMatrix :report="report" :target-names="targetNames" />
        <p v-if="unattributed" class="small text-body-secondary mt-3 mb-0">
          {{ formatCount(unattributed) }} test result(s) could not be attributed to an environment,
          and are not counted above.
        </p>
      </div>
    </div>
  </div>
</template>
