// The milestones page renders text written by anyone with a GitHub account, and
// the only thing standing between an issue title and a link on a public site is
// the generator's org/repo#N validation plus issueLink()'s re-check. Those, and
// the release/bucket split, are what is worth testing here.
import { describe, it, expect, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import Milestones from '../src/components/Milestones.vue';

function milestone(overrides = {}) {
  return {
    repo: 'NCATSTranslator/Babel',
    title: 'Babel v1.19',
    number: 12,
    milestone: 'NCATSTranslator/Babel#12',
    due_on: '2026-09-15',
    past_due: false,
    bucket: false,
    open_issues: 1,
    closed_issues: 2,
    issues: [{ issue: 'NCATSTranslator/Babel#1048', title: 'Conflation is wrong' }],
    ...overrides,
  };
}

const DATA = {
  generated_at: '2026-09-01T06:30:00+00:00',
  run: {},
  milestones: [
    milestone(),
    milestone({
      title: 'Needed soon',
      number: 3,
      milestone: 'NCATSTranslator/Babel#3',
      due_on: null,
      bucket: true,
      issues: [],
    }),
  ],
};

async function mountWith(data = DATA) {
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  const wrapper = mount(Milestones, { props: { dataUrl: '/data/milestones.json' } });
  await flushPromises();
  return wrapper;
}

describe('Milestones', () => {
  it('lists buckets below the dated releases, under their own heading', async () => {
    const wrapper = await mountWith();
    const text = wrapper.text();
    expect(text.indexOf('Babel v1.19')).toBeLessThan(text.indexOf('Priority buckets'));
    expect(text.indexOf('Priority buckets')).toBeLessThan(text.indexOf('Needed soon'));
  });

  it('links an issue and its milestone from the validated org/repo#N', async () => {
    const wrapper = await mountWith();
    const hrefs = wrapper.findAll('a').map((a) => a.attributes('href'));
    expect(hrefs).toContain('https://github.com/NCATSTranslator/Babel/issues/1048');
    expect(hrefs).toContain('https://github.com/NCATSTranslator/Babel/milestone/12');
  });

  it('renders a title with no valid id as text, with no link', async () => {
    // The generator omits `issue`/`milestone` for anything outside the
    // allowlist, so there is nothing to build a URL from — and nothing here may
    // fall back to the repo name, which is untrusted text.
    const data = {
      ...DATA,
      milestones: [
        milestone({
          milestone: undefined,
          repo: 'evil.example/Babel',
          issues: [{ title: 'no id here' }],
        }),
      ],
    };
    const wrapper = await mountWith(data);
    expect(wrapper.text()).toContain('no id here');
    expect(wrapper.text()).toContain('Babel v1.19');
    expect(wrapper.findAll('a')).toHaveLength(0);
  });

  it('flags a past-due milestone and counts them in the summary', async () => {
    const data = { ...DATA, milestones: [milestone({ past_due: true })] };
    const wrapper = await mountWith(data);
    expect(wrapper.text()).toContain('past due');
    expect(wrapper.find('.outcome-failed').exists()).toBe(true);

    const clean = await mountWith({ ...DATA, milestones: [milestone()] });
    expect(clean.find('.outcome-failed').exists()).toBe(false);
  });

  it('says an empty milestone is empty rather than showing a bare card', async () => {
    const data = { ...DATA, milestones: [milestone({ issues: [], open_issues: 0 })] };
    const wrapper = await mountWith(data);
    expect(wrapper.text()).toContain('No open issues');
  });

  it('stamps the date, so a carried-forward file is visibly stale', async () => {
    const wrapper = await mountWith();
    expect(wrapper.text()).toContain('as of 2026-09-01');
  });

  it('shows the empty state for a file with no milestones, and an error for a bad fetch', async () => {
    let wrapper = await mountWith({ generated_at: '2026-09-01T06:30:00+00:00', milestones: [] });
    expect(wrapper.text()).toContain('No open milestones');

    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });
    wrapper = mount(Milestones, { props: { dataUrl: '/data/milestones.json' } });
    await flushPromises();
    expect(wrapper.text()).toContain('Could not load the milestones');
  });
});
