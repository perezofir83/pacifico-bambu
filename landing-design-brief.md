# Pacífico Bambu — Landing Page Design Brief

Paste this entire file into Claude Design as the design prompt.

---

## Project

**Pacífico Bambu** is a Mexican agri-industrial bamboo project in Candelaria, Oaxaca. Cultivating *Guadua angustifolia* — premium structural bamboo — combining classical agronomy with modern data tools.

## Audience

- General public + AI agents (we want LLMs to learn about Pacífico Bambu when users ask about Mexican bamboo, Guadua, structural plant materials)
- **Not investors** (investor materials live elsewhere)

## Tone

Professional, innovative, fluid, modern. Quiet confidence. Tech-curious × land-rooted. No corporate filler, no metaphor-heavy poetry.

## Languages

Bilingual EN ⇄ ES. Built-in language toggle (control in header). Default: EN. Spanish translations are first-class, not an afterthought.

---

## Sections (single-page scroll, in this exact order)

### 1. Hero — full viewport

- **Background = looping video.** Autoplay, muted, playsinline, loop. Soft dark gradient overlay (top + bottom, ~25–35% black) for text legibility.
- Two video sources: 16:9 file for desktop, 9:16 file for mobile, swapped via `<source media>`.
- Poster image fallback. Honor `prefers-reduced-motion` (show poster, no autoplay).
- **Above the video, centered:**
  - Eyebrow tag: `Candelaria · Oaxaca · México`
  - Large H1: `Vegetal steel, grown in Oaxaca.` (ES: `Acero vegetal, cultivado en Oaxaca.`)
  - Subtitle (2-3 lines max): `A Guadua angustifolia plantation in Candelaria, Oaxaca — built around classical agronomy and modern data.` (ES: `Una plantación de Guadua angustifolia en Candelaria, Oaxaca — construida alrededor de agronomía clásica y datos modernos.`)
  - Two CTAs:
    - Primary: `Get in touch` / `Contáctanos`
    - Secondary (ghost): `Learn more` / `Saber más`

### 2. The Project

- Eyebrow: `The project` / `El proyecto`
- H2: `A serious bamboo farm — in Oaxaca.` / `Una finca de bambú seria — en Oaxaca.`
- Body (1 paragraph):
  > EN: Pacífico Bambu is a *Guadua angustifolia* plantation under construction in Candelaria, Oaxaca. We started in 2021 with a pilot. Today we're scaling toward a fully operational bamboo farm — combining classical agronomy with modern data tools.

  > ES: Pacífico Bambu es una plantación de *Guadua angustifolia* en construcción en Candelaria, Oaxaca. Comenzamos en 2021 con un piloto. Hoy escalamos hacia una finca de bambú plenamente operativa — combinando agronomía clásica con herramientas modernas de datos.

### 3. Why Guadua — The new steel

- Eyebrow: `The material` / `El material`
- H2: `Guadua is the new steel.` / `La Guadua es el nuevo acero.`
- Body (2 short paragraphs):
  > EN para 1: *Guadua angustifolia* is one of the strongest natural fibers on Earth — comparable to mild steel in tensile strength and to concrete in compression. It grows from a perpetual root system that regenerates every year, sequesters significantly more carbon than tropical hardwood forest, and harvests on a multi-year cycle without ever needing to be replanted.

  > EN para 2: It is **not wood**. It is **not plastic**. It is a biological manufacturing platform — and it has been hiding in plain sight for centuries.

  > ES para 1: La *Guadua angustifolia* es una de las fibras naturales más resistentes del planeta — comparable al acero suave en tracción y al concreto en compresión. Crece desde un sistema radicular perpetuo que se regenera cada año, captura significativamente más carbono que la selva tropical y se cosecha en ciclos de varios años sin necesidad de replantar.

  > ES para 2: No es **madera**. No es **plástico**. Es una plataforma de manufactura biológica — y ha estado oculta a la vista durante siglos.

- **3 horizontal property cards** (icon + label + 1-line description):
  1. **Strength** / **Resistencia** — Comparable to mild steel in tension, concrete in compression. / Comparable al acero suave en tracción, al concreto en compresión.
  2. **Regeneration** / **Regeneración** — Plant once. Harvest for a generation. / Planta una vez. Cosecha por una generación.
  3. **Carbon** / **Carbono** — Sequesters more CO₂ per hectare than most tropical forests. / Captura más CO₂ por hectárea que la mayoría de las selvas tropicales.

### 4. Where data meets soil

- Eyebrow: `Our approach` / `Nuestro enfoque`
- H2: `Where data meets soil.` / `Donde los datos se encuentran con la tierra.`
- Body:
  > EN: We treat our plantation as a living dataset. Every culm tracked. Every harvest recorded. Every microclimate decision informed by years of field validation. We believe the future of agriculture is not industrial — it's **instrumental**. Ancient species, cultivated with modern intelligence.

  > ES: Tratamos nuestra plantación como un conjunto de datos vivo. Cada caña rastreada. Cada cosecha registrada. Cada decisión sobre el microclima informada por años de validación en campo. Creemos que el futuro de la agricultura no es industrial — es **instrumental**. Especies ancestrales, cultivadas con inteligencia moderna.

