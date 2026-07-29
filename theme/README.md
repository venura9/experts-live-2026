# Deck theme

Reusable across every talk. Three files, no build step, no network.

| File | What it is |
|---|---|
| `theme.css` | All the styling. Change the six colours in `:root` and the deck follows |
| `deck.js` | The engine: navigation, timer, speaker notes, progress bar |
| `TEMPLATE.html` | A starter deck with one example of every layout the theme supports |
| `me.jpg` | Your photo for the who-am-I slide, 400x400 |

## Starting a new talk

```bash
cp -r theme my-new-talk && cd my-new-talk
mv TEMPLATE.html deck.html
open deck.html
```

Edit the `<title>`, the rail label, and the slides. Delete the layouts you do
not need. That is the whole workflow.

If you want a single portable file to email or carry on a USB stick, paste
`theme.css` inside a `<style>` block and `deck.js` inside a `<script>` block,
then drop the two `<link>` and `<src>` references. Do the same with the photo by
base64-encoding it into the `src` attribute:

```bash
python3 -c "import base64,pathlib;print('data:image/jpeg;base64,'+base64.b64encode(pathlib.Path('me.jpg').read_bytes()).decode())"
```

That is how `deck.html` for the Foundry Local talk is built: one file, no
external references, nothing to fetch at the venue.

## Controls

| Key | Does |
|---|---|
| Right, space, PageDown, Down | Forward |
| Left, `p`, PageUp, Up | Back |
| `g` or Escape | All slides as a grid, click one to jump |
| Type a number, Enter | Jump straight to that slide |
| Home / End | First / last slide |
| `n` | Speaker notes panel |
| `t` | Stop and reset the timer |
| `b` | Toggle the rail dot to amber |

The grid is the one to remember. When someone asks a question about a slide you
passed fifteen minutes ago, `g` gets you there in one look instead of holding
the left arrow while the room watches. It builds itself from the slides, so it
can never drift out of date with the deck.

Click the right three quarters to advance, the left quarter to go back.
Right-click or shift-click also goes back. The browser Back button works.

The timer starts itself when you leave the title slide, so there is nothing to
remember. It dims while stopped so a paused clock never looks like a live one.

## Layouts

Each is a `<section class="slide">` with these attributes:

- `data-t` target time, shown bottom right so you can tell if you are behind
- `data-seg` segment name, shown bottom left
- `data-notes` speaker notes, revealed with `n`

| Class | Use for |
|---|---|
| `h1` + `.lede` | Title slide |
| `.whoami` | Who am I. Definition list plus initials mark |
| `.stats` / `.stat` / `.stat.hero` | Big numbers, two to four |
| `ul.pts` | Bullets, five maximum |
| `table` with `td.yes`, `td.no`, `td.mono` | Comparisons |
| `pre` with `span.c`, `span.k` | Commands and code |
| `.invariant` | The one big idea, biggest type in the deck |
| `.live` + `.checklist` | Demo placeholder while you switch windows |
| `.disclaimer` | Small print, views-are-my-own line |

Each demo slide in the template prints the class it shows off next to its
eyebrow. Delete those `<span class="cls">` tags when you start a real deck.

## The Azure and AI nod

Two touches, both CSS, no markup and no logos:

- `--azure` (`#4FA8E8`) tints the top of the left rail and fades back to the
  hairline within a third of the height. Present on every slide, quiet enough
  that nobody consciously registers it.
- An abstract connected-node motif sits in the corner of the title slide at 13%
  opacity. It is three dots and three lines, drawn from scratch. It is
  deliberately **not** the Azure or Microsoft mark, which are trademarks and
  should not be redrawn.

Both hide below 800px. To remove either, delete the `border-image` line on
`#rail` or the `.slide:first-of-type::after` block. To push the accent further,
change `--azure`; it is referenced in exactly two places, and it is kept off the
status colours (`--clear`, `--signal`, `--stop`) on purpose, because those carry
meaning and a decorative colour competing with them would be a real cost.

## Why it looks like this

No web fonts and no CDN, so it renders identically on a plane, on venue wifi
that has fallen over, or on a borrowed laptop. Everything is system fonts.

Respects `prefers-reduced-motion`. Below 800px wide the rail narrows and the
notes panel goes full width, so it is usable on a laptop screen while you
rehearse.
