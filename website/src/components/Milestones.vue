<!--
  Milestones.vue - every open milestone across the Babel repositories, by due
  date, with the open issues in each.

  Two sections, not one list: the legacy priority buckets (Immediate, Needed
  soon, ...) have no due date and never close, so sorting them among real
  deadlines would either bury the deadlines or dress the buckets up as ones.
  The generator flags them; this only honours the flag.

  Values come from GitHub milestones and issues and are untrusted: render them
  with {{ }} only. See MilestoneCard.vue, which does the rendering.
-->
<script>
import { fetchJson } from '../reportData.js';
import MilestoneCard from './MilestoneCard.vue';

export default {
  components: { MilestoneCard },
  props: {
    dataUrl: { type: String, required: true },
  },
  data() {
    return { data: null, loadError: null };
  },
  async mounted() {
    await this.load();
  },
  computed: {
    milestones() {
      return this.data?.milestones ?? [];
    },
    releases() {
      return this.milestones.filter((milestone) => !milestone.bucket);
    },
    buckets() {
      return this.milestones.filter((milestone) => milestone.bucket);
    },
    openIssueCount() {
      return this.milestones.reduce((total, m) => total + (m.issues?.length ?? 0), 0);
    },
    pastDueCount() {
      return this.milestones.filter((milestone) => milestone.past_due).length;
    },
    generatedOn() {
      // Not decoration: the publish job carries forward the last published copy
      // of this file when a run fails to regenerate it, so this date is how you
      // tell today's data from a week-old copy.
      return (this.data?.generated_at ?? '').slice(0, 10);
    },
  },
  methods: {
    async load() {
      this.loadError = null;
      try {
        this.data = await fetchJson(this.dataUrl);
      } catch (e) {
        this.loadError = String(e);
      }
    },
  },
};
</script>

<template>
  <div v-if="loadError" class="card border-danger">
    <div class="card-body">
      <h2 class="h5 card-title">Could not load the milestones</h2>
      <p class="mb-3"><code>{{ dataUrl }}</code> — {{ loadError }}</p>
      <button type="button" class="btn btn-sm btn-outline-danger" @click="load">Try again</button>
    </div>
  </div>

  <div v-else-if="!data" class="card placeholder-glow" aria-busy="true">
    <div class="card-body">
      <span v-for="n in 4" :key="n" class="placeholder col-12 mb-2"></span>
      <span class="visually-hidden">Loading the milestones…</span>
    </div>
  </div>

  <div v-else>
    <p class="text-body-secondary">
      {{ milestones.length }} open milestones · {{ openIssueCount }} open issues<template
        v-if="pastDueCount"
      >
        · <span class="text-danger fw-semibold">{{ pastDueCount }} past due</span> </template
      >· as of {{ generatedOn }}
    </p>

    <p v-if="!milestones.length" class="text-body-secondary">
      No open milestones in any of the Babel repositories.
    </p>

    <MilestoneCard
      v-for="milestone in releases"
      :key="`${milestone.repo}#${milestone.number}`"
      :milestone="milestone"
    />

    <template v-if="buckets.length">
      <h2 class="h5 mt-4 mb-1">Priority buckets (not deadlines)</h2>
      <p class="text-body-secondary small mb-3">
        Undated milestones used to rank work rather than to commit to a date. They never close, so
        they are listed apart from the release schedule above.
      </p>
      <MilestoneCard
        v-for="milestone in buckets"
        :key="`${milestone.repo}#${milestone.number}`"
        :milestone="milestone"
      />
    </template>
  </div>
</template>
