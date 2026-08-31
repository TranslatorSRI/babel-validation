// The history page has to survive a partial or malformed history file: it is
// rebuilt from the previously published one on every run.
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import History from '../src/components/History.vue';

function run(date, babel, failed) {
  return JSON.stringify({
    date,
    targets: { dev: { babel_version: babel, counts: { failed, passed: 10 } } },
  });
}

async function mountWith(lines) {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, text: async () => lines.join('\n') });
  const wrapper = mount(History, { props: { dataUrl: '/data/history.jsonl' } });
  await flushPromises();
  return wrapper;
}

describe('History', () => {
  it('drops history lines that are not run objects', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: async () => ['null', '123', JSON.stringify({ date: 'd', targets: {} }), ''].join('\n'),
    });
    const wrapper = mount(History, { props: { dataUrl: '/data/history.jsonl' } });
    await flushPromises();
    expect(wrapper.vm.runs).toHaveLength(1);
    expect(wrapper.text()).toContain('d');
  });
});


describe('what changed since the previous run', () => {
  it('reports version moves and count deltas, newest run against the one before', async () => {
    const wrapper = await mountWith([
      run('2026-08-26', '2025sep1', 12),
      run('2026-08-27', '2025oct1', 20),
    ]);
    expect(wrapper.vm.changes).toEqual([
      { target: 'dev', label: 'babel version', from: '2025sep1', to: '2025oct1' },
      { target: 'dev', label: 'failed', delta: 8, to: '20' },
    ]);
    expect(wrapper.text()).toContain('+8');
  });

  it('says so when nothing moved, and shows nothing with only one run', async () => {
    let wrapper = await mountWith([run('2026-08-26', '2025sep1', 12), run('2026-08-27', '2025sep1', 12)]);
    expect(wrapper.vm.changes).toEqual([]);
    expect(wrapper.text()).toContain('Nothing changed');

    wrapper = await mountWith([run('2026-08-27', '2025sep1', 12)]);
    expect(wrapper.vm.changes).toEqual([]);
    expect(wrapper.text()).not.toContain('Nothing changed');
  });
});

describe('a malformed history file', () => {
  it('drops only the unparseable line, not every run in the file', async () => {
    // A deploy interrupted mid-write, or a partial CDN response, leaves a
    // truncated last line. JSON.parse over the whole file threw, and the page
    // showed "Could not load the run history" instead of the runs it had.
    const wrapper = await mountWith([
      run('2026-08-26', '2025sep1', 12),
      '{"date": "2026-08-27", "targets": {"dev": {"babel_ver',
    ]);

    expect(wrapper.vm.loadError).toBe(null);
    expect(wrapper.vm.runs).toHaveLength(1);
    expect(wrapper.text()).toContain('2026-08-26');
  });
});

