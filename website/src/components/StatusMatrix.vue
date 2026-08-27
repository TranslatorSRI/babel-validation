<!--
  StatusMatrix.vue - the /status of every environment, side by side in
  deployment order, so that a value differing from its neighbours stands out.

  Report values are untrusted: render them with {{ }} only, never v-html, and
  link only to URLs the generator validated (the `href` in STATUS_ROWS).
-->
<script>
import {
  ALL_OUTCOMES,
  OUTCOME_LABELS,
  STATUS_ROWS,
  formatCount,
} from '../reportData.js';

export default {
  props: {
    report: { type: Object, required: true },
    targetNames: { type: Array, required: true },
  },
  data() {
    return { statusRows: STATUS_ROWS };
  },
  computed: {
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
      if (statusRow.danger?.(info)) return 'table-danger';
      // Only rows the environments should agree on: see `compare` in STATUS_ROWS.
      if (!statusRow.compare) return '';
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
          :class="{ 'table-warning': report.targets[target].unreachable }"
        >
          {{ target }}
          <span v-if="report.targets[target].unreachable" class="badge text-bg-warning">
            no results
          </span>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="statusRow in statusRows" :key="statusRow.label">
        <th class="text-nowrap fw-normal text-body-secondary">{{ statusRow.label }}</th>
        <td
          v-for="target in targetNames"
          :key="target"
          class="text-center text-nowrap"
          :class="statusCellClass(statusRow, target)"
        >
          <a v-if="statusHref(statusRow, target)" :href="statusHref(statusRow, target)">
            {{ statusValue(statusRow, target) }}
          </a>
          <template v-else>{{ statusValue(statusRow, target) ?? '—' }}</template>
        </td>
      </tr>
      <tr v-for="outcome in countRows" :key="outcome">
        <th class="text-nowrap fw-normal text-body-secondary">{{ outcome }} tests</th>
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
