import type { APIRoute } from 'astro';

import { getSkills, readScript } from '~/lib/skills';

// Raw Python scripts for scripted skills: /skills/<slug>/scripts/<stage>.py
export async function getStaticPaths() {
  const skills = await getSkills();
  return skills.flatMap((skill) =>
    skill.scripts.map((stage) => ({
      params: { slug: skill.slug, stage },
      props: { source: readScript(skill.slug, stage) },
    }))
  );
}

export const GET: APIRoute = ({ props }) => {
  const { source } = props as { source: string };
  return new Response(source, {
    headers: { 'Content-Type': 'text/x-python; charset=utf-8' },
  });
};
