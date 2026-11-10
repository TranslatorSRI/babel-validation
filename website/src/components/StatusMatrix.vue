<!--
  StatusMatrix.vue - the /status of every environment, side by side in
  deployment order, so that a value differing from its neighbours stands out.
  NodeNorm and NameRes get a section each, since they are loaded separately and
  can be on different Babel releases; a third section holds the test counts.

  Report values are untrusted: render them with {{ }} only, never v-html, and
  link only to URLs the generator built or validated (a section's `docsUrl`,
  from targets.ini, and a row's `href` in STATUS_SECTIONS).

  Shading uses theme.css's .cell-differs and .cell-broken, not Bootstrap's
  .table-warning and .table-danger, which keep their light colours in dark mode.
-->
<script>
import {
  ALL_OUTCOMES,
  OUTCOME_LABELS,
  STATUS_SECTIONS,
  formatCount,
} from '../reportData.js';

export default {
  props: {
    report: { type: Object, required: true },
    targetNames: { type: Array, required: true },
  },
  computed: {
    sections() {
      // Hide a row no environment has a value for: the Elasticsearch rows on a
      // day with no NodeNorm ES target, say, would otherwise be a line of dashes.
      return STATUS_SECTIONS.map((section) => ({
        ...section,
        rows: section.rows.filter((row) =>
          this.targetNames.some((t) => this.statusValue(row, t) != null)
        ),
      }));
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
    databaseNames() {
      // Every NodeNorm database any environment reports, in first-seen order.
      const names = [];
      for (const target of this.targetNames) {
        for (const name of Object.keys(
          this.report.targets[target].nodenorm_status.databases ?? {}
        )) {
          if (!names.includes(name)) names.push(name);
        }
      }
      return names;
    },
  },
  methods: {
    formatCount,
    outcomeLabel(outcome) {
      return OUTCOME_LABELS[outcome] ?? outcome;
    },
    statusValue(statusRow, target) {
      return statusRow.value(this.report.targets[target]) ?? null;
    },
    statusHref(statusRow, target) {
      return statusRow.href?.(this.report.targets[target]) ?? null;
    },
    statusCellClass(statusRow, target) {
      const info = this.report.targets[target];
      if (statusRow.danger?.(info)) return 'cell-broken';
      // Only rows the environments should agree on: see `compare` in STATUS_SECTIONS.
      if (!statusRow.compare) return '';
      // A service that reports nothing is not an odd one out: the majority is
      // found among reported values only, and shading the em dash too made it
      // look like a disagreement, but only on days the others disagreed.
      if (this.statusValue(statusRow, target) == null) return '';
      // Highlight the odd ones out when environments disagree, e.g. every
      // environment on Babel 2025sep1 except exp.
      const values = this.targetNames.map((t) => this.statusValue(statusRow, t));
      const distinct = new Set(values.filter((value) => value != null));
      if (distinct.size <= 1) return '';
      const tally = new Map();
      for (const value of values) {
        if (value != null) tally.set(value, (tally.get(value) ?? 0) + 1);
      }
      const ranked = [...tally.entries()].sort((a, b) => b[1] - a[1]);
      // A tie has no odd one out. Three environments on the new Babel version
      // and three on the old is exactly what mid-promotion looks like, and
      // picking a winner by Map insertion order would shade half the row amber
      // to say nothing.
      if (ranked.length > 1 && ranked[0][1] === ranked[1][1]) return '';
      const majority = ranked[0][0];
      return this.statusValue(statusRow, target) === majority ? '' : 'cell-differs';
    },
    database(target, name) {
      return this.report.targets[target].nodenorm_status.databases?.[name] ?? null;
    },
  },
};
</script>

<template>
  <table class="table table-dense table-bordered w-auto align-middle mb-0">
    <thead>
      <tr>
        <th></th>
        <th
          v-for="target in targetNames"
          :key="target"
          class="text-center"
          :class="{ 'cell-differs': report.targets[target].unreachable }"
        >
          {{ target }}
          <span
            v-if="report.targets[target].unreachable"
            class="badge bg-warning-subtle text-warning-emphasis"
          >
            no results
          </span>
        </th>
      </tr>
    </thead>
    <tbody>
      <template v-for="section in sections" :key="section.key">
        <tr class="table-group" :data-section="section.key">
          <th class="text-nowrap">{{ section.title }}</th>
          <td v-for="target in targetNames" :key="target" class="text-center text-nowrap small">
            <!-- Each service's /status is linked from its Status row below.
                 "API", not "docs": this is the service's Swagger UI, which a
                 reader could mistake for the written API documentation each
                 service keeps in its repository. -->
            <a v-if="section.docsUrl(report.targets[target])" :href="section.docsUrl(report.targets[target])">
              API
            </a>
          </td>
        </tr>
        <tr v-for="statusRow in section.rows" :key="statusRow.label" :data-section="section.key">
          <th class="text-nowrap fw-normal text-body-secondary ps-3">{{ statusRow.label }}</th>
          <td
            v-for="target in targetNames"
            :key="target"
            class="text-center text-nowrap"
            :class="statusCellClass(statusRow, target)"
            :title="statusRow.title?.(report.targets[target]) ?? undefined"
          >
            <a v-if="statusHref(statusRow, target)" :href="statusHref(statusRow, target)">
              {{ statusValue(statusRow, target) }}
            </a>
            <template v-else>{{ statusValue(statusRow, target) ?? '—' }}</template>
          </td>
        </tr>
      </template>
      <tr class="table-group" data-section="tests">
        <th class="text-nowrap" :colspan="targetNames.length + 1">Tests</th>
      </tr>
      <tr v-for="outcome in countRows" :key="outcome" data-section="tests">
        <th class="text-nowrap fw-normal text-body-secondary ps-3">{{ outcome }} tests</th>
        <td v-for="target in targetNames" :key="target" class="text-center">
          <span
            v-if="report.targets[target].counts[outcome] > 0"
            class="badge outcome"
            :class="`outcome-${outcome}`"
            :title="outcomeLabel(outcome)"
          >
            {{ formatCount(report.targets[target].counts[outcome]) }}
          </span>
          <span v-else class="text-body-secondary">—</span>
        </td>
      </tr>
    </tbody>
  </table>

  <!-- The status endpoint reports seven databases; the table above shows the
       one that matters day to day. The rest are here rather than nowhere. -->
  <details v-if="databaseNames.length" class="mt-3">
    <summary class="small text-body-secondary">All NodeNorm databases</summary>
    <table class="table table-dense table-bordered w-auto align-middle mt-2 mb-0">
      <thead>
        <tr>
          <th></th>
          <th v-for="target in targetNames" :key="target" class="text-center">{{ target }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="name in databaseNames" :key="name">
          <th class="text-nowrap fw-normal text-body-secondary font-monospace small">
            {{ name }}
          </th>
          <td
            v-for="target in targetNames"
            :key="target"
            class="text-center text-nowrap small"
          >
            <template v-if="database(target, name)">
              {{ formatCount(database(target, name).count) ?? '—' }}
              <span class="text-body-secondary">
                · {{ database(target, name).used_memory_rss_human ?? '—' }}
              </span>
            </template>
            <template v-else>—</template>
          </td>
        </tr>
      </tbody>
    </table>
  </details>
</template>
