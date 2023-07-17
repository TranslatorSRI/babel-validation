export function getURLForCURIE(curie) {
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