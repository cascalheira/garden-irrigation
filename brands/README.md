# Brand assets

Home Assistant (and HACS) show an integration's icon from the central
[`home-assistant/brands`](https://github.com/home-assistant/brands) repository,
**not** from this repo. Until `garden_irrigation` is added there, HACS shows a
generic icon.

This folder holds the ready-to-submit icon:

- `icon.png` — 256×256, transparent
- `icon@2x.png` — 512×512, transparent
- `icon.svg` — source

## How to get the icon to show in HACS / Home Assistant

Open a pull request against `home-assistant/brands` adding these files under
`custom_integrations/garden_irrigation/`:

```
custom_integrations/garden_irrigation/icon.png      (256x256)
custom_integrations/garden_irrigation/icon@2x.png   (512x512)
```

(Optionally add `logo.png` / `logo@2x.png` for a wordmark.) Once that PR is
merged, the icon appears automatically at
`https://brands.home-assistant.io/garden_irrigation/icon.png` and HACS/HA will
display it — no change needed in this repository.
