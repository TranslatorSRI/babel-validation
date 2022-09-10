<template>
  <div>
    <template v-if="!testResult">
      WAITING
    </template>
    <template v-else-if="testStatus == 'FAIL'">
      <strong>FAIL: {{testMessage}}</strong>
    </template>
    <template v-else>
      {{testStatus}}: {{testMessage}}
    </template>
  </div>
</template>

<script>
import {Test} from "@/models/tests";

export default {
  props: {
    test: Test,
    endpoint: String,
    description: String,
  },
  data() { return {
    testResult: null,
  }},
  created() {
    const testR = this.test.test(this.endpoint);
    if (!testR) {
      console.log(`Unable to set up test Promise in ${this.description}`);
      return;
    }
    console.log("Returned testR: ", testR);

    testR.then(result => {
      console.log("Got result:", result);
      this.testResult = result;
    });
  },
  computed: {
    testStatus() {
      return this.testResult ? (this.testResult.status ? "PASS" : "FAIL") : "WAITING";
    },
    testMessage() {
      return this.testResult ? this.testResult.message : null;
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