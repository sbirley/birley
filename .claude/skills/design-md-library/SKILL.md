---
name: design-md-library
description: Library of 74 ready-made DESIGN.md design systems analyzed from real brand websites (Stripe, Linear, Vercel, Apple, Notion, Claude, Airbnb, Spotify, Tesla, and more), each with color tokens, typography scale, spacing, components, and layout rules. Use when the user asks for UI "in the style of", "like", or "inspired by" a named brand or product, wants a starting design system or visual direction for a page or app, or asks which design references are available.
---

# DESIGN.md Library

Ready-to-use design-system documents from [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (MIT). Each file in `references/` follows the Google Stitch DESIGN.md format: YAML front matter with tokens (colors, typography, spacing, radii), followed by prose rules for layout, components, and do's and don'ts.

## How to use

1. Pick the reference that matches the request from the index below. If the user names a brand that isn't listed, say so and suggest the closest matches by aesthetic.
2. Read the whole reference file before writing any UI. Treat its tokens and rules as the spec: use its exact colors, type scale, spacing, radii, and component patterns rather than approximating them.
3. Fonts that are proprietary (for example Copernicus or Söhne) won't be available. Use the fallback stack the file lists, or pick the closest free font and say which one you chose.
4. To make a reference the project's standing design system, copy it to `DESIGN.md` at the project root only when the user asks. That file is also what the `impeccable` skill reads as the project's design truth, so don't overwrite an existing root `DESIGN.md` without confirming first.
5. These are "inspired by" analyses of public marketing sites. Use them for visual language only. Don't reproduce a brand's logos, trademarks, or wordmarks, and don't build pages that could pass as the real company's.

## Index

### AI & LLM Platforms
- **Claude** (`references/claude.md`): Anthropic's AI assistant. Warm terracotta accent, clean editorial layout
- **Cohere** (`references/cohere.md`): Enterprise AI platform. Vibrant gradients, data-rich dashboard aesthetic
- **ElevenLabs** (`references/elevenlabs.md`): AI voice platform. Dark cinematic UI, audio-waveform aesthetics
- **Minimax** (`references/minimax.md`): AI model provider. Bold dark interface with neon accents
- **Mistral AI** (`references/mistral.ai.md`): Open-weight LLM provider. French-engineered minimalism, purple-toned
- **Ollama** (`references/ollama.md`): Run LLMs locally. Terminal-first, monochrome simplicity
- **OpenCode AI** (`references/opencode.ai.md`): AI coding platform. Developer-centric dark theme
- **Replicate** (`references/replicate.md`): Run ML models via API. Clean white canvas, code-forward
- **Runway** (`references/runwayml.md`): AI creative-tools platform with an editorial film-festival aesthetic — cinematic dark heroes, paper-white reading bands, single proprietary sans, and pure black pill CTAs.
- **Together AI** (`references/together.ai.md`): Open-source AI infrastructure. Technical, blueprint-style design
- **VoltAgent** (`references/voltagent.md`): AI agent framework. Void-black canvas, emerald accent, terminal-native
- **xAI** (`references/x.ai.md`): Elon Musk's AI lab. Stark monochrome, futuristic minimalism

### Developer Tools & IDEs
- **Cursor** (`references/cursor.md`): AI-first code editor. Sleek dark interface, gradient accents
- **Expo** (`references/expo.md`): React Native platform. Dark theme, tight letter-spacing, code-centric
- **Lovable** (`references/lovable.md`): AI full-stack builder. Playful gradients, friendly dev aesthetic
- **Raycast** (`references/raycast.md`): Productivity launcher. Sleek dark chrome, vibrant gradient accents
- **Superhuman** (`references/superhuman.md`): Fast email client. Premium dark UI, keyboard-first, purple glow
- **Vercel** (`references/vercel.md`): Frontend deployment platform. Black and white precision, Geist font
- **Warp** (`references/warp.md`): Modern terminal. Dark IDE-like interface, block-based command UI

### Backend, Database & DevOps
- **ClickHouse** (`references/clickhouse.md`): Fast analytics database. Yellow-accented, technical documentation style
- **Composio** (`references/composio.md`): Tool integration platform. Modern dark with colorful integration icons
- **HashiCorp** (`references/hashicorp.md`): Infrastructure automation. Enterprise-clean, black and white
- **MongoDB** (`references/mongodb.md`): Document database. Green leaf branding, developer documentation focus
- **PostHog** (`references/posthog.md`): Product analytics. Playful hedgehog branding, developer-friendly dark UI
- **Sanity** (`references/sanity.md`): Headless content platform with a dark-first editorial marketing surface — 112px display type, IBM Plex Mono technical eyebrows, and a single coral-red accent reserved for the highest-priority CTA.
- **Sentry** (`references/sentry.md`): Error monitoring. Dark dashboard, data-dense, pink-purple accent
- **Supabase** (`references/supabase.md`): Open-source Firebase alternative. Dark emerald theme, code-first

### Productivity & SaaS
- **Slack** (`references/slack.md`): Workplace messaging. Deep aubergine brand surfaces
- **Cal.com** (`references/cal.md`): Open-source scheduling. Clean neutral UI, developer-oriented simplicity
- **Intercom** (`references/intercom.md`): Customer messaging. Friendly blue palette, conversational UI patterns
- **Linear** (`references/linear.app.md`): Project management for engineers. Ultra-minimal, precise, purple accent
- **Mintlify** (`references/mintlify.md`): Documentation platform. Clean, green-accented, reading-optimized
- **Notion** (`references/notion.md`): All-in-one workspace. Warm minimalism, serif headings, soft surfaces
- **Resend** (`references/resend.md`): Email API for developers. Minimal dark theme, monospace accents
- **Zapier** (`references/zapier.md`): Automation platform. Warm orange, friendly illustration-driven

### Design & Creative Tools
- **Airtable** (`references/airtable.md`): Spreadsheet-database hybrid. Colorful, friendly, structured data aesthetic
- **Clay** (`references/clay.md`): Creative agency. Organic shapes, soft gradients, art-directed layout
- **Figma** (`references/figma.md`): Collaborative design tool. Vibrant multi-color, playful yet professional
- **Framer** (`references/framer.md`): Website builder. Bold black and blue, motion-first, design-forward
- **Miro** (`references/miro.md`): Visual collaboration. Bright yellow accent, infinite canvas aesthetic
- **Webflow** (`references/webflow.md`): Visual web builder. Blue-accented, polished marketing site aesthetic

### Fintech & Crypto
- **Binance** (`references/binance.md`): Crypto exchange. Bold Binance Yellow on monochrome, trading-floor urgency
- **Coinbase** (`references/coinbase.md`): Crypto exchange. Clean blue identity, trust-focused, institutional feel
- **Kraken** (`references/kraken.md`): Crypto trading platform. Purple-accented dark UI, data-dense dashboards
- **Mastercard** (`references/mastercard.md`): Global payments network. Warm cream canvas, orbital pill shapes, editorial warmth
- **Revolut** (`references/revolut.md`): Digital banking. Sleek dark interface, gradient cards, fintech precision
- **Stripe** (`references/stripe.md`): Payment infrastructure. Signature purple gradients, weight-300 elegance
- **Wise** (`references/wise.md`): International money transfer. Bright green accent, friendly and clear

### E-commerce & Retail
- **Airbnb** (`references/airbnb.md`): Travel marketplace. Warm coral accent, photography-driven, rounded UI
- **Meta** (`references/meta.md`): Tech retail store. Photography-first, binary light/dark surfaces, Meta Blue CTAs
- **Nike** (`references/nike.md`): Athletic retail. Monochrome UI, massive uppercase Futura, full-bleed photography
- **Shopify** (`references/shopify.md`): E-commerce platform. Dark-first cinematic, neon green accent, ultra-light display type
- **Starbucks** (`references/starbucks.md`): Coffee retail flagship. Four-tier earth-green system, warm cream canvas, proprietary SoDoSans typography

### Media & Consumer Tech
- **Apple** (`references/apple.md`): Consumer electronics. Premium white space, SF Pro, cinematic imagery
- **HP** (`references/hp.md`): PC and printer maker. Pure white canvas, HP Electric Blue signal CTA, geometric Forma DJR Micro, blue chevron decorations
- **IBM** (`references/ibm.md`): Enterprise technology. Carbon design system, structured blue palette
- **NVIDIA** (`references/nvidia.md`): GPU computing. Green-black energy, technical power aesthetic
- **Pinterest** (`references/pinterest.md`): Visual discovery platform. Red accent, masonry grid, image-first
- **PlayStation** (`references/playstation.md`): Gaming console retail. Three-surface channel layout, cyan hover-scale interaction
- **SpaceX** (`references/spacex.md`): Space technology. Stark black and white, full-bleed imagery, futuristic
- **Spotify** (`references/spotify.md`): Music streaming. Vibrant green on dark, bold type, album-art-driven
- **The Verge** (`references/theverge.md`): Tech editorial media. Acid-mint and ultraviolet accents, Manuka display type
- **Uber** (`references/uber.md`): Mobility platform. Bold black and white, tight type, urban energy
- **Vodafone** (`references/vodafone.md`): Global telecom brand. Monumental uppercase display, Vodafone Red chapter bands
- **WIRED** (`references/wired.md`): Tech magazine. Paper-white broadsheet density, custom serif, ink-blue links

### Automotive
- **BMW** (`references/bmw.md`): Luxury automotive. Dark premium surfaces, precise German engineering aesthetic
- **BMW M** (`references/bmw-m.md`): Performance automotive. Motorsport-inspired contrast, M color accents, precision-driven layout
- **Bugatti** (`references/bugatti.md`): Luxury hypercar. Cinema-black canvas, monochrome austerity, monumental display type
- **Ferrari** (`references/ferrari.md`): Luxury automotive. Chiaroscuro black-white editorial, Ferrari Red with extreme sparseness
- **Lamborghini** (`references/lamborghini.md`): Luxury automotive. True black cathedral, gold accent, LamboType custom Neo-Grotesk
- **Renault** (`references/renault.md`): French automotive. Vivid aurora gradients, NouvelR proprietary typeface, zero-radius buttons
- **Tesla** (`references/tesla.md`): Electric vehicles. Radical subtraction, cinematic full-viewport photography, Universal Sans

### Retro Web · DESIGN.md Nostalgia
- **Dell (1996)** (`references/dell-1996.md`): Catalog-era enterprise web. Literal black page frame, flat color-block "ribbon cards", chunky Helvetica-Black titles over Times Roman body, and hand-cut GIF stickers (NEW! bursts, award seals, beveled product photos).
- **Nintendo.com (2001)** (`references/nintendo-2001.md`): Y2K "console chrome" web. Brushed-periwinkle beveled metal panels, a halftone-dotted carbon nav glowing amber, outlined Arial-Black box-art wordmarks over circuit-board hero fields, and a pixel Mario welcome bubble.
