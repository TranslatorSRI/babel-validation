<template>
  <b-card title="Query">
    <div class="mb-3">
      <label for="current-endpoint" class="form-label">Choose NameRes endpoint:</label>
      <select id="current-endpoint" class="form-select" aria-label="Current endpoint">
        <option v-for="endpoint in Object.keys(nameResEndpoints)"
              :key="endpoint"
              :selected="currentEndpoint === endpoint"
              @click="currentEndpoint = endpoint">{{endpoint}} ({{nameResEndpoints[endpoint]}})</option>
      </select>
      <p>(You can access this endpoint directly at <a target="current-endpoint-docs" :href="nameResEndpoints[currentEndpoint] + '/docs'">{{nameResEndpoints[currentEndpoint] + '/docs'}}</a>)</p>
    </div>

    <div class="mb-3">
      <label for="query" class="form-label">Search for a term:</label>
      <div class="input-group mb-3">
        <input id="query" type="search" class="form-control" v-model.trim="query" autocomplete="off" />
        <button class="btn btn-success" type="button" id="query-submit"
          @click="
              this.autocompleteResults = [];
              this.searchInProgress = false;
              doAutocomplete();"
        >Search</button>
      </div>
    </div>

    <div class="mb-3">
      <label for="limit" class="form-label">Number of results to return:</label>
      <input id="limit" type="number" class="form-control" v-model="limit" />
    </div>

    <div class="mb-3">
      <label for="biolink-type-filter" class="form-label">Filter to Biolink type (optional):</label>
      <input id="biolink-type-filter" class="form-control" type="text" v-model="biolinkTypeFilter" />
    </div>

    <div class="mb-3">
      <label for="prefix-include-filter" class="form-label">Filter to prefixes to include separated by pipe ('|') (optional):</label>
      <input id="prefix-include-filter" class="form-control" type="text" v-model="prefixIncludeFilter" />
    </div>

    <div class="mb-3">
      <label for="prefix-exclude-filter" class="form-label">Filter to prefixes to exclude separated by pipe ('|') (optional):</label>
      <input id="prefix-exclude-filter" class="form-control" type="text" v-model="prefixExcludeFilter" />
    </div>
  </b-card>

  <b-card :title="'Results (' + autocompleteQuery + ', ' + autocompleteResults.length + ')'">
    {{autocompleteError}}
    <b-table
      striped
      hover
      small
      sticky-header
      :fields="autocompleteFields"
      :items="autocompleteResults"
    />
    <b-button @click="exportAsCSV()" variant="secondary">Export as CSV</b-button>
  </b-card>
</template>

<script>
import { stringify } from "csv-stringify/browser/esm";
import pkg from "file-saver";
const { saveAs } = pkg;

// Bootstrap components
import BCard from "./bootstrap/BCard.vue";

function getURLForCURIE(curie) {
  const [prefix, suffix] = curie.split(':', 2);
  switch (prefix) {
    case 'MONDO':
      return "http://purl.obolibrary.org/obo/MONDO_" + suffix;
    case 'HP':
      return "http://purl.obolibrary.org/obo/HP_" + suffix;
    case 'UBERON':
      return "http://purl.obolibrary.org/obo/UBERON_" + suffix;
    case 'PUBCHEM.COMPOUND':
      return "https://pubchem.ncbi.nlm.nih.gov/compound/" + suffix;
    default:
      return "";
  }
}

