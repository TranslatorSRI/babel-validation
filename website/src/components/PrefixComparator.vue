<script setup lang="ts">
/*
 * PrefixComparator: compare prefix reports from two versions of NodeNorm.
 */
import {computed, ref, onMounted} from "vue";

export interface Props {
  prefix_json_url1?: string,
  prefix_json_url2?: string
}

const props = withDefaults(defineProps<Props>(), {
  prefix_json_url1: '/babel-validation/prefix_reports/prefix_report-2024oct1-maybe.json',
  prefix_json_url2: '/babel-validation/prefix_reports/prefix_report.json',
});

// Display
const showIdentical = ref(false);

// Eventually, we will allow people to paste the JSON in directly.
const report1 = ref('{}');
const report2 = ref('{}');

// Once this page has loaded, load up some default reports.
onMounted(() => {
  if (props.prefix_json_url1) {
    fetch(props.prefix_json_url1).then(res => res.json()).then(report => report1.value = JSON.stringify(report, null, 2))
  }

  if (props.prefix_json_url2) {
    fetch(props.prefix_json_url2).then(res => res.json()).then(report => report2.value = JSON.stringify(report, null, 2))
  }
});

// For each report, calculate a stream of by_clique triples.
/**
 * Represents a CliqueCount object that holds information about a clique leader prefix,
 * a filename, a prefix, and a prefix count.
 *
 * The class is designed to store and represent data relevant to a community or set of cliques,
 * along with their associated metadata.
 *
 * @class
 *
 * @property {string} clique_leader_prefix A string representing the prefix of the clique leader.
 * @property {string} filename A string representing the name of the associated file.
 * @property {string} prefix A string representing the prefix tied to the clique or community.
 * @property {number} prefix_count An integer representing the count or frequency associated with the prefix.
 *
 * @constructor
 * Initializes a new instance of the CliqueCount class with provided clique leader prefix,
 * filename, prefix, and prefix count.
 *
 * @param {string} clique_leader_prefix The prefix associated with the clique leader.
 * @param {string} filename The name of the relevant file.
 * @param {string} prefix The defined prefix for the clique or group.
 * @param {number} prefix_count The frequency or count associated with the given prefix.
 */
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


/**
 * Processes the `by_clique` property of the input report to generate a list of
 * CliqueCount instances, summarizing file-related information for each clique.
 *
 * @param {Object} report - An object containing a `by_clique` property, where the data is organized
 * into cliques and files. Each clique contains detailed information for individual files.
 * @return {CliqueCount[]} An array of CliqueCount objects representing the processed data for
 * each clique and its corresponding files. Returns an empty array if the `by_clique` property is missing.
 */
function report_to_clique_counts(report: dict): CliqueCount[] {
  if (!("by_clique" in report)) return [];

  return Object.entries(report.by_clique)
      .flatMap(kv => {
        const key = kv[0];
        const value: dict = kv[1];

        if (key.startsWith('count_')) return [];
        if ('by_file' in value) {
          const clique_leader = key;
          return Object.entries(value.by_file)
              .flatMap(by_file_items => {
                const filename = by_file_items[0];
                const by_file_values: dict = by_file_items[1];
                return Object.entries(by_file_values).map(
                  clique_item_kv => {
                    // console.log(clique_leader, filename, clique_item_kv[0], clique_item_kv[1]);
                    const prefix_count: number = clique_item_kv[1];
                    return new CliqueCount(clique_leader, filename, clique_item_kv[0], prefix_count)
                  }
                )
              });
        } else {
          return [];
        }
      })
}

// Generate clique count lists whenever the two reports change.
const clique_counts1 = computed(() => {
  return report_to_clique_counts(JSON.parse(report1.value))
});
const clique_counts2 = computed(() => {
  return report_to_clique_counts(JSON.parse(report2.value))
})

/**
 * Adds clique count data to a grouped object under the specified name.
 *
 * We group by:
 * - Clique leader prefix
 * - Filename
 * - Prefix
 *
 * @param {string} name - The key under which the clique count will be added in the grouped object.
 * @param {CliqueCount[]} clique_counts - An array of clique count objects.
 * @param {dict} grouped - An object where the clique count data will be added in groups.
 * @return {void} Does not return a value. The function modifies the `grouped` object in place.
 */
