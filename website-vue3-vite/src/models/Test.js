import {TestResult} from "@/models/TestResult";

export class Test {
    /**
     * Each test has a description, source, source_url and
     */
    constructor(description, urls = {}, source = null, source_url = null, test = function (endpoint) {
        return Promise.resolve(TestResult.failure(`Not implemented (${endpoint})`));
    }) {
        this.description = description;
        this.urls = urls;
        this.source = source;
        this.source_url = source_url;
        this.test = test;
    }
}