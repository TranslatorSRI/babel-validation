<template>
  <h1>Name Resolver Validation</h1>
  <p>
    <a href="https://github.com/TranslatorSRI/babel">Babel</a> is the program that generates the datasets of
    interrelated identifiers that underlies <a href="https://github.com/TranslatorSRI/NodeNormalization">Node Normalization</a>
    and <a href="https://github.com/TranslatorSRI/NameResolution">Name Resolution</a>.

    This page will test several instances of the Name Resolver.
  </p>

  <b-button @click="loadGoogleSheet()">Reload</b-button>

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
        <th v-for="endpoint in Object.keys(nameResEndpoints)">
          <a target="_blank" :href="nameResEndpoints[endpoint] + '/docs'">{{endpoint}}</a>
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="test in tests">
        <td><TextWithURLs :text="test.description" :urls="test.urls"></TextWithURLs></td>
        <td><TextWithURLs :text="test.source" :urls="{'URL': test.source_url}"></TextWithURLs></td>
        <td v-for="endpoint in Object.keys(nameResEndpoints)">
          <TestResult :test="test" :endpoint="nameResEndpoints[endpoint]" :description="test.description + ':' + test.source + ':' + nameResEndpoints[endpoint]"></TestResult>
        </td>
      </tr>
    </tbody>
  </b-table-simple>

</template>

<script>
import {BTable} from "bootstrap-vue-3";
import Papa from 'papaparse';
import TextWithURLs from "@/components/TextWithURLs.vue";
import { Test } from '@/models/NodeNormTesting';
import TestResult from "@/components/TestResult.vue";

export default {
  components: {TestResult, BTable, TextWithURLs},
  data () {
    return {
      nameResEndpoints: {
        "NameRes-RENCI-exp": "https://name-resolution-sri-dev.apps.renci.org",
        "NodeNorm-RENCI-dev": "https://name-resolution-sri.apps.renci.org",
        "NodeNorm-ITRB-ci": "https://name-lookup.ci.transltr.io",
        "NodeNorm-ITRB-test": "https://name-lookup.test.transltr.io",
        "NodeNorm-ITRB-prod": "https://name-lookup.transltr.io"
      },
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
        if(row['Ignore?'] && row['Ignore?'] == 'y') return [];
        return Test.convertRowToTests(row)
      });
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
