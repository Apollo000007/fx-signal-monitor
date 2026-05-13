# Visual Theme Switching

The app now ships with two visual themes:

- `eva`: white background, black/red operation-terminal typography, and the generated command poster asset.
- `olympus`: the previous Olympus × Enlightenment palette and copy.

Set the theme with:

```bash
NEXT_PUBLIC_FX_VISUAL_THEME=eva
```

To restore the previous design:

```bash
NEXT_PUBLIC_FX_VISUAL_THEME=olympus
```

The default is `eva`, so removing the variable keeps the new design.
