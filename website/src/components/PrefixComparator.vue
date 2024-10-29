<script setup lang="ts">
/*
 * SearchCAMs: search for CAMs with a set of criteria.
 */
import {ref, watch} from "vue";

export interface Props {
  prefix_json_url1?: string,
  prefix_json_url2?: string
}

const props = withDefaults(defineProps<Props>(), {
  prefix_json_url1: '/babel-validation/prefix_reports/prefix_report-2024oct1-maybe.json',
  prefix_json_url2: '/babel-validation/prefix_reports/prefix_reports.json',
});

// Eventually, we will allow people to paste the JSON in directly.
const report1 = ref('');
const report2 = ref('');

if (props.prefix_json_url1) {
  fetch(props.prefix_json_url1).then(res => res.json()).then(report => report1.value = JSON.stringify(report, null, 2))
}

if (props.prefix_json_url2) {
  fetch(props.prefix_json_url1).then(res => res.json()).then(report => report2.value = JSON.stringify(report, null, 2))
}

watch([report1, report2], () => {
  // Reparse?
});
</script>

<template>
  <div class="col-12">
    <div class="card">
      <div class="card-header">
        <strong>Prefix Comparator Inputs</strong>
      </div>
      <div class="card-body">
        <div class="form-floating">
          <textarea class="form-control" style="height: 10em" placeholder="Paste a prefix report here." id="prefixReport1" v-model="report1"></textarea>
          <label for="floatingTextarea">Prefix Report 1</label>
        </div>
        <div class="form-floating">
          <textarea class="form-control" style="height: 10em" placeholder="Paste a second prefix report here." id="prefixReport2" v-model="report2"></textarea>
          <label for="floatingTextarea">Prefix Report 2</label>
        </div>
      </div>
    </div>

    <div class="card my-2">
      <div class="card-header">
        <strong>Differences</strong>
      </div>
      <div class="card-body p-0">
        <table class="table table-bordered ">
          <thead>
          <tr>
            <th>Edges</th>
          </tr>
          </thead>
          <tbody>

          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>