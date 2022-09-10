<template>
  <div>
    <template v-if="testResult == null">
      TESTING
    </template>
    <template v-if="testStatus">
      PASS: {{testMessage}}
    </template>
    <template v-else>
      FAIL: {{testMessage}}
    </template>
  </div>
</template>

<script>
import {Test} from "@/models/tests";

export default {
  props: {
    test: Test,
    endpoint: String,
  },
  data() { return {
    testResult: null,
  }},
  created() {
    this.test.test(this.endpoint).then(result => {
      this.testResult = result;
    });
  },
  computed: {
    testStatus() {
      return this.testResult ? this.testResult[0] : "WAITING";
    },
    testMessage() {
      return this.testResult ? this.testResult[1] : null;
    }
  }
}
</script>

<style scoped>
.text { margin-bottom: 0 }
a.small {
  margin: 0;
  padding: 0 1em 0 0;
}
</style>