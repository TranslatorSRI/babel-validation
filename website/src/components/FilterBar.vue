<!--
  FilterBar.vue - the controls above the results matrix, and nothing else. It
  knows nothing about the URL: Results.vue owns that, and passes the filter
  object down.

  The bar sticks to the top of the viewport and the table header sticks
  directly beneath it, which is why it measures itself into --filterbar-h.
  Neither sticky layer survives an ancestor with `overflow: auto`, so this must
  not be wrapped in .table-responsive.

  Category and source values come from the report, which is untrusted: they are
  rendered as text and only ever compared for equality, never interpolated into
  markup or a URL path.
-->
<script>
export default {
  props: {
    filters: { type: Object, required: true },
    kinds: { type: Array, required: true },
    kindHeadings: { type: Object, required: true },
    outcomes: { type: Array, required: true },
    categories: { type: Array, required: true },
    sources: { type: Array, required: true },
    targetNames: { type: Array, required: true },
    shown: { type: Number, required: true },
    total: { type: Number, required: true },
    interesting: { type: Number, required: true },
  },
  emits: ['reset'],
  data() {
    return {
      copyState: null, // null | 'copied' | 'failed'
      observer: null,
    };
  },
  mounted() {
    // The bar wraps to two or three rows on a narrow window, so the offset the
    // table header sticks at cannot be a constant.
    this.publishHeight();
    if (typeof ResizeObserver === 'function') {
      this.observer = new ResizeObserver(this.publishHeight);
      this.observer.observe(this.$el.parentElement ?? this.$el);
    }
  },
  beforeUnmount() {
    this.observer?.disconnect();
    // And remove the property, not just stop updating it: it lives on
    // documentElement, which outlives this component. Results.vue unmounts the
    // bar on a load error, and the stale height then holds the table header's
    // sticky offset down the page with no bar there to justify it.
    document.documentElement.style.removeProperty('--filterbar-h');
  },
  methods: {
    publishHeight() {
      const height = this.$el.parentElement?.offsetHeight ?? this.$el.offsetHeight ?? 0;
      document.documentElement.style.setProperty('--filterbar-h', `${height}px`);
    },
    toggle(list, value) {
      const next = list.includes(value)
        ? list.filter((item) => item !== value)
        : [...list, value];
      // Replace the array rather than mutating it: the parent watches deeply.
      return next;
    },
    async copyLink() {
      try {
        await navigator.clipboard.writeText(window.location.href);
        this.copyState = 'copied';
      } catch {
        this.copyState = 'failed';
      }
      setTimeout(() => {
        this.copyState = null;
      }, 3000);
    },
  },
};
</script>

<template>
  <div class="d-flex flex-wrap align-items-center gap-2 py-2">
    <input
      v-model="filters.q"
      type="search"
      class="form-control form-control-sm"
      style="max-width: 20rem"
      placeholder="Search test, query or category"
      aria-label="Search test, query or category"
    />

    <div class="btn-group btn-group-sm" role="group" aria-label="Filter by outcome">
      <button
        v-for="outcome in outcomes"
        :key="outcome"
        type="button"
        class="btn"
        :class="filters.has.includes(outcome) ? 'btn-secondary' : 'btn-outline-secondary'"
        :aria-pressed="filters.has.includes(outcome)"
        @click="filters.has = toggle(filters.has, outcome)"
      >
        {{ outcome }}
      </button>
    </div>

    <select
      v-model="filters.env"
      class="form-select form-select-sm w-auto"
      aria-label="Restrict the outcome filter to one environment"
    >
      <option value="">any environment</option>
      <option v-for="target in targetNames" :key="target" :value="target">in {{ target }}</option>
    </select>

    <select
      v-model="filters.cat"
      class="form-select form-select-sm w-auto"
      aria-label="Filter by category"
    >
      <option value="">all categories</option>
      <option value="(none)">(no category)</option>
      <option v-for="category in categories" :key="category" :value="category">
        {{ category }}
      </option>
    </select>

    <select
      v-model="filters.src"
      class="form-select form-select-sm w-auto"
      aria-label="Filter by source"
    >
      <option value="">all sources</option>
      <option v-for="source in sources" :key="source" :value="source">{{ source }}</option>
    </select>

    <div class="btn-group btn-group-sm" role="group" aria-label="Filter by test source">
      <button
        v-for="kind in kinds"
        :key="kind"
        type="button"
        class="btn"
        :class="filters.kinds.includes(kind) ? 'btn-secondary' : 'btn-outline-secondary'"
        :aria-pressed="filters.kinds.includes(kind)"
        :title="kindHeadings[kind]"
        @click="filters.kinds = toggle(filters.kinds, kind)"
      >
        {{ kind }}
      </button>
    </div>

    <div class="form-check form-switch mb-0">
      <input
        id="interesting-only"
        v-model="filters.interestingOnly"
        class="form-check-input"
        type="checkbox"
      />
      <label class="form-check-label small text-nowrap" for="interesting-only">
        Interesting only
      </label>
    </div>

    <button
      v-if="filters.sig"
      type="button"
      class="btn btn-sm btn-secondary font-monospace"
      title="Showing one outcome pattern across the environments — click to clear"
      @click="filters.sig = ''"
    >
      pattern {{ filters.sig }} ✕
    </button>

    <div class="ms-auto d-flex align-items-center gap-2">
      <span class="text-body-secondary small text-nowrap">
        {{ shown.toLocaleString('en-US') }} of {{ total.toLocaleString('en-US') }}
      </span>
      <button type="button" class="btn btn-sm btn-outline-primary" @click="copyLink">
        {{ copyState === 'copied' ? 'Copied!' : 'Copy link' }}
      </button>
      <button type="button" class="btn btn-sm btn-outline-secondary" @click="$emit('reset')">
        Reset
      </button>
    </div>

    <div v-if="copyState === 'failed'" class="small text-danger w-100">
      Could not access the clipboard — copy the address bar instead; it carries the same filters.
    </div>
    <div v-if="filters.interestingOnly" class="small text-body-secondary w-100">
      Showing the {{ interesting.toLocaleString('en-US') }} tests that fail, pass unexpectedly, or
      differ across environments. Switch off “Interesting only” for all
      {{ total.toLocaleString('en-US') }}.
    </div>
  </div>
</template>
