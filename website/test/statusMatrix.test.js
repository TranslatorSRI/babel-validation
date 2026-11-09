// The odd-one-out shading is the whole point of showing environments side by
// side, and it had no test before the redesign split it into its own component.
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import StatusMatrix from '../src/components/StatusMatrix.vue';

const TARGETS = ['exp', 'dev', 'prod'];

function target(babel, extra = {}) {
  return {
    nodenorm_status: { status: 'running', babel_version: babel, databases: {}, ...extra.nodenorm },
    nameres_status: { status: 'running', ...extra.nameres },
    counts: { passed: 1, failed: 0, xfailed: 0, xpassed: 0, skipped: 0, error: 0 },
    unreachable: false,
  };
}

function mountWith(targets) {
  return mount(StatusMatrix, {
    props: { report: { targets }, targetNames: Object.keys(targets) },
  });
}

function row(wrapper, section, label) {
  return wrapper
    .findAll(`tbody tr[data-section="${section}"]`)
    .find((tr) => tr.find('th').text() === label);
}

function babelRow(wrapper, section = 'nodenorm') {
  return row(wrapper, section, 'Babel version')
    .findAll('td')
    .map((td) => td.classes().join(' '));
}

describe('StatusMatrix', () => {
  it('shades only the environment that disagrees', () => {
    const wrapper = mountWith({
      exp: target('2025oct1'),
      dev: target('2025sep1'),
      prod: target('2025sep1'),
    });
    const [exp, dev, prod] = babelRow(wrapper);
    expect(exp).toContain('table-warning');
    expect(dev).not.toContain('table-warning');
    expect(prod).not.toContain('table-warning');
  });

  it('shades nothing when every environment agrees', () => {
    const wrapper = mountWith(Object.fromEntries(TARGETS.map((t) => [t, target('2025sep1')])));
    expect(babelRow(wrapper).join(' ')).not.toContain('table-warning');
  });

  it('marks a status error as danger, not as a minority value', () => {
    const wrapper = mountWith({
      exp: target('2025sep1'),
      dev: target('2025sep1'),
      prod: target('2025sep1', { nodenorm: { error: 'ConnectionError', status: undefined } }),
    });
    expect(row(wrapper, 'nodenorm', 'Status').findAll('td')[2].classes()).toContain(
      'table-danger'
    );
  });

  it('gives NodeNorm and NameRes a Babel version each, shaded independently', () => {
    // On test, NodeNorm was on 2025sep1 while NameRes had moved to 2026jul22:
    // a single Babel row, read from NodeNorm, hid that entirely.
    const wrapper = mountWith({
      exp: target('2026jul22', { nameres: { babel_version: '2026jul22' } }),
      dev: target('2026jul22', { nameres: { babel_version: '2026jul22' } }),
      prod: target('2025sep1', { nameres: { babel_version: '2026jul22' } }),
    });
    expect(babelRow(wrapper, 'nodenorm')[2]).toContain('table-warning');
    expect(babelRow(wrapper, 'nameres').join(' ')).not.toContain('table-warning');
    expect(row(wrapper, 'nameres', 'Babel version').findAll('td')[2].text()).toBe('2026jul22');
  });

  it('links each service to the docs and /status URLs the generator built', () => {
    const wrapper = mountWith({
      exp: {
        ...target('2026jul22'),
        nodenorm_docs_url: 'https://nn.example/docs',
        nodenorm_status_url: 'https://nn.example/status',
        nameres_docs_url: 'https://nr-es.example/',
        nameres_status_url: 'https://nr-es.example/status',
      },
    });
    const links = (section) =>
      wrapper
        .find(`tbody tr.table-group[data-section="${section}"]`)
        .findAll('a')
        .map((a) => [a.text(), a.attributes('href')]);
    expect(links('nodenorm')).toEqual([
      ['docs', 'https://nn.example/docs'],
      ['status', 'https://nn.example/status'],
    ]);
    expect(links('nameres')).toEqual([
      ['docs', 'https://nr-es.example/'],
      ['status', 'https://nr-es.example/status'],
    ]);
  });

  it('lists the Babel releases a NodeNorm serves', () => {
    const wrapper = mountWith({
      ci: target('2026jul22', { nodenorm: { babel_available_versions: ['2025sep1', '2026jul22'] } }),
      dev: target('2026jul22'),
    });
    const cells = row(wrapper, 'nodenorm', 'Babel releases served').findAll('td');
    expect(cells.map((td) => td.text())).toEqual(['2025sep1, 2026jul22', '—']);
  });

  it('hides a row that no environment has a value for', () => {
    const wrapper = mountWith({
      exp: target('2026jul22', { nodenorm: { elasticsearch: { nodes: 3, versions: ['9.3.1'] } } }),
      dev: target('2026jul22', {
        nodenorm: { elasticsearch: { nodes: 3, versions: ['8.19.0', '9.3.1'] } },
      }),
    });
    const cells = row(wrapper, 'nodenorm', 'Elasticsearch').findAll('td');
    // dev is mid-upgrade, which the first node's version alone would hide.
    expect(cells.map((td) => td.text())).toEqual(['3 × 9.3.1', '3 × 8.19.0, 9.3.1']);
    // No environment reports a disk percentage, so that row is not shown at all.
    expect(row(wrapper, 'nodenorm', 'ES disk used')).toBeUndefined();
  });
});

describe('an even split', () => {
  it('shades nothing when no value has a majority', () => {
    // Half the environments on the new Babel version and half on the old is
    // what mid-promotion looks like. Picking a "majority" by Map insertion
    // order would shade three of six amber to say nothing at all.
    const wrapper = mountWith({
      exp: target('2025oct1'),
      dev: target('2025oct1'),
      ci: target('2025oct1'),
      test: target('2025sep1'),
      prod: target('2025sep1'),
      staging: target('2025sep1'),
    });

    expect(babelRow(wrapper).join(' ')).not.toContain('table-warning');
  });
});

