// The pipeline order is shared by every table on the site; only the
// Environments table moves a side branch beside its parent.
import { describe, it, expect } from 'vitest';
import { sortBesideParents, sortByDeploymentOrder } from '../src/deploymentOrder.js';

const ALL = ['prod', 'ci-nameres-es', 'test', 'exp', 'ci', 'dev'];

describe('sortBesideParents', () => {
  it('puts ci-nameres-es right after ci, and nothing else moves', () => {
    expect(sortBesideParents(ALL)).toEqual(['exp', 'dev', 'ci', 'ci-nameres-es', 'test', 'prod']);
    // The pipeline order itself is unchanged.
    expect(sortByDeploymentOrder(ALL)).toEqual(['exp', 'dev', 'ci', 'test', 'prod', 'ci-nameres-es']);
  });

  it("leaves a side branch where it was when its parent isn't reported", () => {
    expect(sortBesideParents(['ci-nameres-es', 'prod', 'exp'])).toEqual(['exp', 'prod', 'ci-nameres-es']);
  });

  it('keeps an unknown target last, and is not fooled by prototype names', () => {
    expect(sortBesideParents(['constructor', 'ci', 'staging', 'ci-nameres-es'])).toEqual([
      'ci',
      'ci-nameres-es',
      'constructor',
      'staging',
    ]);
  });
});
