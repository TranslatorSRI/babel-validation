<!--
  Trends.vue - renders history.jsonl (one compact summary line per daily run)
  as a table, newest first. All values are rendered as text via {{ }} - the
  history file is derived from untrusted service responses.
-->
<script>
import { sortByDeploymentOrder } from '../deploymentOrder.js';

export default {
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return {
      runs: null,
      loadError: null,
    };
  },
  async mounted() {
    try {
      const response = await fetch(this.dataUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const text = await response.text();
      this.runs = text
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line))
        .filter((run) => run && typeof run === 'object')
        .reverse();
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
  },
  methods: {
    formatCount(value) {
      return typeof value === 'number' ? value.toLocaleString('en-US') : '—';
    },
  },
};
</script>

<template>
  <div v-if="loadError" class="alert alert-danger">
    Could not load the run history: {{ loadError }}
  </div>
  <div v-else-if="!runs" class="alert alert-info">Loading the run history…</div>
  <table v-else class="table table-sm">
    <thead>
      <tr>
        <th>Date</th>
        <th v-for="target in targetNames" :key="target">{{ target }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="run in runs" :key="run.date + (run.run_id ?? '')">
        <td>{{ run.date }}</td>
        <td v-for="target in targetNames" :key="target" class="small">
          <template v-if="run.targets[target]">
            <div>
              Babel {{ run.targets[target].babel_version ?? '?' }}
              · NameRes {{ run.targets[target].nameres_version ?? '?' }}
            </div>
            <div class="text-muted">
              {{ formatCount(run.targets[target].nn_eq_records) }} ids ·
              {{ formatCount(run.targets[target].solr_docs) }} docs
              <template v-if="run.targets[target].p95_ms != null">
                · p95 {{ run.targets[target].p95_ms }} ms
              </template>
            </div>
            <div>
              <span class="badge text-bg-danger me-1" v-if="run.targets[target].counts?.failed">
                {{ run.targets[target].counts.failed }} failed
              </span>
              <span class="badge text-bg-warning me-1" v-if="run.targets[target].counts?.xpassed">
                {{ run.targets[target].counts.xpassed }} xpassed
              </span>
              <span class="badge text-bg-success" v-if="run.targets[target].counts?.passed">
                {{ run.targets[target].counts.passed }} passed
              </span>
            </div>
          </template>
        </td>
      </tr>
    </tbody>
  </table>
</template>
