# Userscripts

Browser userscripts that integrate with the bitwize-music workflow.

## Suno Auto-Fill (`suno-autofill.user.js`)

Automatically fills Suno's create page with title, style prompt, and lyrics from your clipboard.

### Prerequisites

- [Tampermonkey](https://www.tampermonkey.net/) browser extension (Chrome, Firefox, Edge)
- Suno account with **Custom Mode** enabled (required to see title/style/lyrics fields)

### Installation

1. Install Tampermonkey from your browser's extension store
2. Open `suno-autofill.user.js` in your browser (or copy-paste into Tampermonkey's editor)
3. Click **Install** when Tampermonkey prompts

### Usage

1. Copy track data to clipboard:
   ```
   /clipboard suno my-album 01
   ```
2. Open [suno.com/create](https://suno.com/create)
3. Enable **Custom Mode** (toggle at top of create page)
4. Click the **Paste Track** button (bottom-right corner) or press **Ctrl+Shift+V**
5. Title, style prompt, and lyrics fill automatically

### How It Works

The `/clipboard suno` command copies a JSON object to your clipboard:

```json
{
  "title": "Track Title",
  "style": "electronic, 120 BPM, energetic, male vocals",
  "lyrics": "[Verse 1]\nTesting one two three..."
}
```

The Tampermonkey script reads this JSON from the clipboard and fills the matching fields on Suno's create page using React-compatible input simulation.

### Troubleshooting

#### Clipboard Permission Denied

Your browser requires clipboard permission for suno.com:
- **Chrome**: Click the lock icon in the address bar > Site settings > Clipboard > Allow
- **Firefox**: The permission prompt appears on first use — click Allow

#### Fields Not Filling

Suno's DOM structure may change. The script tries 5 selector strategies (aria-label, placeholder, data-testid, CSS class, DOM position), but if none match:

1. Open browser DevTools console (F12)
2. Run `debugFields()` — this logs all input/textarea elements on the page
3. Update the `CONFIG.fields` object in the script with matching selectors
4. Save in Tampermonkey

#### Custom Mode Not Enabled

The title, style, and lyrics fields only appear when Custom Mode is toggled on. If fields aren't visible on the page, the script cannot fill them.

#### Script Not Running

- Verify Tampermonkey is enabled (check the extension icon)
- Verify the script is enabled in Tampermonkey's dashboard
- Check that the URL matches `https://suno.com/create*`
