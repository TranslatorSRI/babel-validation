<template>
  <h1>Babel Validator</h1>

  <p>
    <a href="https://github.com/TranslatorSRI/babel">Babel</a> is the program that generates the datasets of
    interrelated identifiers that underlies <a href="https://github.com/TranslatorSRI/NodeNormalization">Node Normalization</a>
    and <a href="https://github.com/TranslatorSRI/NameResolution">Name Resolution</a>. This website is intended to provide
    allows JavaScript-based tests to be executed against multiple instances of these tools.
  </p>

  <ul>
    <li><router-link to="/nodenorm/">Node Normalization Validator</router-link></li>
    <li><router-link to="/nameres/">Name Resolver Validator</router-link></li>
    <li><router-link to="/autocomplete-bulk/">Autocomplete Validator</router-link></li>
  </ul>
</template>

<script>
import {RouterLink} from "vue-router";

export default {
  components: {RouterLink},
}
</script>