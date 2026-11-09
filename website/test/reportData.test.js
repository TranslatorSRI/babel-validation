// The link builders turn untrusted report text into URLs, so they are the one
// piece of reportData.js worth testing directly.
import { describe, it, expect } from 'vitest';
import {
  explorerLink,
  isInteresting,
  issueLink,
  milestoneLink,
  rowLabel,
  runLink,
} from '../src/reportData.js';

describe('link builders', () => {
  it('only links an issue id shaped like org/repo#N', () => {
    expect(issueLink({ issue: 'NCATSTranslator/Babel#71' })).toBe(
      'https://github.com/NCATSTranslator/Babel/issues/71'
    );
    for (const issue of ['evil/repo#1);drop', '../../etc#1', 'no-slash#1', 'a/b#x', undefined]) {
      expect(issueLink({ issue })).toBeNull();
    }
  });

  it('only links a milestone id shaped like org/repo#N', () => {
    // Same validation as issueLink, different path. The milestones page would
    // otherwise be tempted to build this from milestone.repo, which is
    // sanitized for display but never checked against the allowlist.
    expect(milestoneLink({ milestone: 'NCATSTranslator/Babel#12' })).toBe(
      'https://github.com/NCATSTranslator/Babel/milestone/12'
    );
    for (const milestone of ['evil/repo#1);drop', '../../etc#1', 'no-slash#1', 'a/b#x', undefined]) {
      expect(milestoneLink({ milestone })).toBeNull();
    }
  });

  it('encodes query values into the Explorer link', () => {
    const link = explorerLink('nodenorm/t.py::x', { query_id: 'FOO:1&a#b', outcomes: { dev: {} } }, [
      'dev',
    ]);
    expect(link).toContain('curie=FOO%3A1%26a%23b');
    expect(link).not.toContain('#b');
  });

  it('only links a numeric run id', () => {
    expect(runLink('123')).toContain('/actions/runs/123');
    expect(runLink('1 2')).toBeNull();
    expect(runLink(undefined)).toBeNull();
  });
});

describe('row classification', () => {
  it('counts disagreement between environments as interesting', () => {
    expect(isInteresting({ outcomes: { dev: { o: 'passed' }, prod: { o: 'passed' } } })).toBe(false);
    expect(isInteresting({ outcomes: { dev: { o: 'passed' }, prod: { o: 'xfailed' } } })).toBe(true);
    expect(isInteresting({ outcomes: { dev: { o: 'failed' } } })).toBe(true);
  });

  it('never labels a blocklist row with its content', () => {
    const label = rowLabel('nameres/test_blocklist.py::test[entry47]', {
      kind: 'blocklist',
      query_label: 'a blocked term',
    });
    expect(label).toBe('blocklist entry (details withheld)');
  });
});

describe('row labels', () => {
  it('labels a sheet row by its number when it has neither a label nor an id', () => {
    expect(rowLabel('k', { kind: 'gsheet', row: 53 })).toBe('row 53');
    expect(rowLabel('k', { kind: 'gsheet', row: 53, query_label: '' })).toBe('row 53');
  });

  it('still puts the label after the row number when there is one', () => {
    expect(rowLabel('k', { kind: 'gsheet', row: 53, query_label: 'MONDO:1' })).toBe(
      'row 53: MONDO:1'
    );
    expect(rowLabel('k', { kind: 'gsheet', row: 7, query_id: 'CHEBI:2' })).toBe('row 7: CHEBI:2');
  });
});

