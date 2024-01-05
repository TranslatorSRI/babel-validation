import {TestResult} from "@/models/TestResult";
import {getURLForCURIE} from "@/models/helpers";
import {Test} from "@/models/Test";

// Helper functions
/**
 * This function generates tests for the previous NameRes format.
 *
 * We mainly need this to compare the outputs as we implement the new NameRes format,
 * so this needs to be a quick-and-dirty implementation, which will eventually be phased out.
 */
function convertPrevNameResFormatToCurrent(response) {
    // result is a dictionary, but when we iterate over it, we should get it in the same order as the input keys.
    return Object.entries(response).map(([key, value]) => {
        return {
            curie: key,
            synonyms: value.sort((a, b) => a.length - b.length),
        };
    });
}

// A helper function that returns a Promise that evaluates to a JSON result object.
// TODO: cache this.
export function lookupNameRes(nameResEndpoint, query, limit=10) {
    // TODO: once all current instances are upgraded to 1.3.2+, we can replace this with a GET request.
    const url = nameResEndpoint + "/lookup?string=" + encodeURIComponent(query) + "&limit=" + encodeURIComponent(limit);
    const request = new Request(
        url, {
            method: "POST"
        }
    );

    return fetch(request).then(response => {
        if (!response.ok) return TestResult.failure("Could not submit request to NameRes /lookup", 'text', response.statusText);
        return response.json()
            .catch(err => {
                return TestResult.failure(`NameRes /lookup returned a non-JSON result: ${err}`, 'text', response);
            })
            .then(responseJson => {
                // There are two possible formats that could be returned. If this is the old format, the results
                // will be a dictionary; if the new format, this will be a list.
                let results;
                if (Array.isArray(responseJson)) {
                    results = responseJson;
                } else if(typeof responseJson === 'object') {
                    results = convertPrevNameResFormatToCurrent(responseJson);
                } else {
                    return TestResult.failure(`NameRes /lookup returned an unexpected response`, 'json', responseJson);
                }

                return TestResult.success(`NameRes /lookup returned ${results.length} results`, 'NameRes', results);
            });
    });
}

/**
 * Represents a single NameRes test in our test suite. This is constructed in some way (currently, from a row in a spreadsheet)
 * and includes within it a closure that includes the test itself. The test can be executed by passing it an endpoint to
 * test, and it returns a TestResult representing the result.
 */
export class NameResTest extends Test {
    /**
     * Convert a single row into zero or more tests.
     */
    static convertRowToTests(row) {
        const source = row['Source'];
        const source_url = row['Source URL'];

        // Define some standard test types.
        function createCheckIDTest(id) {
            return new NodeNormTest(`Check for ID ${id}`, {
                [id]: getURLForCURIE(id)
            }, source, source_url, function(nodeNormEndpoint) {
                // Check to see if NodeNorm know about this ID.
                // We have a success! Since the identifier was returned, this test is now passed.
                return lookupNameRes(nodeNormEndpoint, id);
            });
        }

        /**
         * Check whether this identifier is of a particular Biolink class.
         * Include a class in the format '!biolink:className' to pass only if this className is NOT present.
         */
        function createBiolinkClassTest(id, biolinkClass) {
            return new NodeNormTest(`Check that ID ${id} has Biolink class ${biolinkClass}`, {
                [id]: getURLForCURIE(id)
            }, source, source_url, function(nodeNormEndpoint) {
                // Check to see if NodeNorm know about this ID.
                // We have a success! Since the identifier was returned, this test is now passed.
                return lookupNameRes(nodeNormEndpoint, id)
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
            return new NodeNormTest(`Check ID ${query_id} has preferred ID ${preferred_id}`, {
                [query_id]: getURLForCURIE(query_id),
                [preferred_id]: getURLForCURIE(preferred_id),
            }, source, source_url, function(nodeNormEndpoint) {
                return lookupNameRes(nodeNormEndpoint, query_id)
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
            return new NodeNormTest(`Check ID ${id1} and ID ${id2} cluster together`, {
                [id1]: getURLForCURIE(id1),
                [id2]: getURLForCURIE(id2),
            }, source, source_url,function(nodeNormEndpoint) {
                return lookupNameRes(nodeNormEndpoint, id1)
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
        if('Query Label' in row) { // || 'Preferred label' in row) {
            const query_label = row['Query Label'];

            if (query_label !== '') {
                // To begin with, let's just return the results as-is.
                tests.push(new NameResTest(`Lookup "${query_label}"`, {}, source, source_url, (nameResURL) => {
                    return lookupNameRes(nameResURL, query_label);
                }));
            }

            const preferred_label = row['Preferred Label'];
            if (preferred_label !== '') {
                // To begin with, let's just return the results as-is.
                tests.push(new NameResTest(`Lookup "${preferred_label}"`, {}, source, source_url, (nameResURL) => {
                    return lookupNameRes(nameResURL, preferred_label);
                }));
            }


            const additional_labels = row['Additional Labels'].split('|');
            additional_labels.forEach(additional_label => {
                if (!additional_label) return;

                // To begin with, let's just return the results as-is.
                tests.push(new NameResTest(`Lookup "${additional_label}"`, {}, source, source_url, (nameResURL) => {
                    return lookupNameRes(nameResURL, additional_label);
                }));
            });

        } else {
            tests.push(TestResult.failure(`Could not understand row`, 'json', row));
        }

        return tests;

        /*
            tests.push(createCheckIDTest(query_id));
            if(row['Preferred ID']) {
                const preferred_id = row['Preferred ID'];
                tests.push(createCheckIDTest(preferred_id));
                tests.push(createPreferredIdTest(query_id, preferred_id));

                if(row['Additional IDs']) {
                    const additional_ids = row['Additional IDs'].split(/\s*\|\s* /);

                    additional_ids.forEach(additional_id => {
                        tests.push(createPreferredIdTest(additional_id, preferred_id));
                        tests.push(createClusterTogetherTest(additional_id, query_id));
                    });
                }
            } else if(row['Additional IDs']) {
                const additional_ids = row['Additional IDs'].split(/\s*\|\s* /);

                additional_ids.forEach(additional_id => {
                    tests.push(createClusterTogetherTest(additional_id, query_id));
                });
            }

            if(row['Biolink classes']) {
                const biolink_classes = row['Biolink classes'].split(/\s*\|\s* /);
                biolink_classes.forEach(biolink_class => {
                    tests.push(createBiolinkClassTest(query_id, biolink_class));
                });
            } */
    }
}