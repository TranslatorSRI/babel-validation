<script setup lang="ts">
/*
 * SearchCAMs: search for CAMs with a set of criteria.
 */
import {computed, ref, watch} from "vue";
import _ from "lodash";

export interface Props {
  prefix_json_url1?: string,
  prefix_json_url2?: string
}

const props = withDefaults(defineProps<Props>(), {
  prefix_json_url1: '/babel-validation/prefix_reports/prefix_report-2024oct1-maybe.json',
  prefix_json_url2: '/babel-validation/prefix_reports/prefix_report.json',
});

// Eventually, we will allow people to paste the JSON in directly.
const report1 = ref('');
const report2 = ref('');

if (props.prefix_json_url1) {
  fetch(props.prefix_json_url1).then(res => res.json()).then(report => report1.value = JSON.stringify(report, null, 2))
}

if (props.prefix_json_url2) {
  fetch(props.prefix_json_url2).then(res => res.json()).then(report => report2.value = JSON.stringify(report, null, 2))
}

// For each report, calculate a stream of by_clique triples.
class CliqueCount {
  clique_leader_prefix: string;
  filename: string;
  prefix: string;
  prefix_count: int;

  constructor(clique_leader_prefix: string, filename: string, prefix: string, prefix_count: number) {
    this.clique_leader_prefix = clique_leader_prefix;
    this.filename = filename;
    this.prefix = prefix;
    this.prefix_count = prefix_count;
  }
}

function report_to_clique_counts(report) {
  return Object.entries(report.by_clique)
      .flatMap(clique_items => {
        if (clique_items[0].startsWith('count_')) return [];
        if ("by_file" in clique_items[1]) {
          const clique_leader = clique_items[0];
          return Object.entries(clique_items[1].by_file)
              .flatMap(by_file_items => {
                const filename = by_file_items[0];
                return Object.entries(by_file_items[1]).map(
                  clique_item => {
                    // console.log(clique_leader, filename, clique_item[0], clique_item[1]);
                    return new CliqueCount(clique_leader, filename, clique_item[0], clique_item[1])
                  }
                )
              });
        } else {
          return [];
        }
      })
}

const clique_counts1 = computed(() => {
  return report_to_clique_counts(JSON.parse(report1.value))
});
const clique_counts2 = computed(() => {
  return report_to_clique_counts(JSON.parse(report2.value))
})

function add_clique_count_to_grouped(name: string, clique_counts: list[CliqueCount], grouped: dict) {
  clique_counts.forEach(c => {
    grouped[c.clique_leader_prefix] = grouped[c.clique_leader_prefix] || {};
    grouped[c.clique_leader_prefix][c.filename] = grouped[c.clique_leader_prefix][c.filename] || {};
    grouped[c.clique_leader_prefix][c.filename][c.prefix] = grouped[c.clique_leader_prefix][c.filename][c.prefix] || {};
    if (!(name in grouped[c.clique_leader_prefix][c.filename][c.prefix])) {
      grouped[c.clique_leader_prefix][c.filename][c.prefix][name] = 0;
    }
    grouped[c.clique_leader_prefix][c.filename][c.prefix][name] += c.prefix_count;

    // console.log(c);
    console.log(c, grouped[c.clique_leader_prefix][c.filename][c.prefix]);
  });
}

const three_level_grouping = computed(() => {
  const grouped = {};

  add_clique_count_to_grouped("c1", clique_counts1.value, grouped);
  add_clique_count_to_grouped("c2", clique_counts2.value, grouped);

  return grouped;
});

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
            <th>Clique leader</th>
            <th>Filename</th>
            <th>Prefix</th>
            <th>c1</th>
            <th>c2</th>
          </tr>
          </thead>
          <tbody>
            <tr v-for="clique_leader_prefix in three_level_grouping" :key="clique_leader_prefix">
              <template v-for="filename in three_level_grouping[clique_leader_prefix]" :key="filename">
                <template v-for="prefix in three_level_grouping[clique_leader_prefix][filename]" :key="prefix">
                  <td>{{clique_leader_prefix}}</td>
                  <td>{{filename}}</td>
                  <td>{{prefix}}</td>
                  <td>{{three_level_grouping[clique_leader_prefix][filename]["c1"]}}</td>
                  <td>{{three_level_grouping[clique_leader_prefix][filename]["c2"]}}</td>
                </template>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>