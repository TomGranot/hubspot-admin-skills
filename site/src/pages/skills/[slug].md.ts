import type { APIRoute } from 'astro';

import { getSkills, type Skill } from '~/lib/skills';

// Raw-markdown twin of every skill page: /skills/<slug>.md serves the
// verbatim SKILL.md, frontmatter included. Content-Type and canonical Link
// headers are applied by public/_headers at the Netlify edge.
export async function getStaticPaths() {
  const skills = await getSkills();
  return skills.map((skill) => ({ params: { slug: skill.slug }, props: { skill } }));
}

export const GET: APIRoute = ({ props }) => {
  const { skill } = props as { skill: Skill };
  return new Response(skill.raw, {
    headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
  });
};
