<!--
  DriftPanel.vue - the shapes failures make across the deployment pipeline.

  Of the tests worth looking at, almost all differ between environments, and
  they differ in a small number of recurring ways: "passes everywhere but prod"
  is one finding about one Babel version, not 147 unrelated failures. Grouping
  by the outcome tuple turns the matrix into that finding.

  Signatures are built from outcome names, never from report text.
-->
<script>
import { OUTCOME_LABELS, isInteresting, signature } from '../reportData.js';

const TOP_N = 8;

export default {
  props: {
    results: { type: Object, required: true },
    targetNames: { type: Array, required: true },
    resultsUrl: { type: String, required: true },
  },
  data() {
    return { outcomeLabels: OUTCOME_LABELS };
  },
  computed: {
    patterns() {
      const tally = new Map();
      for (const result of Object.values(this.results)) {
        if (!isInteresting(result)) continue;
        const sig = signature(result, this.targetNames);
        const entry = tally.get(sig) ?? { sig, count: 0, outcomes: [] };
        if (!entry.count) {
          entry.outcomes = this.targetNames.map(
            (target) => result.outcomes[target]?.o ?? null
          );
        }
        entry.count += 1;
        tally.set(sig, entry);
      }
      return [...tally.values()].sort((a, b) => b.count - a.count).slice(0, TOP_N);
    },
    totalPatterns() {
      const seen = new Set();
      for (const result of Object.values(this.results)) {
        if (isInteresting(result)) seen.add(signature(result, this.targetNames));
      }
      return seen.size;
    },
  },
  methods: {
    patternUrl(sig) {
      return `${this.resultsUrl}?${new URLSearchParams({ sig }).toString()}`;
    },
  },
};
</script>

<template>
  <div class="card mb-4">
    <div class="card-header">
      How failures fall across the pipeline
      <span class="fw-normal text-body-secondary">
        — the {{ patterns.length }} most common of {{ totalPatterns }} patterns
      </span>
    </div>
    <div class="table-responsive">
      <table class="table table-dense table-hover align-middle mb-0">
        <thead>
          <tr>
            <th class="text-end">Tests</th>
            <th v-for="target in targetNames" :key="target" class="text-center">{{ target }}</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pattern in patterns" :key="pattern.sig">
            <td class="text-end fw-semibold">{{ pattern.count.toLocaleString('en-US') }}</td>
            <td v-for="(outcome, index) in pattern.outcomes" :key="index" class="text-center">
              <span v-if="outcome" class="badge outcome" :class="`outcome-${outcome}`">
                {{ outcomeLabels[outcome] }}
              </span>
              <span v-else class="text-body-secondary">—</span>
            </td>
            <td class="text-end">
              <a class="btn btn-sm btn-outline-secondary" :href="patternUrl(pattern.sig)">Show</a>
            </td>
          </tr>
          <tr v-if="!patterns.length">
            <td :colspan="targetNames.length + 2" class="text-center text-body-secondary py-3">
              Every environment agrees, and nothing is failing.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
