// New Babel versions land in exp first and are promoted towards prod, so every
// table on the site shows environments in deployment order: a value that
// differs from its left neighbour is a change working its way through.
const DEPLOYMENT_ORDER = ['exp', 'dev', 'ci', 'ci-es', 'test', 'prod'];

export function sortByDeploymentOrder(targetNames) {
  const index = (name) => {
    const i = DEPLOYMENT_ORDER.indexOf(name);
    return i === -1 ? DEPLOYMENT_ORDER.length : i;
  };
  return [...targetNames].sort((a, b) => index(a) - index(b) || a.localeCompare(b));
}
