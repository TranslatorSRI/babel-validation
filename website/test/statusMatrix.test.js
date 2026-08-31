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

function babelRow(wrapper) {
  const row = wrapper
    .findAll('tbody tr')
    .find((tr) => tr.find('th').text() === 'Babel version');
  return row.findAll('td').map((td) => td.classes().join(' '));
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
    const row = wrapper
      .findAll('tbody tr')
      .find((tr) => tr.find('th').text() === 'NodeNorm status');
    expect(row.findAll('td')[2].classes()).toContain('table-danger');
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

