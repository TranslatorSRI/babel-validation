// The drift panel is the redesign's one piece of new logic: it groups tests by
// how they behave along the pipeline, so 147 rows read as one finding.
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import DriftPanel from '../src/components/DriftPanel.vue';
import { signature } from '../src/reportData.js';

const TARGETS = ['exp', 'dev', 'prod'];

function row(exp, dev, prod) {
  return { kind: 'gsheet', outcomes: { exp: { o: exp }, dev: { o: dev }, prod: { o: prod } } };
}

const RESULTS = {
  a: row('passed', 'passed', 'failed'),
  b: row('passed', 'passed', 'failed'),
  c: row('passed', 'passed', 'failed'),
  d: row('passed', 'failed', 'failed'),
  e: row('passed', 'passed', 'passed'), // uninteresting: excluded
};

describe('signature', () => {
  it('reads one character per environment, in deployment order', () => {
    expect(signature(RESULTS.a, TARGETS)).toBe('ppF');
    expect(signature({ outcomes: { dev: { o: 'xpassed' } } }, TARGETS)).toBe('-X-');
  });
});

describe('DriftPanel', () => {
  const wrapper = mount(DriftPanel, {
    props: { results: RESULTS, targetNames: TARGETS, resultsUrl: '/results/' },
  });

  it('groups interesting rows by pattern, most common first', () => {
    expect(wrapper.vm.patterns.map((p) => [p.sig, p.count])).toEqual([
      ['ppF', 3],
      ['pFF', 1],
    ]);
    expect(wrapper.vm.totalPatterns).toBe(2);
  });

  it('links each pattern into the results page', () => {
    expect(wrapper.find('tbody a').attributes('href')).toBe('/results/?sig=ppF');
  });
});
