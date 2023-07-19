<template>
  <small><a href="/">Return to front page</a></small>

  <h1>Autocomplete Validation</h1>
  <p>
    Autocomplete validation uses the <a href="https://github.com/TranslatorSRI/NameResolution">Name Resolution</a> service,
    but checks to ensure that autocompletion works as expected, i.e. after the minimum character count (currently {{minimumAutocompleteChars}}),
    every additional character should bring the correct match closer to the top of the list. Because this requires many more
    queries than the <a href="/nameres">Name Resolution validator</a>, we will only test a single endpoint at a time.
  </p>

  <b-card title="Settings">
    <b-card-body>
      <p>Choose NameRes endpoint:</p>
      <b-dropdown :text="currentEndpoint">
        <b-dropdown-item
            v-for="endpoint in Object.keys(nameResEndpoints)"
            @click="setCurrentEndpoint(endpoint)"
        >{{endpoint}}</b-dropdown-item>
      </b-dropdown>
    </b-card-body>

    <b-card-footer>
      <b-button-group>
        <b-button @click="loadGoogleSheet()">Reload Google Sheet</b-button>
        <b-button @click="nameResResults = {}; currentEndpoint = '';">Reset NameRes results</b-button>
      </b-button-group>
    </b-card-footer>
  </b-card>



  <h2 class="mt-2">Tests</h2>

  <template v-if="testDataErrors">
    <ul>
      <li v-for="error in testDataErrors">{{error}}</li>
    </ul>
  </template>

  <b-table-simple striped hover bordered>
    <thead>
      <tr>
        <th>Test</th>
        <th>Source</th>
        <th>Query text</th>
        <th>Results</th>
      </tr>
    </thead>
    <tbody>
      <template v-for="row in rowsHead(2)">
        <tr>
          <td :rowspan="generateAutocompleteTexts(row['Query label']).length + 1">{{row['Query label']}}</td>
          <td :rowspan="generateAutocompleteTexts(row['Query label']).length + 1">{{row['Query ID']}}</td>
          <td>{{row['Query label']}}</td>
          <td>
            <ul>
              <li v-for="res in getNameResResults(currentEndpoint, row['Query label'])">
                {{res.curie}} ({{res.synonyms[0]}})
              </li>
            </ul>
          </td>
        </tr>
        <template v-for="text in generateAutocompleteTexts(row['Query label'])">
          <tr>
            <td>{{text}}</td>
            <td>
              <ul>
                <li v-for="res in getNameResResults(currentEndpoint, text)">
                  {{res.curie}} ({{res.synonyms[0]}})
                </li>
              </ul>
            </td>
          </tr>
        </template>
      </template>
    </tbody>
  </b-table-simple>

</template>

<script>
import {BTable} from "bootstrap-vue-3";
import Papa from 'papaparse';
import { head} from 'lodash';
import Bottleneck from "bottleneck";
import TextWithURLs from "@/components/TextWithURLs.vue";
import TestResult from "@/components/TestResult.vue";
import { lookupNameRes } from "@/models/NameResTest";

const nameResBottleneck = new Bottleneck({
  maxConcurrent: 10,
  minTime: 333,
});

export default {
  components: {TestResult, BTable, TextWithURLs},
  props: {
    minimumAutocompleteChars: {
      type: Number,
      default: 3
    },
  },
  data () {
    return {
      nameResEndpoints: {
	      "NameRes-localhost": "http://localhost:8080",
        "NameRes-RENCI-exp": "http://name-resolution-sri-dev.apps.renci.org",
        "NameRes-RENCI-dev": "https://name-resolution-sri.renci.org",
        "NameRes-ITRB-ci": "https://name-lookup.ci.transltr.io",
        "NameRes-ITRB-test": "https://name-lookup.test.transltr.io",
        "NameRes-ITRB-prod": "https://name-lookup.transltr.io"
      },
      currentEndpoint: "NameRes-RENCI-dev",
      testData: [],
      testDataErrors: [],
      testDataIncomplete: true,
      nameResResults: {},
    }
  },
  created() {
    this.loadGoogleSheet();
  },
  computed: {
    rows() {
      if (this.testDataIncomplete) return [];
      return this.testData
          .filter(row => !(row['Ignore?'] && row['Ignore?'] === 'y'))
          .filter(row => row['Query label']);
    },
  },
  methods: {
    rowsHead(count) {
      return this.rows.slice(0, count);
    },
    loadGoogleSheet() {
      this.testDataIncomplete = true;
      this.testData = [];
      Papa.parse('https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/gviz/tq?tqx=out:csv&sheet=Tests', {
        download: true,
        header: true,
        complete: (results => {
          this.testData = results.data;
          this.testDataIncomplete = false;
        }),
        error: (err => {
          this.testDataErrors.push(err);
        })
      })
    },
    getNameResResults(endpoint, text) {
      if (!(endpoint in this.nameResResults)) return [];
      if (!(text in this.nameResResults[endpoint])) return [];
      return this.nameResResults[endpoint][text];
    },
    generateAutocompleteTexts(string = "") {
      // Given a string (e.g. "Botulinum toxin type A"), break it down into autocomplete texts (e.g. "Botu", "Botul",
      // and so on). We start from the minimum character size.
      const texts = [];

      for (let i = this.minimumAutocompleteChars; i < string.length; i++) {
        texts.push(string.substring(0, i));
      }

      return texts.reverse();
    },
    setCurrentEndpoint(endpoint) {
      this.currentEndpoint = endpoint;
      console.log("this.currentEndpoint is now", this.currentEndpoint);
      // Start loading NameRes results for every text for every row.
      this.rowsHead(2).forEach(row => {
        const query = row['Query label'];

        this.loadNameResResults(endpoint, query, 10)
        const texts = this.generateAutocompleteTexts(query);
        texts.forEach(text => {
          console.log("Loading NameRes results for text: ", text);
          // TODO: we can await this to slow the entire process down.
          this.loadNameResResults(endpoint, text, 10)
        });
      });
    },
    async loadNameResResults(endpoint, query, limit = 10) {
      // Don't load a query that has already been cached.
      if (endpoint in this.nameResResults && query in this.nameResResults[endpoint]) return;

      // Use the nameResBottleneck to make queries at a suitable rate.
      return await nameResBottleneck.schedule(() => lookupNameRes(this.nameResEndpoints[endpoint], query, limit)
          .then(tr => {
            console.info(`Found results in ${endpoint} (${this.currentEndpoint}) for query ${query} with result`, tr.result);

            // If the endpoint is no longer the current endpoint, then stop download these results.
            if (endpoint !== this.currentEndpoint) return;

            // If the endpoint has not been created in the nameResResults, create it now. Then save the result to it.
            if (!(endpoint in this.nameResResults)) {
              this.nameResResults[endpoint] = {};
            }
            this.nameResResults[endpoint][query] = tr.result;

            console.log(`Set this.nameResResults[${endpoint}][${query}] to:`, tr.result);
          }));
    },
  }
}
</script>
