import fs from 'node:fs';
import path from 'node:path';

import { getCollection, type CollectionEntry } from 'astro:content';

import { CATEGORIES, getCategory, type Category, type CategorySlug } from '~/data/categories';

export const GITHUB_REPO_URL = 'https://github.com/TomGranot/hubspot-admin-skills';
export const MARKETPLACE_ADD_COMMAND = '/plugin marketplace add tomgranot/hubspot-admin-skills';
export const PLUGIN_INSTALL_COMMAND = '/plugin install hubspot-admin@hubspot-admin-skills';

/**
 * Absolute path of the repo-root skills/ directory. Resolved from the working
 * directory (astro build runs with cwd = site/, so the repo root is one level
 * up) rather than import.meta.url, which points into dist/.prerender chunks
 * during the build.
 */
const findSkillsDir = (): string => {
  let dir = process.cwd();
  for (let i = 0; i < 4; i++) {
    const candidate = path.join(dir, 'skills');
    if (
      fs.existsSync(candidate) &&
      fs.readdirSync(candidate).some((entry) => fs.existsSync(path.join(candidate, entry, 'SKILL.md')))
    ) {
      return candidate;
    }
    dir = path.dirname(dir);
  }
  throw new Error(`skills/ directory not found walking up from ${process.cwd()}`);
};

export const SKILLS_DIR = findSkillsDir();

const SCRIPT_STAGES = ['before', 'execute', 'after'] as const;
export type ScriptStage = (typeof SCRIPT_STAGES)[number];

export interface Skill {
  slug: string;
  title: string;
  description: string;
  category: Category;
  version: string;
  author: string;
  license: string;
  /** Script stages that ship as ready-to-run Python files, e.g. ['before', 'execute', 'after']. */
  scripts: ScriptStage[];
  /** All .py files under scripts/, as paths relative to scripts/ (includes nested files like providers/apollo.py). */
  scriptFiles: string[];
  /** The "Why This Matters" section body, when present. */
  whyItMatters: string | undefined;
  /** Raw SKILL.md source, frontmatter included. */
  raw: string;
  /** Markdown body (no frontmatter). */
  body: string;
  entry: CollectionEntry<'skills'>;
}

const skillDir = (slug: string) => path.join(SKILLS_DIR, slug);

const detectScripts = (slug: string): ScriptStage[] =>
  SCRIPT_STAGES.filter((stage) => fs.existsSync(path.join(skillDir(slug), 'scripts', `${stage}.py`)));

/** All .py files under a skill's scripts/ dir, recursive, relative to scripts/. */
const listScriptFiles = (slug: string): string[] => {
  const scriptsDir = path.join(skillDir(slug), 'scripts');
  if (!fs.existsSync(scriptsDir)) return [];
  return fs
    .readdirSync(scriptsDir, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.py'))
    .map((entry) => path.relative(scriptsDir, path.join(entry.parentPath, entry.name)))
    .sort();
};

/** Extract the text of a `## <heading>` section from a markdown body. */
export const extractSection = (body: string, heading: string): string | undefined => {
  const match = body.match(new RegExp(`^## ${heading}\\s*\\n([\\s\\S]*?)(?=\\n## |$)`, 'm'));
  return match ? match[1].trim() : undefined;
};

/** First paragraph of a section, with inline markdown emphasis markers stripped. */
export const firstParagraph = (text: string | undefined): string | undefined => {
  if (!text) return undefined;
  const para = text
    .split(/\n\s*\n/)[0]
    ?.replace(/\*\*|__/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  return para || undefined;
};

const toTitle = (body: string, fallback: string): string => {
  const h1 = body.match(/^# (.+)$/m);
  return h1 ? h1[1].trim() : fallback;
};

let cache: Skill[] | undefined;

export const getSkills = async (): Promise<Skill[]> => {
  if (cache) return cache;

  const entries = await getCollection('skills');
  const skills = entries.map((entry): Skill => {
    const slug = entry.id.split('/')[0];
    const body = entry.body ?? '';
    return {
      slug,
      title: toTitle(body, entry.data.name),
      description: entry.data.description,
      category: getCategory(entry.data.metadata.category),
      version: entry.data.metadata.version,
      author: entry.data.metadata.author,
      license: entry.data.license,
      scripts: detectScripts(slug),
      scriptFiles: listScriptFiles(slug),
      whyItMatters: extractSection(body, 'Why This Matters'),
      raw: fs.readFileSync(path.join(skillDir(slug), 'SKILL.md'), 'utf-8'),
      body,
      entry,
    };
  });

  const categoryOrder = new Map(CATEGORIES.map((c, i) => [c.slug, i]));
  skills.sort(
    (a, b) =>
      (categoryOrder.get(a.category.slug) ?? 99) - (categoryOrder.get(b.category.slug) ?? 99) ||
      a.slug.localeCompare(b.slug)
  );

  cache = skills;
  return skills;
};

export const getSkill = async (slug: string): Promise<Skill> => {
  const skill = (await getSkills()).find((s) => s.slug === slug);
  if (!skill) throw new Error(`Unknown skill: ${slug}`);
  return skill;
};

export const getSkillsByCategory = async (category: CategorySlug): Promise<Skill[]> =>
  (await getSkills()).filter((s) => s.category.slug === category);

export const getRelatedSkills = async (skill: Skill, count = 4): Promise<Skill[]> =>
  (await getSkillsByCategory(skill.category.slug)).filter((s) => s.slug !== skill.slug).slice(0, count);

/** Read a script by its path relative to the skill's scripts/ dir; rejects path traversal. */
export const readScript = (slug: string, relPath: string): string => {
  const scriptsDir = path.join(skillDir(slug), 'scripts');
  const resolved = path.resolve(scriptsDir, relPath);
  if (!resolved.startsWith(scriptsDir + path.sep)) throw new Error(`Invalid script path: ${relPath}`);
  return fs.readFileSync(resolved, 'utf-8');
};

// URL helpers (paths only — join with Astro.site / SITE.site for absolute URLs)
export const skillPath = (slug: string) => `/skills/${slug}`;
export const skillMdPath = (slug: string) => `/skills/${slug}.md`;
export const scriptPath = (slug: string, relPath: string) => `/skills/${slug}/scripts/${relPath}`;
export const categoryPath = (slug: string) => `/categories/${slug}`;
export const skillGithubUrl = (slug: string) => `${GITHUB_REPO_URL}/tree/main/skills/${slug}`;
