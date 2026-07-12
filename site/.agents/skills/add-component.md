# Add a Widget Component

## Steps

1. Create a new `.astro` file in `src/components/widgets/`
2. Define a Props interface in `src/types.d.ts` (or use inline)
3. Follow the existing component patterns

## Template

```astro
---
import WidgetWrapper from '~/components/ui/WidgetWrapper.astro';
import Headline from '~/components/ui/Headline.astro';
import type { MyWidget as Props } from '~/types';

const {
  title = await Astro.slots.render('title'),
  subtitle = await Astro.slots.render('subtitle'),
  tagline,
  items = [],
  id,
  isDark = false,
  classes = {},
  bg = await Astro.slots.render('bg'),
} = Astro.props;
---

<WidgetWrapper id={id} isDark={isDark} containerClass={classes?.container ?? ''} bg={bg}>
  <Headline title={title} subtitle={subtitle} tagline={tagline} classes={classes?.headline} />
  <div class="max-w-5xl mx-auto">
    <!-- Widget content here -->
  </div>
</WidgetWrapper>
```

## Conventions

- Extend the `Widget` base interface from `~/types`
- Use `WidgetWrapper` for consistent spacing and dark mode support
- Use `Headline` for title/subtitle/tagline rendering
- Accept `classes` prop with `twMerge()` for style overrides
- Support named slots for `title`, `subtitle`, and `bg`
- Use `intersect-once` classes for scroll-triggered animations
