/*
 * This file collects several model classes that we need to process data.
 */

export class Test {
    /**
     * Each test has a description, source, source_url and
     */
    constructor(description, urls={}, source=null, source_url=null, test=function(nodeNormEndpoint) { return [false, `Not implemented (${nodeNormEndpoint})`] }) {
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
        // Helper functions.
        function getURLForCURIE(curie) {
            return 'https://google.com/search?q=' + encodeURIComponent(curie);
        }

        const source = row['Source'];
        const source_url = row['Source URL'];

        // Define some standard test types.
        function createCheckIDTest(id) {
            return new Test(`Check for ID ${id}`, {
                [id]: getURLForCURIE(id)
            }, source, source_url, function(nodeNormEndpoint, callback) {
                // Check to see if NodeNorm know about this ID.
                const url = nodeNormEndpoint + "/get_normalized_nodes?curie=" + encodeURIComponent(id);
                console.log("Querying", url);
                return fetch(url).then(response => {
                    if (!response.ok) return [false, "Could not get_normalized_nodes: " + response.statusText];
                    return response.json().then(results => {
                        console.log("Results:", results);
                        if (!results) return [false, `get_normalized_nodes returned invalid response: ${response}`];
                        const result = results[id];
                        console.log("Result:", result);
                        if (!result) return [false, `get_normalized_nodes returned no response for ${id}: ${results}`];
                        const equiv_ids = new Set(result['equivalent_identifiers'].map(r => r.identifier));
                        const equiv_ids_str = [...equiv_ids].join(", ");
                        console.log("Equiv IDs:", equiv_ids);
                        if (equiv_ids.has(id)) {
                            return [true, `${id} is included in cluster ${result['id']['identifier']}: ${equiv_ids_str}`];
                        } else {
                            return [false, `${id} is NOT included in cluster ${result['id']['identifier']}: ${equiv_ids_str}`]
                        }
                    });
                });
            });
        }

        function createPreferredIdTest(query_id, preferred_id) {
            return new Test(`Check ID ${query_id} has preferred ID ${preferred_id}`, {
                [query_id]: getURLForCURIE(query_id),
                [preferred_id]: getURLForCURIE(preferred_id),
            }, source, source_url);
        }

        function createClusterTogetherTest(id1, id2) {
            return new Test(`Check ID ${id1} and ID ${id2} cluster together`, {
                [id1]: getURLForCURIE(id1),
                [id2]: getURLForCURIE(id2),
            }, source, source_url);
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
                        tests.push(createCheckIDTest(additional_id));
                        tests.push(createPreferredIdTest(additional_id, preferred_id));
                    });
                }
            } else if(row['Additional IDs']) {
                const additional_ids = row['Additional IDs'].split(/\s*\|\s*/);

                additional_ids.forEach(additional_id => {
                    tests.push(createCheckIDTest(additional_id));
                    tests.push(createClusterTogetherTest(additional_id, query_id));
                });
            }
        }

        return tests;
    }
}