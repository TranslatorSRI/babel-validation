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

</template>

<script>
import {BTable} from "bootstrap-vue-3";
export default {
  components: {BTable},
  data () {
    return {
      nodeNormEndpoints: {
        "NodeNorm-RENCI-exp": "https://nodenormalization-dev.apps.renci.org/1.3",
        "NodeNorm-RENCI-dev": "https://nodenormalization-sri.renci.org/1.3",
        "NodeNorm-ITRB-prod": "https://nodenorm.transltr.io/1.3/"
      },
      tests: fetch("")
    }
  },
  computed: {
    test_fields() {
      /* Return a list of fields to display in the tests list */
      return [ "Test", ...Object.keys(this.nodeNormEndpoints)]
    },
  }
}
</script>