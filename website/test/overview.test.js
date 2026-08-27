// The landing page's job is to point at the right corner of the results table,
// so the links it builds are the part worth testing.
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import Overview from '../src/components/Overview.vue';

function target(counts, extra = {}) {
  return {
    nodenorm_status: { status: 'running', babel_version: '2025sep1', databases: {} },
    nameres_status: { status: 'running' },
    counts: { passed: 0, failed: 0, xfailed: 0, xpassed: 0, skipped: 0, error: 0, ...counts },
    unreachable: false,
    ...extra,
  };
}

const REPORT = {
  generated_at: '2026-08-27T15:53:57+00:00',
  run: { github_run_id: '33088526759', git_sha: '80f750a1502c288532369f3a6bbbeb233d8ddd51' },
  github_issues_ran: true,
  unattributed_counts: { passed: 1, failed: 0 },
  targets: {
    prod: target({ failed: 326, xpassed: 73, passed: 327 }),
    dev: target({ failed: 79, xpassed: 7, passed: 567 }),
    exp: target({ failed: 20 }, { unreachable: true }),
  },
  results: {
    a: { kind: 'gsheet', outcomes: { dev: { o: 'passed' }, prod: { o: 'failed' } } },
    b: { kind: 'gsheet', outcomes: { dev: { o: 'passed' }, prod: { o: 'passed' } } },
  },
};

async function mountOverview(report = REPORT) {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => report });
  const wrapper = mount(Overview, {
    props: { dataUrl: '/data/report.json', resultsUrl: '/babel-validation/results/' },
  });
  await flushPromises();
  return wrapper;
}

describe('Overview', () => {
  it('orders the environment cards by deployment, not by report order', async () => {
    const wrapper = await mountOverview();
    const names = wrapper.findAll('.col .card-body > .d-flex > .fw-semibold').map((el) => el.text());
    expect(names).toEqual(['exp', 'dev', 'prod']);
  });

  it('links each count into the results page, filtered to that environment', async () => {
    const wrapper = await mountOverview();
    const hrefs = wrapper.findAll('a').map((a) => a.attributes('href'));
    expect(hrefs).toContain('/babel-validation/results/?env=prod&has=failed');
    expect(hrefs).toContain('/babel-validation/results/?env=dev&has=xpassed');
  });

  it('says an unreachable environment has no results instead of showing zeroes', async () => {
    const wrapper = await mountOverview();
    const exp = wrapper.findAll('.col')[0];
    expect(exp.text()).toContain('no results');
    expect(exp.text()).not.toContain('0 failed');
  });

  it('surfaces results that no environment claimed', async () => {
    const wrapper = await mountOverview();
    expect(wrapper.text()).toContain('could not be attributed');
    const quiet = await mountOverview({ ...REPORT, unattributed_counts: { passed: 0 } });
    expect(quiet.text()).not.toContain('could not be attributed');
  });

  it('warns when the GitHub issue tests did not run at all', async () => {
    const wrapper = await mountOverview({ ...REPORT, github_issues_ran: false });
    expect(wrapper.text()).toContain('A green board proves nothing about them');
  });
});
