/*
 * This file collects several model classes that we need to process data.
 */

/**
 * A class representing the result of a test.
 */
export class TestResult {
    /** Construct a TestResult based largely on a JSON result from . */
    constructor(status, message, resultType= "null", result = {}) {
        this.status = status;
        this.message = message;
        this.resultType = resultType;
        this.result = result;
    }

    /** Create a TestResult for a success. */
    static success(message, resultType = "unknown", result = null) {
        return new TestResult(true, message, resultType, result);
    }

    /** Create a TestResult for a failure. */
    static failure(message, resultType="unknown", result=null) {
        return new TestResult(false, message, resultType, result);
    }
}


/**
 * Represents a single test in our test suite. This is constructed in some way (currently, from a row in a spreadsheet)
 * and includes within it a closure that includes the test itself. The test can be executed by passing it an endpoint to
 * test, and it returns a TestResult representing the result.
 */
export class Test {
    /**
     * Each test has a description, source, source_url and
     */
    constructor(description, urls={}, source=null, source_url=null, test=function(nodeNormEndpoint) { return Promise.resolve(TestResult.failure(`Not implemented (${nodeNormEndpoint})`)); }) {
        this.description = description;
        this.urls = urls;
        this.source = source;
        this.source_url = source_url;
        this.test = test;
    }

