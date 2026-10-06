# Plan2Build: cost model

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/COST_MODEL.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. Every price is an estimate from public pricing pages read on 2026-10-03; re-verify before purchase. Exchange rate assumed at ₹85 per US dollar; GST (18%) is excluded unless stated. |
| Business authority | Chirag's baseline (low-cost, appropriately sized; spend only where it materially improves reliability, speed, security, functionality or velocity); CQ-01 (package price), CQ-24 (engine and image budget) |
| Related | CLOUD_AND_HOSTING_ARCHITECTURE.md, SCALABILITY_AND_MIGRATION_PLAN.md, INTEGRATION_ARCHITECTURE.md |

## 1. Unit prices (estimates, 2026-10-03)

| Item | Price | Notes |
|---|---|---|
| Hostinger KVM 2 (2 vCPU, 8 GB, 100 GB) | ₹799 per month on a 12 to 24 month term paid upfront; ₹1,199 renewal | KVM 4 (4 vCPU, 16 GB): ₹1,099 promo, ₹2,399 renewal |
| Supabase | Free: $0 (500 MB, pauses after 7 idle days, no backups). Pro: $25 per month including $10 compute credit (Micro), 8 GB disk, daily backups 7 days; Small compute +$15; disk $0.125 per GB beyond 8 GB; PITR add-on about $100 per month | Mumbai region |
| Cloudflare R2 | Free: 10 GB storage, 1M class A, 10M class B per month; then $0.015 per GB-month, $4.50 per million class A, $0.36 per million class B; no egress fees | |
| Cloudflare (DNS, proxy, WAF basic) | $0 | Load balancing later: $5 per month plus per-origin |
| Upstash Redis | Free: 500K commands per month, 256 MB; pay as you go $0.20 per 100K commands; fixed $10 per month plan | |
| Resend | Free: 3,000 emails per month (100 per day); Pro $20 per month for 50,000 | The 100 per day cap matters once homeowners are live |
| Sentry | Developer: $0 (5K errors, limited performance); Team from $26 per month | |
| Grafana Cloud | Free: 10K metric series, 50 GB logs, 14 days | |
| UptimeRobot | Free: 50 monitors at 5-minute intervals | |
| GitHub | Free for private repositories with 2,000 Actions minutes per month; Team $4 per user per month if minutes or features are needed | CI at about 15 minutes per run, 100 runs per month = 1,500 minutes |
| Razorpay | 2% plus GST (2.36% effective) per domestic transaction; 3% for international and some premium instruments; no setup or annual fee; 0% for the first 90 days up to ₹5 lakh for new merchants (offer, verify) | |
| MSG91 SMS (later) | ₹0.16 to ₹0.25 per SMS plus GST; DLT registration ₹5,900 entity plus ₹5,900 per sender header, one-time | |
| WhatsApp Business (later) | Conversation-based, roughly ₹0.3 to ₹0.9 per conversation by category, plus BSP fees | |
| Gemini 3.1 Flash Image | About $0.067 per image | FLUX.1 Kontext pro about $0.04 |
| MapTiler (tiles) | Free: 100K tile requests per month; then from $25 per month | Protomaps self-hosted on R2: storage only |
| Domain `plan2build.in` | About ₹700 to ₹1,000 per year | |
| External penetration test | ₹50,000 to ₹1,50,000 one-time (Indian vendors, scope of three hosts and an API) | Before the first real payment, then yearly |
| ClamAV, Caddy, Procrastinate, fpdf2 (ADR-023), PostGIS, OSRM, Nominatim software | $0 (open source) | |

## 2. Phases

Volumes are assumptions used for the arithmetic; they are not forecasts.

### 2.1 POC build (months 0 to 3; synthetic data; no homeowners)

| Category | Item | Monthly |
|---|---|---|
| Fixed | VPS KVM 2 (promo, prepaid) | ₹799 |
| Fixed | Domain (amortised) | ₹80 |
| Fixed | Supabase Free ×2 (prod placeholder, staging) | ₹0 |
| Fixed | R2, Upstash, Cloudflare, Sentry, Grafana, UptimeRobot, GitHub, Resend free tiers | ₹0 |
| Usage | Image generation trials (about 100 images) | ₹570 |
| Usage | Razorpay test mode | ₹0 |
| Optional | None | |
| Total | | about ₹1,450 per month |

### 2.2 Early production (months 3 to 12; up to 50 projects in Raipur; about 100 active users per day)

| Category | Item | Monthly |
|---|---|---|
| Fixed | VPS KVM 2 (renewal price assumed) | ₹1,199 |
| Fixed | Supabase Pro (production); staging stays Free | ₹2,125 |
| Fixed | Domain | ₹80 |
| Fixed | Resend Pro (emails exceed 100 per day with reminders and OTP) | ₹1,700 |
| Fixed | R2 (under 10 GB at first; about 50 projects × 300 photos × 3 MB = 45 GB by month 12: $0.50) | ₹0 to ₹45 |
| Fixed | Upstash, Cloudflare, Sentry developer, Grafana, UptimeRobot, GitHub free tiers | ₹0 |
| Usage | Image generation (about 5 projects per month × 10 images) | ₹300 |
| Usage | Razorpay fees: 2.36% of package revenue (price CQ-01; at ₹25,000 per package and 5 packages per month, ₹2,950) | depends on CQ-01 |
| Usage | SMS once enabled (about 2,000 per month) | ₹500 plus ₹11,800 one-time DLT |
| Optional | Sentry Team (more errors and performance retention) | ₹2,200 |
| Optional | Supabase PITR | ₹8,500 |
| Optional | Penetration test (one-time, before the first payment) | ₹50,000 to ₹1,50,000 |
| Total fixed and usage (without optional, without gateway fees) | | about ₹5,500 to ₹6,000 per month |