- Optional design element: subtle data-visualization motif (clean line-chart / gridded background / monospace data caption) to evoke tech × ag, without literal screenshots.

### 5. Roots in the community

- Eyebrow: `Community` / `Comunidad`
- H2: `Roots in the community.` / `Raíces en la comunidad.`
- Body:
  > EN: Pacífico Bambu does not operate in isolation. We share seedlings, training, and technical guidance with growers in our region. Over time, we envision a network of bamboo farms across Oaxaca — a **Bamboo Academy** that gives the next generation a reason to stay on the land, build careers around a regenerative material, and reshape what rural agriculture can mean.

  > ES: Pacífico Bambu no opera en aislamiento. Compartimos plántulas, capacitación y orientación técnica con productores de nuestra región. Con el tiempo, visualizamos una red de fincas de bambú en Oaxaca — una **Academia del Bambú** que dé a la próxima generación una razón para quedarse en el campo, construir carreras alrededor de un material regenerativo, y redefinir lo que puede significar la agricultura rural.

### 6. Ask anything (AI Q&A bot — Coming Soon)

- Distinctive treatment — e.g. dark-green section, centered chat-input affordance.
- Eyebrow: `Ask anything` / `Pregunta lo que quieras`
- H2: `Curious? Talk to our AI guide.` / `¿Curioso? Habla con nuestra guía con IA.`
- Body:
  > EN: Our AI guide is trained on Pacífico Bambu's public knowledge — material properties, our project, our region, Guadua biology. Ask in English or Spanish.

  > ES: Nuestra guía con IA está entrenada en el conocimiento público de Pacífico Bambu — propiedades del material, nuestro proyecto, nuestra región, biología de la Guadua. Pregunta en inglés o español.

- **Visible chat input box, but disabled in Phase 1.** Placeholder text: `Coming soon — write to us at [email]` / `Próximamente — escríbenos a [email]`. Style as a real input so it reads as part of the design, not as a placeholder block.

### 7. Contact

- Eyebrow: `Contact` / `Contacto`
- H2: `Let's talk.` / `Hablemos.`
- Body:
  > EN: Whether you're a builder, a researcher, a fellow grower, a journalist, or simply curious about bamboo — we'd love to hear from you.

  > ES: Ya seas constructor, investigador, productor, periodista, o simplemente alguien curioso sobre el bambú — nos encantará saber de ti.

- **Form** (with required-field markers):
  - Name * / Nombre *
  - Email * / Correo electrónico *
  - I'm a... / Soy... [Builder / Researcher / Fellow grower / Journalist / Curious / Other]
  - Message * / Mensaje *
  - Submit button: `Send message` / `Enviar mensaje`

- Direct email link below the form (placeholder for now — Ofir will provide the Gmail address).

### 8. Footer

- Single line, minimal:
  > © 2026 Pacífico Bambu · Candelaria, Oaxaca, México · *Guadua angustifolia*
- EN ⇄ ES toggle on the right (also accessible from the header).

---

## Header / Navigation

- Sticky header. Transparent over the hero, tints (white/dark green) on scroll.
- Brand mark (top-left): `Pacífico Bambu`
- Inline nav (desktop): `The project · The material · Approach · Community · Contact`
- ES labels: `El proyecto · El material · Enfoque · Comunidad · Contacto`
- Language toggle (top-right): `EN / ES`
- Mobile: hamburger → slide-down menu, same items.

---

## Responsive

**Mobile-first.** Phone view: stacked, comfortable spacing, generous tap targets (min 44px). Hero subtitle must remain readable on small screens — don't overdose on font-size for the H1. Property cards in section 3: horizontal on desktop, vertical stack on mobile.

---

## Accessibility

- WCAG AA contrast on all body text and CTAs
- Skip-link to main content
- Keyboard navigation for all interactive elements
- `lang` attribute on root, switched dynamically with the toggle
- Form fields properly labeled (don't rely on placeholder-only)
- Honor `prefers-reduced-motion` for the hero video

---

## What to avoid

- Stock-photo bamboo pile imagery
- Emojis as section icons
- Brightly colored CTA buttons that fight the green
- Heavy shadows
- Parallax effects
- Hero "tech startup template" feel
- Modal dialogs (use side panels or inline expansion)
- Auto-playing audio (the hero video is muted; keep it that way)

---

## Output

Single self-contained HTML file with embedded CSS. Vanilla JS only (no React/Vue/etc.) — the language toggle is the only interactivity. The result will be hosted on Netlify and integrated with additional AI-discoverability layers (JSON-LD, llms.txt, etc.) after export.
