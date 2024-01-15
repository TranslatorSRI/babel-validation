<template>
  <small><router-link to="/">Return to front page</router-link></small>

  <h1>Autocomplete</h1>
  <p>
    This implements a simple autocomplete in front of NameRes, allowing NameRes instances
    to be tested in a manner similar to that used by the Translator UI. The main advantages
    of this view are:
  </p>

  <ul>
    <li>The ability to switch between different NameRes instances.</li>
    <li>Try different flags and settings.</li>
  </ul>

  <p>
    You might prefer to look at the top result only in the
    <a href="/nameres">NameRes validator</a> or look at the
    character-by-character behavior in the autocomplete using the
    <a href="/autocomplete-bulk">NameRes Bulk Importer</a>.
  </p>

  <b-card title="Query">
    <b-card-body>
      <b-form-group label="Choose NameRes endpoint:" label-for="current-endpoint">
        <b-dropdown id="current-endpoint" :text="currentEndpoint">
          <b-dropdown-item
            v-for="endpoint in Object.keys(nameResEndpoints)"
            :key="endpoint"
            @click="currentEndpoint = endpoint"
          >{{ endpoint }}</b-dropdown-item
          >
        </b-dropdown>
      </b-form-group>

      <b-form-group
        label="Search for a term:"
        label-for="query"
        >
        <b-input-group>
          <b-form-input
            type="search"
            id="query"
            v-model.trim="query"
            autocomplete="off"
          />
          <b-input-group-append>
            <b-button
              variant="success"
              @click="
                this.autocompleteResults = [];
                this.searchInProgress = false;
                doAutocomplete();
              "
              >Search</b-button
            >
          </b-input-group-append>
        </b-input-group>
      </b-form-group>

      <b-form-group label="Number of results to return:" label-for="limit">
        <b-form-input id="limit" type="number" v-model="limit" />
      </b-form-group>

      <b-form-group label="Filter to Biolink type (optional):" label-for="biolink-type-filter">
        <b-form-input id="biolink-type-filter" type="text" v-model="biolinkTypeFilter" />
      </b-form-group>

      <b-form-group label="Filter to prefixes to include separated by pipe ('|') (optional):" label-for="prefix-filter">
        <b-form-input id="prefix-filter" type="text" v-model="prefixIncludeFilter" />
      </b-form-group>

      <b-form-group label="Filter to prefixes to exclude separated by pipe ('|') (optional):" label-for="prefix-filter">
        <b-form-input id="prefix-filter" type="text" v-model="prefixExcludeFilter" />
      </b-form-group>
    </b-card-body>
  </b-card>

  <b-card :title="'Results (' + autocompleteQuery + ', ' + autocompleteResults.length + ')'" class="mt-2">
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
import { saveAs } from "file-saver";

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