import type { APIRoute } from 'astro';
import sharp from 'sharp';

import { CATEGORIES } from '~/data/categories';
import { PROBLEMS } from '~/data/problems';
import { getSkills } from '~/lib/skills';

// Build-time generated Open Graph images: /og/skills/<slug>.png and
// /og/problems/<slug>.png. Rendered from an SVG template via sharp (librsvg),
// so no headless browser or extra font tooling is needed at build time.

interface OgProps {
  title: string;
  kicker: string;
  badge?: string;
}

export async function getStaticPaths() {
  const skills = await getSkills();
  const scriptedCount = skills.filter((s) => s.scriptFiles.length > 0).length;

  const pages: { path: string; props: OgProps }[] = [
    {
      path: 'home',
      props: {
        title: 'The HubSpot cleanup you keep postponing, run by Claude Code',
        kicker: 'Open source · MIT',
        badge: `${skills.length} skills, ${scriptedCount} with Python scripts`,
      },
    },
    {
      path: 'pages/skills',
      props: { title: `All ${skills.length} skills, one safe pattern`, kicker: 'Skills reference' },
    },
    {
      path: 'pages/problems',
      props: { title: "What's broken in your HubSpot portal?", kicker: 'Problem index' },
    },
    {
      path: 'pages/install',
      props: { title: 'Install in two commands', kicker: 'Get started', badge: 'Humans and agents welcome' },
    },
    {
      path: 'pages/contributing',
      props: { title: 'Help build the skill set', kicker: 'Community' },
    },
    ...CATEGORIES.map((category) => ({
      path: `categories/${category.slug}`,
      props: {
        title: category.title,
        kicker: 'Skill category',
        badge: `${skills.filter((s) => s.category.slug === category.slug).length} skills`,
      },
    })),
  ];

  return [
    ...pages.map(({ path, props }) => ({ params: { path }, props })),
    ...skills.map((skill) => ({
      params: { path: `skills/${skill.slug}` },
      props: {
        title: skill.title,
        kicker: skill.category.title,
        badge: skill.scriptFiles.length > 0 ? 'Python scripts included' : undefined,
      } satisfies OgProps,
    })),
    ...PROBLEMS.map((problem) => ({
      params: { path: `problems/${problem.slug}` },
      props: { title: problem.title, kicker: 'Common HubSpot problem, solved' } satisfies OgProps,
    })),
  ];
}

const escapeXml = (text: string) =>
  text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Greedy word wrap tuned for the 64px font below. */
const wrapTitle = (title: string, maxChars = 25, maxLines = 4): string[] => {
  const words = title.split(' ');
  const lines: string[] = [];
  let line = '';
  for (const word of words) {
    if (line && (line + ' ' + word).length > maxChars) {
      lines.push(line);
      line = word;
    } else {
      line = line ? `${line} ${word}` : word;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    lines[maxLines - 1] = lines[maxLines - 1].replace(/.{3}$/, '') + '…';
  }
  return lines;
};

const template = ({ title, kicker, badge }: OgProps) => {
  const lines = wrapTitle(title);
  const tspans = lines.map((line, i) => `<tspan x="80" dy="${i === 0 ? 0 : 76}">${escapeXml(line)}</tspan>`).join('');
  const titleY = 300 - (lines.length - 1) * 30;

  return `<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e3a8a"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="0" y="0" width="1200" height="8" fill="#0161ef"/>
  <text x="80" y="150" font-family="DejaVu Sans, Arial, sans-serif" font-size="28" font-weight="bold" fill="#60a5fa" letter-spacing="2">${escapeXml(kicker.toUpperCase())}</text>
  <text y="${titleY}" font-family="DejaVu Sans, Arial, sans-serif" font-size="64" font-weight="bold" fill="#ffffff">${tspans}</text>
  ${
    badge
      ? `<rect x="80" y="480" rx="18" width="${badge.length * 13 + 40}" height="40" fill="#065f46"/>
  <text x="100" y="507" font-family="DejaVu Sans, Arial, sans-serif" font-size="22" fill="#a7f3d0">${escapeXml(badge)}</text>`
      : ''
  }
  <text x="80" y="575" font-family="DejaVu Sans, Arial, sans-serif" font-size="26" fill="#94a3b8">hubspot.granot.io — HubSpot Admin Skills for Claude Code</text>
</svg>`;
};

export const GET: APIRoute = async ({ props }) => {
  const png = await sharp(Buffer.from(template(props as OgProps)))
    .png()
    .toBuffer();
  return new Response(new Uint8Array(png), { headers: { 'Content-Type': 'image/png' } });
};
