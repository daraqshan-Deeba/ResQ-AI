# ResQ AI — Data Sourcing & Reference Content

**A note on scope before anything else:** This document deliberately does **not** contain 500 fabricated hospital records, invented phone numbers, or synthetic "official" NDMA/WHO guidance text. Inventing facility names, addresses, and phone numbers and presenting them as real data is a genuine safety risk in an emergency app — a wrong or disconnected number isn't a cosmetic bug here. Where real, verifiable data exists, this document points to it. Where I can genuinely author content (example phrases, general safety guidance written in my own words), I've done that at a size that's actually useful for a 7-8 category fixed set — not inflated to hit a row-count target.

It's also worth flagging that the source prompt this was built from describes a different stack (Flask, Supabase/pgvector, Whisper) than your actual codebase (FastAPI, Firebase, Groq) — this document is written for *your* actual architecture.

---

## 1. Hospitals — use real data, don't seed a static file

**Your codebase already handles this correctly.** `maps_service.py` calls Google Places live via `get_nearby_hospitals()` — there's no static hospital dataset to seed at all, and that's the right design: hospital names, addresses, and phone numbers change, and stale seeded data is worse than a live lookup. Keep this as-is.

If you want a **fallback/offline dataset** for demo purposes when Google Places is unavailable, these are real, verifiable sources — not something I've generated:

