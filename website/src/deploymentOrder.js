// New Babel versions land in exp first and are promoted towards prod, so every
// table on the site shows environments in deployment order: a value that
// differs from its left neighbour is a change working its way through.
// ci-nameres-es is ci's NodeNorm against the NameRes ES under validation: a sibling of ci,
// not a promotion step, so it sits beside it.
const DEPLOYMENT_ORDER = ['exp', 'dev', 'ci', 'ci-nameres-es', 'test', 'prod'];

// The environments this list does not know about. It is the third place a target
// has to be registered — targets.ini defines it, the workflow and generate_report
// now both read that, and the promotion order is a *semantic* fact about the
// pipeline that no config file states, so it cannot be derived and has to stay
// here. What can be avoided is failing silently: an unknown target sorts last,
// which is a plausible-looking position, so the Dashboard says so out loud, and
// tests/unit/test_deployment_order.py fails before it gets that far.
export function unknownTargets(targetNames) {
  return targetNames.filter((name) => !DEPLOYMENT_ORDER.includes(name));
}

export function sortByDeploymentOrder(targetNames) {
  const index = (name) => {
    const i = DEPLOYMENT_ORDER.indexOf(name);
    return i === -1 ? DEPLOYMENT_ORDER.length : i;
  };
  return [...targetNames].sort((a, b) => index(a) - index(b) || a.localeCompare(b));
}
