# Hook and rhythm

Rules for step 3 (which lines stay, what goes first) and step 5 (where graphics and camera moves go). Adapted from the
beat rules of vox-director (Alisa0808, MIT) for a talking-head reel. The person's own words always win: these rules
help you propose, they never replace what they said.

## The hook (first 3 s)

The opener must make the viewer stay. When you propose cuts, look for a line in their own recording that already works as
one of these, and offer to start the reel on it. The hook TITLE text is still theirs (SKILL.md, «Hook title»): use these
types only to explain the 3 options you build from their words.

| Type | What it does | From their words, e.g. |
|---|---|---|
| Помилка | names a mistake the viewer makes | «Ти пишеш промт щоразу з нуля» |
| Біль | names what hurts right now | «Звіт клієнту знову забрав вечір» |
| Несподівана цифра | one surprising number | «2 хвилини на рілс» |
| Пряме питання | asks the viewer | «Скільки ти платиш монтажеру?» |
| Попередження | something to stop doing | «Не купуй курс, поки не подивишся це» |
| Секрет | reveals what others hide | «Ось що я роблю замість дизайнера» |
| Експеримент | «я спробувала X» | «Я віддала монтаж Claude на тиждень» |
| Злам шаблону | an unexpected first frame or line | a prop, a sound, a strange first sentence |
| Анонс результату | shows the end first | «Ось рілс, змонтований за 2 хвилини» |

Rules: the hook is under 3 s of speech, says one thing, and the reel pays it off (no hook the reel doesn't answer).

## The arc

Name the arc in the plan so the cuts serve it. Most talking-head reels are one of these:

- **Хук → відповідь** (`hook_payoff`): question or claim, then the answer. The default for tips.
- **Проблема → загострення → рішення** (`pas`): their pain, why it gets worse, their way out.
- **До → після → міст** (`bab`): how it was, how it is, what changed it.
- **Як це працює** (`how_it_works`): steps in order. Splits and step tags fit here.
- **Список** (`listicle`): 3-5 items; list cards and step numbers.
- **Міф → правда** (`myth_buster`): the common belief, then why it's wrong.
- **Історія** (`story`): situation, problem, turn, result.
- **Таймлайн** (`timeline`): dates or stages in order.

Shares: hook ≤ 3 s, body 70-80 %, payoff 10-20 %, CTA ≤ 2-3 s at the very end (move it there if they said it earlier).

## Length

- 30 s ≈ 75 spoken words ≈ 6-8 beats. 60 s ≈ 140 words ≈ 10-12 beats. A beat = one thought, 3-6 s.
- Over 60 s: propose which lines to drop to get under it (SKILL.md step 3), never speed the voice past the preset.

## Rhythm of graphics and camera

- Something changes on screen every 4-6 s (a card, a motion, a camera move, a head layout). No graphic longer than ~7 s
  except splits and full-reel elements (stopwatch, step tags).
- **No two neighbours alike.** Alternate families: scale (in, out, whip, shrink, push) ↔ position (split, steps, head
  layouts, paper pieces flying in) ↔ still (a still card, bigtext). build_reel already prints `variety:` for three alike in
  a row; with these rules two alike in a row is already too many.
- Keep a still moment for the payoff: the line that answers the hook gets the calmest, clearest graphic (or none).
- One «hero» move per reel: the biggest effect (scrapbook, starburst, full-screen takeover) goes on the key beat only.
- Endings: `hard_cut` after the last word (default), `quick_cta` (3-5 words on screen), or `loop_close` (the last line
  echoes the first, so the reel loops): suggest loop_close when their last sentence already mirrors the hook.