export default {
  components: {
    BCard,
  },
  data() {
    return {
      nameResEndpoints: {
        "NameRes-localhost": "http://localhost:8080",
        "NameRes-RENCI-exp": "http://name-resolution-sri-dev.apps.renci.org",
        "NameRes-RENCI-dev": "https://name-resolution-sri.renci.org",
        "NameRes-ITRB-ci": "https://name-lookup.ci.transltr.io",
        "NameRes-ITRB-test": "https://name-lookup.test.transltr.io",
        "NameRes-ITRB-prod": "https://name-lookup.transltr.io",
      },
      currentEndpoint: "NameRes-RENCI-dev",
      query: "",
      biolinkTypeFilter: "",
      prefixIncludeFilter: "",
      prefixExcludeFilter: "",
      limit: 10,
      autocompleteFields: ["CURIE", "Label", "Synonyms", "Types", "URL", "Score", "Synopsis"],
      results: [],
      autocompleteResults: [],
      autocompleteError: "",
      autocompleteQuery: "",
      searchInProgress: "",
    };
  },
  watch: {
    query() {
      // It would be neat to actually run this as an autocomplete, but that is buggy.
      this.doAutocomplete();
    },
  },
  methods: {
    doAutocomplete() {
      // if (this.searchInProgress) return;
      const query = this.query;
      this.searchInProgress = query;

      console.log(
        "Query in progress for ",
        this.query,
        " with limit ",
        this.limit,
        ", Biolink type filter: ",
        this.biolinkTypeFilter,
        ", prefix include filter: ",
        this.prefixIncludeFilter,
        ", prefix exclude filter: ",
        this.prefixExcludeFilter
      );
      this.autocompleteError = `Query in progress for '${this.query}' with limit ${this.limit}, Biolink type filter: ${this.biolinkTypeFilter}, prefix filter: ${this.prefixIncludeFilter}.`;

      const currentEndpoint = this.nameResEndpoints[this.currentEndpoint];
      const url =
        currentEndpoint +
        "/lookup?limit=" +
        this.limit +
        "&biolink_type=" +
        this.biolinkTypeFilter +
        "&only_prefixes=" +
        this.prefixIncludeFilter +
        "&exclude_prefixes=" +
        this.prefixExcludeFilter +
        "&string=" +
        query;

      fetch(url).then(response => {
        if (this.searchInProgress !== query) {
          // Oops, our query is no longer relevant. Forget about it!
          console.log(`Skipping outdated query '${query}'`);
          return;
        }
        if (!response.ok) {
          this.autocompleteError = `Could not retrieve ${url}: ${response}.`;
          this.searchInProgress = "";
          return;
        }
        return response
          .json()
          .catch((err) => {
            this.autocompleteError = `Could not retrieve ${url}: ${err}.`;
            this.searchInProgress = "";
          })
          .then((results) => {
            this.results = results;
            this.autocompleteResults = results.map((res) => {
              const url = getURLForCURIE(res["curie"]);
              const biolinkType = res["types"][0];
              let synopsis = "";
              if (url) {
                synopsis = `[${res["curie"]} "${res["label"]}"](${url})`;
              } else {
                synopsis = `${res["curie"]} "${res["label"]}"`;
              }
              if (biolinkType) {
                synopsis += ` (${biolinkType})`;
              }
              if (res["synonyms"]) {
                synopsis += `: ${res["synonyms"].join(", ")}`;
              }

              return {
                CURIE: res["curie"],
                Label: res["label"],
                Types: res["types"].join(", "),
                Synonyms: res["synonyms"].join(", "),
                URL: url,
                Score: res["score"],
                Synopsis: synopsis,
              };
            });
            this.autocompleteError = "";
            this.searchInProgress = "";
            this.autocompleteQuery = query;
          });
      });
    },
    exportAsCSV() {
      if (this.autocompleteResults.length === 0) return;

      const rows = [
        this.autocompleteFields,
        ...this.autocompleteResults.map(row => {
          return this.autocompleteFields.map(field => row[field] || '')
        }),
      ];
      console.log(rows);

      stringify(
        rows,
        (err, csv) => {
          if (err) {
            alert("Could not export as CSV: " + err);
            return;
          }

          const content = [csv];
          const csvFile = new Blob(content, {type: 'text/csv;charset=utf-8'});
          saveAs(csvFile, 'autocomplete.csv', { autoBom: false });
        }
      );
    },
  },
};
</script>