| Source | What it has | Format | License |
|---|---|---|---|
| [data.telangana.gov.in via opencity.in](https://data.opencity.in/dataset/hyderabad-public-health-centres/resource/location-of-hospitals-in-hyderabad---2018) | Hospital locations in Hyderabad (2018 snapshot), government + private | KML | Public Domain |
| [Humanitarian Data Exchange — India Health Facilities (OSM export)](https://data.humdata.org/dataset/eb18fd07-1656-4b5b-b865-aa2cb6a5c101) | Nationwide, includes Hyderabad; name, amenity type, address, coordinates | CSV/Shapefile | Open (OSM contributors) |
| OpenStreetMap Overpass API, live query | Always-current hospital locations, no download needed | JSON via API call | Open Database License |

**No Kaggle-hosted Hyderabad-specific hospital dataset exists as of this writing** — I checked and didn't find one. The two sources above are the actual real alternatives; if a Kaggle dataset does turn up later, it likely traces back to the same OSM/government sources rather than being independently verified data.

**How to use the Overpass API for a live/offline-cache hybrid**, if you want this instead of a one-time seed file:
```
Overpass query pattern: amenity=hospital within a bounding box around
17.0–17.8°N, 78.0–79.0°E (Greater Hyderabad). Returns name, address tags,
and coordinates as JSON. Can be run on-demand or cached with a refresh interval.
```
This is a genuinely better fit than a static seed file if you want an offline fallback, since it stays current without manual maintenance.

---

## 2. Shelters — no reliable public dataset exists, and that's expected

I looked for a Telangana/GHMC-specific shelter dataset and a Kaggle equivalent — **neither exists in any verifiable form.** This isn't a gap in my search; disaster shelter capacity/occupancy data for Indian cities generally isn't published as open data, which is exactly what your own `backend/README.md` already states honestly: *"shelter list and occupancy numbers live in Firestore and are whatever you (or an admin) put there."*

**Recommendation:** Keep the existing manual-seed approach in `seed_shelters.py` as-is. If you want more than the current 3 sample shelters for demo purposes, extend that list with real, findable Hyderabad community halls/schools (a handful, manually verified by you — not 20-50 invented ones), each clearly carrying `source: "manual"` as the schema already does. Don't try to hit a large row count here; a demo needs enough shelters to make the UI look populated, not a comprehensive directory.

---

## 3. Triage Tier 1 — keyword/phrase table (authored content)

These are genuinely authored example phrases, sized for a fixed 8-category set — not padded. 15-25 phrases per category is enough for Tier 1 to catch common direct phrasing; beyond that, you're diminishing-returns into Tier 2's job (paraphrase handling via embeddings), which is the point of having two tiers.

### flooding
water is rising fast · house is flooding · water entering my home · street is underwater · car stuck in flood water · basement is flooding · flash flood · water level rising quickly · road submerged · stranded in flood water · drain overflowing into house · waterlogged street · rising water outside my door · flood water coming in · can't leave house because of flooding · water up to my knees · heavy flooding in my area · storm drain backed up · water rushing into the street · trapped by floodwater

### electrocution
live wire down · electric shock · power line fell · exposed wiring near water · sparking wire · electrical short circuit · touched a live wire · someone got shocked · downed power cable · wire sparking in water · smell of burning wires · electrical panel sparking · live cable on the ground · shocked by appliance · current in standing water · transformer sparking · wire fell during storm

### injury
someone is bleeding · deep cut · broken bone · fracture · someone fell and is hurt · head injury · unconscious person · can't move my leg · severe bleeding · someone is badly hurt · slipped and got injured · spinal injury · someone hit their head · bone sticking out · person not responding · deep wound · lost a lot of blood

### snakebite
snake bite · bitten by a snake · snake bit my hand · venomous snake · saw a snake and got bitten · swelling after snake bite · someone was bitten by a snake · snake attacked · need antivenom · fang marks on skin

### cyclone
cyclone warning · strong winds approaching · storm surge · cyclone hitting our area · roof blown off · trees falling due to wind · extreme wind speed · cyclone alert issued · storm approaching fast · wind damage to house

### structural_damage
building collapsed · roof caved in · wall came down · trapped under rubble · house is collapsing · ceiling fell · structure is unstable · building crack getting worse · debris blocking the door · trapped inside damaged building · wall crack spreading

### accident
car accident · vehicle collision · hit by a car · road accident · multi-car crash · pedestrian hit by vehicle · motorcycle accident · truck collision · accident on the highway · vehicle overturned

### Explicit negative examples (should NOT trigger any category — needed for Tier 1/2 tuning)
the accident happened last year · I read about a flood in the news · just checking if this app works · what should I do if there's ever a flood · my friend once got bitten by a snake · there was a fire drill at work today · testing this input

---

## 4. Triage Tier 2 — canonical example sentences (for embedding similarity)

These are natural, non-keyword-stuffed sentences — the phrasing style Tier 2 needs, distinct from Tier 1's direct keyword list. 6-8 per category, which is enough for a small fixed category set; more examples help mainly if testing reveals a specific phrasing gap, at which point add targeted examples rather than bulk-generating more.

**flooding:** "Water is coming into my house through the front door and it keeps rising." / "My street has turned into a river and I can't get my car out." / "The ground floor of my building is filling up with water fast." / "I'm stuck on the second floor because the stairs are underwater." / "Rain has caused the nearby drain to overflow into our compound." / "My neighborhood is completely waterlogged after last night's rain."

**electrocution:** "There's a power line that fell during the storm and it's lying near a puddle." / "I saw sparks coming from a wire outside my house." / "Someone touched an exposed wire and got a shock." / "The electrical box in our building is sparking." / "A cable came loose and is touching the wet ground." / "I smell something burning near the wiring in my kitchen."

**injury:** "My father fell down the stairs and can't get up." / "There's a lot of blood coming from a cut on my arm." / "Someone in my family hit their head and isn't responding normally." / "I think my leg is broken, I can't put weight on it." / "A worker fell from scaffolding and is in pain." / "My child fell off a bike and is bleeding badly."

**snakebite:** "A snake bit me on the leg while I was in the garden." / "My neighbor was bitten by a snake and the area is swelling." / "I saw fang marks after something bit me in the grass." / "Someone got bitten by a snake near the walking trail." / "There's swelling and pain spreading from where I was bitten."

**cyclone:** "The wind outside is extremely strong and things are flying around." / "Our roof tiles are being ripped off by the storm." / "There's a cyclone warning for our area and the wind is picking up fast." / "Trees are falling in our street because of the storm." / "The storm surge is pushing water further inland than usual."

**structural_damage:** "Part of our building's roof just collapsed." / "There's a big crack in the wall that's getting worse by the hour." / "The ceiling in our living room came down." / "I think someone is trapped under debris from the collapsed structure." / "Our building feels unstable after the heavy rain."

**accident:** "There's been a car crash right outside and people look hurt." / "A motorcycle collided with a car at the intersection." / "Someone was hit by a vehicle while crossing the road." / "Multiple vehicles crashed on the highway near us." / "Our car flipped over after skidding on a wet road."

---

## 5. Action-plan reference templates (general safety guidance, authored — not sourced from a specific citation)

**Important honesty note:** The content below is general safety knowledge, written by me, not verbatim or paraphrased content lifted from NDMA, WHO, or Red Cross materials — I haven't verified each line against a specific current official document, so it should be labeled in your system as general guidance, not an official citation. If you want content that can be labeled as sourced from NDMA/WHO/Red Cross specifically, that requires pulling and verifying the actual current documents, which I can do via search if you want it — flag if so.

### flooding
- **Immediate actions:** Move to higher ground immediately. Turn off electricity at the main breaker if it's safe to reach. Avoid walking or driving through moving water. Keep away from downed power lines near water.
- **Avoid:** Don't walk through floodwater of unknown depth. Don't drive through flooded roads. Don't touch electrical equipment while wet or standing in water.
- **Escalate when:** Water is entering living spaces rapidly, anyone is trapped, or floodwater has any contact with electrical sources.

### electrocution
- **Immediate actions:** Do not touch the person or the wire. Turn off power at the main source if accessible without contact. Call for emergency help immediately. Keep others away from the area.
- **Avoid:** Never touch someone who may still be in contact with a live source. Don't use water near the hazard. Don't attempt to move a downed wire yourself.
- **Escalate when:** Any person has been in contact with a live wire, regardless of how minor it seems.

### injury
- **Immediate actions:** Apply firm, direct pressure to any bleeding wound. Keep the injured person still, especially if head or spinal injury is suspected. Call for emergency medical help.
- **Avoid:** Don't move someone with a suspected spinal injury unless there's immediate danger. Don't remove embedded objects from a wound.
- **Escalate when:** Bleeding won't stop, the person is unconscious or unresponsive, or a head/spinal injury is suspected.

### snakebite
- **Immediate actions:** Keep the person calm and still to slow venom spread. Immobilize the bitten limb, keeping it at or below heart level. Get to a hospital with antivenom as quickly as possible. Note the snake's appearance if safely possible, but don't delay seeking help to do so.
- **Avoid:** Don't cut the wound. Don't attempt to suck out venom. Don't apply a tight tourniquet.
- **Escalate when:** Always — snakebite requires professional medical evaluation regardless of apparent severity.

### cyclone
- **Immediate actions:** Move away from windows and secure loose outdoor items if time allows. Follow official evacuation guidance if issued for your area. Have emergency supplies and a charged phone ready.
- **Avoid:** Don't go outside during peak winds. Don't shelter under trees or weak structures.
- **Escalate when:** Structural damage to your shelter occurs, or official evacuation orders are issued.

### structural_damage
- **Immediate actions:** Get away from the damaged structure if it's safe to move. If trapped, make noise or tap on surfaces at intervals to signal your location. Stay as still as possible to avoid further collapse or injury.
- **Avoid:** Don't re-enter a damaged building to retrieve belongings. Don't use elevators.
- **Escalate when:** Anyone is trapped, or the structure shows continuing signs of instability.

### accident
- **Immediate actions:** Ensure the scene is safe before approaching (check for ongoing traffic danger). Call for emergency help immediately. Check for responsiveness and breathing if trained to do so.
- **Avoid:** Don't move an injured person unless there's immediate danger (fire, further traffic risk). Don't leave the scene before help arrives if you're the reporting party.
- **Escalate when:** Any injury, loss of consciousness, or significant vehicle damage is involved.

### Trusted India emergency contacts (verify current numbers before relying on these — helpline numbers do change)
112 — National Emergency · 108 — Ambulance · 100 — Police · 101 — Fire · 1070 — Disaster Management Helpline

---

## 6. Explicitly deferred — not included here on purpose

Per the scope-governance discussion already had for this project, the following categories from the original data-request are **not built here**, because they belong to features still undecided in scope (community reports, knowledge-base/RAG, voice transcription):

- Community reports synthetic dataset
- Knowledge assets / RAG corpus with embeddings
- Voice/transcription test scripts

If voice input and community reports get formally accepted into scope (per the governance decisions still open), these become worth building — but not before that decision is made, consistent with "fix/decide before adding."

---

## 7. How to use this file

1. **Hospitals:** no action needed — live Google Places lookup already covers this. Use the Overpass/OSM source only if you specifically want an offline fallback.
2. **Shelters:** manually extend `seed_shelters.py` with a small number of real, verified local shelters if you want more than the current 3 — don't bulk-generate.
3. **Triage phrases (Section 3):** merge directly into Tier 1's keyword table.
4. **Canonical examples (Section 4):** use as the embedding corpus for Tier 2, one embedding computed per sentence at startup.
5. **Action-plan templates (Section 5):** use as a deterministic fallback/reference the LLM's structured output (Fix 2) can be grounded against or fall back to entirely if the LLM call fails — which also gives Fix 1's failure-handling path a real, pre-written message to return instead of a generic error.

---

*End of document.*
