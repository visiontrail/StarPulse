---
version: "alpha"
name: "NeuroSync | Master Your Mind"
description: "Neurosync Master Feature Section is designed for highlighting product capabilities and value points. Key features include reusable structure, responsive behavior, and production-ready presentation. It is suitable for component libraries and responsive product interfaces."
colors:
  primary: "#4B4BA0"
  secondary: "#FFFFFF"
  tertiary: "#8F47AE"
  neutral: "#FFFFFF"
  background: "#FFFFFF"
  surface: "#000000"
  text-primary: "#FFFFFF"
  text-secondary: "#D4D4D8"
  accent: "#4B4BA0"
typography:
  display-lg:
    fontFamily: "Inter"
    fontSize: "72px"
    fontWeight: 600
    lineHeight: "72px"
    letterSpacing: "-0.05em"
  body-md:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  label-md:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
rounded:
  md: "0px"
spacing:
  base: "4px"
  sm: "2px"
  md: "4px"
  lg: "6px"
  xl: "8px"
  gap: "12px"
  card-padding: "20px"
  section-padding: "48px"
components:
  button-primary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.surface}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    padding: "6px"
  button-link:
    textColor: "{colors.text-secondary}"
    typography: "{typography.body-md}"
    rounded: "{rounded.md}"
    padding: "0px"
  card:
    rounded: "{rounded.md}"
    padding: "20px"
---

## Overview

- **Composition cues:**
  - Layout: Grid
  - Content Width: Full Bleed
  - Framing: Glassy
  - Grid: Strong

## Colors

The color system uses dark mode with #4B4BA0 as the main accent and #FFFFFF as the neutral foundation.

