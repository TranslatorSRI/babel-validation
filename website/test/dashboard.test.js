// Regression tests for the dashboard's client-side logic. Everything here was
// a real bug: shared links that lost their page, and a query parameter that
// reached Object.prototype.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import Dashboard from '../src/components/Dashboard.vue';
import Trends from '../src/components/Trends.vue';

const TARGETS = ['dev', 'prod'];

function target() {
  return {
    nodenorm_url: 'https://nodenorm.example/',
    nameres_url: 'https://nameres.example/',
    nodenorm_status: {},
    nameres_status: {},
    counts: { passed: 1, failed: 0, xfailed: 0, xpassed: 0, skipped: 0, error: 0 },
    unreachable: false,
  };
}

// Enough rows to paginate: the default page size is 25.
function report(rowCount = 60) {
  const results = {};
  for (let i = 0; i < rowCount; i++) {
    results[`nodenorm/test_nodenorm_from_gsheet.py::test_normalization[row=${i}]`] = {
      kind: 'gsheet',
      row: i,
      category: i % 2 ? 'Diseases' : 'Genes',
      outcomes: { dev: { o: 'failed' }, prod: { o: 'passed' } },
    };
  }
  return {
    generated_at: '2026-08-27T00:00:00+00:00',
    run: {},
    repos_allowlist: [],
    github_issues_ran: true,
    targets: Object.fromEntries(TARGETS.map((t) => [t, target()])),
    results,
    unattributed_counts: {},
  };
}

async function mountAt(query, data = report()) {
  window.history.replaceState(null, '', query);
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  const wrapper = mount(Dashboard, { props: { dataUrl: '/data/report.json' } });
  await flushPromises();
  return wrapper;
}

describe('Dashboard URL state', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('keeps the page a shared link asks for', async () => {
    const wrapper = await mountAt('/?page=2&ps=25');
    expect(wrapper.vm.page).toBe(2);
    expect(window.location.search).toContain('page=2');
  });

  it('resets to page 1 once the reader changes a filter', async () => {
    const wrapper = await mountAt('/?page=2');
    wrapper.vm.filters.q = 'diseases';
    await flushPromises();
    expect(wrapper.vm.page).toBe(1);
    expect(window.location.search).toContain('q=diseases');
  });

  it('restores filters without writing them back as edits', async () => {
    const wrapper = await mountAt('/?all=1&kinds=gsheet&has=failed&page=2');
    expect(wrapper.vm.filters.interestingOnly).toBe(false);
    expect(wrapper.vm.filters.kinds).toEqual(['gsheet']);
    expect(wrapper.vm.filters.has).toEqual(['failed']);
    expect(wrapper.vm.page).toBe(2);
  });

  it('ignores a ?test= key that is only on Object.prototype', async () => {
    const wrapper = await mountAt('/?test=constructor');
    expect(wrapper.vm.rows.every((row) => row.key !== 'constructor')).toBe(true);
    expect(wrapper.text()).not.toContain('[native code]');
  });

  it('pins a real ?test= row the filters would otherwise hide', async () => {
    const key = 'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[row=59]';
    // 30 rows sort ahead of it, so a 25-row page cannot show it.
    const wrapper = await mountAt(`/?ps=25&test=${encodeURIComponent(key)}`);
    expect(wrapper.vm.rows[0].key).toBe(key);
  });
});

describe('Trends', () => {
  it('drops history lines that are not run objects', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => ['null', '123', JSON.stringify({ date: 'd', targets: {} }), ''].join('\n'),
    });
    const wrapper = mount(Trends, { props: { dataUrl: '/data/history.jsonl' } });
    await flushPromises();
    expect(wrapper.vm.runs).toHaveLength(1);
    expect(wrapper.text()).toContain('d');
  });
});
