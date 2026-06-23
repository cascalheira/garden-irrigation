# Brand assets

Home Assistant (and HACS) show an integration's icon from the central
[`home-assistant/brands`](https://github.com/home-assistant/brands) repository,
**not** from this repo. Until `garden_irrigation` is added there, HACS shows a
generic icon.

This folder already mirrors the `home-assistant/brands` layout, so the files can
be copied straight into a brands fork:

```
custom_integrations/garden_irrigation/icon.png      (256x256, transparent)
custom_integrations/garden_irrigation/icon@2x.png   (512x512, transparent)
```

`icon.svg` is the source.

## How to get the icon to show in HACS / Home Assistant

The icon **cannot** be served from this repository — HACS and HA only read
integration icons from `home-assistant/brands`. To make it appear:

```bash
# 1. Fork and clone home-assistant/brands, then from this repo:
cp -r brands/custom_integrations/garden_irrigation \
      <path-to-brands>/custom_integrations/

# 2. Commit in the brands fork and open a PR against home-assistant/brands.
```

(Optionally add `logo.png` / `logo@2x.png` for a wordmark.) Once that PR is
merged, the icon appears automatically at
`https://brands.home-assistant.io/garden_irrigation/icon.png` and HACS/HA show
it — no further change needed here.