### 2.3 Growth (year 2; 100 to 500 projects per year; a second city; about 500 active users per day)

| Category | Item | Monthly |
|---|---|---|
| Fixed | VPS KVM 4 (or KVM 2 plus a second KVM 2 for the worker) | ₹2,399 |
| Fixed | Supabase Pro with Small compute; disk about 20 GB | ₹3,400 plus ₹130 |
| Fixed | Supabase PITR (recommended once payments are daily) | ₹8,500 |
| Fixed | R2 (about 300 GB, 2M class A) | ₹770 |
| Fixed | Upstash fixed plan | ₹850 |
| Fixed | Resend Pro | ₹1,700 |
| Fixed | Sentry Team | ₹2,200 |
| Fixed | MapTiler paid tier if tile requests exceed the free tier | ₹0 to ₹2,125 |
| Fixed | GitHub Team (2 to 4 users) | ₹700 to ₹1,400 |
| Usage | Image generation (30 projects per month) | ₹1,700 |
| Usage | SMS (10,000 per month) and WhatsApp (5,000 conversations) | ₹2,500 plus ₹3,000 |
| Usage | Razorpay fees | 2.36% of revenue |
| Optional | Cloudflare load balancing and a second application VPS (stage 5) | ₹1,600 plus ₹1,200 |
| Total fixed and usage (without optional) | | about ₹28,000 to ₹32,000 per month |

### 2.4 Scale (1,000 or more projects per year; several cities)

Rough order: two application VPS and one worker VPS (₹5,000), Supabase Medium with a read replica (₹17,000 to ₹25,000), PITR (₹8,500), R2 at 2 TB (₹2,600 storage plus operations), messaging at volume (₹15,000 to ₹30,000), observability paid tiers (₹5,000), images (₹6,000). About ₹60,000 to ₹1,00,000 per month. At this point infrastructure is still under 1% of revenue at any plausible package price, so the spend decisions are about reliability, not cost.

## 3. Where the money goes and the one change that halves it

| Phase | Largest driver | The one change |
|---|---|---|
| POC | VPS | Nothing to halve; it is already the floor |
| Early | Supabase Pro and Resend Pro (fixed subscriptions) | Stay on Resend Free by keeping optional notices as in-app only until volume justifies Pro (saves ₹1,700); the Supabase Pro cost is not negotiable because backups are |
| Growth | PITR plus messaging | Defer PITR until payment volume justifies it (SCALABILITY trigger); prefer in-app and email over SMS for optional reminders (SMS only for OTP and mandatory notices) |
| Scale | Database and messaging | Read replica only if measurement shows reads dominate; WhatsApp only for the events where pilot data shows it changes response rates (S07 §16.7) |

Payment gateway fees are the only cost that scales with revenue and are outside architecture; the 90-day 0% offer should be timed to the first paying homeowners if the offer still exists at launch.

## 4. Cost to serve one house (infrastructure only)

Early phase: about ₹5,800 per month ÷ 5 new projects per month ≈ ₹1,160 per project at low volume; growth phase: ₹30,000 ÷ 30 ≈ ₹1,000; plus about ₹60 of image generation and ₹100 to ₹300 of messaging over a project's life. Against any package price in the tens of thousands of rupees this is a rounding error, which is the point of the baseline: the expensive parts of Plan2Build are people (advisors, auditors, curation), not servers.

## 5. What is deliberately not bought

| Item | Monthly saved (estimate) | Why not |
|---|---|---|
| Managed Kubernetes or a cloud with managed load balancers | ₹8,000 and up | One VPS carries the POC with headroom (CLOUD_AND_HOSTING_ARCHITECTURE.md section 2.2) |
| A managed queue (SQS, managed RabbitMQ, Upstash QStash paid) | ₹500 to ₹5,000 | The Postgres queue handles the volume; adapter exists |
| OpenSearch or Algolia | ₹2,000 and up | Postgres search covers the scale |
| A paid APM (Datadog, New Relic) | ₹3,000 to ₹15,000 | Sentry and Grafana free tiers cover errors, metrics and logs at this size |
| A second cloud copy of files from day one | ₹500 to ₹2,000 | R2 durability plus monthly bucket-to-bucket sync; a second provider when data volume and revenue justify it |
| Native apps and app store accounts | ₹8,000 per year plus build time | PWA covers both audiences at the POC (BR-151) |

## 6. Open points

| ID | Question | Default until answered |
|---|---|---|
| CQ-01 | Package price and instalment plan | Needed to compute gateway fees and revenue per house; not needed for the infrastructure budget |
| CQ-24 | Budget for the engine and image generation | Image cost under ₹100 per project; engine cost is developer time, not infrastructure |
| AQ-35 | Who pays the VPS, Supabase, Cloudflare and provider accounts (ConjunIQ or Plan2Build), and in whose name they are registered | Plan2Build's company name with Chirag as the technical administrator; accounts transferable |
