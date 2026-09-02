<!--
  MilestoneCard.vue - one milestone and its open issues, for Milestones.vue.

  Every string here is a milestone title, an issue title, a label or a login,
  written by anyone with a GitHub account. The generator escaped them; render
  with {{ }} only, and build links through milestoneLink()/issueLink(), which
  re-validate the org/repo#N the generator emitted rather than trusting any
  text in the file.
-->
<script>
import { issueLink, milestoneLink } from '../reportData.js';

export default {
  props: {
    milestone: { type: Object, required: true },
  },
  computed: {
    totalIssues() {
      return this.milestone.open_issues + this.milestone.closed_issues;
    },
  },
  methods: { issueLink, milestoneLink },
};
</script>

<template>
  <div class="card mb-3">
    <div class="card-header d-flex justify-content-between align-items-baseline flex-wrap gap-2">
      <span>
        <a v-if="milestoneLink(milestone)" :href="milestoneLink(milestone)" class="fw-semibold">
          {{ milestone.title }}
        </a>
        <span v-else class="fw-semibold">{{ milestone.title }}</span>
        <span class="text-body-secondary fw-normal ms-2">{{ milestone.repo }}</span>
      </span>
      <span class="small">
        <template v-if="milestone.due_on">
          due {{ milestone.due_on }}
          <span v-if="milestone.past_due" class="badge outcome outcome-failed ms-1">past due</span>
        </template>
        <span v-else class="text-body-secondary">no due date</span>
        <span class="text-body-secondary ms-2">
          {{ milestone.open_issues }} open / {{ totalIssues }} total
        </span>
      </span>
    </div>
    <ul class="list-group list-group-flush">
      <li v-for="(issue, index) in milestone.issues" :key="index" class="list-group-item small">
        <a v-if="issueLink(issue)" :href="issueLink(issue)" class="font-monospace me-2">
          {{ issue.issue }}
        </a>
        {{ issue.title }}
        <span v-if="issue.assignee" class="text-body-secondary ms-1">@{{ issue.assignee }}</span>
        <span
          v-for="label in issue.labels ?? []"
          :key="label"
          class="badge text-bg-secondary ms-1 fw-normal"
        >
          {{ label }}
        </span>
      </li>
      <!-- An empty milestone is a cleanup candidate, so it reads as empty
           rather than as a card with nothing under it. -->
      <li v-if="!milestone.issues.length" class="list-group-item small text-body-secondary">
        No open issues — a cleanup candidate.
      </li>
    </ul>
  </div>
</template>
