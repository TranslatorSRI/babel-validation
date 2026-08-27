// Regression tests for the results page's client-side logic. Everything in the
// first block was a real bug: shared links that lost their page, and a query
// parameter that reached Object.prototype.
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import Results from '../src/components/Results.vue';

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
      source: i % 3 ? 'Reported in an issue' : 'TAQA',
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
  const wrapper = mount(Results, { props: { dataUrl: '/data/report.json' } });
  await flushPromises();
  return wrapper;
}

describe('Results URL state', () => {
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

describe('Results filters', () => {
  it('round-trips the category, source and environment filters through the URL', async () => {
    const wrapper = await mountAt('/?cat=Diseases&src=TAQA&env=dev&has=failed');
    expect(wrapper.vm.filters.cat).toBe('Diseases');
    expect(wrapper.vm.filters.src).toBe('TAQA');
    expect(wrapper.vm.filters.env).toBe('dev');
    wrapper.vm.filters.q = 'row';
    await flushPromises();
    const params = new URLSearchParams(window.location.search);
    expect([params.get('cat'), params.get('src'), params.get('env')]).toEqual([
      'Diseases',
      'TAQA',
      'dev',
    ]);
  });

  it('applies the outcome filter to the chosen environment only', async () => {
    const wrapper = await mountAt('/?env=prod&has=failed');
    // Every row passes in prod and fails in dev, so nothing matches.
    expect(wrapper.vm.filteredRows).toHaveLength(0);
    wrapper.vm.filters.env = 'dev';
    await flushPromises();
    expect(wrapper.vm.filteredRows.length).toBeGreaterThan(0);
  });

  it('withholds every detail of a blocklist row, whatever the report carries', async () => {
    const key = 'nameres/test_blocklist.py::test_check_blocklist_entry[blocklist_entry47]';
    const data = report(2);
    // A generator regression that started emitting these must not leak them here.
    data.results[key] = {
      kind: 'blocklist',
      query_id: 'SECRET:12345',
      query_label: 'a blocked term',
      issue: 'NCATSTranslator/Babel#71',
      source: 'the blocklist sheet',
      outcomes: { dev: { o: 'failed', msg: 'blocked term SECRET:12345 was returned' } },
    };
    const wrapper = await mountAt(`/?all=1&test=${encodeURIComponent(key)}`, data);
    const text = wrapper.text();
    expect(text).toContain('blocklist entry (details withheld)');
    for (const secret of ['SECRET:12345', 'a blocked term', 'Babel#71', 'the blocklist sheet']) {
      expect(text).not.toContain(secret);
    }
  });
});

describe('Results pattern filter', () => {
  it('shows only the rows matching a ?sig= pattern, and rejects a malformed one', async () => {
    const data = report(4);
    data.results['nodenorm/x.py::t[odd]'] = {
      kind: 'gsheet',
      row: 999,
      category: 'Genes',
      outcomes: { dev: { o: 'failed' }, prod: { o: 'failed' } },
    };
    let wrapper = await mountAt('/?sig=FF', data);
    expect(wrapper.vm.filteredRows.map((r) => r.key)).toEqual(['nodenorm/x.py::t[odd]']);

    wrapper = await mountAt('/?sig=<script>', data);
    expect(wrapper.vm.filters.sig).toBe('');
    expect(wrapper.vm.filteredRows.length).toBeGreaterThan(1);
  });
});

describe('FilterBar', () => {
  it('toggles an outcome chip on and off, and shows it in the URL', async () => {
    const wrapper = await mountAt('/');
    const chip = wrapper
      .findAll('button')
      .find((button) => button.text() === 'failed');
    await chip.trigger('click');
    await flushPromises();
    expect(wrapper.vm.filters.has).toEqual(['failed']);
    expect(chip.classes()).toContain('btn-secondary');
    expect(chip.attributes('aria-pressed')).toBe('true');
    expect(window.location.search).toContain('has=failed');

    await chip.trigger('click');
    await flushPromises();
    expect(wrapper.vm.filters.has).toEqual([]);
    expect(window.location.search).not.toContain('has=');
  });

  it('clears every filter at once, and empties the query string with them', async () => {
    const wrapper = await mountAt('/?all=1&q=row&kinds=gsheet&cat=Genes&env=dev&page=2');
    const reset = wrapper.findAll('button').find((button) => button.text() === 'Reset');
    await reset.trigger('click');
    await flushPromises();
    expect(wrapper.vm.filters).toEqual({
      interestingOnly: true,
      q: '',
      kinds: [],
      has: [],
      cat: '',
      src: '',
      env: '',
      sig: '',
    });
    expect(window.location.search).toBe('');
  });
});