function add_clique_count_to_grouped(name: string, clique_counts: CliqueCount[], grouped: dict) {
  clique_counts.forEach(c => {
    grouped[c.clique_leader_prefix] = grouped[c.clique_leader_prefix] || {};
    grouped[c.clique_leader_prefix][c.filename] = grouped[c.clique_leader_prefix][c.filename] || {};
    grouped[c.clique_leader_prefix][c.filename][c.prefix] = grouped[c.clique_leader_prefix][c.filename][c.prefix] || {};
    if (!(name in grouped[c.clique_leader_prefix][c.filename][c.prefix])) {
      grouped[c.clique_leader_prefix][c.filename][c.prefix][name] = 0;
    }
    grouped[c.clique_leader_prefix][c.filename][c.prefix][name] += c.prefix_count;

    // console.log(c, grouped[c.clique_leader_prefix][c.filename][c.prefix]);
  });

  console.log(grouped);
}

// Calculate a grouped list of clique counts.
const three_level_grouping = computed(() => {
  const grouped = {};

  add_clique_count_to_grouped("c1", clique_counts1.value, grouped);
  add_clique_count_to_grouped("c2", clique_counts2.value, grouped);

  return grouped;
});

// Calculate the clique counts to display in the table.
const clique_count_rows = computed(() => {
  const rows = [];

  const three_level_grouping_value = three_level_grouping.value;

  // console.log('three_level_grouping_value = ', three_level_grouping_value, ', keys = ', Object.keys(three_level_grouping_value));

  for (const clique_leader_prefix of Object.keys(three_level_grouping_value)) {
    // console.log('filenames to consider for ', clique_leader_prefix, ': ', three_level_grouping_value[clique_leader_prefix]);
    for (const filename of Object.keys(three_level_grouping_value[clique_leader_prefix])) {
      // console.log('prefixes to consider: ', three_level_grouping_value[clique_leader_prefix][filename]);
      for (const prefix of Object.keys(three_level_grouping_value[clique_leader_prefix][filename])) {
        const c1 = three_level_grouping_value[clique_leader_prefix][filename][prefix]["c1"] || 0;
        const c2 = three_level_grouping_value[clique_leader_prefix][filename][prefix]["c2"] || 0;
        const diff = c2 - c1;
        if (showIdentical.value || (diff != 0)) {
          rows.push({
            clique_leader_prefix: clique_leader_prefix,
            filename: filename,
            prefix: prefix,
            c1: c1,
            c2: c2,
            diff: diff,
            absolute_diff: Math.abs(diff),
            percentage_diff: (diff / c1) * 100,
          });
        }
      }
    }
  }

  return rows.sort((a, b) => b.absolute_diff - a.absolute_diff);
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
        <div>
          <input type="checkbox" v-model="showIdentical" /> Show prefix counts that don't differ between the two versions.
        </div>
      </div>
    </div>

    <div class="card my-2">
      <div class="card-header">
        <strong>Differences</strong>
      </div>
      <div class="card-body p-0">
        <table class="table">
          <thead>
          <tr>
            <th>Clique leader</th>
            <th>Filename</th>
            <th>Prefix</th>
            <th style="text-align: right">Prefix Report 1 (contains {{(JSON.parse(report1).count_curies || 0).toLocaleString()}}&nbsp;CURIEs)</th>
            <th style="text-align: right">Prefix Report 2 (contains {{(JSON.parse(report2).count_curies || 0).toLocaleString()}}&nbsp;CURIEs)</th>
            <th style="text-align: right">Diff</th>
            <th style="text-align: right">% Diff</th>
          </tr>
          </thead>
          <tbody>
            <tr v-for="row in clique_count_rows">
              <td>{{row.clique_leader_prefix}}</td>
              <td>{{row.filename}}</td>
              <td>{{row.prefix}}</td>
              <td style="text-align: right">{{row.c1.toLocaleString()}}</td>
              <td style="text-align: right">{{row.c2.toLocaleString()}}</td>
              <td style="text-align: right">{{(row.diff > 0 ? '+' : '') + row.diff.toLocaleString()}}</td>
              <td style="text-align: right">{{row.percentage_diff.toFixed(2) + '%'}}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>

</style>
