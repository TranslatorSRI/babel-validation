<!--
  History.vue - one row per daily validation run, newest first, and a summary
  of what moved since the run before it.

  No chart: with a handful of runs a table says more, and every value here is
  nullable. ponytail: revisit once there are ~14 runs, when a sparkline per
  environment would beat reading down a column.

  Values come from each service's /status endpoint and are untrusted: render
  them with {{ }} only.
-->
<script>
import { sortByDeploymentOrder } from '../deploymentOrder.js';
import { fetchHistory, formatCount } from '../reportData.js';

const COUNTS = ['failed', 'xpassed', 'passed'];

export default {
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return { runs: null, loadError: null };
  },
  async mounted() {
    try {
      this.runs = await fetchHistory(this.dataUrl);
    } catch (e) {
      this.loadError = String(e);
    }
  },
  computed: {
    targetNames() {
      const names = [];
      for (const run of this.runs ?? []) {
        for (const name of Object.keys(run.targets ?? {})) {
          if (!names.includes(name)) names.push(name);
        }
      }
      return sortByDeploymentOrder(names);
    },
    // What moved between the two most recent runs: version bumps and count
    // deltas, per environment. Everything else in the file stays as it was.
    changes() {
      const [latest, previous] = this.runs ?? [];
      if (!latest || !previous) return [];
      const changes = [];
      for (const target of this.targetNames) {
        const now = latest.targets?.[target];
        const before = previous.targets?.[target];
        if (!now || !before) continue;
        for (const field of ['babel_version', 'nameres_version']) {
          if (now[field] !== before[field]) {
            changes.push({
              target,
              label: field.replace('_', ' '),
              from: before[field] ?? '—',
              to: now[field] ?? '—',
            });
          }
        }
        for (const count of COUNTS) {
          const delta = (now.counts?.[count] ?? 0) - (before.counts?.[count] ?? 0);
          if (delta !== 0) {
            changes.push({
              target,
              label: count,
              delta,
              to: formatCount(now.counts?.[count]) ?? '—',
            });
          }
        }
      }
      return changes;
    },
  },
  methods: {
    formatCount(value) {
      return formatCount(value) ?? '—';
    },
  },
};
</script>

<template>
  <div v-if="loadError" class="card border-danger">
    <div class="card-body">
      <h2 class="h5 card-title">Could not load the run history</h2>
      <p class="mb-0"><code>{{ dataUrl }}</code> — {{ loadError }}</p>
    </div>
  </div>

  <div v-else-if="!runs" class="card placeholder-glow" aria-busy="true">
    <div class="card-body">
      <span v-for="n in 4" :key="n" class="placeholder col-12 mb-2"></span>
      <span class="visually-hidden">Loading the run history…</span>
    </div>
  </div>

  <div v-else>
    <div v-if="changes.length" class="card mb-4">
      <div class="card-header">
        Since the previous run
        <span class="fw-normal text-body-secondary">({{ runs[1].date }})</span>
      </div>
      <ul class="list-group list-group-flush">
        <li v-for="(change, index) in changes" :key="index" class="list-group-item small">
          <span class="fw-semibold">{{ change.target }}</span>
          {{ change.label }}
          <template v-if="change.delta != null">
            <span
              class="badge"
              :class="change.delta > 0 ? 'outcome outcome-failed' : 'outcome outcome-passed'"
            >
              {{ change.delta > 0 ? '+' : '' }}{{ change.delta }}
            </span>
            → {{ change.to }}
          </template>
          <template v-else> {{ change.from }} → {{ change.to }} </template>
        </li>
      </ul>
    </div>
    <p v-else-if="runs.length > 1" class="text-body-secondary">
      Nothing changed between the last two runs.
    </p>

    <div class="card">
      <table class="table table-dense align-middle mb-0">
        <thead>
          <tr>
            <th>Date</th>
            <th v-for="target in targetNames" :key="target">{{ target }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="run in runs" :key="run.date + (run.run_id ?? '')">
            <td class="text-nowrap">{{ run.date }}</td>
            <td v-for="target in targetNames" :key="target" class="small">
              <template v-if="run.targets?.[target]">
                <div>
                  Babel {{ run.targets[target].babel_version ?? '?' }} · NameRes
                  {{ run.targets[target].nameres_version ?? '?' }}
                </div>
                <div class="text-body-secondary">
                  {{ formatCount(run.targets[target].nn_eq_records) }} ids ·
                  {{ formatCount(run.targets[target].solr_docs) }} docs
                  <template v-if="run.targets[target].p95_ms != null">
                    · p95 {{ run.targets[target].p95_ms }} ms
                  </template>
                </div>
                <div class="mt-1">
                  <span
                    v-if="run.targets[target].counts?.failed"
                    class="badge outcome outcome-failed me-1"
                  >
                    {{ run.targets[target].counts.failed }} failed
                  </span>
                  <span
                    v-if="run.targets[target].counts?.xpassed"
                    class="badge outcome outcome-xpassed me-1"
                  >
                    {{ run.targets[target].counts.xpassed }} xpassed
                  </span>
                  <span
                    v-if="run.targets[target].counts?.passed"
                    class="badge outcome outcome-passed"
                  >
                    {{ run.targets[target].counts.passed }} passed
                  </span>
                </div>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
