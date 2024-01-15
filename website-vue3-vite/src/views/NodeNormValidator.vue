<template>
  <small><router-link to="/">Return to front page</router-link></small>
  <h1>Node Normalization Validation</h1>
  <p>
    <a href="https://github.com/TranslatorSRI/babel">Babel</a> is the program that generates the datasets of
    interrelated identifiers that underlies <a href="https://github.com/TranslatorSRI/NodeNormalization">Node Normalization</a>
    and <a href="https://github.com/TranslatorSRI/NameResolution">Name Resolution</a>.

    This page will test several instances of the Node Normalization service.
  </p>

  <b-card title="Filter">
    <b-card-body>
      <b-form-group label="Choose categories:" label-for="selected-categories">
        <b-form-select id="selected-categories" multiple v-model="selectedCategories" :options="googleSheetCategories" />
      </b-form-group>
    </b-card-body>

    <b-form-group label="Choose NodeNorm endpoints:" label-for="current-endpoints">
      <b-form-select id="current-endpoints" multiple v-model="currentEndpoints" :options="nodeNormEndpointsAsList" />
    </b-form-group>

    <b-card-footer>
      <b-button @click="loadGoogleSheet()">Reload Google Sheet</b-button>
    </b-card-footer>
  </b-card>

  <h2>Tests</h2>

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
        <th v-for="endpoint in currentEndpoints">
          <a target="_blank" :href="nodeNormEndpoints[endpoint] + '/docs'">{{endpoint}}</a>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="test in tests">
        <td><TextWithURLs :text="test.description" :urls="test.urls"></TextWithURLs></td>
        <td><TextWithURLs :text="test.source" :urls="{'URL': test.source_url}"></TextWithURLs></td>
        <td v-for="endpoint in currentEndpoints">
          <TestResult :test="test" :endpoint="nodeNormEndpoints[endpoint]" :description="test.description + ':' + test.source + ':' + nodeNormEndpoints[endpoint]"></TestResult>
        </td>
      </tr>
    </tbody>
  </b-table-simple>

</template>

<script>
import {BTable} from "bootstrap-vue-3";
import Papa from 'papaparse';
import TextWithURLs from "@/components/TextWithURLs.vue";
import { NodeNormTest } from '@/models/NodeNormTest';
import TestResult from "@/components/TestResult.vue";
import {RouterLink} from "vue-router";

export default {
  components: {TestResult, BTable, TextWithURLs, RouterLink},
  data () {
    return {
      nodeNormEndpoints: {
        "NodeNorm-RENCI-exp": "https://nodenormalization-dev.apps.renci.org",
        "NodeNorm-RENCI-dev": "https://nodenormalization-sri.renci.org",
        "NodeNorm-ITRB-ci": "https://nodenorm.ci.transltr.io",
        "NodeNorm-ITRB-test": "https://nodenorm.test.transltr.io",
        "NodeNorm-ITRB-prod": "https://nodenorm.transltr.io"
      },
      currentEndpoints: ["NodeNorm-RENCI-dev", "NodeNorm-ITRB-test"],
      selectedCategories: ["Unit Tests"],
      testData: [],
      testDataErrors: [],
      testDataIncomplete: true,
    }
  },
  created() {
    this.loadGoogleSheet();
  },
  computed: {
    tests() {
      if (this.testDataIncomplete) return [];
      return this.testData.flatMap(row => {
        if ('Category' in row && this.selectedCategories.includes(row['Category'])) {
          return NodeNormTest.convertRowToTests(row);
        }
        return [];
      });
    },
    nodeNormEndpointsAsList() {
      return Object.entries(this.nodeNormEndpoints).map(([name, endpointURL]) => ({ "value": name, "text": `${name} (${endpointURL})` }));
    },
    googleSheetCategories() {
      const categories = this.testData.map(row => {
        if ('Category' in row) return row['Category'];
        return '(undefined)';
      });

      let counts = {};
      categories.forEach(category => {
        counts[category] = counts[category] ? counts[category] + 1 : 1;
      });

      return Object.entries(counts).map(([key, value]) => ({value: key, text: `${key} (${value})`}));
    },
  },
  methods: {
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
    }
  }
}
</script>
