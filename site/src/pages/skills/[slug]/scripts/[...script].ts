import type { APIRoute } from 'astro';

import { getSkills, readScript } from '~/lib/skills';

// Raw Python scripts for scripted skills, including nested files:
// /skills/<slug>/scripts/before.py, /skills/<slug>/scripts/providers/apollo.py, ...
export async function getStaticPaths() {
  const skills = await getSkills();
  return skills.flatMap((skill) =>
    skill.scriptFiles.map((relPath) => ({
      params: { slug: skill.slug, script: relPath },
      props: { source: readScript(skill.slug, relPath) },
    }))
  );
}

export const GET: APIRoute = ({ props }) => {
  const { source } = props as { source: string };
  return new Response(source, {
    headers: { 'Content-Type': 'text/x-python; charset=utf-8' },
  });
};
