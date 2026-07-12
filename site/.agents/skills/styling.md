# Styling Guide

## Tailwind CSS v4 Configuration

All Tailwind config is in `src/assets/styles/tailwind.css`:

### Theme Tokens

Defined in `@theme` block, mapped to CSS variables from `CustomStyles.astro`:

| Token               | CSS Variable              | Usage                            |
| ------------------- | ------------------------- | -------------------------------- |
| `--color-primary`   | `--aw-color-primary`      | `bg-primary`, `text-primary`     |
| `--color-secondary` | `--aw-color-secondary`    | `bg-secondary`, `text-secondary` |
| `--color-accent`    | `--aw-color-accent`       | `bg-accent`, `text-accent`       |
| `--color-default`   | `--aw-color-text-default` | `text-default`                   |
| `--color-muted`     | `--aw-color-text-muted`   | `text-muted`                     |

### Custom Utilities

| Utility         | Purpose               |
| --------------- | --------------------- |
| `bg-page`       | Page background color |
| `bg-dark`       | Dark page background  |
| `text-page`     | Page text color       |
| `btn`           | Base button styles    |
| `btn-primary`   | Primary CTA button    |
| `btn-secondary` | Secondary button      |
| `btn-tertiary`  | Text-style button     |

### Dark Mode

Class-based: add/remove `.dark` on `<html>`. Registered as:

```css
@variant dark (&:where(.dark, .dark *));
```

Use `dark:` prefix on any utility: `dark:text-slate-300`, `dark:bg-slate-800`.

### Scroll Animations

Custom `intersect` variant for IntersectionObserver animations:

```html
<div class="intersect-once intersect-quarter motion-safe:md:opacity-0 motion-safe:md:intersect:animate-fade"></div>
```

## Changing Colors

Edit `src/components/CustomStyles.astro`:

```css
:root {
  --aw-color-primary: rgb(1 97 239);
  --aw-color-secondary: rgb(1 84 207);
  /* ... */
}
.dark {
  --aw-color-primary: rgb(1 97 239);
  /* ... */
}
```

## Changing Fonts

1. Install the font: `npm install @fontsource-variable/your-font`
2. Import in `CustomStyles.astro`: `import '@fontsource-variable/your-font'`
3. Update the CSS variable: `--aw-font-sans: 'Your Font Variable'`

## Adding a New Theme Color

1. Add the CSS variable in `CustomStyles.astro` for both `:root` and `.dark`
2. Register in `tailwind.css` under `@theme`: `--color-yourcolor: var(--aw-color-yourcolor);`
3. Use as `bg-yourcolor`, `text-yourcolor`, etc.
