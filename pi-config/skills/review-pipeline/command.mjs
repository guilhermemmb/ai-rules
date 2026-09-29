const SCOPES = new Set(['current', 'branch', 'staged', 'unstaged', 'pr']);
const MODES = new Set(['parallel', 'single']);
const USAGE = 'Usage: /review [parallel|single|<focus>] [current|branch|staged|unstaged|pr <url>]';

function catalogFrom(registry) {
  const focuses = registry?.focuses;
  if (!Array.isArray(focuses)) throw new Error(`Invalid focus registry. ${USAGE}`);
  const catalog = new Map();
  const ids = new Set();
  for (const focus of focuses) {
    const id = focus?.id?.toLowerCase();
    if (!id || ids.has(id) || SCOPES.has(id) || MODES.has(id) || id === 'general') {
      throw new Error(`Duplicate or colliding focus ID: ${focus?.id}. ${USAGE}`);
    }
    ids.add(id);
    for (const name of [focus.id, ...(focus.aliases ?? [])]) {
      const key = name?.toLowerCase();
      if (!key || catalog.has(key) || SCOPES.has(key) || MODES.has(key) || key === 'general') {
        throw new Error(`Ambiguous or colliding focus alias: ${name}. ${USAGE}`);
      }
      catalog.set(key, id);
    }
  }
  return catalog;
}

export function parseReviewInvocation(tokens, registry) {
  const catalog = catalogFrom(registry);
  if (!Array.isArray(tokens) || tokens.some(token => typeof token !== 'string')) throw new Error(USAGE);
  const words = tokens.map(token => token.toLowerCase());
  let mode = 'parallel';
  let focusId = null;
  let scope = 'current';
  let prUrl = null;
  let legacySyntax = false;
  let index = 0;
  if (MODES.has(words[index])) mode = words[index++];
  else if (catalog.has(words[index])) {
    mode = 'focus';
    focusId = catalog.get(words[index++]);
  } else if (SCOPES.has(words[index])) {
    scope = words[index++];
    legacySyntax = false;
  } else if (words.length) throw new Error(USAGE);

  if (SCOPES.has(words[index]) && (mode !== 'parallel' || !legacySyntax)) scope = words[index++];
  if (scope === 'pr') {
    const url = tokens[index++];
    if (!url || !/^https?:\/\/[^/]+\/[^/]+\/[^/]+\/(?:pull|merge_requests)\/\d+\/?(?:[?#].*)?$/i.test(url)) {
      throw new Error(`Invalid PR URL. ${USAGE}`);
    }
    prUrl = url;
  }
  if (SCOPES.has(words[0]) && catalog.has(words[index])) {
    mode = 'focus';
    focusId = catalog.get(words[index++]);
    legacySyntax = true;
  }
  if (index !== words.length) throw new Error(USAGE);
  return { mode, focusId, scope, prUrl, legacySyntax };
}
