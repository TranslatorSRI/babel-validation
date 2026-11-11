// The pipeline order is shared by every table on the site; only the
// Environments table moves a side branch beside its parent.
import { describe, it, expect } from 'vitest';
import { sortBesideParents, sortByDeploymentOrder } from '../src/deploymentOrder.js';

const ALL = ['prod', 'ci-nameres-es', 'test', 'exp', 'ci', 'dev'];
// As the report gives it, from targets.ini's SideBranchOf.
const PARENTS = { 'ci-nameres-es': 'ci' };
const parentOf = (name) => (Object.hasOwn(PARENTS, name) ? PARENTS[name] : null);

describe('sortBesideParents', () => {
  it('puts ci-nameres-es right after ci, and nothing else moves', () => {
    expect(sortBesideParents(ALL, parentOf)).toEqual(['exp', 'dev', 'ci', 'ci-nameres-es', 'test', 'prod']);
    // The pipeline order itself is unchanged.
    expect(sortByDeploymentOrder(ALL)).toEqual(['exp', 'dev', 'ci', 'test', 'prod', 'ci-nameres-es']);
  });

  it("leaves a side branch where it was when its parent isn't reported", () => {
    expect(sortBesideParents(['ci-nameres-es', 'prod', 'exp'], parentOf)).toEqual(['exp', 'prod', 'ci-nameres-es']);
  });

  it('keeps an unknown target last, and is not fooled by prototype names', () => {
    expect(sortBesideParents(['constructor', 'ci', 'staging', 'ci-nameres-es'], parentOf)).toEqual([
      'ci',
      'ci-nameres-es',
      'constructor',
      'staging',
    ]);
  });

  it('moves any branch its parentOf names, not only ci-nameres-es', () => {
    const parents = { 'dev-nodenorm-es': 'dev' };
    const of = (name) => parents[name] ?? null;
    expect(sortBesideParents(['prod', 'dev-nodenorm-es', 'dev', 'exp'], of)).toEqual([
      'exp',
      'dev',
      'dev-nodenorm-es',
      'prod',
    ]);
  });

  it('moves nothing when no target names a parent (a report from before side_branch_of)', () => {
    expect(sortBesideParents(ALL, () => undefined)).toEqual(sortByDeploymentOrder(ALL));
  });
});