    /**
     * Convert a single row into zero or more tests.
     */
    static convertRowToTests(row) {
        const source = row['Source'];
        const source_url = row['Source URL'];

        // Helper functions.
        function getURLForCURIE(curie) {
            const iri_stems = {
                'UMLS': 'https://uts.nlm.nih.gov/uts/umls/concept/',
            }

            const curie_split = (curie.toUpperCase().split(':') || [''])
            const curie_prefix = curie_split[0];
            if (new Set('HTTP', 'HTTPS', 'URN').has(curie_prefix)) {
                // Looks like a URI! Leave it unchanged.
                return curie;
            }

            if (iri_stems[curie_prefix] && curie_split.length > 1) {
                return iri_stems[curie_prefix] + curie.substring(curie.indexOf(':') + 1);
            }

            // Default to bioregistry.io lookup
            return 'http://bioregistry.io/' + encodeURIComponent(curie);
            // return 'https://google.com/search?q=' + encodeURIComponent(curie);
        }

        function getEquivalentIDs(result) {
            return new Set((result['equivalent_identifiers'] || []).map(r => r.identifier))
        }

        // A helper function that returns a Promise that evaluates to a JSON result object.
        // TODO: cache this.
        function getNormalizedNodes(nodeNormEndpoint, id) {
            const url = nodeNormEndpoint + "/get_normalized_nodes?curie=" + encodeURIComponent(id);
            // console.log("Querying", url);
            return fetch(url).then(response => {
                if (!response.ok) return TestResult.failure("Could not get_normalized_nodes", 'text', response.statusText);
                return response.json().then(results => {
                    // console.log("Results:", results);
                    if (!results) return TestResult.failure(`get_normalized_nodes returned invalid response`, 'text', response);
                    const result = results[id];
                    // console.log("Result:", result);
                    if (!result) return TestResult.failure(`get_normalized_nodes returned no response for ${id}`, 'json', results);
                    const equiv_ids = getEquivalentIDs(result);
                    // console.log("Equiv IDs:", equiv_ids);
                    if (!equiv_ids.has(id)) {
                        return TestResult.failure(`ID ${id} could not be found`, 'NodeNorm', result);
                    } else {
                        let preferred_label_text = "";
                        if (result['id']) {
                            const preferred_id = result.id['identifier'];
                            const preferred_label = result.id['label'];
                            if (id == preferred_id) {
                                preferred_label_text = ` (\"${preferred_label}\")`;
                            } else {
                                preferred_label_text = ` (${preferred_id} "${preferred_label}\")`;
                            }
                        }
                        return TestResult.success(`Found ID ${id}${preferred_label_text}`, "NodeNorm", result);
                    }
                });
            });
        }

        // Define some standard test types.
        /** Check whether this identifier is present in this NodeNorm instance. */
        function createCheckIDTest(id) {
            return new Test(`Check for ID ${id}`, {
                [id]: getURLForCURIE(id)
            }, source, source_url, function(nodeNormEndpoint) {
                // Check to see if NodeNorm know about this ID.
                // We have a success! Since the identifier was returned, this test is now passed.
                return getNormalizedNodes(nodeNormEndpoint, id);
            });
        }

        /**
         * Check whether this identifier is of a particular Biolink class.
         * Include a class in the format '!biolink:className' to pass only if this className is NOT present.
         */
        function createBiolinkClassTest(id, biolinkClass) {
            return new Test(`Check that ID ${id} has Biolink class ${biolinkClass}`, {
                [id]: getURLForCURIE(id)
            }, source, source_url, function(nodeNormEndpoint) {
                // Check to see if NodeNorm know about this ID.
                // We have a success! Since the identifier was returned, this test is now passed.
                return getNormalizedNodes(nodeNormEndpoint, id)
                    .then(result => {
                        // Continue propagating errors.
                        if (!result.status) return result;

                        // We have a success if query_id was found at all.
                        // But to pass this test, we need to check that biolinkClass
                        // is one of the Biolink classes of this identifier.
                        const json = result.result;
                        const biolinkClasses = new Set(json['type'] || []);

                        if (biolinkClass.startsWith('!')) {
                            const invertedBiolinkClass = biolinkClass.substring(1);
                            if (biolinkClasses.has(invertedBiolinkClass)) {
                                return TestResult.failure(`ID ${id} should not have Biolink class ${invertedBiolinkClass} but does`, 'NodeNorm', json);
                            } else {
                                return TestResult.success(`ID ${id} does not have Biolink class ${invertedBiolinkClass} as expected`, 'NodeNorm', json);
                            }
                        } else {
                            if (biolinkClasses.has(biolinkClass)) {
                                return TestResult.success(`ID ${id} has Biolink class ${biolinkClass}`, 'NodeNorm', json);
                            } else {
                                return TestResult.failure(`ID ${id} does not have Biolink class ${biolinkClass}`, 'NodeNorm', json);
                            }
                        }
                    })
            });
        }

        function createPreferredIdTest(query_id, preferred_id) {
            return new Test(`Check ID ${query_id} has preferred ID ${preferred_id}`, {
                [query_id]: getURLForCURIE(query_id),
                [preferred_id]: getURLForCURIE(preferred_id),
            }, source, source_url, function(nodeNormEndpoint) {
                return getNormalizedNodes(nodeNormEndpoint, query_id)
                    .then(result => {
                        // Continue propagating errors.
                        if (!result.status) return result;

                        // We have a success if query_id was found at all.
                        // But to pass this test, we need to check that the
                        // preferred_id is specifically the preferred ID in
                        // the returned cluster.
                        const json = result.result;
                        const equiv_ids = getEquivalentIDs(json);

                        if (json['id']['identifier'] === preferred_id && equiv_ids.has(query_id)) {
                            return TestResult.success(`Query ID ${query_id} has preferred ID ${preferred_id}`, 'NodeNorm', json);
                        } else {
                            return TestResult.failure(`Query ID ${query_id} has preferred ID ${json['id']['identifier']}, not ${preferred_id}`, 'NodeNorm', json);
                        }
                    });
            });
        }

        function createClusterTogetherTest(id1, id2) {
            return new Test(`Check ID ${id1} and ID ${id2} cluster together`, {
                [id1]: getURLForCURIE(id1),
                [id2]: getURLForCURIE(id2),
            }, source, source_url,function(nodeNormEndpoint) {
                return getNormalizedNodes(nodeNormEndpoint, id1)
                    .then(result => {
                        // Continue propagating errors.
                        if (!result.status) return result;

                        // We have a success if id1 was found at all.
                        // But to pass this test, we need to check that the
                        // id2 is one of the equivalent identifiers.
                        const json = result.result;
                        const equiv_ids = getEquivalentIDs(json);
                        const preferred_id = json.id.identifier;

                        if (equiv_ids.has(id1) && equiv_ids.has(id2)) {
                            return TestResult.success(`ID ${id1} and ID ${id2} are both equivalent to ${preferred_id}.`, 'NodeNorm', json);
                        } else {
                            return TestResult.failure(`ID ${id1} is equivalent to ${preferred_id} but ID ${id2} is not.`, 'NodeNorm', json);
                        }
                    });
            });
        }

        // Look for tests in this row.
        const tests = [];
        if(row['Query ID']) {
            const query_id = row['Query ID'];

            tests.push(createCheckIDTest(query_id));
            if(row['Preferred ID']) {
                const preferred_id = row['Preferred ID'];
                tests.push(createCheckIDTest(preferred_id));
                tests.push(createPreferredIdTest(query_id, preferred_id));

                if(row['Additional IDs']) {
                    const additional_ids = row['Additional IDs'].split(/\s*\|\s*/);

                    additional_ids.forEach(additional_id => {
                        tests.push(createPreferredIdTest(additional_id, preferred_id));
                        tests.push(createClusterTogetherTest(additional_id, query_id));
                    });
                }
            } else if(row['Additional IDs']) {
                const additional_ids = row['Additional IDs'].split(/\s*\|\s*/);

                additional_ids.forEach(additional_id => {
                    tests.push(createClusterTogetherTest(additional_id, query_id));
                });
            }

            if(row['Biolink classes']) {
                const biolink_classes = row['Biolink classes'].split(/\s*\|\s*/);
                biolink_classes.forEach(biolink_class => {
                    tests.push(createBiolinkClassTest(query_id, biolink_class));
                });
            }
        }

        return tests;
    }
}