- **Primary (#4B4BA0):** Main accent and emphasis color.
- **Secondary (#FFFFFF):** Supporting accent for secondary emphasis.
- **Tertiary (#8F47AE):** Reserved accent for supporting contrast moments.
- **Neutral (#FFFFFF):** Neutral foundation for backgrounds, surfaces, and supporting chrome.

- **Usage:** Background: #FFFFFF; Surface: #000000; Text Primary: #FFFFFF; Text Secondary: #D4D4D8; Accent: #4B4BA0

- **Gradients:** bg-gradient-to-t from-zinc-950 to-transparent via-zinc-950/60, bg-gradient-to-r from-zinc-950/90 to-transparent via-zinc-950/40

## Typography

Typography relies on Inter across display, body, and utility text.

- **Display (`display-lg`):** Inter, 72px, weight 600, line-height 72px, letter-spacing -0.05em.
- **Body (`body-md`):** Inter, 14px, weight 400, line-height 20px.
- **Labels (`label-md`):** Inter, 14px, weight 500, line-height 20px.

## Layout

Layout follows a grid composition with reusable spacing tokens. Preserve the grid, full bleed structural frame before changing ornament or component styling. Use 4px as the base rhythm and let larger gaps step up from that cadence instead of introducing unrelated spacing values.

Treat the page as a grid / full bleed composition, and keep that framing stable when adding or remixing sections.

- **Layout type:** Grid
- **Content width:** Full Bleed
- **Base unit:** 4px
- **Scale:** 2px, 4px, 6px, 8px, 16px, 18px, 20px, 24px
- **Section padding:** 48px
- **Card padding:** 20px, 48px
- **Gaps:** 12px, 16px, 20px, 32px

## Elevation & Depth

Depth is communicated through glass, border contrast, and reusable shadow or blur treatments. Keep those recipes consistent across hero panels, cards, and controls so the page reads as one material system.

Surfaces should read as glass first, with borders, shadows, and blur only reinforcing that material choice.

- **Surface style:** Glass
- **Shadows:** rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0) 0px 0px 0px 0px, rgba(0, 0, 0, 0.1) 0px 2px 3px -1px, rgba(25, 28, 33, 0.02) 0px 1px 0px 0px, rgba(25, 28, 33, 0.08) 0px 0px 0px 1px
- **Blur:** 12px

### Techniques
- **Gradient border shell:** Use a thin gradient border shell around the main card. Wrap the surface in an outer shell with 0px padding and a 0px radius. Drive the shell with linear-gradient(to top, rgb(9, 9, 11), rgba(9, 9, 11, 0.6), rgba(0, 0, 0, 0)) so the edge reads like premium depth instead of a flat stroke. Keep the actual stroke understated so the gradient shell remains the hero edge treatment. Inset the real content surface inside the wrapper with a slightly smaller radius so the gradient only appears as a hairline frame.

## Shapes

Shapes stay consistent across cards, controls, and icon treatments.

- **Icon treatment:** Linear
- **Icon sets:** Solar

## Components

Anchor interactions to the detected button styles. Reuse the existing card surface recipe for content blocks.

### Buttons
- **Primary:** background #FFFFFF, text #000000, radius 0px, padding 6px, border 0px solid rgb(229, 231, 235).
- **Links:** text #D4D4D8, radius 0px, padding 0px, border 0px solid rgb(229, 231, 235).

### Cards and Surfaces
- **Card surface:** border 1px solid rgba(0, 0, 0, 0), radius 0px, padding 20px, shadow none, blur 12px.

### Iconography
- **Treatment:** Linear.
- **Sets:** Solar.

## Do's and Don'ts

Use these constraints to keep future generations aligned with the current system instead of drifting into adjacent styles.

### Do
- Do use the primary palette as the main accent for emphasis and action states.
- Do keep spacing aligned to the detected 4px rhythm.
- Do reuse the Glass surface treatment consistently across cards and controls.

### Don't
- Don't introduce extra accent colors outside the core palette roles unless the page needs a new semantic state.
- Don't mix unrelated shadow or blur recipes that break the current depth system.
- Don't exceed the detected expressive motion intensity without a deliberate reason.

## Motion

Motion feels expressive but remains focused on interface, text, and layout transitions. Timing clusters around 150ms and 200ms. Easing favors ease and cubic-bezier(0.4. Hover behavior focuses on text and transform changes. Scroll choreography uses GSAP ScrollTrigger for section reveals and pacing.

**Motion Level:** expressive

**Durations:** 150ms, 200ms, 300ms, 1000ms

**Easings:** ease, cubic-bezier(0.4, 0, 0.2, 1)

**Hover Patterns:** text, transform, color

**Scroll Patterns:** gsap-scrolltrigger

## WebGL

Reconstruct the graphics as a full-bleed background field using webgl, renderer, antialias, dpr clamp, custom shaders. The effect should read as retro-futurist, technical, and meditative: dot-matrix particle field with green on black and sparse spacing. Build it from dot particles + soft depth fade so the effect reads clearly. Animate it as slow breathing pulse. Interaction can react to the pointer, but only as a subtle drift. Preserve dom fallback.

**Id:** webgl

**Label:** WebGL

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Full-bleed background field
  - **Effect:**
    - **Value:** Dot-matrix particle field
  - **Primitives:**
    - **Value:** Dot particles + soft depth fade
  - **Motion:**
    - **Value:** Slow breathing pulse
  - **Interaction:**
    - **Value:** Pointer-reactive drift
  - **Render:**
    - **Value:** WebGL, Renderer, antialias, DPR clamp, custom shaders

**Techniques:** Dot matrix, Breathing pulse, Pointer parallax, Shader gradients, DOM fallback

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- WebGL Canvas for Trail Animation -->
      <canvas id="webgl-canvas" class="fixed inset-0 z-0 pointer-events-none opacity-70 mix-blend-screen"></canvas>

      <!-- Main Content Wrapper -->
      ```
  - **JS reference:**
    - **Language:** js
    - **Snippet:**
      ```
      "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
      }

      import * as THREE from 'three';
      import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
      import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
      …
      ```
  - **Scene setup:**
    - **Language:** js
    - **Snippet:**
      ```json
      {
        "imports": {
          "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
      }
      ```

## ThreeJS

Reconstruct the Three.js layer as a full-bleed background field with layered spatial depth that feels retro-futurist, volumetric, and technical. Use antialias, tone mapping, dpr clamp renderer settings, perspective, ~55deg fov, plane + custom buffer geometry geometry, shadermaterial + meshbasicmaterial materials, and ambient + key + rim lighting. Motion should read as slow orbital drift, with poster frame + dom fallback.

**Id:** threejs

**Label:** ThreeJS

**Stack:** ThreeJS, WebGL

**Insights:**
  - **Scene:**
    - **Value:** Full-bleed background field with layered spatial depth
  - **Render:**
    - **Value:** antialias, tone mapping, DPR clamp
  - **Camera:**
    - **Value:** Perspective, ~55deg FOV
  - **Lighting:**
    - **Value:** ambient + key + rim
  - **Materials:**
    - **Value:** ShaderMaterial + MeshBasicMaterial
  - **Geometry:**
    - **Value:** plane + custom buffer geometry
  - **Motion:**
    - **Value:** Slow orbital drift

**Techniques:** Shader materials, Bloom shaping, Timeline beats, antialias, tone mapping, DPR clamp, Poster frame + DOM fallback

**Code Evidence:**
  - **HTML reference:**
    - **Language:** html
    - **Snippet:**
      ```html
      <!-- WebGL Canvas for Trail Animation -->
      <canvas id="webgl-canvas" class="fixed inset-0 z-0 pointer-events-none opacity-70 mix-blend-screen"></canvas>

      <!-- Main Content Wrapper -->
      ```
  - **JS reference:**
    - **Language:** js
    - **Snippet:**
      ```
      "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
      }

      import * as THREE from 'three';
      import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
      import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
      …
      ```
  - **Scene setup:**
    - **Language:** js
    - **Snippet:**
      ```json
      {
        "imports": {
          "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
          "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
        }
      }
      ```
