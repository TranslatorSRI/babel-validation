<template>
  <div>
    <template v-if="!testResult">
      WAITING
    </template>
    <template v-else>
      <template v-if="testStatus == 'FAIL'">
        <strong>FAIL: {{testMessage}}</strong>
        <b-button size="sm" class="col-12" @click="displayDetailed = !displayDetailed">Additional</b-button>
        <div v-if="displayDetailed" class="bg-light border-dark border-1 p-1 m-1" style="white-space: pre">
          {{testResultAsJson}}
        </div>
      </template>
      <template v-else>
        {{testStatus}}: {{testMessage}}
      </template>

      <div v-if="testResult.resultType === 'NameRes'">
        <ul>
          <li v-for="result in testResult.result" :key="result['curie']">
            {{result['curie']}}
            ({{result['label'] || (result['synonyms'] || [])[0]}})
            <template v-if="result['types']">[{{result['types'][0]}}]</template>
          </li>
        </ul>
      </div>
    </template>
  </div>
</template>

<script>
import {Test} from "@/models/Test";

export default {
  props: {
    test: Test,
    endpoint: String,
    description: String,
  },
  data() { return {
    testResult: null,
    displayDetailed: false,
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
    },
    testResultAsObj() {
      if (!this.testResult) return { "error": "No test result" };
      switch (this.testResult.resultType) {
        case 'text':
          return this.testResult.result;
        case 'json':
        case 'NodeNorm':
          return this.testResult.result;
      }
    },
    testResultAsJson() {
      return JSON.stringify(this.testResultAsObj, null, 2);
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