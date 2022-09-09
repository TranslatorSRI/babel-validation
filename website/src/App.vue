<template>
  <h1>Babel Validation</h1>
  <p>
    <a href="https://github.com/TranslatorSRI/babel">Babel</a> is the program that generates the datasets of
    interrelated identifiers that underlies <a href="https://github.com/TranslatorSRI/NodeNormalization">Node Normalization</a>
    and <a href="https://github.com/TranslatorSRI/NameResolution">Name Resolution</a>. This website is intended to provide
    a single place where tests can be executed against multiple versions of these tools.
  </p>

  <h2>Tests</h2>

  <b-table striped hover :items="testResults" :fields="test_fields">
  </b-table>

  <h3>Debug</h3>

  <p>{{testDataIncomplete}}: {{testData}}</p>

  <p>{{testDataErrors}}</p>

</template>

<script>
import {BTable} from "bootstrap-vue-3";
import Papa from 'papaparse';

export default {
  components: {BTable},
  data () {
    return {
      nodeNormEndpoints: {
        "NodeNorm-RENCI-exp": "https://nodenormalization-dev.apps.renci.org/1.3",
        "NodeNorm-RENCI-dev": "https://nodenormalization-sri.renci.org/1.3",
        "NodeNorm-ITRB-prod": "https://nodenorm.transltr.io/1.3/"
      },
      testData: [],
      testDataErrors: [],
      testDataIncomplete: true,
    }
  },
  created() {
    Papa.parse('https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/gviz/tq?tqx=out:csv&sheet=Tests', {
      download: true,
      header: true,
      complete: (results => {
        this.testData = results.data
        this.testDataIncomplete = false
      }),
      error: (err => {
        this.testDataErrors.push(err);
      })
    })
  },
  computed: {
    test_fields() {
      /* Return a list of fields to display in the tests list */
      return [ "Test", ...Object.keys(this.nodeNormEndpoints)]
    },
  }
}
</script>